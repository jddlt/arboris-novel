import logging
import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException, status
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, InternalServerError

from ..core.config import settings
from ..repositories.llm_config_repository import LLMConfigRepository
from ..repositories.system_config_repository import SystemConfigRepository
from ..repositories.user_repository import UserRepository
from ..services.admin_setting_service import AdminSettingService
from ..services.prompt_service import PromptService
from ..services.usage_service import UsageService
from ..utils.llm_tool import ChatMessage, LLMClient

logger = logging.getLogger(__name__)

try:  # pragma: no cover - 运行环境未安装时兼容
    from ollama import AsyncClient as OllamaAsyncClient
except ImportError:  # pragma: no cover - Ollama 为可选依赖
    OllamaAsyncClient = None


class LLMService:
    """封装与大模型交互的所有逻辑，包括配额控制与配置选择。"""

    def __init__(self, session):
        self.session = session
        self.llm_repo = LLMConfigRepository(session)
        self.system_config_repo = SystemConfigRepository(session)
        self.user_repo = UserRepository(session)
        self.admin_setting_service = AdminSettingService(session)
        self.usage_service = UsageService(session)
        self._embedding_dimensions: Dict[str, int] = {}

    async def get_llm_response(
        self,
        system_prompt: str,
        conversation_history: List[Dict[str, str]],
        *,
        temperature: float = 0.7,
        user_id: Optional[int] = None,
        timeout: float = 300.0,
        response_format: Optional[str] = "json_object",
    ) -> str:
        messages = [{"role": "system", "content": system_prompt}, *conversation_history]
        return await self._stream_and_collect(
            messages,
            temperature=temperature,
            user_id=user_id,
            timeout=timeout,
            response_format=response_format,
        )

    async def get_summary(
        self,
        chapter_content: str,
        *,
        temperature: float = 0.2,
        user_id: Optional[int] = None,
        timeout: float = 180.0,
        system_prompt: Optional[str] = None,
    ) -> str:
        if not system_prompt:
            prompt_service = PromptService(self.session)
            system_prompt = await prompt_service.get_prompt("extraction")
        if not system_prompt:
            logger.error("未配置名为 'extraction' 的摘要提示词，无法生成章节摘要")
            raise HTTPException(status_code=500, detail="未配置摘要提示词，请联系管理员配置 'extraction' 提示词")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": chapter_content},
        ]
        return await self._stream_and_collect(messages, temperature=temperature, user_id=user_id, timeout=timeout)

    async def _stream_and_collect(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float,
        user_id: Optional[int],
        timeout: float,
        response_format: Optional[str] = None,
    ) -> str:
        config = await self._resolve_llm_config(user_id)
        client = LLMClient(api_key=config["api_key"], base_url=config.get("base_url"))

        chat_messages = [ChatMessage(role=msg["role"], content=msg["content"]) for msg in messages]

        full_response = ""
        finish_reason = None

        logger.info(
            "Streaming LLM response: model=%s user_id=%s messages=%d",
            config.get("model"),
            user_id,
            len(messages),
        )

        try:
            async for part in client.stream_chat(
                messages=chat_messages,
                model=config.get("model"),
                temperature=temperature,
                timeout=int(timeout),
                response_format=response_format,
            ):
                if part.get("content"):
                    full_response += part["content"]
                if part.get("finish_reason"):
                    finish_reason = part["finish_reason"]
        except InternalServerError as exc:
            detail = "AI 服务内部错误，请稍后重试"
            response = getattr(exc, "response", None)
            if response is not None:
                try:
                    payload = response.json()
                    error_data = payload.get("error", {}) if isinstance(payload, dict) else {}
                    detail = error_data.get("message_zh") or error_data.get("message") or detail
                except Exception:
                    detail = str(exc) or detail
            else:
                detail = str(exc) or detail
            logger.error(
                "LLM stream internal error: model=%s user_id=%s detail=%s",
                config.get("model"),
                user_id,
                detail,
                exc_info=exc,
            )
            raise HTTPException(status_code=503, detail=detail)
        except (httpx.RemoteProtocolError, httpx.ReadTimeout, APIConnectionError, APITimeoutError) as exc:
            if isinstance(exc, httpx.RemoteProtocolError):
                detail = "AI 服务连接被意外中断，请稍后重试"
            elif isinstance(exc, (httpx.ReadTimeout, APITimeoutError)):
                detail = "AI 服务响应超时，请稍后重试"
            else:
                detail = "无法连接到 AI 服务，请稍后重试"
            logger.error(
                "LLM stream failed: model=%s user_id=%s detail=%s",
                config.get("model"),
                user_id,
                detail,
                exc_info=exc,
            )
            raise HTTPException(status_code=503, detail=detail) from exc

        logger.debug(
            "LLM response collected: model=%s user_id=%s finish_reason=%s preview=%s",
            config.get("model"),
            user_id,
            finish_reason,
            full_response[:500],
        )

        if finish_reason == "length":
            logger.warning(
                "LLM response truncated: model=%s user_id=%s response_length=%d",
                config.get("model"),
                user_id,
                len(full_response),
            )
            raise HTTPException(
                status_code=500,
                detail=f"AI 响应因长度限制被截断（已生成 {len(full_response)} 字符），请缩短输入内容或调整模型参数"
            )

        if not full_response:
            logger.error(
                "LLM returned empty response: model=%s user_id=%s finish_reason=%s",
                config.get("model"),
                user_id,
                finish_reason,
            )
            raise HTTPException(
                status_code=500,
                detail=f"AI 未返回有效内容（结束原因: {finish_reason or '未知'}），请稍后重试或联系管理员"
            )

        await self.usage_service.increment("api_request_count")
        logger.info(
            "LLM response success: model=%s user_id=%s chars=%d",
            config.get("model"),
            user_id,
            len(full_response),
        )
        return full_response

    async def chat_with_tools(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict],
        *,
        temperature: float = 0.7,
        user_id: Optional[int] = None,
        timeout: float = 300.0,
        enable_web_search: bool = False,
    ) -> Dict[str, Any]:
        """带工具调用的 LLM 对话。

        用于 GM Agent 等需要 Function Calling 的场景。
        不使用流式响应，直接返回完整结果。

        Args:
            system_prompt: 系统提示词
            messages: 对话历史
            tools: 工具定义列表（OpenAI Function Calling 格式）
            temperature: 温度参数
            user_id: 用户 ID（用于配额控制）
            timeout: 超时时间（秒）
            enable_web_search: 是否启用联网搜索（仅 Gemini 模型支持）

        Returns:
            包含 content 和 tool_calls 的字典
        """
        config = await self._resolve_llm_config(user_id)
        model_name = (config.get("model") or "").lower()
        is_gemini = "gemini" in model_name

        # Gemini 模型统一使用原生 API 格式（更好的工具调用支持）
        if is_gemini:
            logger.info("使用 Gemini 原生 API 格式（非流式）")
            return await self._call_gemini_native(
                config=config,
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
                temperature=temperature,
                timeout=timeout,
                enable_web_search=enable_web_search,
                user_id=user_id,
            )

        # 其他模型使用 OpenAI 兼容格式
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=config["api_key"],
            base_url=config.get("base_url"),
        )

        # 构建消息（转换带图片的消息为 OpenAI 多模态格式）
        full_messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            converted_msg = self._convert_message_to_openai_format(msg)
            full_messages.append(converted_msg)

        # 构建工具列表
        final_tools = list(tools) if tools else []

        logger.info(
            "LLM chat_with_tools (OpenAI格式): model=%s user_id=%s messages=%d tools=%d",
            config.get("model"),
            user_id,
            len(full_messages),
            len(final_tools),
        )

        try:
            response = await client.chat.completions.create(
                model=config.get("model") or "gpt-4",
                messages=full_messages,
                tools=final_tools if final_tools else None,
                tool_choice="auto" if final_tools else None,
                temperature=temperature,
                timeout=int(timeout),
            )
        except Exception as exc:
            logger.error(
                "LLM chat_with_tools failed: model=%s user_id=%s error=%s",
                config.get("model"),
                user_id,
                exc,
                exc_info=True,
            )
            raise

        # 解析响应
        choice = response.choices[0] if response.choices else None
        if not choice:
            logger.warning("LLM 返回空响应")
            return {"content": "", "tool_calls": []}

        content = choice.message.content or ""
        tool_calls = []

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                })

        await self.usage_service.increment("api_request_count")
        logger.info(
            "LLM chat_with_tools success: model=%s user_id=%s content_len=%d tool_calls=%d",
            config.get("model"),
            user_id,
            len(content),
            len(tool_calls),
        )

        return {
            "content": content,
            "tool_calls": tool_calls,
        }

    async def _call_gemini_native(
        self,
        config: Dict[str, Optional[str]],
        system_prompt: str,
        messages: List[Dict[str, str]],
        tools: List[Dict],
        temperature: float,
        timeout: float,
        enable_web_search: bool,
        user_id: Optional[int],
    ) -> Dict[str, Any]:
        """使用 Gemini 原生 API 格式进行非流式调用。"""
        import json

        base_url = config.get("base_url") or "https://generativelanguage.googleapis.com"
        api_key = config["api_key"]
        model = config.get("model") or "gemini-2.0-flash"

        # 构建 Gemini 格式的 contents
        contents = self._convert_messages_to_gemini_format(system_prompt, messages)

        # 构建 Gemini 格式的 tools
        gemini_tools = self._convert_tools_to_gemini_format(tools, enable_web_search)

        # 构建请求体
        request_body: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
            },
        }

        if gemini_tools:
            request_body["tools"] = gemini_tools

        # 构建 URL（非流式端点）
        # 处理 OpenAI 兼容代理格式 - 去掉 /v1 后缀
        normalized_base_url = base_url.rstrip('/')
        if normalized_base_url.endswith('/v1'):
            normalized_base_url = normalized_base_url[:-3]

        if "/models/" in base_url:
            url = f"{base_url.rstrip('/')}:generateContent?key={api_key}"
        else:
            url = f"{normalized_base_url}/v1beta/models/{model}:generateContent?key={api_key}"

        logger.info(
            "Gemini 原生非流式请求: model=%s url=%s tools=%d web_search=%s",
            model,
            url.split("?")[0],
            len(gemini_tools) if gemini_tools else 0,
            enable_web_search,
        )

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    url,
                    json=request_body,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code != 200:
                    logger.error("Gemini API 错误: status=%d, body=%s", response.status_code, response.text)
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Gemini API 错误: {response.text}"
                    )

                data = response.json()

        except httpx.TimeoutException as exc:
            logger.error("Gemini API 超时: %s", exc)
            raise HTTPException(status_code=504, detail="Gemini API 请求超时")
        except httpx.RequestError as exc:
            logger.error("Gemini API 请求错误: %s", exc, exc_info=True)
            raise HTTPException(status_code=503, detail=f"Gemini API 连接错误: {str(exc)}")

        # 解析响应
        full_content = ""
        tool_calls: List[Dict[str, Any]] = []

        candidates = data.get("candidates", [])
        for candidate in candidates:
            content = candidate.get("content", {})
            parts = content.get("parts", [])

            for part in parts:
                if "text" in part:
                    full_content += part["text"]
                if "functionCall" in part:
                    fc = part["functionCall"]
                    tool_calls.append({
                        "id": f"call_{len(tool_calls)}",
                        "name": fc.get("name", ""),
                        "arguments": json.dumps(fc.get("args", {}), ensure_ascii=False),
                    })

        # 记录 grounding metadata
        grounding_metadata = data.get("groundingMetadata")
        if grounding_metadata:
            logger.info("收到 Gemini grounding 元数据: %s", list(grounding_metadata.keys()))

        await self.usage_service.increment("api_request_count")

        logger.info(
            "Gemini 原生非流式请求完成: model=%s content_len=%d tool_calls=%d",
            model,
            len(full_content),
            len(tool_calls),
        )

        return {
            "content": full_content,
            "tool_calls": tool_calls,
        }

    async def stream_chat_with_tools(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict],
        *,
        temperature: float = 0.7,
        user_id: Optional[int] = None,
        timeout: float = 300.0,
        enable_web_search: bool = False,
    ):
        """带工具调用的流式 LLM 对话。

        用于 GM Agent 需要流式输出的场景。
        逐步 yield 内容片段，最后 yield 完整的工具调用。

        Args:
            system_prompt: 系统提示词
            messages: 对话历史（支持带 images 字段的消息）
            tools: 工具定义列表（OpenAI Function Calling 格式）
            temperature: 温度参数
            user_id: 用户 ID（用于配额控制）
            timeout: 超时时间（秒）
            enable_web_search: 是否启用联网搜索（仅 Gemini 模型支持）

        Yields:
            dict: {"type": "content", "content": "..."} 或
                  {"type": "tool_calls", "tool_calls": [...]} 或
                  {"type": "done", "content": "...", "tool_calls": [...]}
        """
        config = await self._resolve_llm_config(user_id)
        model_name = (config.get("model") or "").lower()
        is_gemini = "gemini" in model_name

        # Gemini 模型统一使用原生 API 格式（更好的工具调用支持）
        if is_gemini:
            logger.info("使用 Gemini 原生 API 格式（流式）")
            async for event in self._stream_gemini_native(
                config=config,
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
                temperature=temperature,
                timeout=timeout,
                enable_web_search=enable_web_search,
                user_id=user_id,
            ):
                yield event
            return

        # 其他模型使用 OpenAI 兼容格式
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=config["api_key"],
            base_url=config.get("base_url"),
        )

        # 构建消息（转换带图片的消息为 OpenAI 多模态格式）
        full_messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            converted_msg = self._convert_message_to_openai_format(msg)
            full_messages.append(converted_msg)

        # 构建工具列表
        final_tools = list(tools) if tools else []

        logger.info(
            "LLM stream_chat_with_tools (OpenAI格式): model=%s user_id=%s messages=%d tools=%d",
            config.get("model"),
            user_id,
            len(full_messages),
            len(final_tools),
        )

        try:
            stream = await client.chat.completions.create(
                model=config.get("model") or "gpt-4",
                messages=full_messages,
                tools=final_tools if final_tools else None,
                tool_choice="auto" if final_tools else None,
                temperature=temperature,
                timeout=int(timeout),
                stream=True,
            )
        except Exception as exc:
            logger.error(
                "LLM stream_chat_with_tools failed to start: model=%s user_id=%s error=%s",
                config.get("model"),
                user_id,
                exc,
                exc_info=True,
            )
            raise

        full_content = ""
        tool_calls_data: Dict[int, Dict[str, Any]] = {}  # index -> {id, name, arguments}

        try:
            async for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # 处理文本内容
                if delta.content:
                    full_content += delta.content
                    yield {"type": "content", "content": delta.content}

                # 处理工具调用
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_data:
                            tool_calls_data[idx] = {
                                "id": tc.id or "",
                                "name": tc.function.name if tc.function and tc.function.name else "",
                                "arguments": "",
                            }
                        else:
                            if tc.id:
                                tool_calls_data[idx]["id"] = tc.id
                            if tc.function and tc.function.name:
                                tool_calls_data[idx]["name"] = tc.function.name

                        if tc.function and tc.function.arguments:
                            tool_calls_data[idx]["arguments"] += tc.function.arguments

        except Exception as exc:
            logger.error(
                "LLM stream_chat_with_tools stream error: model=%s user_id=%s error=%s",
                config.get("model"),
                user_id,
                exc,
                exc_info=True,
            )
            raise

        # 整理工具调用结果
        tool_calls = []
        for idx in sorted(tool_calls_data.keys()):
            tc_data = tool_calls_data[idx]
            if tc_data["name"]:  # 只添加有名称的工具调用
                tool_calls.append(tc_data)

        await self.usage_service.increment("api_request_count")

        logger.info(
            "LLM stream_chat_with_tools complete: model=%s user_id=%s content_len=%d tool_calls=%d",
            config.get("model"),
            user_id,
            len(full_content),
            len(tool_calls),
        )

        # 最终 yield 完整结果
        yield {
            "type": "done",
            "content": full_content,
            "tool_calls": tool_calls,
        }

    async def _stream_gemini_native(
        self,
        config: Dict[str, Optional[str]],
        system_prompt: str,
        messages: List[Dict[str, str]],
        tools: List[Dict],
        temperature: float,
        timeout: float,
        enable_web_search: bool,
        user_id: Optional[int],
    ):
        """使用 Gemini 原生 API 格式进行流式调用。

        Gemini REST API 格式与 OpenAI 不同，需要单独处理。
        参考: https://ai.google.dev/gemini-api/docs/text-generation
        """
        import json

        base_url = config.get("base_url") or "https://generativelanguage.googleapis.com"
        api_key = config["api_key"]
        model = config.get("model") or "gemini-2.0-flash"

        # 构建 Gemini 格式的 contents
        contents = self._convert_messages_to_gemini_format(system_prompt, messages)

        # 构建 Gemini 格式的 tools
        gemini_tools = self._convert_tools_to_gemini_format(tools, enable_web_search)

        # 构建请求体
        request_body: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
            },
        }

        if gemini_tools:
            request_body["tools"] = gemini_tools

        # 构建 URL（流式端点）
        # 支持多种 URL 格式：
        # 1. 官方格式: https://generativelanguage.googleapis.com/v1beta/models/gemini-xxx:streamGenerateContent
        # 2. 代理 Gemini 格式: https://your-proxy.com/v1beta/models/gemini-xxx:streamGenerateContent
        # 3. 代理 OpenAI 兼容格式: https://your-proxy.com/v1 (需要转换)

        # 处理 OpenAI 兼容代理格式 - 去掉 /v1 后缀
        normalized_base_url = base_url.rstrip('/')
        if normalized_base_url.endswith('/v1'):
            normalized_base_url = normalized_base_url[:-3]

        if "/models/" in base_url:
            # URL 已经包含 model 路径，直接追加 :streamGenerateContent
            url = f"{base_url.rstrip('/')}:streamGenerateContent?alt=sse&key={api_key}"
        else:
            # 标准格式，需要拼接 model 路径
            url = f"{normalized_base_url}/v1beta/models/{model}:streamGenerateContent?alt=sse&key={api_key}"

        logger.info(
            "Gemini 原生流式请求: model=%s url=%s tools=%d web_search=%s",
            model,
            url.split("?")[0],  # 隐藏 API key
            len(gemini_tools) if gemini_tools else 0,
            enable_web_search,
        )
        logger.debug("Gemini 请求体: %s", json.dumps(request_body, ensure_ascii=False, indent=2))

        full_content = ""
        tool_calls: List[Dict[str, Any]] = []

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    url,
                    json=request_body,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        logger.error("Gemini API 错误: status=%d, body=%s", response.status_code, error_text)
                        raise HTTPException(
                            status_code=response.status_code,
                            detail=f"Gemini API 错误: {error_text.decode('utf-8', errors='ignore')}"
                        )

                    # 处理 SSE 流
                    async for line in response.aiter_lines():
                        if not line:
                            continue

                        # 记录原始行（调试用）
                        if not line.startswith("data:"):
                            logger.info("Gemini SSE 非 data 行: %s", line[:100])

                        # SSE 格式: data: {...}
                        if line.startswith("data: "):
                            data_str = line[6:]  # 去掉 "data: " 前缀
                            if data_str.strip() == "[DONE]":
                                logger.info("收到 [DONE] 信号")
                                break

                            try:
                                data = json.loads(data_str)
                            except json.JSONDecodeError:
                                logger.warning("无法解析 Gemini SSE 数据: %s", data_str[:200])
                                continue

                            # 检查是否有 finishReason
                            candidates = data.get("candidates", [])
                            for candidate in candidates:
                                finish_reason = candidate.get("finishReason")
                                if finish_reason:
                                    logger.info("Gemini finishReason: %s", finish_reason)

                            # 解析 Gemini 响应格式
                            candidates = data.get("candidates", [])
                            for candidate in candidates:
                                content = candidate.get("content", {})
                                parts = content.get("parts", [])

                                # DEBUG: 记录每个 part 的结构
                                for i, part in enumerate(parts):
                                    part_keys = list(part.keys())
                                    logger.info("Gemini part[%d] keys: %s", i, part_keys)

                                for part in parts:
                                    # 文本内容
                                    if "text" in part:
                                        text = part["text"]
                                        full_content += text
                                        yield {"type": "content", "content": text}
                                        logger.debug("Gemini 返回文本: %s...", text[:100] if len(text) > 100 else text)

                                    # 工具调用
                                    if "functionCall" in part:
                                        fc = part["functionCall"]
                                        tool_call = {
                                            "id": f"call_{len(tool_calls)}",
                                            "name": fc.get("name", ""),
                                            "arguments": json.dumps(fc.get("args", {}), ensure_ascii=False),
                                        }
                                        tool_calls.append(tool_call)
                                        # 立即通知前端有新的工具调用
                                        yield {"type": "tool_call", "tool_call": tool_call}
                                        logger.debug("Gemini 返回工具调用: %s", fc.get("name", ""))

                            # 检查 grounding metadata（google_search 结果）
                            grounding_metadata = data.get("groundingMetadata")
                            if grounding_metadata:
                                logger.info("收到 Gemini grounding 元数据: %s", list(grounding_metadata.keys()))

        except httpx.TimeoutException as exc:
            logger.error("Gemini API 超时: %s", exc)
            raise HTTPException(status_code=504, detail="Gemini API 请求超时")
        except httpx.RequestError as exc:
            logger.error("Gemini API 请求错误: %s", exc, exc_info=True)
            raise HTTPException(status_code=503, detail=f"Gemini API 连接错误: {str(exc)}")

        await self.usage_service.increment("api_request_count")

        logger.info(
            "Gemini 原生流式请求完成: model=%s content_len=%d tool_calls=%d",
            model,
            len(full_content),
            len(tool_calls),
        )

        yield {
            "type": "done",
            "content": full_content,
            "tool_calls": tool_calls,
        }

    def _convert_messages_to_gemini_format(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """将 OpenAI 格式的消息转换为 Gemini 格式。

        Gemini 格式:
        [
            {"role": "user", "parts": [{"text": "..."}, {"inline_data": {"mime_type": "...", "data": "..."}}]},
            {"role": "model", "parts": [{"text": "..."}, {"functionCall": {"name": "...", "args": {...}}}]},
            {"role": "function", "parts": [{"functionResponse": {"name": "...", "response": {...}}}]},
        ]

        注意: Gemini 用 "model" 而不是 "assistant"
        系统提示词需要作为第一条 user 消息的一部分
        支持图片：消息中如果有 images 字段，转换为 inline_data parts
        支持工具调用：assistant 消息中如果有 tool_calls 字段，转换为 functionCall parts
        """
        import json as _json

        contents = []

        # 处理消息
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            images = msg.get("images", [])
            tool_calls = msg.get("tool_calls", [])

            # 转换角色名
            if role == "assistant":
                gemini_role = "model"
            elif role == "system":
                # Gemini 不直接支持 system role，跳过（已在第一条消息中处理）
                continue
            elif role == "tool":
                # 工具响应需要特殊处理
                gemini_role = "function"
            else:
                gemini_role = "user"

            # 如果是第一条 user 消息，prepend system prompt
            if gemini_role == "user" and not contents and system_prompt:
                content = f"{system_prompt}\n\n---\n\n{content}"

            if gemini_role == "function":
                # 工具响应格式
                # 从 msg 中获取工具名称，如果没有则使用 tool_call_id
                tool_name = msg.get("tool_name") or msg.get("tool_call_id", "unknown")
                contents.append({
                    "role": "function",
                    "parts": [{
                        "functionResponse": {
                            "name": tool_name,
                            "response": {"result": content}
                        }
                    }]
                })
            else:
                # 构建 parts 列表
                parts = []

                # 添加文本内容
                if content:
                    parts.append({"text": content})

                # 添加图片内容
                if images:
                    for img in images:
                        parts.append({
                            "inline_data": {
                                "mime_type": img.get("mime_type", "image/png"),
                                "data": img.get("base64", "")
                            }
                        })

                # 添加工具调用内容（assistant/model 消息可能包含 tool_calls）
                if tool_calls and gemini_role == "model":
                    for tc in tool_calls:
                        tc_name = tc.get("name") or tc.get("function", {}).get("name", "")
                        tc_args_str = tc.get("arguments") or tc.get("function", {}).get("arguments", "{}")
                        try:
                            tc_args = _json.loads(tc_args_str) if isinstance(tc_args_str, str) else tc_args_str
                        except _json.JSONDecodeError:
                            tc_args = {}
                        if tc_name:
                            parts.append({
                                "functionCall": {
                                    "name": tc_name,
                                    "args": tc_args
                                }
                            })

                if parts:
                    contents.append({
                        "role": gemini_role,
                        "parts": parts
                    })

        # 如果没有消息但有 system prompt，创建一条
        if not contents and system_prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": system_prompt}]
            })

        return contents

    def _convert_message_to_openai_format(
        self,
        msg: Dict[str, Any],
    ) -> Dict[str, Any]:
        """将带图片的消息转换为 OpenAI 多模态格式。

        OpenAI 多模态格式:
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "..."},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
            ]
        }

        如果消息没有图片，保持原格式不变。
        """
        images = msg.get("images", [])
        if not images:
            # 没有图片，返回简化格式（兼容性更好）
            return {"role": msg.get("role", "user"), "content": msg.get("content", "")}

        # 有图片，转换为多模态格式
        content_parts = []

        # 添加文本部分
        text_content = msg.get("content", "")
        if text_content:
            content_parts.append({"type": "text", "text": text_content})

        # 添加图片部分
        for img in images:
            mime_type = img.get("mime_type", "image/png")
            base64_data = img.get("base64", "")
            data_url = f"data:{mime_type};base64,{base64_data}"
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": data_url}
            })

        return {"role": msg.get("role", "user"), "content": content_parts}

    def _convert_tools_to_gemini_format(
        self,
        tools: List[Dict],
        enable_web_search: bool,
    ) -> List[Dict[str, Any]]:
        """将 OpenAI 格式的工具定义转换为 Gemini 格式。

        OpenAI 格式:
        [{"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}]

        Gemini 格式:
        [
            {"functionDeclarations": [{"name": "...", "description": "...", "parameters": {...}}]},
            {"google_search": {}}  # 可选
        ]
        """
        gemini_tools = []

        # 转换 function tools
        function_declarations = []
        for tool in tools:
            if tool.get("type") == "function" and "function" in tool:
                func = tool["function"]
                function_declarations.append({
                    "name": func.get("name"),
                    "description": func.get("description"),
                    "parameters": func.get("parameters"),
                })

        if function_declarations:
            gemini_tools.append({"functionDeclarations": function_declarations})
            logger.info("已转换 %d 个工具为 Gemini functionDeclarations 格式", len(function_declarations))

        # 添加 google_search grounding 工具
        if enable_web_search:
            gemini_tools.append({"google_search": {}})
            logger.info("已添加 Gemini google_search grounding 工具")

        return gemini_tools

    async def _resolve_llm_config(self, user_id: Optional[int]) -> Dict[str, Optional[str]]:
        if user_id:
            config = await self.llm_repo.get_by_user(user_id)
            if config and config.llm_provider_api_key:
                return {
                    "api_key": config.llm_provider_api_key,
                    "base_url": config.llm_provider_url,
                    "model": config.llm_provider_model,
                }

        # 检查每日使用次数限制
        if user_id:
            await self._enforce_daily_limit(user_id)

        api_key = await self._get_config_value("llm.api_key")
        base_url = await self._get_config_value("llm.base_url")
        model = await self._get_config_value("llm.model")

        if not api_key:
            logger.error("未配置默认 LLM API Key，且用户 %s 未设置自定义 API Key", user_id)
            raise HTTPException(
                status_code=500,
                detail="未配置默认 LLM API Key，请联系管理员配置系统默认 API Key 或在个人设置中配置自定义 API Key"
            )

        return {"api_key": api_key, "base_url": base_url, "model": model}

    async def get_embedding(
        self,
        text: str,
        *,
        user_id: Optional[int] = None,
        model: Optional[str] = None,
    ) -> List[float]:
        """生成文本向量，用于章节 RAG 检索，支持 openai 与 ollama 双提供方。"""
        provider = await self._get_config_value("embedding.provider") or "openai"
        default_model = (
            await self._get_config_value("ollama.embedding_model") or "nomic-embed-text:latest"
            if provider == "ollama"
            else await self._get_config_value("embedding.model") or "text-embedding-3-large"
        )
        target_model = model or default_model

        if provider == "ollama":
            if OllamaAsyncClient is None:
                logger.error("未安装 ollama 依赖，无法调用本地嵌入模型。")
                raise HTTPException(status_code=500, detail="缺少 Ollama 依赖，请先安装 ollama 包。")

            base_url = (
                await self._get_config_value("ollama.embedding_base_url")
                or await self._get_config_value("embedding.base_url")
            )
            client = OllamaAsyncClient(host=base_url)
            try:
                response = await client.embeddings(model=target_model, prompt=text)
            except Exception as exc:  # pragma: no cover - 本地服务调用失败
                logger.error(
                    "Ollama 嵌入请求失败: model=%s base_url=%s error=%s",
                    target_model,
                    base_url,
                    exc,
                    exc_info=True,
                )
                return []
            embedding: Optional[List[float]]
            if isinstance(response, dict):
                embedding = response.get("embedding")
            else:
                embedding = getattr(response, "embedding", None)
            if not embedding:
                logger.warning("Ollama 返回空向量: model=%s", target_model)
                return []
            if not isinstance(embedding, list):
                embedding = list(embedding)
        else:
            config = await self._resolve_llm_config(user_id)
            api_key = await self._get_config_value("embedding.api_key") or config["api_key"]
            base_url = await self._get_config_value("embedding.base_url") or config.get("base_url")
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            try:
                response = await client.embeddings.create(
                    input=text,
                    model=target_model,
                )
            except Exception as exc:  # pragma: no cover - 网络或鉴权失败
                logger.error(
                    "OpenAI 嵌入请求失败: model=%s base_url=%s user_id=%s error=%s",
                    target_model,
                    base_url,
                    user_id,
                    exc,
                    exc_info=True,
                )
                return []
            if not response.data:
                logger.warning("OpenAI 嵌入请求返回空数据: model=%s user_id=%s", target_model, user_id)
                return []
            embedding = response.data[0].embedding

        if not isinstance(embedding, list):
            embedding = list(embedding)

        dimension = len(embedding)
        if not dimension:
            vector_size_str = await self._get_config_value("embedding.model_vector_size")
            if vector_size_str:
                dimension = int(vector_size_str)
        if dimension:
            self._embedding_dimensions[target_model] = dimension
        return embedding

    async def get_embedding_dimension(self, model: Optional[str] = None) -> Optional[int]:
        """获取嵌入向量维度，优先返回缓存结果，其次读取配置。"""
        provider = await self._get_config_value("embedding.provider") or "openai"
        default_model = (
            await self._get_config_value("ollama.embedding_model") or "nomic-embed-text:latest"
            if provider == "ollama"
            else await self._get_config_value("embedding.model") or "text-embedding-3-large"
        )
        target_model = model or default_model
        if target_model in self._embedding_dimensions:
            return self._embedding_dimensions[target_model]
        vector_size_str = await self._get_config_value("embedding.model_vector_size")
        return int(vector_size_str) if vector_size_str else None

    async def _enforce_daily_limit(self, user_id: int) -> None:
        limit_str = await self.admin_setting_service.get("daily_request_limit", "100")
        limit = int(limit_str or 10)
        used = await self.user_repo.get_daily_request(user_id)
        if used >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="今日请求次数已达上限，请明日再试或设置自定义 API Key。",
            )
        await self.user_repo.increment_daily_request(user_id)
        await self.session.commit()

    async def _get_config_value(self, key: str) -> Optional[str]:
        record = await self.system_config_repo.get_by_key(key)
        if record:
            return record.value
        # 兼容环境变量，首次迁移时无需立即写入数据库
        env_key = key.upper().replace(".", "_")
        return os.getenv(env_key)

"""GM Agent 对话编排服务。

核心调度层，负责：
1. 对话管理（创建、获取对话）
2. 上下文构建（委托给 ContextBuilder）
3. LLM 调用（委托给 LLMService）
4. 工具调用解析与待执行操作创建
5. 操作执行编排（委托给具体执行器）
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Optional
from uuid import uuid4

from fastapi import HTTPException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from ...models.gm import GMPendingAction
from ...repositories.gm_repository import GMRepository
from ..llm_service import LLMService
from ..prompt_service import PromptService
from .context_builder import ContextBuilder
from .tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class PendingActionInfo:
    """待执行操作信息（用于返回给前端）。"""

    action_id: str
    tool_name: str
    params: Dict[str, Any]
    preview: str
    status: str = "pending"


@dataclass
class GMChatResponse:
    """GM 对话响应。"""

    conversation_id: str
    message: str
    pending_actions: List[PendingActionInfo]


@dataclass
class ActionResult:
    """单个操作执行结果。"""

    action_id: str
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


@dataclass
class ApplyResult:
    """批量操作执行结果。"""

    applied: List[str]
    results: List[ActionResult]


class GMService:
    """GM Agent 对话编排服务。

    作为 GM Agent 的核心调度层，只负责流程编排，不包含具体业务逻辑。
    具体的工具执行逻辑委托给各自的 Executor。

    Example:
        ```python
        gm_service = GMService(session)

        # 发送消息
        response = await gm_service.chat(
            project_id="xxx",
            message="新增3个配角",
            user_id=1,
        )

        # 应用操作
        result = await gm_service.apply_actions(
            project_id="xxx",
            action_ids=["action-id-1", "action-id-2"],
        )
        ```
    """

    def __init__(self, session: "AsyncSession"):
        """初始化 GM 服务。

        Args:
            session: SQLAlchemy 异步会话
        """
        self.session = session
        self.llm_service = LLMService(session)
        self.prompt_service = PromptService(session)
        self.gm_repo = GMRepository(session)
        self.context_builder = ContextBuilder(session)

    async def chat(
        self,
        project_id: str,
        message: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[int] = None,
        enable_web_search: bool = False,
    ) -> GMChatResponse:
        """处理用户消息，返回 GM 响应。

        Args:
            project_id: 小说项目 ID
            message: 用户消息
            conversation_id: 对话 ID（可选，不传则创建新对话）
            user_id: 用户 ID（用于配额控制）
            enable_web_search: 是否启用联网搜索（仅 Gemini 模型支持）

        Returns:
            GMChatResponse 包含响应内容和待执行操作
        """
        # 1. 获取或创建对话
        conversation = await self.gm_repo.get_or_create_conversation(
            project_id, conversation_id
        )
        logger.info(
            "GM 对话: project=%s, conversation=%s, message=%s",
            project_id,
            conversation.id,
            message[:100],
        )

        # 2. 构建上下文
        context = await self.context_builder.build(project_id)

        # 3. 获取系统提示词
        system_prompt = await self._load_system_prompt()
        full_system_prompt = system_prompt + "\n\n---\n\n" + context

        # 4. 构建对话历史
        history = self._build_message_history(conversation.messages)
        history.append({"role": "user", "content": message})

        # 5. 获取工具定义
        tools = ToolRegistry.get_all_definitions()

        # 6. 调用 LLM
        try:
            response = await self.llm_service.chat_with_tools(
                system_prompt=full_system_prompt,
                messages=history,
                tools=tools,
                user_id=user_id,
                enable_web_search=enable_web_search,
            )
        except Exception as e:
            logger.error("LLM 调用失败: %s", e, exc_info=True)
            raise HTTPException(status_code=503, detail=f"AI 服务暂时不可用: {str(e)}")

        # 7. 解析响应
        assistant_content = response.get("content", "")
        tool_calls = response.get("tool_calls", [])

        # 8. 创建待执行操作
        pending_actions, normalized_tool_calls = await self._create_pending_actions(
            conversation.id,
            len(conversation.messages),
            tool_calls,
        )

        # 9. 保存消息到对话历史
        # 保存用户消息
        await self.gm_repo.append_message(
            conversation_id=conversation.id,
            role="user",
            content=message,
        )

        # 保存助手消息（使用规范化的 tool_calls，其中 id 为 action.id）
        pending_action_ids = [a.action_id for a in pending_actions]
        await self.gm_repo.append_message(
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_content,
            tool_calls=normalized_tool_calls if normalized_tool_calls else None,
            pending_action_ids=pending_action_ids if pending_action_ids else None,
        )

        await self.session.commit()

        return GMChatResponse(
            conversation_id=conversation.id,
            message=assistant_content,
            pending_actions=pending_actions,
        )

    async def stream_chat(
        self,
        project_id: str,
        message: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[int] = None,
        enable_web_search: bool = False,
        images: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """流式处理用户消息，支持多轮工具调用。

        Args:
            project_id: 小说项目 ID
            message: 用户消息
            conversation_id: 对话 ID（可选，不传则创建新对话）
            user_id: 用户 ID（用于配额控制）
            enable_web_search: 是否启用联网搜索（仅 Gemini 模型支持）
            images: 图片列表，每个元素包含 base64 和 mime_type

        Yields:
            dict: 流式事件
                - {"type": "start", "conversation_id": "..."} 开始
                - {"type": "content", "content": "..."} 内容片段
                - {"type": "tool_executing", "tool_name": "...", "params": {...}} 正在执行只读工具
                - {"type": "tool_result", "tool_name": "...", "result": "..."} 只读工具执行结果
                - {"type": "pending_actions", "actions": [...]} 待执行操作（修改类）
                - {"type": "done", "message": "..."} 完成
                - {"type": "error", "error": "..."} 错误
        """
        from ...executors.gm.base import ToolResult

        # 最大循环次数，防止无限循环
        MAX_ITERATIONS = 10

        # 1. 获取或创建对话
        try:
            conversation = await self.gm_repo.get_or_create_conversation(
                project_id, conversation_id
            )
        except Exception as e:
            logger.error("创建对话失败: %s", e)
            yield {"type": "error", "error": str(e)}
            return

        yield {"type": "start", "conversation_id": conversation.id}

        logger.info(
            "GM 流式对话: project=%s, conversation=%s, message=%s",
            project_id,
            conversation.id,
            message[:100],
        )

        # 2. 构建上下文
        try:
            context = await self.context_builder.build(project_id)
        except Exception as e:
            logger.error("构建上下文失败: %s", e)
            yield {"type": "error", "error": f"构建上下文失败: {str(e)}"}
            return

        # 3. 获取系统提示词
        system_prompt = await self._load_system_prompt()
        full_system_prompt = system_prompt + "\n\n---\n\n" + context

        # 4. 构建对话历史
        history = self._build_message_history(conversation.messages)
        # 构建用户消息（支持图片）
        user_message: Dict[str, Any] = {"role": "user", "content": message}
        if images:
            user_message["images"] = images
        history.append(user_message)

        # 5. 获取工具定义
        tools = ToolRegistry.get_all_definitions()

        # 6. 保存用户消息
        await self.gm_repo.append_message(
            conversation_id=conversation.id,
            role="user",
            content=message,
        )

        # 7. 多轮工具调用循环
        all_pending_actions: List[PendingActionInfo] = []
        all_content = ""
        iteration = 0
        # AI 通过 signal_task_status 工具设置的任务状态
        # None: 未设置, "awaiting": 需要确认后继续, "complete": 任务完成
        task_status_signal: Optional[str] = None

        while iteration < MAX_ITERATIONS:
            iteration += 1
            logger.debug("GM 对话第 %d 轮调用", iteration)

            # 流式调用 LLM
            full_content = ""
            tool_calls = []

            try:
                async for event in self.llm_service.stream_chat_with_tools(
                    system_prompt=full_system_prompt,
                    messages=history,
                    tools=tools,
                    user_id=user_id,
                    enable_web_search=enable_web_search,
                ):
                    event_type = event.get("type")

                    if event_type == "content":
                        yield {"type": "content", "content": event["content"]}
                        full_content += event["content"]

                    elif event_type == "done":
                        full_content = event.get("content", "") or full_content
                        tool_calls = event.get("tool_calls", [])

            except Exception as e:
                logger.error("LLM 流式调用失败: %s", e, exc_info=True)
                yield {"type": "error", "error": f"AI 服务暂时不可用: {str(e)}"}
                return

            all_content += full_content

            # 没有工具调用，结束循环
            if not tool_calls:
                logger.debug("无工具调用，结束循环")
                break

            # 分类工具调用
            read_only_calls = []
            write_calls = []

            for call in tool_calls:
                tool_name = call.get("name") or call.get("function", {}).get("name")
                if not tool_name:
                    continue

                try:
                    executor_class = ToolRegistry.get_executor(tool_name)
                    if executor_class.is_read_only:
                        read_only_calls.append(call)
                    else:
                        write_calls.append(call)
                except ValueError:
                    # 未知工具，当作修改类处理
                    write_calls.append(call)

            logger.debug(
                "工具分类: 只读=%d, 修改=%d",
                len(read_only_calls),
                len(write_calls),
            )

            # 处理修改类工具 -> 创建 pending_actions
            if write_calls:
                pending_actions, normalized_tool_calls = await self._create_pending_actions(
                    conversation.id,
                    len(conversation.messages),
                    write_calls,
                )
                all_pending_actions.extend(pending_actions)

                # 保存助手消息（使用累积内容 all_content，确保多轮内容完整）
                pending_action_ids = [a.action_id for a in pending_actions]
                await self.gm_repo.append_message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=all_content,  # 使用累积内容而非当前轮内容
                    tool_calls=normalized_tool_calls if normalized_tool_calls else None,
                    pending_action_ids=pending_action_ids if pending_action_ids else None,
                )
                await self.session.commit()

            # 如果有修改类工具，结束循环（用户需要先确认操作）
            # 即使同时有只读工具，也应该先让用户确认修改操作
            if write_calls:
                logger.debug("存在修改类工具调用，结束循环等待用户确认")
                # 如果同时有只读工具，仍然执行它们但不继续循环
                if not read_only_calls:
                    break
                # 执行只读工具后再退出
            elif not read_only_calls:
                logger.debug("无工具调用，结束循环")
                break

            # 执行只读工具并收集结果
            tool_results_for_llm = []

            for call in read_only_calls:
                tool_name = call.get("name") or call.get("function", {}).get("name")
                arguments = call.get("arguments") or call.get("function", {}).get("arguments")
                call_id = call.get("id") or f"call_{len(tool_results_for_llm)}"

                # 解析参数
                if isinstance(arguments, str):
                    try:
                        params = json.loads(arguments)
                    except json.JSONDecodeError:
                        params = {"raw": arguments}
                else:
                    params = arguments or {}

                # 通知前端正在执行
                yield {
                    "type": "tool_executing",
                    "tool_name": tool_name,
                    "params": params,
                }

                # 执行工具
                try:
                    executor_class = ToolRegistry.get_executor(tool_name)
                    executor = executor_class(self.session)

                    # 参数校验
                    error = await executor.validate_params(params)
                    if error:
                        result_message = f"参数校验失败: {error}"
                    else:
                        result: ToolResult = await executor.execute(project_id, params)
                        if result.data:
                            result_message = f"{result.message}\n\n数据:\n{json.dumps(result.data, ensure_ascii=False, indent=2)}"
                        else:
                            result_message = result.message

                        # 捕获 signal_task_status 工具的信号
                        if tool_name == "signal_task_status" and result.data:
                            task_status_signal = result.data.get("status")
                            logger.info("AI 设置任务状态信号: %s", task_status_signal)

                except Exception as e:
                    logger.error("只读工具执行失败: %s, error=%s", tool_name, e, exc_info=True)
                    result_message = f"执行失败: {str(e)}"

                logger.info(
                    "只读工具执行: tool=%s, result_preview=%s",
                    tool_name,
                    result_message[:200],
                )

                # 通知前端执行结果
                yield {
                    "type": "tool_result",
                    "tool_name": tool_name,
                    "result": result_message[:500] + "..." if len(result_message) > 500 else result_message,
                }

                # 收集结果用于下一轮 LLM 调用
                tool_results_for_llm.append({
                    "call_id": call_id,
                    "tool_name": tool_name,
                    "result": result_message,
                })

            # 更新历史，加入助手消息和工具结果
            history.append({
                "role": "assistant",
                "content": full_content,
                "tool_calls": [
                    {
                        "id": r["call_id"],
                        "type": "function",
                        "function": {
                            "name": r["tool_name"],
                            "arguments": "{}",  # 简化，不需要保存完整参数
                        },
                    }
                    for r in tool_results_for_llm
                ],
            })

            for r in tool_results_for_llm:
                history.append({
                    "role": "tool",
                    "tool_call_id": r["call_id"],
                    "tool_name": r["tool_name"],  # Gemini 格式需要工具名称
                    "content": r["result"],
                })

            # 如果本轮有修改类工具，执行完只读工具后结束循环
            if write_calls:
                logger.debug("修改类工具已创建，只读工具执行完毕，结束循环")
                break

            # 继续下一轮循环

        # 8. 如果没有保存过助手消息（没有修改类工具），现在保存
        if not all_pending_actions and all_content:
            await self.gm_repo.append_message(
                conversation_id=conversation.id,
                role="assistant",
                content=all_content,
            )
            await self.session.commit()

        # 9. 发送待执行操作
        if all_pending_actions:
            yield {
                "type": "pending_actions",
                "actions": [
                    {
                        "action_id": a.action_id,
                        "tool_name": a.tool_name,
                        "params": a.params,
                        "preview": a.preview,
                        "status": a.status,
                    }
                    for a in all_pending_actions
                ],
                # 标识是否有后续任务（Agent 可能还没完成）
                "has_more": iteration < MAX_ITERATIONS,
            }

        # 10. 发送完成事件
        # 判断是否需要确认后继续：
        # 1. 如果 AI 明确调用了 signal_task_status，以其信号为准
        # 2. 如果没有调用且有待执行操作，默认需要确认后继续（兼容旧逻辑）
        if task_status_signal is not None:
            awaiting = task_status_signal == "awaiting"
        else:
            # 兼容：如果 AI 没有调用 signal_task_status，有操作就默认需要继续
            awaiting = len(all_pending_actions) > 0

        yield {
            "type": "done",
            "conversation_id": conversation.id,
            "message": all_content,
            "awaiting_confirmation": awaiting,
        }

    async def apply_actions(
        self,
        project_id: str,
        action_ids: List[str],
    ) -> ApplyResult:
        """执行待执行操作。

        Args:
            project_id: 项目 ID
            action_ids: 要执行的操作 ID 列表

        Returns:
            ApplyResult 包含执行结果
        """
        from ...executors.gm.base import ToolResult

        results: List[ActionResult] = []
        applied: List[str] = []

        for action_id in action_ids:
            # 获取操作
            action = await self.gm_repo.get_pending_action(action_id)
            if not action:
                results.append(ActionResult(
                    action_id=action_id,
                    success=False,
                    message=f"操作 {action_id} 不存在",
                ))
                continue

            if action.status != "pending":
                results.append(ActionResult(
                    action_id=action_id,
                    success=False,
                    message=f"操作已{action.status}，无法再次执行",
                ))
                continue

            # 获取执行器
            try:
                executor_class = ToolRegistry.get_executor(action.tool_name)
            except ValueError as e:
                await self.gm_repo.update_action_status(action_id, "failed", error_message=str(e))
                results.append(ActionResult(
                    action_id=action_id,
                    success=False,
                    message=str(e),
                ))
                continue

            executor = executor_class(self.session)

            # 参数校验
            error = await executor.validate_params(action.params)
            if error:
                await self.gm_repo.update_action_status(action_id, "failed", error_message=error)
                results.append(ActionResult(
                    action_id=action_id,
                    success=False,
                    message=error,
                ))
                continue

            # 执行
            try:
                result: ToolResult = await executor.execute(project_id, action.params)
            except Exception as e:
                logger.error(
                    "工具执行失败: tool=%s, action=%s, error=%s",
                    action.tool_name,
                    action_id,
                    e,
                    exc_info=True,
                )
                await self.gm_repo.update_action_status(
                    action_id, "failed", error_message=str(e)
                )
                results.append(ActionResult(
                    action_id=action_id,
                    success=False,
                    message=f"执行失败: {str(e)}",
                ))
                continue

            # 记录历史
            if result.success:
                await self.gm_repo.record_history(
                    project_id=project_id,
                    action=action,
                    before_state=result.before_state,
                    after_state=result.after_state,
                )
                await self.gm_repo.update_action_status(action_id, "applied")
                applied.append(action_id)

                # 将工具执行结果添加到对话历史，让模型知道操作已完成
                await self.gm_repo.append_message(
                    conversation_id=action.conversation_id,
                    role="tool",
                    content=result.message,
                    tool_call_id=action_id,  # 使用 action_id 作为 tool_call_id
                )
            else:
                await self.gm_repo.update_action_status(
                    action_id, "failed", error_message=result.message
                )

            results.append(ActionResult(
                action_id=action_id,
                success=result.success,
                message=result.message,
                data=result.data,
            ))

        await self.session.commit()

        logger.info(
            "批量执行操作完成: project=%s, total=%d, applied=%d",
            project_id,
            len(action_ids),
            len(applied),
        )

        return ApplyResult(applied=applied, results=results)

    async def discard_actions(
        self,
        action_ids: List[str],
    ) -> int:
        """放弃待执行操作。

        Args:
            action_ids: 要放弃的操作 ID 列表

        Returns:
            成功放弃的操作数量
        """
        count = 0
        for action_id in action_ids:
            action = await self.gm_repo.get_pending_action(action_id)
            if action and action.status == "pending":
                await self.gm_repo.update_action_status(action_id, "discarded")
                count += 1

        await self.session.commit()
        return count

    async def continue_chat(
        self,
        project_id: str,
        conversation_id: str,
        action_results: List[Dict[str, Any]],
        user_id: Optional[int] = None,
        enable_web_search: bool = False,
    ) -> AsyncIterator[Dict[str, Any]]:
        """在用户应用操作后继续对话。

        将操作执行结果反馈给模型，让模型根据结果决定下一步。

        Args:
            project_id: 小说项目 ID
            conversation_id: 对话 ID
            action_results: 操作执行结果列表，每个包含 action_id, success, message
            user_id: 用户 ID（用于配额控制）
            enable_web_search: 是否启用联网搜索

        Yields:
            dict: 流式事件（与 stream_chat 相同）
        """
        # 获取对话
        conversation = await self.gm_repo.conversations.get_by_id(conversation_id)
        if not conversation:
            yield {"type": "error", "error": "对话不存在"}
            return

        # 构造执行结果消息
        result_lines = []
        success_count = 0
        fail_count = 0

        for r in action_results:
            status = "✓" if r.get("success") else "✗"
            message = r.get("message", "")
            if r.get("success"):
                success_count += 1
            else:
                fail_count += 1
            result_lines.append(f"  {status} {message}")

        summary = f"执行了 {len(action_results)} 个操作"
        if fail_count > 0:
            summary += f"（{success_count} 成功，{fail_count} 失败）"

        result_message = f"[操作执行结果]\n{summary}\n" + "\n".join(result_lines)

        # 调用 stream_chat 继续对话
        async for event in self.stream_chat(
            project_id=project_id,
            message=result_message,
            conversation_id=conversation_id,
            user_id=user_id,
            enable_web_search=enable_web_search,
        ):
            yield event

    async def get_conversations(
        self,
        project_id: str,
        include_archived: bool = False,
    ) -> List[Dict[str, Any]]:
        """获取项目的对话列表。

        Args:
            project_id: 项目 ID
            include_archived: 是否包含已归档对话

        Returns:
            对话列表
        """
        conversations = await self.gm_repo.conversations.get_by_project(
            project_id, include_archived=include_archived
        )
        return [
            {
                "id": c.id,
                "title": c.title or self._generate_title(c.messages),
                "message_count": len(c.messages),
                "is_archived": c.is_archived,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
            }
            for c in conversations
        ]

    async def get_conversation_detail(
        self,
        conversation_id: str,
    ) -> Optional[Dict[str, Any]]:
        """获取对话详情。

        Args:
            conversation_id: 对话 ID

        Returns:
            对话详情，包含完整消息历史
        """
        conversation = await self.gm_repo.conversations.get_by_id(conversation_id)
        if not conversation:
            return None

        # 获取待执行操作
        pending_actions = await self.gm_repo.pending_actions.get_by_conversation(
            conversation_id
        )
        actions_map = {a.id: a for a in pending_actions}

        # 构建消息列表，附带操作信息
        messages = []
        for msg in conversation.messages:
            msg_data = {
                "role": msg["role"],
                "content": msg["content"],
            }

            # 如果消息关联了操作，附带操作信息
            if msg.get("pending_action_ids"):
                msg_data["actions"] = [
                    {
                        "action_id": aid,
                        "tool_name": actions_map[aid].tool_name if aid in actions_map else None,
                        "params": actions_map[aid].params if aid in actions_map else {},
                        "preview": actions_map[aid].preview_text if aid in actions_map else None,
                        "status": actions_map[aid].status if aid in actions_map else None,
                    }
                    for aid in msg["pending_action_ids"]
                    if aid in actions_map
                ]

            messages.append(msg_data)

        return {
            "id": conversation.id,
            "project_id": conversation.project_id,
            "title": conversation.title or self._generate_title(conversation.messages),
            "messages": messages,
            "is_archived": conversation.is_archived,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
        }

    async def _load_system_prompt(self) -> str:
        """加载 GM 系统提示词。"""
        prompt = await self.prompt_service.get_prompt("gm_system")
        if prompt:
            return prompt

        # 使用默认提示词
        return self._get_default_system_prompt()

    def _get_default_system_prompt(self) -> str:
        """获取默认系统提示词。"""
        return """你是这本小说的 GM（Game Master），拥有完整的创作权限。你的职责是帮助作者完善小说的各项设定，包括角色、关系、大纲、世界观等。

## 你的能力

你可以通过调用工具来：
- 添加、修改、删除角色
- 管理角色之间的关系
- 调整章节大纲
- 修改世界观设定
- 搜索小说内容

## 工作原则

1. **理解意图**：仔细理解用户的需求，必要时请求澄清
2. **创意建议**：基于现有设定提供有创意但合理的建议
3. **保持一致**：确保新增内容与现有设定不冲突
4. **批量操作**：当用户要求多个修改时，一次性返回所有操作
5. **解释说明**：简要解释为什么这样设计

## 注意事项

- 所有修改操作都需要用户确认后才会生效
- 对于重大修改（如删除角色、修改主线剧情），请提醒用户谨慎
- 如果用户的要求可能导致剧情矛盾，请指出并建议解决方案
"""

    def _build_message_history(self, messages: List[Dict]) -> List[Dict[str, Any]]:
        """构建消息历史（用于 LLM 调用）。

        包含 tool_calls 和 tool 结果消息，确保模型知道之前调用了什么工具以及执行结果。
        """
        history = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "assistant":
                # assistant 消息可能包含 tool_calls
                assistant_msg: Dict[str, Any] = {
                    "role": "assistant",
                    "content": content,
                }
                if msg.get("tool_calls"):
                    assistant_msg["tool_calls"] = msg["tool_calls"]
                history.append(assistant_msg)
            elif role == "tool":
                # 工具执行结果消息
                history.append({
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id", ""),
                    "content": msg.get("content", ""),
                })
            else:
                # user 消息
                history.append({
                    "role": role,
                    "content": content,
                })
        return history

    async def _create_pending_actions(
        self,
        conversation_id: str,
        message_index: int,
        tool_calls: List[Dict],
    ) -> tuple[List[PendingActionInfo], List[Dict]]:
        """创建待执行操作。

        Returns:
            tuple: (pending_actions, normalized_tool_calls)
            - pending_actions: 待执行操作列表
            - normalized_tool_calls: 规范化的 tool_calls，使用 action.id 作为 id
        """
        actions = []
        normalized_calls = []

        for call in tool_calls:
            tool_name = call.get("name") or call.get("function", {}).get("name")
            arguments = call.get("arguments") or call.get("function", {}).get("arguments")

            if not tool_name:
                continue

            # 解析参数
            if isinstance(arguments, str):
                try:
                    params = json.loads(arguments)
                except json.JSONDecodeError:
                    params = {"raw": arguments}
            else:
                params = arguments or {}

            # 生成预览
            try:
                executor_class = ToolRegistry.get_executor(tool_name)
                executor = executor_class(self.session)
                preview = executor.generate_preview(params)
            except ValueError:
                preview = f"执行工具: {tool_name}"

            # 保存操作
            action = await self.gm_repo.save_pending_action(
                conversation_id=conversation_id,
                message_index=message_index,
                tool_name=tool_name,
                params=params,
                preview_text=preview,
            )

            actions.append(PendingActionInfo(
                action_id=action.id,
                tool_name=tool_name,
                params=params,
                preview=preview,
            ))

            # 创建规范化的 tool_call，使用 action.id 作为 id
            normalized_calls.append({
                "id": action.id,
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(params, ensure_ascii=False),
                },
            })

        return actions, normalized_calls

    def _generate_title(self, messages: List[Dict]) -> str:
        """根据对话内容生成标题。"""
        if not messages:
            return "新对话"

        # 取第一条用户消息作为标题
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if len(content) > 30:
                    return content[:30] + "..."
                return content or "新对话"

        return "新对话"

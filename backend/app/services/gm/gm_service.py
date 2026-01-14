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
from .context_builder import ContextBuilder, ContextSnapshot
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
                    tool_name=action.tool_name,  # Gemini 需要工具名称
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

            # 如果消息关联了待执行操作（SSE 模式），附带操作信息
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

            # 如果消息有已执行的工具记录（WebSocket 模式），直接使用
            if msg.get("executed_tools"):
                msg_data["executed_tools"] = msg["executed_tools"]

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
        return '''# 你的身份

你是这部小说的 **创作顾问**，集以下角色于一身：
- **资深网文编辑**：精通网文套路，擅长节奏把控、爽点设计、伏笔布局
- **角色心理专家**：能塑造立体人物，把握人物弧光和成长轨迹
- **世界观架构师**：擅长构建自洽的世界体系，避免设定矛盾

你的核心使命是：**帮助作者把脑海中的故事变成一部完整、精彩、逻辑自洽的小说**。

---

# 你的能力

## 可用工具一览

### 📖 查询类工具（自动执行）
| 工具 | 用途 |
|------|------|
| `get_characters` | 查询角色列表 |
| `get_relationships` | 查询角色关系 |
| `get_outlines` | 查询章节大纲 |
| `get_volumes` | 查询卷结构 |
| `get_chapter_content` | 获取章节正文 |
| `get_chapter_versions` | 查看章节的多个版本 |
| `get_world_setting` | 查询世界观设定 |
| `get_foreshadowing` | 查询伏笔列表 |
| `get_author_notes` | 查询作者备忘录 |
| `get_character_states` | 查询角色状态（数值流小说） |
| `search_content` | 语义搜索小说内容 |

### ✏️ 角色管理（需用户确认）
| 工具 | 用途 |
|------|------|
| `add_character` | 添加新角色 |
| `update_character` | 修改角色属性 |
| `delete_character` | 删除角色（同时删除相关关系） |

### 🔗 关系管理（需用户确认）
| 工具 | 用途 |
|------|------|
| `add_relationship` | 建立角色关系 |
| `update_relationship` | 更新关系描述 |
| `delete_relationship` | 删除关系 |

### 📝 大纲管理（需用户确认）
| 工具 | 用途 |
|------|------|
| `add_outline` | 添加章节大纲 |
| `update_outline` | 修改大纲内容 |
| `delete_outline` | 删除大纲（有正文的章节无法删除） |
| `reorder_outlines` | 调整章节顺序 |
| `assign_outlines_to_volume` | 批量分配章节到卷 |

### 📚 卷管理（需用户确认）
| 工具 | 用途 |
|------|------|
| `add_volume` | 添加新卷 |
| `update_volume` | 更新卷信息 |
| `delete_volume` | 删除卷（不删除章节） |

### 🔮 伏笔系统（需用户确认）
| 工具 | 用途 |
|------|------|
| `add_foreshadowing` | 创建伏笔 |
| `add_clue` | 为伏笔添加线索 |
| `update_foreshadowing` | 更新伏笔 |
| `reveal_foreshadowing` | 标记伏笔已揭示 |
| `delete_foreshadowing` | 删除伏笔 |

### 📄 章节内容（需用户确认）
| 工具 | 用途 |
|------|------|
| `generate_chapter_content` | 保存生成的章节正文 |
| `update_chapter_content` | 修改章节正文 |
| `clear_chapter_content` | 清空章节内容 |

### 🌍 蓝图设定（需用户确认）
| 工具 | 用途 |
|------|------|
| `update_blueprint` | 更新小说蓝图（标题、题材、世界观等） |

### 📌 作者工具（需用户确认）
| 工具 | 用途 |
|------|------|
| `add_author_note` | 添加备忘录 |
| `update_author_note` | 更新备忘录 |
| `update_character_state` | 更新角色状态数据 |

---

# 工作原则

## 1. 主动发现问题

在了解小说设定后，你应该**主动指出**可能的问题：
- 角色设定不完整（缺少动机、性格模糊）
- 关系网络有缺口（重要角色没有关系链接）
- 大纲节奏问题（连续平淡、缺少高潮）
- 伏笔未回收（设置了伏笔但没有揭示计划）
- 设定矛盾（世界观与剧情冲突）

## 2. 创意与专业并重

- **创意建议**：不只执行用户指令，还要提供专业的创作建议
- **多方案呈现**：重要决策提供 2-3 个方案供选择
- **风格匹配**：根据小说题材（玄幻/都市/科幻等）调整建议风格

## 3. 保持一致性

- 新增内容必须与现有设定兼容
- 修改前检查是否会产生连锁影响
- 发现矛盾时主动提醒用户

## 4. 高效批量操作

- 用户要求多个修改时，一次性生成所有操作
- 相关联的修改要一起提出（如添加角色时顺便建立关系）

## 5. 先查询再操作（必须遵守）

**任何修改类操作之前，必须先调用对应的查询工具：**

| 操作类型 | 必须先调用 |
|---------|-----------|
| 添加/修改/删除角色 | `get_characters` |
| 添加/修改/删除关系 | `get_relationships` |
| 添加/修改/删除大纲 | `get_outlines` |
| 添加/修改/删除卷 | `get_volumes` |
| 添加/修改/删除伏笔 | `get_foreshadowing` |
| 修改世界观设定 | `get_world_setting` |
| 修改章节内容 | `get_chapter_content` |
| 添加/修改备忘录 | `get_author_notes` |

**原因：**
- 避免创建重复数据（如角色已存在）
- 确保基于最新状态进行修改（上下文可能已过时）
- 减少因信息不完整导致的错误操作

**绝对禁止：未经查询就直接调用修改类工具。**

---

# 交互规范（必须遵守）

## 核心原则：先对话，后行动

**用户的消息有两种类型，你必须区分对待：**

1. **提问/反馈型**：用户在问问题、表达困惑、提供反馈
   - 例如：「你的设定更新到哪里去了？」「我没看到呀」「这个角色为什么这样设计？」
   - → **必须先用自然语言回答问题**，解释清楚后，才能决定是否需要调用工具

2. **任务/指令型**：用户在下达明确任务
   - 例如：「帮我创建3个配角」「重写第10章大纲」
   - → 可以先简要说明你的计划，然后调用工具执行

**绝对禁止：用户问了问题，你却直接调用工具而不回答。这会让用户感到被忽视。**

## 调用工具前

1. **先回应用户**：无论用户说什么，首先用自然语言回应：
   - 如果是问题 → 回答问题
   - 如果是任务 → 说明你要做什么、为什么这样做
   - 例如：「关于你问的设定更新，我已经提交了修改大纲的操作，你需要点击确认后才会生效。接下来让我查一下具体情况...」

2. **危险操作需强调**：删除类操作要明确提醒影响范围

## 调用工具后

1. **用户确认后必须回复**：
   - 全部确认 → 总结完成的操作
   - 部分确认 → 说明执行了什么、跳过了什么
   - 全部拒绝 → 询问需要调整什么

2. **不要沉默结束**：用户需要明确的反馈

---

# 创作引导

当小说处于早期阶段时，你可以主动引导用户思考：

**角色不足时**：
> 「目前只有 X 个角色，对于这类小说，建议至少需要：主角、对手、导师、伙伴。要我帮你设计吗？」

**大纲缺失时**：
> 「故事还没有章节规划。要我根据类型帮你规划一个初步的章节结构吗？」

**伏笔未设置时**：
> 「检测到目前没有伏笔系统，伏笔对于长篇小说的可读性很重要。要我帮你梳理可能的伏笔点吗？」

**进入创作中期时**：
> 「已完成 X 章，接下来的剧情走向有几个可能...」

---

# 注意事项

- 所有修改操作需用户确认后才生效
- 删除角色会同时删除其所有关系
- 有正文的章节无法删除大纲
- 工具参数都是纯文本字符串，不要传 JSON 对象
'''

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
                    "tool_name": msg.get("tool_name", ""),  # Gemini 需要工具名称
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

    # ========================================================================
    # WebSocket 版本（新架构）
    # ========================================================================

    def _parse_tool_params(self, call: Dict) -> Dict[str, Any]:
        """解析工具调用参数。"""
        arguments = call.get("arguments") or call.get("function", {}).get("arguments")
        if isinstance(arguments, str):
            try:
                return json.loads(arguments)
            except json.JSONDecodeError:
                return {"raw": arguments}
        return arguments or {}

    def _get_tool_name(self, call: Dict) -> Optional[str]:
        """从工具调用中提取工具名称。"""
        return call.get("name") or call.get("function", {}).get("name")

    def _get_call_id(self, call: Dict, fallback_index: int = 0) -> str:
        """从工具调用中提取 call_id。"""
        return call.get("id") or f"call_{fallback_index}"

    def _classify_tool_calls(
        self, tool_calls: List[Dict]
    ) -> tuple[List[Dict], List[Dict]]:
        """将工具调用分类为只读和修改两类。

        Returns:
            (read_only_calls, write_calls)
        """
        read_only_calls = []
        write_calls = []

        for call in tool_calls:
            tool_name = self._get_tool_name(call)
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

        return read_only_calls, write_calls

    async def _ws_execute_read_only_tools(
        self,
        websocket: "WebSocket",
        project_id: str,
        read_only_calls: List[Dict],
        make_tool_executing,
        make_tool_result,
    ) -> List[Dict[str, Any]]:
        """执行只读工具并返回结果列表。

        Args:
            websocket: WebSocket 连接
            project_id: 项目 ID
            read_only_calls: 只读工具调用列表
            make_tool_executing: 工具执行中消息构造函数
            make_tool_result: 工具结果消息构造函数

        Returns:
            工具执行结果列表，格式：[{call_id, tool_name, params, content, status, message}]
        """
        results = []

        for idx, call in enumerate(read_only_calls):
            tool_name = self._get_tool_name(call)
            params = self._parse_tool_params(call)
            call_id = self._get_call_id(call, idx)

            # 通知前端
            await websocket.send_json(
                make_tool_executing(tool_name, params, f"执行 {tool_name}")
            )

            # 执行
            result = await self._execute_single_tool(project_id, tool_name, params)

            # 通知前端结果
            result_preview = result.message
            if len(result_preview) > 500:
                result_preview = result_preview[:500] + "..."

            if result.data:
                result_content = f"{result.message}\n\n数据:\n{json.dumps(result.data, ensure_ascii=False, indent=2)}"
            else:
                result_content = result.message

            await websocket.send_json(
                make_tool_result(
                    tool_name,
                    result.success,
                    result_preview,
                    result.data,
                )
            )

            results.append({
                "call_id": call_id,
                "tool_name": tool_name,
                "params": params,
                "content": result_content,
                "status": "success" if result.success else "failed",
                "message": result_preview,
            })

        return results

    async def _ws_wait_for_confirmation(
        self,
        websocket: "WebSocket",
        make_done,
        all_content: str,
    ) -> Optional[Dict]:
        """等待用户确认响应。

        Args:
            websocket: WebSocket 连接
            make_done: done 消息构造函数
            all_content: 累积的内容

        Returns:
            确认数据字典，或 None（如果用户取消或连接断开）
        """
        while True:
            try:
                received_data = await websocket.receive_json()
            except Exception as e:
                logger.warning("等待确认时连接断开: %s", e)
                return None

            received_type = received_data.get("type")

            if received_type == "cancel":
                return {"type": "cancel"}

            if received_type == "confirm_response":
                return received_data

            if received_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            logger.warning("等待确认期间收到非预期消息类型: %s，忽略并继续等待", received_type)

    async def _execute_single_tool(
        self,
        project_id: str,
        tool_name: str,
        params: Dict[str, Any],
    ) -> "ToolResult":
        """执行单个工具。"""
        from ...executors.gm.base import ToolResult

        try:
            executor_class = ToolRegistry.get_executor(tool_name)
            executor = executor_class(self.session)

            # 参数校验
            error = await executor.validate_params(params)
            if error:
                return ToolResult(success=False, message=f"参数校验失败: {error}")

            # 执行
            return await executor.execute(project_id, params)

        except ValueError as e:
            return ToolResult(success=False, message=f"未知工具: {tool_name}")
        except Exception as e:
            logger.error("工具执行异常: tool=%s, error=%s", tool_name, e, exc_info=True)
            return ToolResult(success=False, message=f"执行异常: {str(e)}")

    async def websocket_chat(
        self,
        websocket: "WebSocket",
        project_id: str,
        message: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[int] = None,
        images: Optional[List[Dict[str, str]]] = None,
        enable_web_search: bool = False,
    ) -> None:
        """WebSocket 版本的对话，支持同步确认。

        核心特性：
        1. 只读工具自动执行
        2. 修改工具等待用户确认后执行
        3. 确认在同一个连接内完成，无需单独 API 调用
        4. 执行完成后自动继续 Agent 循环

        Args:
            websocket: FastAPI WebSocket 连接
            project_id: 小说项目 ID
            message: 用户消息
            conversation_id: 对话 ID（可选）
            user_id: 用户 ID
            images: 图片列表
            enable_web_search: 是否启用联网搜索（仅 Gemini 模型支持）
        """
        import asyncio
        from ...executors.gm.base import ToolResult
        from ...schemas.gm_websocket import (
            make_content,
            make_tool_call,
            make_tool_executing,
            make_tool_result,
            make_confirm_actions,
            make_tool_executed,
            make_done,
            make_error,
            make_round_start,
            WSClientMessageType,
        )

        MAX_ITERATIONS = 15

        # 1. 获取或创建对话
        try:
            conversation = await self.gm_repo.get_or_create_conversation(
                project_id, conversation_id
            )
        except Exception as e:
            logger.error("创建对话失败: %s", e)
            await websocket.send_json(make_error(f"创建对话失败: {str(e)}"))
            return

        logger.info(
            "GM WebSocket 对话开始: project=%s, conversation=%s, enable_web_search=%s",
            project_id,
            conversation.id,
            enable_web_search,
        )

        # 2. 构建上下文（首次，同时创建初始快照）
        try:
            context, context_snapshot, _ = await self.context_builder.build_with_diff(project_id)
        except Exception as e:
            logger.error("构建上下文失败: %s", e)
            await websocket.send_json(make_error(f"构建上下文失败: {str(e)}"))
            return

        system_prompt = await self._load_system_prompt()
        full_system_prompt = system_prompt + "\n\n---\n\n" + context

        # 3. 构建对话历史
        logger.info("=== 原始对话消息（共 %d 条） ===", len(conversation.messages))
        for i, msg in enumerate(conversation.messages[-10:]):
            logger.info("  msg[%d]: role=%s, keys=%s", i, msg.get("role"), list(msg.keys()))
        history = self._build_message_history(conversation.messages)
        user_msg: Dict[str, Any] = {"role": "user", "content": message}
        if images:
            logger.info("收到图片: count=%d, keys=%s", len(images), [list(img.keys()) for img in images])
            user_msg["images"] = images
        history.append(user_msg)

        # 保存用户消息
        await self.gm_repo.append_message(
            conversation_id=conversation.id,
            role="user",
            content=message,
        )

        tools = ToolRegistry.get_all_definitions()

        # 4. Agent 循环
        all_content = ""
        execution_stats = {"success": 0, "failed": 0, "skipped": 0}
        # 记录所有工具执行信息（用于保存到对话历史）
        all_tool_executions: List[Dict[str, Any]] = []

        for iteration in range(MAX_ITERATIONS):
            logger.debug("Agent 循环第 %d 轮", iteration + 1)

            # 4.0 每轮循环都重新构建上下文（确保数据最新），并检测变更
            try:
                context, new_snapshot, diff_markdown = await self.context_builder.build_with_diff(
                    project_id, context_snapshot
                )
                # 更新快照
                context_snapshot = new_snapshot

                # 如果有变更，将变更说明添加到上下文前面
                if diff_markdown:
                    logger.info("检测到上下文变更:\n%s", diff_markdown)
                    full_system_prompt = system_prompt + "\n\n---\n\n" + diff_markdown + "\n\n" + context
                else:
                    full_system_prompt = system_prompt + "\n\n---\n\n" + context
            except Exception as e:
                logger.warning("刷新上下文失败: %s", e)

            # 4.1 流式调用 LLM
            full_content = ""
            tool_calls = []
            # 记录流式收到的工具调用（用于立即通知前端）
            streaming_tool_calls: List[Dict[str, Any]] = []

            # 调试：打印传给模型的最后几条消息
            logger.info("=== 迭代 %d: 传给模型的消息历史（共 %d 条，最后 10 条） ===", iteration, len(history))
            for msg in history[-10:]:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")[:200]  # 截断
                has_tools = "tool_calls" in msg
                tool_call_id = msg.get("tool_call_id", "")
                tool_name = msg.get("tool_name", "")
                logger.info("  [%s] %s%s%s%s", role, content, " (有工具调用)" if has_tools else "", f" (tool_call_id={tool_call_id})" if tool_call_id else "", f" (tool_name={tool_name})" if tool_name else "")
            logger.info("=== 消息历史结束 ===")

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
                        await websocket.send_json(make_content(event["content"]))
                        full_content += event["content"]

                    elif event_type == "tool_call":
                        # 立即通知前端有新的工具调用
                        tool_call = event["tool_call"]
                        tool_name = tool_call.get("name", "")
                        call_id = tool_call.get("id", f"call_{len(streaming_tool_calls)}")

                        # 解析参数
                        arguments = tool_call.get("arguments", "{}")
                        if isinstance(arguments, str):
                            try:
                                params = json.loads(arguments)
                            except json.JSONDecodeError:
                                params = {"raw": arguments}
                        else:
                            params = arguments or {}

                        # 发送工具调用通知给前端
                        await websocket.send_json(make_tool_call(tool_name, params, call_id))
                        streaming_tool_calls.append({
                            "id": call_id,
                            "name": tool_name,
                            "arguments": arguments,
                        })
                        logger.debug("流式工具调用通知: %s", tool_name)

                    elif event_type == "done":
                        full_content = event.get("content", "") or full_content
                        tool_calls = event.get("tool_calls", [])

            except Exception as e:
                logger.error("LLM 调用失败: %s", e, exc_info=True)
                await websocket.send_json(make_error(f"AI 服务暂时不可用: {str(e)}"))
                return

            all_content += full_content

            # 4.2 没有工具调用 = 任务完成
            if not tool_calls:
                logger.debug("无工具调用，任务完成")
                # 立即保存 assistant 消息（无工具调用的纯文本响应）
                if full_content:
                    await self.gm_repo.append_message(
                        conversation_id=conversation.id,
                        role="assistant",
                        content=full_content,
                    )
                    await self.session.commit()
                break

            # 4.3 分类工具（使用公共方法）
            read_only_calls, write_calls = self._classify_tool_calls(tool_calls)

            logger.debug(
                "工具分类: 只读=%d, 修改=%d",
                len(read_only_calls),
                len(write_calls),
            )

            # 4.4 执行只读工具（自动）
            tool_results_for_history = []

            for idx, call in enumerate(read_only_calls):
                tool_name = self._get_tool_name(call)
                params = self._parse_tool_params(call)
                call_id = self._get_call_id(call, idx)

                # 通知前端
                await websocket.send_json(
                    make_tool_executing(tool_name, params, f"执行 {tool_name}")
                )

                # 执行
                result = await self._execute_single_tool(project_id, tool_name, params)

                # 通知前端结果
                result_preview = result.message
                if len(result_preview) > 500:
                    result_preview = result_preview[:500] + "..."
                await websocket.send_json(
                    make_tool_result(tool_name, result.success, result_preview)
                )

                if result.success:
                    execution_stats["success"] += 1
                else:
                    execution_stats["failed"] += 1

                # 构建完整结果消息
                if result.data:
                    result_content = f"{result.message}\n\n数据:\n{json.dumps(result.data, ensure_ascii=False, indent=2)}"
                else:
                    result_content = result.message

                tool_results_for_history.append({
                    "call_id": call_id,
                    "tool_name": tool_name,
                    "params": params,
                    "content": result_content,
                    "status": "success" if result.success else "failed",
                    "message": result_preview,
                })

            # 4.5 处理修改工具（等待用户确认后执行）
            if write_calls:
                # 使用现有的 _create_pending_actions 方法保存到数据库
                pending_actions, normalized_tool_calls = await self._create_pending_actions(
                    conversation.id,
                    len(conversation.messages),
                    write_calls,
                )

                # ★ 立即保存 assistant 消息（在等待用户确认前）
                # 这样即使用户刷新页面，消息也不会丢失
                pending_action_ids = [a.action_id for a in pending_actions]
                # 合并只读工具执行记录
                current_tool_executions = []
                for r in tool_results_for_history:
                    current_tool_executions.append({
                        "tool_name": r["tool_name"],
                        "params": r.get("params", {}),
                        "status": r.get("status", "success"),
                        "message": r.get("message", ""),
                        "preview": r.get("preview"),
                    })

                await self.gm_repo.append_message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=full_content,
                    tool_calls=normalized_tool_calls if normalized_tool_calls else None,
                    pending_action_ids=pending_action_ids if pending_action_ids else None,
                    executed_tools=current_tool_executions if current_tool_executions else None,
                )
                await self.session.commit()
                logger.debug("已保存 assistant 消息（等待用户确认前）")

                # 发送确认请求，标记 awaiting_confirmation=True 表示需要继续
                await websocket.send_json(
                    make_confirm_actions(
                        [
                            {
                                "action_id": a.action_id,
                                "tool_name": a.tool_name,
                                "params": a.params,
                                "preview": a.preview,
                                "is_dangerous": getattr(
                                    ToolRegistry.get_executor(a.tool_name), "is_dangerous", False
                                ) if a.tool_name else False,
                            }
                            for a in pending_actions
                        ],
                        timeout_ms=0,  # 0 表示无超时限制
                        awaiting_confirmation=True,  # 表示确认后需要继续 Agent 循环
                    )
                )

                # 等待用户确认（阻塞直到收到 confirm_response 或 cancel）
                logger.info("等待用户确认操作: pending=%d", len(pending_actions))

                # 使用 while 循环等待正确的消息类型
                confirm_data = None
                while True:
                    try:
                        received_data = await websocket.receive_json()
                    except Exception as e:
                        logger.warning("等待确认时连接断开: %s", e)
                        # 保存当前状态后退出
                        pending_action_ids = [a.action_id for a in pending_actions]
                        await self.gm_repo.append_message(
                            conversation_id=conversation.id,
                            role="assistant",
                            content=all_content + full_content,
                            tool_calls=normalized_tool_calls if normalized_tool_calls else None,
                            pending_action_ids=pending_action_ids if pending_action_ids else None,
                            executed_tools=all_tool_executions if all_tool_executions else None,
                        )
                        await self.session.commit()
                        return

                    received_type = received_data.get("type")

                    if received_type == "cancel":
                        # 用户取消，放弃所有操作
                        await self.discard_actions([a.action_id for a in pending_actions])
                        await websocket.send_json(
                            make_done(
                                conversation_id=conversation.id,
                                message=all_content + full_content + "\n\n[用户取消了操作]",
                            )
                        )
                        return

                    if received_type == "confirm_response":
                        confirm_data = received_data
                        break  # 收到正确的消息类型，退出等待循环

                    if received_type == "ping":
                        # 处理心跳
                        await websocket.send_json({"type": "pong"})
                        continue

                    # 其他消息类型，记录警告但继续等待
                    logger.warning("等待确认期间收到非预期消息类型: %s，忽略并继续等待", received_type)

                # 解析确认结果
                approved_ids = confirm_data.get("approved", [])
                rejected_ids = confirm_data.get("rejected", [])

                logger.info("收到确认响应: approved=%d, rejected=%d", len(approved_ids), len(rejected_ids))

                # 执行被批准的操作
                write_tool_results = []
                for action in pending_actions:
                    if action.action_id in approved_ids:
                        # 执行操作
                        result = await self._execute_single_tool(
                            project_id, action.tool_name, action.params
                        )
                        # 更新数据库状态
                        await self.gm_repo.pending_actions.update_status(
                            action.action_id,
                            "applied" if result.success else "failed",
                        )
                        # 通知前端
                        await websocket.send_json(
                            make_tool_executed(
                                action_id=action.action_id,
                                tool_name=action.tool_name,
                                success=result.success,
                                message=result.message,
                            )
                        )
                        if result.success:
                            execution_stats["success"] += 1
                        else:
                            execution_stats["failed"] += 1

                        # 记录执行结果（用于 Agent 循环）
                        write_tool_results.append({
                            "call_id": action.action_id,
                            "tool_name": action.tool_name,
                            "params": action.params,
                            "content": result.message,
                            "status": "success" if result.success else "failed",
                            "message": result.message[:200] if len(result.message) > 200 else result.message,
                        })
                        all_tool_executions.append({
                            "tool_name": action.tool_name,
                            "params": action.params,
                            "status": "success" if result.success else "failed",
                            "message": result.message[:200] if len(result.message) > 200 else result.message,
                            "preview": action.preview,
                        })

                    elif action.action_id in rejected_ids:
                        # 放弃操作
                        await self.gm_repo.pending_actions.update_status(
                            action.action_id, "discarded"
                        )
                        execution_stats["skipped"] += 1

                await self.session.commit()

                # ★ 更新对话历史（无论工具是否执行都要更新，否则模型不知道自己说过什么）
                # 构建所有工具调用的记录（包括被拒绝的）
                all_write_tool_calls = []
                for action in pending_actions:
                    all_write_tool_calls.append({
                        "id": action.action_id,
                        "type": "function",
                        "function": {
                            "name": action.tool_name,
                            "arguments": json.dumps(action.params, ensure_ascii=False),
                        },
                    })

                # 添加 assistant 消息到 history（包含所有工具调用）
                history.append({
                    "role": "assistant",
                    "content": full_content,
                    "tool_calls": all_write_tool_calls,
                })

                # 添加 tool 结果消息（包括执行成功、失败、被拒绝的）
                for action in pending_actions:
                    if action.action_id in approved_ids:
                        # 查找执行结果
                        result_item = next(
                            (r for r in write_tool_results if r["call_id"] == action.action_id),
                            None
                        )
                        if result_item:
                            history.append({
                                "role": "tool",
                                "tool_call_id": action.action_id,
                                "tool_name": action.tool_name,
                                "content": result_item["content"],
                            })
                        else:
                            # 执行失败，没有结果
                            history.append({
                                "role": "tool",
                                "tool_call_id": action.action_id,
                                "tool_name": action.tool_name,
                                "content": f"工具 {action.tool_name} 执行失败",
                            })
                    elif action.action_id in rejected_ids:
                        # 用户拒绝的操作
                        history.append({
                            "role": "tool",
                            "tool_call_id": action.action_id,
                            "tool_name": action.tool_name,
                            "content": f"用户拒绝了此操作（{action.preview}）",
                        })

                logger.debug(
                    "已更新 history: assistant 消息 + %d 个工具结果",
                    len(pending_actions),
                )

                # 继续下一轮循环（不 return）
                # 注意：all_content 已在第 1104 行累加，此处不再重复

            # 4.6 更新对话历史（只有只读工具的情况）
            all_tool_results = tool_results_for_history

            if all_tool_results and not write_calls:
                # ★ 只读工具执行完后立即保存 assistant 消息
                current_tool_executions = []
                for r in all_tool_results:
                    current_tool_executions.append({
                        "tool_name": r["tool_name"],
                        "params": r.get("params", {}),
                        "status": r.get("status", "success"),
                        "message": r.get("message", r["content"][:200] if len(r["content"]) > 200 else r["content"]),
                        "preview": r.get("preview"),
                    })

                await self.gm_repo.append_message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=full_content,
                    executed_tools=current_tool_executions if current_tool_executions else None,
                )
                await self.session.commit()
                logger.debug("已保存 assistant 消息（只读工具执行后）")

                # 累积工具执行信息（用于统计）
                all_tool_executions.extend(current_tool_executions)

                # 添加 assistant 消息到 history（用于下一轮 LLM 调用）
                history.append({
                    "role": "assistant",
                    "content": full_content,
                    "tool_calls": [
                        {
                            "id": r["call_id"],
                            "type": "function",
                            "function": {
                                "name": r["tool_name"],
                                "arguments": "{}",
                            },
                        }
                        for r in all_tool_results
                    ],
                })

                # 添加 tool 结果消息到 history
                for r in all_tool_results:
                    history.append({
                        "role": "tool",
                        "tool_call_id": r["call_id"],
                        "content": r["content"],
                    })

            # 继续下一轮循环

        # 5. 发送完成消息（消息已在循环中保存，无需再次保存）
        await websocket.send_json(
            make_done(
                conversation_id=conversation.id,
                message=all_content,
                summary=execution_stats,  # 始终发送统计
            )
        )

        logger.info(
            "GM WebSocket 对话完成: project=%s, conversation=%s, stats=%s",
            project_id,
            conversation.id,
            execution_stats,
        )

"""GM Agent 数据访问层。

提供 GM 对话、待执行操作、操作历史的 CRUD 操作。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.gm import GMActionHistory, GMConversation, GMPendingAction
from .base import BaseRepository

logger = logging.getLogger(__name__)


class GMConversationRepository(BaseRepository[GMConversation]):
    """GM 对话仓储。"""

    model = GMConversation

    async def get_by_id(self, conversation_id: str) -> Optional[GMConversation]:
        """根据 ID 获取对话。

        Args:
            conversation_id: 对话 ID

        Returns:
            GMConversation 实例或 None
        """
        stmt = (
            select(GMConversation)
            .where(GMConversation.id == conversation_id)
            .options(selectinload(GMConversation.pending_actions))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_project(
        self,
        project_id: str,
        *,
        include_archived: bool = False,
        limit: int = 50,
    ) -> List[GMConversation]:
        """获取项目的所有对话。

        Args:
            project_id: 项目 ID
            include_archived: 是否包含已归档对话
            limit: 返回数量限制

        Returns:
            对话列表，按更新时间倒序
        """
        stmt = (
            select(GMConversation)
            .where(GMConversation.project_id == project_id)
            .order_by(GMConversation.updated_at.desc())
            .limit(limit)
        )

        if not include_archived:
            stmt = stmt.where(GMConversation.is_archived == False)  # noqa: E712

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        project_id: str,
        title: Optional[str] = None,
    ) -> GMConversation:
        """创建新对话。

        Args:
            project_id: 项目 ID
            title: 对话标题（可选）

        Returns:
            新创建的 GMConversation 实例
        """
        conversation = GMConversation(
            id=str(uuid4()),
            project_id=project_id,
            title=title,
            messages=[],
            is_archived=False,
        )
        self.session.add(conversation)
        await self.session.flush()
        logger.info("创建 GM 对话: id=%s, project_id=%s", conversation.id, project_id)
        return conversation

    async def get_or_create(
        self,
        project_id: str,
        conversation_id: Optional[str] = None,
    ) -> GMConversation:
        """获取或创建对话。

        Args:
            project_id: 项目 ID
            conversation_id: 对话 ID（可选，不传则创建新对话）

        Returns:
            GMConversation 实例
        """
        if conversation_id:
            conversation = await self.get_by_id(conversation_id)
            if conversation:
                return conversation
            logger.warning(
                "对话 %s 不存在，将创建新对话",
                conversation_id,
            )

        return await self.create(project_id)

    async def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool_calls: Optional[List[dict]] = None,
        pending_action_ids: Optional[List[str]] = None,
    ) -> None:
        """追加消息到对话历史。

        Args:
            conversation_id: 对话 ID
            role: 消息角色 (user/assistant)
            content: 消息内容
            tool_calls: 工具调用列表（可选）
            pending_action_ids: 关联的待执行操作 ID（可选）
        """
        conversation = await self.get_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"对话 {conversation_id} 不存在")

        message = {
            "role": role,
            "content": content,
        }
        if tool_calls:
            message["tool_calls"] = tool_calls
        if pending_action_ids:
            message["pending_action_ids"] = pending_action_ids

        # 需要创建新列表以触发 SQLAlchemy 变更检测
        messages = list(conversation.messages)
        messages.append(message)
        conversation.messages = messages

        await self.session.flush()

    async def update_title(self, conversation_id: str, title: str) -> None:
        """更新对话标题。

        Args:
            conversation_id: 对话 ID
            title: 新标题
        """
        stmt = (
            update(GMConversation)
            .where(GMConversation.id == conversation_id)
            .values(title=title)
        )
        await self.session.execute(stmt)

    async def archive(self, conversation_id: str) -> None:
        """归档对话。

        Args:
            conversation_id: 对话 ID
        """
        stmt = (
            update(GMConversation)
            .where(GMConversation.id == conversation_id)
            .values(is_archived=True)
        )
        await self.session.execute(stmt)


class GMPendingActionRepository(BaseRepository[GMPendingAction]):
    """GM 待执行操作仓储。"""

    model = GMPendingAction

    async def get_by_id(self, action_id: str) -> Optional[GMPendingAction]:
        """根据 ID 获取待执行操作。

        Args:
            action_id: 操作 ID

        Returns:
            GMPendingAction 实例或 None
        """
        stmt = select(GMPendingAction).where(GMPendingAction.id == action_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_conversation(
        self,
        conversation_id: str,
        *,
        status: Optional[str] = None,
    ) -> List[GMPendingAction]:
        """获取对话的所有待执行操作。

        Args:
            conversation_id: 对话 ID
            status: 状态筛选（可选）

        Returns:
            操作列表，按创建时间排序
        """
        stmt = (
            select(GMPendingAction)
            .where(GMPendingAction.conversation_id == conversation_id)
            .order_by(GMPendingAction.created_at)
        )

        if status:
            stmt = stmt.where(GMPendingAction.status == status)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_by_ids(self, action_ids: List[str]) -> List[GMPendingAction]:
        """批量获取待执行操作（仅 pending 状态）。

        Args:
            action_ids: 操作 ID 列表

        Returns:
            操作列表
        """
        if not action_ids:
            return []

        stmt = (
            select(GMPendingAction)
            .where(
                GMPendingAction.id.in_(action_ids),
                GMPendingAction.status == "pending",
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        conversation_id: str,
        message_index: int,
        tool_name: str,
        params: dict,
        preview_text: str,
    ) -> GMPendingAction:
        """创建待执行操作。

        Args:
            conversation_id: 对话 ID
            message_index: 消息索引
            tool_name: 工具名称
            params: 工具参数
            preview_text: 预览文本

        Returns:
            新创建的 GMPendingAction 实例
        """
        action = GMPendingAction(
            id=str(uuid4()),
            conversation_id=conversation_id,
            message_index=message_index,
            tool_name=tool_name,
            params=params,
            preview_text=preview_text,
            status="pending",
        )
        self.session.add(action)
        await self.session.flush()
        logger.info(
            "创建待执行操作: id=%s, tool=%s, conversation=%s",
            action.id,
            tool_name,
            conversation_id,
        )
        return action

    async def update_status(
        self,
        action_id: str,
        status: str,
        *,
        error_message: Optional[str] = None,
    ) -> None:
        """更新操作状态。

        Args:
            action_id: 操作 ID
            status: 新状态
            error_message: 错误信息（可选）
        """
        values = {"status": status}

        if status == "applied":
            values["applied_at"] = datetime.utcnow()
        if error_message:
            values["error_message"] = error_message

        stmt = (
            update(GMPendingAction)
            .where(GMPendingAction.id == action_id)
            .values(**values)
        )
        await self.session.execute(stmt)

    async def discard(self, action_id: str) -> None:
        """放弃操作。

        Args:
            action_id: 操作 ID
        """
        await self.update_status(action_id, "discarded")


class GMActionHistoryRepository(BaseRepository[GMActionHistory]):
    """GM 操作历史仓储。"""

    model = GMActionHistory

    async def get_by_project(
        self,
        project_id: str,
        *,
        limit: int = 100,
    ) -> List[GMActionHistory]:
        """获取项目的操作历史。

        Args:
            project_id: 项目 ID
            limit: 返回数量限制

        Returns:
            操作历史列表，按创建时间倒序
        """
        stmt = (
            select(GMActionHistory)
            .where(GMActionHistory.project_id == project_id)
            .order_by(GMActionHistory.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        project_id: str,
        action_id: str,
        tool_name: str,
        params: dict,
        before_state: Optional[dict] = None,
        after_state: Optional[dict] = None,
    ) -> GMActionHistory:
        """记录操作历史。

        Args:
            project_id: 项目 ID
            action_id: 待执行操作 ID
            tool_name: 工具名称
            params: 工具参数
            before_state: 操作前状态
            after_state: 操作后状态

        Returns:
            新创建的 GMActionHistory 实例
        """
        history = GMActionHistory(
            id=str(uuid4()),
            project_id=project_id,
            action_id=action_id,
            tool_name=tool_name,
            params=params,
            before_state=before_state,
            after_state=after_state,
            is_reverted=False,
        )
        self.session.add(history)
        await self.session.flush()
        logger.info(
            "记录操作历史: id=%s, tool=%s, project=%s",
            history.id,
            tool_name,
            project_id,
        )
        return history

    async def mark_reverted(self, history_id: str) -> None:
        """标记操作已撤销。

        Args:
            history_id: 历史记录 ID
        """
        stmt = (
            update(GMActionHistory)
            .where(GMActionHistory.id == history_id)
            .values(is_reverted=True, reverted_at=datetime.utcnow())
        )
        await self.session.execute(stmt)


class GMRepository:
    """GM 数据访问层聚合类。

    提供统一的访问入口，内部组合各子仓储。
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.conversations = GMConversationRepository(session)
        self.pending_actions = GMPendingActionRepository(session)
        self.action_history = GMActionHistoryRepository(session)

    async def get_or_create_conversation(
        self,
        project_id: str,
        conversation_id: Optional[str] = None,
    ) -> GMConversation:
        """获取或创建对话。"""
        return await self.conversations.get_or_create(project_id, conversation_id)

    async def get_pending_action(self, action_id: str) -> Optional[GMPendingAction]:
        """获取待执行操作。"""
        return await self.pending_actions.get_by_id(action_id)

    async def save_pending_action(
        self,
        conversation_id: str,
        message_index: int,
        tool_name: str,
        params: dict,
        preview_text: str,
    ) -> GMPendingAction:
        """保存待执行操作。"""
        return await self.pending_actions.create(
            conversation_id=conversation_id,
            message_index=message_index,
            tool_name=tool_name,
            params=params,
            preview_text=preview_text,
        )

    async def update_action_status(
        self,
        action_id: str,
        status: str,
        *,
        error_message: Optional[str] = None,
    ) -> None:
        """更新操作状态。"""
        await self.pending_actions.update_status(action_id, status, error_message=error_message)

    async def record_history(
        self,
        project_id: str,
        action: GMPendingAction,
        before_state: Optional[dict] = None,
        after_state: Optional[dict] = None,
    ) -> GMActionHistory:
        """记录操作历史。"""
        return await self.action_history.create(
            project_id=project_id,
            action_id=action.id,
            tool_name=action.tool_name,
            params=action.params,
            before_state=before_state,
            after_state=after_state,
        )

    async def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool_calls: Optional[List[dict]] = None,
        pending_action_ids: Optional[List[str]] = None,
    ) -> None:
        """追加消息到对话。"""
        await self.conversations.append_message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            pending_action_ids=pending_action_ids,
        )

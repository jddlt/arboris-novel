"""GM Agent 相关数据模型。

包含：
- GMConversation: GM对话记录
- GMPendingAction: 待执行操作
- GMActionHistory: 操作历史（支持撤销）
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base
from .novel import BIGINT_PK_TYPE, LONG_TEXT_TYPE

# JSON 类型需要特殊处理以支持跨数据库
try:
    from sqlalchemy.dialects.mysql import JSON as MySQLJSON
    from sqlalchemy import JSON
except ImportError:
    from sqlalchemy import JSON


class GMConversation(Base):
    """GM对话记录表。

    存储用户与GM Agent的对话历史，支持多轮对话。
    每个小说项目可以有多个对话会话。
    """

    __tablename__ = "gm_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="对话标题，可自动生成或用户自定义",
    )
    messages: Mapped[list] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="对话消息列表 [{role, content, tool_calls, pending_action_ids}]",
    )
    is_archived: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="是否已归档",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # 关联关系
    project: Mapped["NovelProject"] = relationship(
        "NovelProject",
        back_populates="gm_conversations",
    )
    pending_actions: Mapped[list["GMPendingAction"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="GMPendingAction.created_at",
    )


class GMPendingAction(Base):
    """待执行操作表。

    存储GM Agent返回的工具调用，等待用户确认后执行。
    每个操作独立存储，支持单独应用或放弃。
    """

    __tablename__ = "gm_pending_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("gm_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="所属消息在对话中的索引",
    )
    tool_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="工具名称",
    )
    params: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="工具调用参数",
    )
    preview_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="操作预览文本，用于前端展示",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        index=True,
        comment="状态: pending/applied/discarded/failed",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="执行失败时的错误信息",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    applied_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="应用时间",
    )

    # 关联关系
    conversation: Mapped[GMConversation] = relationship(
        back_populates="pending_actions",
    )
    history: Mapped[Optional["GMActionHistory"]] = relationship(
        back_populates="action",
        uselist=False,
    )


class GMActionHistory(Base):
    """操作历史表。

    记录已执行的操作，保存操作前后的状态快照，支持撤销功能。
    """

    __tablename__ = "gm_action_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_id: Mapped[str] = mapped_column(
        ForeignKey("gm_pending_actions.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        comment="关联的待执行操作ID",
    )
    tool_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="工具名称",
    )
    params: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="执行时的参数",
    )
    before_state: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="操作前的状态快照，用于撤销",
    )
    after_state: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="操作后的状态快照",
    )
    is_reverted: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="是否已撤销",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    reverted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="撤销时间",
    )

    # 关联关系
    project: Mapped["NovelProject"] = relationship("NovelProject")
    action: Mapped[Optional[GMPendingAction]] = relationship(
        back_populates="history",
    )

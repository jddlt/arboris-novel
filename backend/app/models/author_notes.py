"""作者备忘录和角色状态追踪模型。

用于支持：
1. 作者手动维护的备忘信息（章节备忘、角色秘密、写作风格等）
2. 角色状态快照（数值流小说的等级、装备、技能等）
3. 生成时可选择注入的上下文
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Boolean, JSON, func
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base

# 自定义列类型：兼容跨数据库环境
from .novel import BIGINT_PK_TYPE, LONG_TEXT_TYPE


class AuthorNoteType(str, Enum):
    """备忘录类型枚举。"""
    # 基础类型
    CHAPTER = "chapter"           # 章节备忘
    CHARACTER_SECRET = "character_secret"  # 角色秘密
    STYLE = "style"               # 写作风格
    TODO = "todo"                 # 待办事项
    GLOBAL = "global"             # 全局备忘
    # 扩展类型
    PLOT_THREAD = "plot_thread"   # 剧情线索（多条剧情线追踪）
    TIMELINE = "timeline"         # 时间线（重要时间节点）
    ITEM = "item"                 # 物品/道具（重要物品信息）
    LOCATION = "location"         # 地点场景（场景描写参考）
    ABILITY = "ability"           # 技能/能力（特殊能力说明）
    REVISION = "revision"         # 待修改（需要回头修改的内容）
    WORLD_BUILDING = "world_building"  # 世界观补充（设定补充说明）


class AuthorNote(Base):
    """作者备忘录。

    存储作者手动维护的各类笔记，可在生成章节时选择性注入。

    Attributes:
        id: 主键
        project_id: 关联的小说项目
        type: 备忘类型
        chapter_number: 关联章节（仅 chapter 类型）
        volume_id: 关联卷（卷级别的备忘录）
        character_id: 关联角色（仅 character_secret 类型）
        title: 简短标题（列表显示用）
        content: 详细内容
        is_active: 是否有效（伏笔回收后可标记无效）
        priority: 优先级（用于排序）
        created_at: 创建时间
        updated_at: 更新时间
    """

    __tablename__ = "author_notes"

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # 关联字段（可选）
    chapter_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    volume_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("volumes.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    character_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("blueprint_characters.id", ondelete="SET NULL"),
        nullable=True
    )

    # 内容字段
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(LONG_TEXT_TYPE, nullable=False)

    # 状态字段
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关系
    project: Mapped["NovelProject"] = relationship("NovelProject", back_populates="author_notes")
    character: Mapped[Optional["BlueprintCharacter"]] = relationship(
        "BlueprintCharacter", back_populates="secrets"
    )


class CharacterState(Base):
    """角色状态快照。

    追踪角色在每章的状态变化，适用于数值流小说（网游、修仙等）。

    Attributes:
        id: 主键
        character_id: 关联角色
        chapter_number: 状态所属章节
        data: 动态数据（JSON，结构由模板决定）
        change_note: 变更说明
        created_at: 创建时间
    """

    __tablename__ = "character_states"

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(
        ForeignKey("blueprint_characters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # 动态数据
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # 变更说明
    change_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # 关系
    character: Mapped["BlueprintCharacter"] = relationship(
        "BlueprintCharacter", back_populates="states"
    )

    # 复合唯一约束
    __table_args__ = (
        # 同一角色同一章节只能有一个状态快照
        {"sqlite_autoincrement": True},
    )


class StateTemplate(Base):
    """状态模板。

    定义不同类型小说的状态追踪字段结构。

    Attributes:
        id: 主键
        name: 模板名称（如 "网游"、"修仙"、"都市"）
        display_name: 显示名称
        description: 模板描述
        schema: 字段结构定义（JSON Schema 格式）
        is_system: 是否为系统预设模板
        created_at: 创建时间
    """

    __tablename__ = "state_templates"

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 字段结构定义
    schema: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # 是否为系统预设
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class GenerationContext(Base):
    """生成上下文记录。

    记录每次章节生成时选择的上下文，用于复现和分析。

    Attributes:
        id: 主键
        chapter_id: 关联章节
        selected_note_ids: 选中的备忘录 ID 列表
        selected_state_ids: 选中的状态快照 ID 列表
        extra_instruction: 额外指令
        created_at: 创建时间
    """

    __tablename__ = "generation_contexts"

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False
    )

    # 选中的上下文
    selected_note_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    selected_state_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # 额外指令
    extra_instruction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # 关系
    chapter: Mapped["Chapter"] = relationship("Chapter", back_populates="generation_contexts")

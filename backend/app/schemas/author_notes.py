"""作者备忘录和角色状态的 Pydantic Schema。"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ==================== 备忘录类型枚举 ====================

class AuthorNoteType(str, Enum):
    """备忘录类型。"""
    # 基础类型
    CHAPTER = "chapter"
    CHARACTER_SECRET = "character_secret"
    STYLE = "style"
    TODO = "todo"
    GLOBAL = "global"
    # 扩展类型
    PLOT_THREAD = "plot_thread"
    TIMELINE = "timeline"
    ITEM = "item"
    LOCATION = "location"
    ABILITY = "ability"
    REVISION = "revision"
    WORLD_BUILDING = "world_building"


# ==================== 备忘录 Schema ====================

class AuthorNoteBase(BaseModel):
    """备忘录基础字段。"""
    type: AuthorNoteType
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    chapter_number: Optional[int] = None
    volume_id: Optional[int] = None
    character_id: Optional[int] = None
    priority: int = 0


class AuthorNoteCreate(AuthorNoteBase):
    """创建备忘录请求。"""
    pass


class AuthorNoteUpdate(BaseModel):
    """更新备忘录请求。"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = Field(None, min_length=1)
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    volume_id: Optional[int] = None
    chapter_number: Optional[int] = None


class AuthorNoteResponse(AuthorNoteBase):
    """备忘录响应。"""
    id: int
    project_id: str
    is_active: bool
    volume_title: Optional[str] = None  # 关联卷的标题
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AuthorNoteListResponse(BaseModel):
    """备忘录列表响应。"""
    notes: List[AuthorNoteResponse]
    total: int


# ==================== 角色状态 Schema ====================

class CharacterStateBase(BaseModel):
    """角色状态基础字段。"""
    data: Dict[str, Any] = Field(default_factory=dict)
    change_note: Optional[str] = None


class CharacterStateCreate(CharacterStateBase):
    """创建角色状态请求。"""
    character_id: int
    chapter_number: int


class CharacterStateUpdate(BaseModel):
    """更新角色状态请求。"""
    data: Optional[Dict[str, Any]] = None
    change_note: Optional[str] = None


class CharacterStateResponse(CharacterStateBase):
    """角色状态响应。"""
    id: int
    character_id: int
    chapter_number: int
    created_at: datetime

    class Config:
        from_attributes = True


class CharacterStateWithName(CharacterStateResponse):
    """带角色名称的状态响应。"""
    character_name: str


class CharacterStatesListResponse(BaseModel):
    """角色状态列表响应。"""
    states: List[CharacterStateWithName]


# ==================== 状态模板 Schema ====================

class StateTemplateBase(BaseModel):
    """状态模板基础字段。"""
    name: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = None
    schema: Dict[str, Any] = Field(default_factory=dict)


class StateTemplateCreate(StateTemplateBase):
    """创建状态模板请求。"""
    pass


class StateTemplateResponse(StateTemplateBase):
    """状态模板响应。"""
    id: int
    is_system: bool
    created_at: datetime

    class Config:
        from_attributes = True


class StateTemplateListResponse(BaseModel):
    """状态模板列表响应。"""
    templates: List[StateTemplateResponse]


# ==================== 生成上下文 Schema ====================

class GenerationContextCreate(BaseModel):
    """创建生成上下文请求。"""
    selected_note_ids: Optional[List[int]] = None
    selected_state_ids: Optional[List[int]] = None
    extra_instruction: Optional[str] = None


class GenerationContextResponse(GenerationContextCreate):
    """生成上下文响应。"""
    id: int
    chapter_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== 生成弹窗可选上下文 Schema ====================

class SelectableNote(BaseModel):
    """可勾选的备忘录。"""
    id: int
    type: AuthorNoteType
    title: str
    content: str
    chapter_number: Optional[int] = None
    volume_id: Optional[int] = None
    volume_title: Optional[str] = None
    character_name: Optional[str] = None
    is_recommended: bool = False  # 是否推荐勾选


class SelectableState(BaseModel):
    """可勾选的角色状态。"""
    id: int
    character_id: int
    character_name: str
    chapter_number: int
    data: Dict[str, Any]
    summary: str  # 状态摘要（如 "Lv36 攻击1200"）


class GenerationContextOptions(BaseModel):
    """生成章节时可选择的上下文。"""
    notes: List[SelectableNote] = Field(default_factory=list)
    states: List[SelectableState] = Field(default_factory=list)
    # 推荐自动勾选的 ID
    recommended_note_ids: List[int] = Field(default_factory=list)
    recommended_state_ids: List[int] = Field(default_factory=list)


# ==================== 批量操作 Schema ====================

class BatchDeleteRequest(BaseModel):
    """批量删除请求。"""
    ids: List[int]


class BatchUpdateActiveRequest(BaseModel):
    """批量更新激活状态请求。"""
    ids: List[int]
    is_active: bool

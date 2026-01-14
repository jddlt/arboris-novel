"""添加作者备忘录工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.author_notes import AuthorNote
from ....services.gm.tool_registry import ToolRegistry

# 备忘录类型显示名称映射（公共常量）
NOTE_TYPE_DISPLAY = {
    "chapter": "章节备忘",
    "character_secret": "角色秘密",
    "style": "写作风格",
    "todo": "待办事项",
    "global": "全局备忘",
    "plot_thread": "剧情线索",
    "timeline": "时间线",
    "item": "物品/道具",
    "location": "地点场景",
    "ability": "技能/能力",
    "revision": "待修改",
    "world_building": "世界观补充",
}

# 所有有效的备忘录类型
VALID_NOTE_TYPES = list(NOTE_TYPE_DISPLAY.keys())

logger = logging.getLogger(__name__)


@ToolRegistry.register
class AddAuthorNoteExecutor(BaseToolExecutor):
    """添加作者备忘录。"""

    @classmethod
    def get_name(cls) -> str:
        return "add_author_note"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="add_author_note",
            description="添加作者备忘录。用于记录章节写作要点、角色秘密、写作风格指南、待办事项、剧情线索、时间线等私人笔记。这些信息会在生成章节时作为上下文参考。",
            parameters={
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "description": "备忘录类型：chapter（章节备忘）、character_secret（角色秘密）、style（写作风格）、todo（待办事项）、global（全局备忘）、plot_thread（剧情线索）、timeline（时间线）、item（物品/道具）、location（地点场景）、ability（技能/能力）、revision（待修改）、world_building（世界观补充）",
                        "enum": VALID_NOTE_TYPES,
                    },
                    "title": {
                        "type": "string",
                        "description": "备忘录标题，简短概括",
                    },
                    "content": {
                        "type": "string",
                        "description": "备忘录详细内容",
                    },
                    "chapter_number": {
                        "type": "integer",
                        "description": "关联的章节号（仅 chapter 类型需要，生成该章节时会自动注入此备忘录）",
                    },
                    "volume_id": {
                        "type": "integer",
                        "description": "关联的卷 ID（可选，生成该卷下的章节时会自动注入此备忘录）",
                    },
                    "character_id": {
                        "type": "integer",
                        "description": "关联的角色 ID（仅 character_secret 类型需要）",
                    },
                    "priority": {
                        "type": "integer",
                        "description": "优先级，数值越大越优先显示（默认 0）",
                    },
                },
                "required": ["type", "title", "content"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        note_type = params.get("type", "global")
        title = params.get("title", "未命名")
        return f"添加{NOTE_TYPE_DISPLAY.get(note_type, '备忘录')}：{title}"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        note_type = params.get("type")
        if not note_type:
            return "备忘录类型不能为空"

        if note_type not in VALID_NOTE_TYPES:
            return f"无效的备忘录类型：{note_type}，可选值：{', '.join(VALID_NOTE_TYPES)}"

        title = params.get("title")
        if not title or not title.strip():
            return "备忘录标题不能为空"

        content = params.get("content")
        if not content or not content.strip():
            return "备忘录内容不能为空"

        if note_type == "chapter" and not params.get("chapter_number"):
            return "章节备忘必须指定章节号"

        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        note = AuthorNote(
            project_id=project_id,
            type=params["type"],
            title=params["title"].strip(),
            content=params["content"].strip(),
            chapter_number=params.get("chapter_number"),
            volume_id=params.get("volume_id"),
            character_id=params.get("character_id"),
            priority=params.get("priority", 0),
            is_active=True,
        )

        self.session.add(note)
        await self.session.flush()

        logger.info(
            "添加备忘录成功: project=%s, type=%s, title=%s, id=%d",
            project_id, note.type, note.title, note.id
        )

        return ToolResult(
            success=True,
            message=f"成功添加{NOTE_TYPE_DISPLAY.get(note.type, '备忘录')}「{note.title}」",
            data={
                "note_id": note.id,
                "type": note.type,
                "title": note.title,
            },
            after_state={
                "id": note.id,
                "type": note.type,
                "title": note.title,
                "content": note.content,
                "chapter_number": note.chapter_number,
                "volume_id": note.volume_id,
                "character_id": note.character_id,
                "priority": note.priority,
            },
        )

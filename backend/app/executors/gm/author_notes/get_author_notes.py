"""获取作者备忘录工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....services.gm.tool_registry import ToolRegistry
from .add_author_note import NOTE_TYPE_DISPLAY

logger = logging.getLogger(__name__)


@ToolRegistry.register
class GetAuthorNotesExecutor(BaseToolExecutor):
    """获取作者备忘录列表。"""

    is_read_only = True

    @classmethod
    def get_name(cls) -> str:
        return "get_author_notes"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        from .add_author_note import VALID_NOTE_TYPES
        return ToolDefinition(
            name="get_author_notes",
            description="获取作者的备忘录列表。可按类型过滤：chapter（章节备忘）、character_secret（角色秘密）、style（写作风格）、todo（待办事项）、global（全局备忘）、plot_thread（剧情线索）、timeline（时间线）、item（物品/道具）、location（地点场景）、ability（技能/能力）、revision（待修改）、world_building（世界观补充）。",
            parameters={
                "type": "object",
                "properties": {
                    "note_type": {
                        "type": "string",
                        "description": "备忘录类型过滤（可选）",
                        "enum": VALID_NOTE_TYPES,
                    },
                    "active_only": {
                        "type": "boolean",
                        "description": "是否只返回有效的备忘录（默认 true）",
                    },
                },
                "required": [],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        note_type = params.get("note_type")
        if note_type:
            return f"查询备忘录：{NOTE_TYPE_DISPLAY.get(note_type, note_type)}"
        return "查询所有备忘录"

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        from ....repositories.author_notes_repository import AuthorNoteRepository

        repo = AuthorNoteRepository(self.session)
        note_type = params.get("note_type")
        active_only = params.get("active_only", True)

        notes = await repo.list_by_project(
            project_id,
            note_type=note_type,
            active_only=active_only,
        )

        notes_data = []
        for note in notes:
            notes_data.append({
                "id": note.id,
                "type": note.type,
                "title": note.title,
                "content": note.content[:200] + "..." if len(note.content) > 200 else note.content,
                "chapter_number": note.chapter_number,
                "volume_id": note.volume_id,
                "is_active": note.is_active,
            })

        if note_type:
            msg = f"找到 {len(notes)} 条{NOTE_TYPE_DISPLAY.get(note_type, note_type)}"
        else:
            msg = f"找到 {len(notes)} 条备忘录"

        return ToolResult(
            success=True,
            message=msg,
            data={"notes": notes_data, "count": len(notes)},
        )

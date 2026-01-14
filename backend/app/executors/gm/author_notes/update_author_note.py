"""更新作者备忘录工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy import select

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.author_notes import AuthorNote
from ....services.gm.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


@ToolRegistry.register
class UpdateAuthorNoteExecutor(BaseToolExecutor):
    """更新作者备忘录。"""

    @classmethod
    def get_name(cls) -> str:
        return "update_author_note"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="update_author_note",
            description="更新已有的作者备忘录。可以修改标题、内容、状态、关联的卷等。设置 is_active=false 可以归档备忘录。",
            parameters={
                "type": "object",
                "properties": {
                    "note_id": {
                        "type": "integer",
                        "description": "要更新的备忘录 ID",
                    },
                    "title": {
                        "type": "string",
                        "description": "新的标题（可选）",
                    },
                    "content": {
                        "type": "string",
                        "description": "新的内容（可选）",
                    },
                    "volume_id": {
                        "type": "integer",
                        "description": "关联的卷 ID（可选，设为 null 可取消关联）",
                    },
                    "chapter_number": {
                        "type": "integer",
                        "description": "关联的章节号（可选，设为 null 可取消关联）",
                    },
                    "is_active": {
                        "type": "boolean",
                        "description": "是否有效（设为 false 可归档备忘录）",
                    },
                    "priority": {
                        "type": "integer",
                        "description": "新的优先级",
                    },
                },
                "required": ["note_id"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        note_id = params.get("note_id")
        if params.get("is_active") is False:
            return f"归档备忘录 #{note_id}"
        return f"更新备忘录 #{note_id}"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        note_id = params.get("note_id")
        if not note_id:
            return "备忘录 ID 不能为空"
        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        note_id = params["note_id"]

        stmt = select(AuthorNote).where(
            AuthorNote.id == note_id,
            AuthorNote.project_id == project_id,
        )
        result = await self.session.execute(stmt)
        note = result.scalars().first()

        if not note:
            return ToolResult(
                success=False,
                message=f"备忘录 #{note_id} 不存在",
            )

        before_state = {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "volume_id": note.volume_id,
            "chapter_number": note.chapter_number,
            "is_active": note.is_active,
            "priority": note.priority,
        }

        # 更新字段
        if "title" in params:
            note.title = params["title"].strip()
        if "content" in params:
            note.content = params["content"].strip()
        if "volume_id" in params:
            note.volume_id = params["volume_id"]
        if "chapter_number" in params:
            note.chapter_number = params["chapter_number"]
        if "is_active" in params:
            note.is_active = params["is_active"]
        if "priority" in params:
            note.priority = params["priority"]

        await self.session.flush()

        action = "归档" if params.get("is_active") is False else "更新"
        logger.info(
            "%s备忘录成功: project=%s, id=%d, title=%s",
            action, project_id, note.id, note.title
        )

        return ToolResult(
            success=True,
            message=f"成功{action}备忘录「{note.title}」",
            data={"note_id": note.id, "title": note.title},
            before_state=before_state,
            after_state={
                "id": note.id,
                "title": note.title,
                "content": note.content,
                "volume_id": note.volume_id,
                "chapter_number": note.chapter_number,
                "is_active": note.is_active,
                "priority": note.priority,
            },
        )

"""删除大纲工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import select

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import ChapterOutline, Chapter
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class DeleteOutlineExecutor(BaseToolExecutor):
    """删除章节大纲。"""

    @classmethod
    def get_name(cls) -> str:
        return "delete_outline"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="delete_outline",
            description="删除指定章节的大纲。注意：如果该章节已有正文内容，将拒绝删除。",
            parameters={
                "type": "object",
                "properties": {
                    "chapter_number": {
                        "type": "integer",
                        "description": "要删除的章节号",
                    },
                },
                "required": ["chapter_number"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        chapter_number = params.get("chapter_number", "?")
        return f"删除大纲：第{chapter_number}章"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        chapter_number = params.get("chapter_number")
        if chapter_number is None:
            return "必须指定章节号"
        if chapter_number < 1:
            return "章节号必须大于0"
        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        chapter_number = params["chapter_number"]

        # 查找大纲
        stmt = select(ChapterOutline).where(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == chapter_number,
        )
        result = await self.session.execute(stmt)
        outline = result.scalars().first()

        if not outline:
            return ToolResult(
                success=False,
                message=f"第{chapter_number}章大纲不存在",
            )

        # 检查是否有已生成的章节正文
        chapter_stmt = select(Chapter).where(
            Chapter.project_id == project_id,
            Chapter.chapter_number == chapter_number,
            Chapter.status != "not_generated",
        )
        chapter_result = await self.session.execute(chapter_stmt)
        if chapter_result.scalars().first():
            return ToolResult(
                success=False,
                message=f"第{chapter_number}章已有正文内容，无法删除大纲。如需修改，请使用 update_outline",
            )

        before_state = {
            "id": outline.id,
            "chapter_number": outline.chapter_number,
            "title": outline.title,
            "summary": outline.summary,
        }

        title = outline.title
        await self.session.delete(outline)
        await self.session.flush()

        logger.info(
            "删除大纲成功: project=%s, chapter=%d, title=%s",
            project_id,
            chapter_number,
            title,
        )

        return ToolResult(
            success=True,
            message=f"成功删除第{chapter_number}章大纲：{title}",
            data={"deleted_chapter": chapter_number, "deleted_title": title},
            before_state=before_state,
            after_state=None,
        )

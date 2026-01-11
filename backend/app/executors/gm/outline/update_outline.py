"""更新大纲工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import select

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import ChapterOutline
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class UpdateOutlineExecutor(BaseToolExecutor):
    """更新章节大纲。"""

    @classmethod
    def get_name(cls) -> str:
        return "update_outline"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="update_outline",
            description="更新指定章节的大纲内容。可以修改标题和/或摘要。",
            parameters={
                "type": "object",
                "properties": {
                    "chapter_number": {
                        "type": "integer",
                        "description": "要修改的章节号",
                    },
                    "title": {
                        "type": "string",
                        "description": "新的章节标题（可选）",
                    },
                    "summary": {
                        "type": "string",
                        "description": "新的章节摘要（可选）",
                    },
                },
                "required": ["chapter_number"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        chapter_number = params.get("chapter_number", "?")
        title = params.get("title")
        if title:
            return f"修改大纲：第{chapter_number}章 - {title}"
        return f"修改大纲：第{chapter_number}章"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        chapter_number = params.get("chapter_number")
        if chapter_number is None:
            return "必须指定章节号"
        if chapter_number < 1:
            return "章节号必须大于0"

        title = params.get("title")
        summary = params.get("summary")
        if not title and not summary:
            return "必须至少提供新的标题或摘要"

        if title and len(title) > 255:
            return "章节标题过长，最多255个字符"
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

        before_state = {
            "id": outline.id,
            "chapter_number": outline.chapter_number,
            "title": outline.title,
            "summary": outline.summary,
        }

        # 更新字段
        if "title" in params and params["title"]:
            outline.title = params["title"].strip()
        if "summary" in params and params["summary"]:
            outline.summary = params["summary"].strip()

        await self.session.flush()

        after_state = {
            "id": outline.id,
            "chapter_number": outline.chapter_number,
            "title": outline.title,
            "summary": outline.summary,
        }

        logger.info(
            "更新大纲成功: project=%s, chapter=%d",
            project_id,
            chapter_number,
        )

        return ToolResult(
            success=True,
            message=f"成功更新第{chapter_number}章大纲",
            data={"outline_id": outline.id, "chapter_number": chapter_number},
            before_state=before_state,
            after_state=after_state,
        )

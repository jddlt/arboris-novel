"""添加大纲工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import select, func

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import ChapterOutline
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class AddOutlineExecutor(BaseToolExecutor):
    """添加章节大纲。"""

    @classmethod
    def get_name(cls) -> str:
        return "add_outline"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="add_outline",
            description="添加一个新的章节大纲。可以指定章节号，也可以自动追加到末尾。",
            parameters={
                "type": "object",
                "properties": {
                    "chapter_number": {
                        "type": "integer",
                        "description": "章节号。如不指定，则追加到现有大纲之后。",
                    },
                    "title": {
                        "type": "string",
                        "description": "章节标题",
                    },
                    "summary": {
                        "type": "string",
                        "description": "章节内容摘要，描述本章的主要情节",
                    },
                },
                "required": ["title", "summary"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        chapter_number = params.get("chapter_number")
        title = params.get("title", "未命名")
        if chapter_number:
            return f"添加大纲：第{chapter_number}章 - {title}"
        return f"添加大纲：{title}（追加到末尾）"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        title = params.get("title")
        summary = params.get("summary")

        if not title or not title.strip():
            return "必须提供章节标题"
        if not summary or not summary.strip():
            return "必须提供章节摘要"
        if len(title) > 255:
            return "章节标题过长，最多255个字符"

        chapter_number = params.get("chapter_number")
        if chapter_number is not None:
            try:
                chapter_number = int(chapter_number)
                if chapter_number < 1:
                    return "章节号必须大于0"
            except (ValueError, TypeError):
                return "章节号必须是有效的整数"
        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        title = params["title"].strip()
        summary = params["summary"].strip()
        chapter_number = int(params["chapter_number"]) if params.get("chapter_number") is not None else None

        # 如果没有指定章节号，获取当前最大章节号
        if chapter_number is None:
            max_num_stmt = select(func.max(ChapterOutline.chapter_number)).where(
                ChapterOutline.project_id == project_id
            )
            max_num_result = await self.session.execute(max_num_stmt)
            max_num = max_num_result.scalar() or 0
            chapter_number = max_num + 1
        else:
            # 检查章节号是否已存在
            existing_stmt = select(ChapterOutline).where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == chapter_number,
            )
            existing_result = await self.session.execute(existing_stmt)
            if existing_result.scalars().first():
                return ToolResult(
                    success=False,
                    message=f"第{chapter_number}章大纲已存在，请使用 update_outline 修改",
                )

        # 创建大纲
        outline = ChapterOutline(
            project_id=project_id,
            chapter_number=chapter_number,
            title=title,
            summary=summary,
        )

        self.session.add(outline)
        await self.session.flush()

        logger.info(
            "添加大纲成功: project=%s, chapter=%d, title=%s",
            project_id,
            chapter_number,
            title,
        )

        return ToolResult(
            success=True,
            message=f"成功添加第{chapter_number}章大纲：{title}",
            data={
                "outline_id": outline.id,
                "chapter_number": chapter_number,
                "title": title,
            },
            before_state=None,
            after_state={
                "id": outline.id,
                "chapter_number": chapter_number,
                "title": title,
                "summary": summary,
            },
        )

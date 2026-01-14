"""查询章节大纲工具执行器。"""

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
class GetOutlinesExecutor(BaseToolExecutor):
    """查询章节大纲列表（只读工具，自动执行）。"""

    is_read_only = True

    @classmethod
    def get_name(cls) -> str:
        return "get_outlines"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="get_outlines",
            description="查询小说的章节大纲。可以获取所有大纲或按章节范围筛选。用于获取章节规划的最新信息。",
            parameters={
                "type": "object",
                "properties": {
                    "start_chapter": {
                        "type": "integer",
                        "description": "起始章节号（含），如只查单章则与 end_chapter 相同",
                    },
                    "end_chapter": {
                        "type": "integer",
                        "description": "结束章节号（含）",
                    },
                    "volume_number": {
                        "type": "integer",
                        "description": "按卷筛选，只返回该卷的章节",
                    },
                },
                "required": [],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        start = params.get("start_chapter")
        end = params.get("end_chapter")
        volume = params.get("volume_number")

        if start and end:
            if start == end:
                return f"查询第{start}章大纲"
            return f"查询第{start}-{end}章大纲"
        elif volume:
            return f"查询第{volume}卷的章节大纲"
        return "查询所有章节大纲"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        start = params.get("start_chapter")
        end = params.get("end_chapter")

        if start is not None and end is not None:
            try:
                if int(start) > int(end):
                    return "起始章节号不能大于结束章节号"
            except (ValueError, TypeError):
                return "章节号必须是整数"
        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        start_chapter = params.get("start_chapter")
        end_chapter = params.get("end_chapter")
        volume_number = params.get("volume_number")

        stmt = select(ChapterOutline).where(
            ChapterOutline.project_id == project_id
        ).order_by(ChapterOutline.chapter_number)

        # 章节范围筛选
        if start_chapter is not None:
            stmt = stmt.where(ChapterOutline.chapter_number >= int(start_chapter))
        if end_chapter is not None:
            stmt = stmt.where(ChapterOutline.chapter_number <= int(end_chapter))
        if volume_number is not None:
            stmt = stmt.where(ChapterOutline.volume_number == int(volume_number))

        result = await self.session.execute(stmt)
        outlines = result.scalars().all()

        # 获取章节完成状态
        chapter_stmt = select(Chapter).where(
            Chapter.project_id == project_id
        )
        chapter_result = await self.session.execute(chapter_stmt)
        chapters = {ch.chapter_number: ch for ch in chapter_result.scalars().all()}

        if not outlines:
            return ToolResult(
                success=True,
                message="未找到匹配的章节大纲",
                data={"outlines": [], "total": 0},
            )

        # 构建返回数据
        outlines_data = []
        for outline in outlines:
            chapter = chapters.get(outline.chapter_number)
            status = "未开始"
            if chapter:
                if chapter.status == "successful" and chapter.selected_version:
                    status = "已完成"
                elif chapter.versions and len(chapter.versions) > 0:
                    status = "待选择版本"
                else:
                    status = "进行中"

            outlines_data.append({
                "chapter_number": outline.chapter_number,
                "title": outline.title or f"第{outline.chapter_number}章",
                "summary": outline.summary or "",
                "volume_number": outline.volume.volume_number if outline.volume else None,
                "status": status,
            })

        logger.info(
            "查询大纲成功: project=%s, count=%d",
            project_id,
            len(outlines_data),
        )

        return ToolResult(
            success=True,
            message=f"找到 {len(outlines_data)} 章大纲",
            data={"outlines": outlines_data, "total": len(outlines_data)},
        )

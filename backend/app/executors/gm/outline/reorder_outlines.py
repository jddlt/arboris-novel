"""调整大纲顺序工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from sqlalchemy import select, update

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import ChapterOutline, Chapter
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class ReorderOutlinesExecutor(BaseToolExecutor):
    """调整章节大纲顺序。"""

    @classmethod
    def get_name(cls) -> str:
        return "reorder_outlines"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="reorder_outlines",
            description="调整章节大纲的顺序。将指定章节移动到新位置，其他章节自动重排。注意：已有正文的章节无法移动。",
            parameters={
                "type": "object",
                "properties": {
                    "from_chapter": {
                        "type": "integer",
                        "description": "要移动的章节号",
                    },
                    "to_chapter": {
                        "type": "integer",
                        "description": "目标位置的章节号",
                    },
                },
                "required": ["from_chapter", "to_chapter"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        from_ch = params.get("from_chapter", "?")
        to_ch = params.get("to_chapter", "?")
        return f"移动大纲：第{from_ch}章 → 第{to_ch}章"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        from_chapter = params.get("from_chapter")
        to_chapter = params.get("to_chapter")

        if from_chapter is None:
            return "必须指定要移动的章节号"
        if to_chapter is None:
            return "必须指定目标位置"

        try:
            from_chapter = int(from_chapter)
            to_chapter = int(to_chapter)
        except (ValueError, TypeError):
            return "章节号必须是有效的整数"

        if from_chapter < 1 or to_chapter < 1:
            return "章节号必须大于0"
        if from_chapter == to_chapter:
            return "起始位置和目标位置相同，无需移动"
        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        from_chapter = int(params["from_chapter"])
        to_chapter = int(params["to_chapter"])

        # 检查源章节是否存在
        from_stmt = select(ChapterOutline).where(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == from_chapter,
        )
        from_result = await self.session.execute(from_stmt)
        source_outline = from_result.scalars().first()

        if not source_outline:
            return ToolResult(
                success=False,
                message=f"第{from_chapter}章大纲不存在",
            )

        # 检查源章节是否有正文
        chapter_stmt = select(Chapter).where(
            Chapter.project_id == project_id,
            Chapter.chapter_number == from_chapter,
            Chapter.status != "not_generated",
        )
        chapter_result = await self.session.execute(chapter_stmt)
        if chapter_result.scalars().first():
            return ToolResult(
                success=False,
                message=f"第{from_chapter}章已有正文内容，无法移动",
            )

        # 获取所有大纲并排序
        all_stmt = select(ChapterOutline).where(
            ChapterOutline.project_id == project_id
        ).order_by(ChapterOutline.chapter_number)
        all_result = await self.session.execute(all_stmt)
        all_outlines = list(all_result.scalars().all())

        # 记录变更前状态
        before_state = {
            "outlines": [
                {"chapter_number": o.chapter_number, "title": o.title}
                for o in all_outlines
            ]
        }

        # 找到目标位置的最大章节号
        max_chapter = max(o.chapter_number for o in all_outlines) if all_outlines else 0
        if to_chapter > max_chapter + 1:
            to_chapter = max_chapter + 1 if from_chapter <= max_chapter else max_chapter

        # 执行移动逻辑
        if from_chapter < to_chapter:
            # 向后移动：from+1 到 to 的章节都要减1
            for outline in all_outlines:
                if from_chapter < outline.chapter_number <= to_chapter:
                    outline.chapter_number -= 1
            source_outline.chapter_number = to_chapter
        else:
            # 向前移动：to 到 from-1 的章节都要加1
            for outline in all_outlines:
                if to_chapter <= outline.chapter_number < from_chapter:
                    outline.chapter_number += 1
            source_outline.chapter_number = to_chapter

        await self.session.flush()

        # 获取变更后状态
        after_stmt = select(ChapterOutline).where(
            ChapterOutline.project_id == project_id
        ).order_by(ChapterOutline.chapter_number)
        after_result = await self.session.execute(after_stmt)
        after_outlines = list(after_result.scalars().all())

        after_state = {
            "outlines": [
                {"chapter_number": o.chapter_number, "title": o.title}
                for o in after_outlines
            ]
        }

        logger.info(
            "调整大纲顺序成功: project=%s, from=%d, to=%d",
            project_id,
            from_chapter,
            to_chapter,
        )

        return ToolResult(
            success=True,
            message=f"成功将第{from_chapter}章移动到第{to_chapter}章位置",
            data={"from": from_chapter, "to": to_chapter},
            before_state=before_state,
            after_state=after_state,
        )

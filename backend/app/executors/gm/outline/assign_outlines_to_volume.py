"""批量分配章节到卷工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from sqlalchemy import select

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import ChapterOutline, Volume
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class AssignOutlinesToVolumeExecutor(BaseToolExecutor):
    """批量分配章节到指定卷。"""

    @classmethod
    def get_name(cls) -> str:
        return "assign_outlines_to_volume"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="assign_outlines_to_volume",
            description="批量将多个章节大纲分配到指定卷。用于快速组织章节结构。",
            parameters={
                "type": "object",
                "properties": {
                    "chapter_numbers": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "要分配的章节号列表，如 [1, 2, 3, 4, 5]",
                    },
                    "chapter_range": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "integer", "description": "起始章节号"},
                            "end": {"type": "integer", "description": "结束章节号"},
                        },
                        "description": "章节范围，如 {start: 1, end: 10} 表示第1-10章。与 chapter_numbers 二选一",
                    },
                    "volume_number": {
                        "type": "integer",
                        "description": "目标卷号（传0表示取消卷分配）",
                    },
                },
                "required": ["volume_number"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        volume_number = params.get("volume_number", "?")
        chapter_numbers = params.get("chapter_numbers", [])
        chapter_range = params.get("chapter_range", {})

        if chapter_range:
            start = chapter_range.get("start", "?")
            end = chapter_range.get("end", "?")
            chapters_desc = f"第{start}-{end}章"
        elif chapter_numbers:
            if len(chapter_numbers) <= 5:
                chapters_desc = f"第{', '.join(map(str, chapter_numbers))}章"
            else:
                chapters_desc = f"{len(chapter_numbers)}个章节"
        else:
            chapters_desc = "未指定章节"

        if volume_number == 0:
            return f"取消卷分配：{chapters_desc}"
        return f"分配到第{volume_number}卷：{chapters_desc}"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        volume_number = params.get("volume_number")
        if volume_number is None:
            return "必须指定目标卷号"
        try:
            volume_number = int(volume_number)
            if volume_number < 0:
                return "卷号不能为负数"
        except (ValueError, TypeError):
            return "卷号必须是有效的整数"

        chapter_numbers = params.get("chapter_numbers", [])
        chapter_range = params.get("chapter_range", {})

        if not chapter_numbers and not chapter_range:
            return "必须指定 chapter_numbers 或 chapter_range"

        if chapter_numbers:
            if not isinstance(chapter_numbers, list):
                return "chapter_numbers 必须是数组"
            for num in chapter_numbers:
                try:
                    if int(num) < 1:
                        return "章节号必须大于0"
                except (ValueError, TypeError):
                    return "章节号必须是有效的整数"

        if chapter_range:
            start = chapter_range.get("start")
            end = chapter_range.get("end")
            if start is None or end is None:
                return "chapter_range 必须包含 start 和 end"
            try:
                start = int(start)
                end = int(end)
                if start < 1 or end < 1:
                    return "章节号必须大于0"
                if end < start:
                    return "结束章节号必须大于或等于起始章节号"
            except (ValueError, TypeError):
                return "章节号必须是有效的整数"

        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        volume_number = int(params["volume_number"])
        chapter_numbers = params.get("chapter_numbers", [])
        chapter_range = params.get("chapter_range", {})

        # 构建要更新的章节号列表
        target_chapters: List[int] = []
        if chapter_range:
            start = int(chapter_range["start"])
            end = int(chapter_range["end"])
            target_chapters = list(range(start, end + 1))
        elif chapter_numbers:
            target_chapters = [int(n) for n in chapter_numbers]

        if not target_chapters:
            return ToolResult(
                success=False,
                message="没有指定要分配的章节",
            )

        # 获取目标卷的 ID
        volume_id = None
        if volume_number != 0:
            vol_result = await self.session.execute(
                select(Volume).where(
                    Volume.project_id == project_id,
                    Volume.volume_number == volume_number,
                )
            )
            volume = vol_result.scalars().first()
            if not volume:
                return ToolResult(
                    success=False,
                    message=f"第{volume_number}卷不存在，请先创建卷",
                )
            volume_id = volume.id

        # 查找所有目标章节
        outlines_result = await self.session.execute(
            select(ChapterOutline).where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number.in_(target_chapters),
            )
        )
        outlines = outlines_result.scalars().all()

        if not outlines:
            return ToolResult(
                success=False,
                message="未找到任何匹配的章节大纲",
            )

        # 记录修改前状态
        before_state = [
            {
                "chapter_number": o.chapter_number,
                "title": o.title,
                "volume_id": o.volume_id,
            }
            for o in outlines
        ]

        # 批量更新
        updated_chapters = []
        for outline in outlines:
            outline.volume_id = volume_id
            updated_chapters.append(outline.chapter_number)

        await self.session.flush()

        # 记录修改后状态
        after_state = [
            {
                "chapter_number": o.chapter_number,
                "title": o.title,
                "volume_id": o.volume_id,
            }
            for o in outlines
        ]

        if volume_number == 0:
            message = f"成功取消 {len(updated_chapters)} 个章节的卷分配"
        else:
            message = f"成功将 {len(updated_chapters)} 个章节分配到第{volume_number}卷"

        logger.info(
            "批量分配章节到卷: project=%s, volume=%d, chapters=%s",
            project_id,
            volume_number,
            updated_chapters,
        )

        return ToolResult(
            success=True,
            message=message,
            data={
                "volume_number": volume_number,
                "updated_chapters": updated_chapters,
                "count": len(updated_chapters),
            },
            before_state=before_state,
            after_state=after_state,
        )

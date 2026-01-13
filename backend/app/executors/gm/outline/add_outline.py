"""添加大纲工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import select, func

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import ChapterOutline, Volume
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
            description="添加一个新的章节大纲。可以指定章节号，也可以自动追加到末尾。可选分配到指定卷。",
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
                    "volume_number": {
                        "type": "integer",
                        "description": "分配到指定卷（可选）",
                    },
                },
                "required": ["title", "summary"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        chapter_number = params.get("chapter_number")
        title = params.get("title", "未命名")
        volume_number = params.get("volume_number")
        parts = []
        if chapter_number:
            parts.append(f"添加大纲：第{chapter_number}章 - {title}")
        else:
            parts.append(f"添加大纲：{title}（追加到末尾）")
        if volume_number:
            parts.append(f"分配到第{volume_number}卷")
        return " - ".join(parts) if len(parts) > 1 else parts[0]

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        # 参数别名标准化
        if "chapter_index" in params and "chapter_number" not in params:
            params["chapter_number"] = params.pop("chapter_index")
        if "章节号" in params and "chapter_number" not in params:
            params["chapter_number"] = params.pop("章节号")
        if "标题" in params and "title" not in params:
            params["title"] = params.pop("标题")
        if "摘要" in params and "summary" not in params:
            params["summary"] = params.pop("摘要")
        if "内容" in params and "summary" not in params:
            params["summary"] = params.pop("内容")
        if "卷号" in params and "volume_number" not in params:
            params["volume_number"] = params.pop("卷号")

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

        volume_number = params.get("volume_number")
        if volume_number is not None:
            try:
                volume_number = int(volume_number)
                if volume_number < 1:
                    return "卷号必须大于0"
            except (ValueError, TypeError):
                return "卷号必须是有效的整数"

        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        title = params["title"].strip()
        summary = params["summary"].strip()
        chapter_number = int(params["chapter_number"]) if params.get("chapter_number") is not None else None
        volume_number = int(params["volume_number"]) if params.get("volume_number") is not None else None

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

        # 处理卷分配
        volume_id = None
        if volume_number is not None:
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

        # 创建大纲
        outline = ChapterOutline(
            project_id=project_id,
            chapter_number=chapter_number,
            title=title,
            summary=summary,
            volume_id=volume_id,
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
                "volume_id": volume_id,
            },
        )

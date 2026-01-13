"""查询卷结构工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import select

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import Volume
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class GetVolumesExecutor(BaseToolExecutor):
    """查询卷结构列表（只读工具，自动执行）。"""

    is_read_only = True

    @classmethod
    def get_name(cls) -> str:
        return "get_volumes"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="get_volumes",
            description="查询小说的卷结构。可以获取所有卷的信息，包括标题、概要、核心冲突、高潮点和包含的章节数。",
            parameters={
                "type": "object",
                "properties": {
                    "volume_number": {
                        "type": "integer",
                        "description": "查询特定卷的详细信息，留空则返回所有卷",
                    },
                },
                "required": [],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        volume_number = params.get("volume_number")
        if volume_number:
            return f"查询第{volume_number}卷信息"
        return "查询所有卷结构"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        volume_number = params.get("volume_number")

        stmt = select(Volume).where(
            Volume.project_id == project_id
        ).order_by(Volume.volume_number)

        if volume_number is not None:
            stmt = stmt.where(Volume.volume_number == int(volume_number))

        result = await self.session.execute(stmt)
        volumes = result.scalars().all()

        if not volumes:
            if volume_number:
                return ToolResult(
                    success=True,
                    message=f"未找到第{volume_number}卷",
                    data={"volumes": [], "total": 0},
                )
            return ToolResult(
                success=True,
                message="当前小说暂无卷结构",
                data={"volumes": [], "total": 0},
            )

        # 构建返回数据
        volumes_data = []
        for vol in volumes:
            chapter_count = len(vol.outlines) if vol.outlines else 0
            status_map = {
                "completed": "已完成",
                "in_progress": "进行中",
                "planned": "计划中",
            }

            vol_info = {
                "volume_number": vol.volume_number,
                "title": vol.title or f"第{vol.volume_number}卷",
                "summary": vol.summary or "",
                "core_conflict": vol.core_conflict or "",
                "climax": vol.climax or "",
                "status": status_map.get(vol.status, vol.status or "计划中"),
                "chapter_count": chapter_count,
            }

            # 如果查询单卷，返回章节列表
            if volume_number and vol.outlines:
                vol_info["chapters"] = [
                    {"chapter_number": o.chapter_number, "title": o.title}
                    for o in sorted(vol.outlines, key=lambda x: x.chapter_number)
                ]

            volumes_data.append(vol_info)

        logger.info(
            "查询卷结构成功: project=%s, count=%d",
            project_id,
            len(volumes_data),
        )

        return ToolResult(
            success=True,
            message=f"找到 {len(volumes_data)} 卷",
            data={"volumes": volumes_data, "total": len(volumes_data)},
        )

"""删除卷工具执行器。"""

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
class DeleteVolumeExecutor(BaseToolExecutor):
    """删除卷。"""

    @classmethod
    def get_name(cls) -> str:
        return "delete_volume"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="delete_volume",
            description="从小说中删除一个卷。注意：这不会删除卷内的章节，只是移除卷的划分。",
            parameters={
                "type": "object",
                "properties": {
                    "volume_number": {
                        "type": "integer",
                        "description": "要删除的卷序号",
                    },
                },
                "required": ["volume_number"],
            },
        )

    def _normalize_params(self, params: Dict[str, Any]) -> None:
        """参数别名标准化 - 模型可能使用不同的参数名。"""
        if "order" in params and "volume_number" not in params:
            params["volume_number"] = params.pop("order")
        if "卷号" in params and "volume_number" not in params:
            params["volume_number"] = params.pop("卷号")
        if "序号" in params and "volume_number" not in params:
            params["volume_number"] = params.pop("序号")

    def generate_preview(self, params: Dict[str, Any]) -> str:
        self._normalize_params(params)
        volume_number = params.get("volume_number")
        try:
            volume_number = int(volume_number) if volume_number is not None else "?"
        except (ValueError, TypeError):
            volume_number = "?"
        return f"删除卷：第{volume_number}卷"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        self._normalize_params(params)
        volume_number = params.get("volume_number")
        try:
            volume_number = int(volume_number)
            if volume_number < 1:
                return "卷序号必须大于0"
        except (ValueError, TypeError):
            return "卷序号必须是有效的整数"
        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        volume_number = int(params["volume_number"])

        # 查找目标卷
        result = await self.session.execute(
            select(Volume).where(
                Volume.project_id == project_id,
                Volume.volume_number == volume_number,
            )
        )
        volume = result.scalars().first()

        if not volume:
            return ToolResult(
                success=False,
                message=f"第{volume_number}卷不存在",
            )

        before_state = {
            "id": volume.id,
            "volume_number": volume.volume_number,
            "title": volume.title,
            "summary": volume.summary,
            "core_conflict": volume.core_conflict,
            "climax": volume.climax,
            "status": volume.status,
        }

        title = volume.title
        await self.session.delete(volume)
        await self.session.flush()

        logger.info(
            "删除卷成功: project=%s, volume_number=%d, title=%s",
            project_id,
            volume_number,
            title,
        )

        return ToolResult(
            success=True,
            message=f"成功删除第{volume_number}卷：{title}",
            data={
                "volume_number": volume_number,
                "title": title,
            },
            before_state=before_state,
            after_state=None,
        )

"""更新卷工具执行器。"""

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
class UpdateVolumeExecutor(BaseToolExecutor):
    """更新卷信息。"""

    @classmethod
    def get_name(cls) -> str:
        return "update_volume"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="update_volume",
            description="更新小说中已存在的卷信息。",
            parameters={
                "type": "object",
                "properties": {
                    "volume_number": {
                        "type": "integer",
                        "description": "要修改的卷序号",
                    },
                    "title": {
                        "type": "string",
                        "description": "新的卷标题",
                    },
                    "summary": {
                        "type": "string",
                        "description": "卷概要",
                    },
                    "core_conflict": {
                        "type": "string",
                        "description": "本卷的核心冲突",
                    },
                    "climax": {
                        "type": "string",
                        "description": "本卷的高潮点",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["planned", "in_progress", "completed"],
                        "description": "卷状态",
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
        if "标题" in params and "title" not in params:
            params["title"] = params.pop("标题")
        if "概要" in params and "summary" not in params:
            params["summary"] = params.pop("概要")
        if "描述" in params and "summary" not in params:
            params["summary"] = params.pop("描述")

    def generate_preview(self, params: Dict[str, Any]) -> str:
        self._normalize_params(params)
        volume_number = params.get("volume_number")
        try:
            volume_number = int(volume_number) if volume_number is not None else "?"
        except (ValueError, TypeError):
            volume_number = "?"
        return f"更新卷：第{volume_number}卷"

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

        # 更新字段
        if "title" in params and params["title"]:
            volume.title = str(params["title"]).strip()
        if "summary" in params:
            volume.summary = params["summary"]
        if "core_conflict" in params:
            volume.core_conflict = params["core_conflict"]
        if "climax" in params:
            volume.climax = params["climax"]
        if "status" in params:
            volume.status = params["status"]

        await self.session.flush()

        logger.info(
            "更新卷成功: project=%s, volume_number=%d",
            project_id,
            volume_number,
        )

        after_state = {
            "id": volume.id,
            "volume_number": volume.volume_number,
            "title": volume.title,
            "summary": volume.summary,
            "core_conflict": volume.core_conflict,
            "climax": volume.climax,
            "status": volume.status,
        }

        return ToolResult(
            success=True,
            message=f"成功更新第{volume_number}卷",
            data={
                "volume_number": volume_number,
                "title": volume.title,
            },
            before_state=before_state,
            after_state=after_state,
        )

"""查询世界观设定工具执行器。"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import select

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import NovelBlueprint
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class GetWorldSettingExecutor(BaseToolExecutor):
    """查询世界观设定（只读工具，自动执行）。"""

    is_read_only = True

    @classmethod
    def get_name(cls) -> str:
        return "get_world_setting"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="get_world_setting",
            description="查询小说的世界观设定。获取完整的世界观、背景设定信息。",
            parameters={
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "description": "查询特定部分，如：地理、历史、魔法体系等（留空返回全部）",
                    },
                },
                "required": [],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        section = params.get("section")
        if section:
            return f"查询世界观：{section}"
        return "查询世界观设定"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        section_filter = params.get("section", "").strip()

        # 获取蓝图
        stmt = select(NovelBlueprint).where(
            NovelBlueprint.project_id == project_id
        )
        result = await self.session.execute(stmt)
        blueprint = result.scalars().first()

        if not blueprint:
            return ToolResult(
                success=True,
                message="当前小说暂无蓝图设定",
                data={"world_setting": None},
            )

        world_setting = blueprint.world_setting
        if not world_setting:
            return ToolResult(
                success=True,
                message="当前小说暂无世界观设定",
                data={"world_setting": None},
            )

        # 解析世界观数据
        if isinstance(world_setting, str):
            try:
                world_setting = json.loads(world_setting)
            except json.JSONDecodeError:
                # 纯文本格式
                return ToolResult(
                    success=True,
                    message="获取世界观设定成功",
                    data={"world_setting": world_setting, "format": "text"},
                )

        # 如果是 JSON 对象且有 section 筛选
        if isinstance(world_setting, dict) and section_filter:
            # 尝试按 key 筛选
            matched = {}
            for key, value in world_setting.items():
                if section_filter.lower() in key.lower():
                    matched[key] = value

            if matched:
                return ToolResult(
                    success=True,
                    message=f"找到 {len(matched)} 个相关设定",
                    data={"world_setting": matched, "format": "json"},
                )
            else:
                return ToolResult(
                    success=True,
                    message=f"未找到与「{section_filter}」相关的世界观设定",
                    data={"world_setting": None},
                )

        logger.info("查询世界观成功: project=%s", project_id)

        return ToolResult(
            success=True,
            message="获取世界观设定成功",
            data={
                "world_setting": world_setting,
                "format": "json" if isinstance(world_setting, dict) else "text",
            },
        )

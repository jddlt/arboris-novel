"""查询角色列表工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from sqlalchemy import select

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import BlueprintCharacter
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class GetCharactersExecutor(BaseToolExecutor):
    """查询角色列表（只读工具，自动执行）。"""

    is_read_only = True

    @classmethod
    def get_name(cls) -> str:
        return "get_characters"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="get_characters",
            description="查询小说中的角色列表。可以获取所有角色或按名称筛选特定角色。用于获取角色的最新信息。",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "按角色名称筛选（模糊匹配），留空则返回所有角色",
                    },
                    "identity": {
                        "type": "string",
                        "description": "按身份筛选，如：主角、配角、反派",
                    },
                },
                "required": [],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        name = params.get("name")
        identity = params.get("identity")
        if name:
            return f"查询角色：{name}"
        elif identity:
            return f"查询{identity}角色"
        return "查询所有角色"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        name_filter = params.get("name", "").strip()
        identity_filter = params.get("identity", "").strip()

        stmt = select(BlueprintCharacter).where(
            BlueprintCharacter.project_id == project_id
        ).order_by(BlueprintCharacter.position)

        result = await self.session.execute(stmt)
        characters = result.scalars().all()

        # 应用过滤
        filtered = []
        for char in characters:
            if name_filter and name_filter.lower() not in char.name.lower():
                continue
            if identity_filter and (not char.identity or identity_filter.lower() not in char.identity.lower()):
                continue
            filtered.append(char)

        if not filtered:
            if name_filter or identity_filter:
                return ToolResult(
                    success=True,
                    message="未找到匹配的角色",
                    data={"characters": [], "total": 0},
                )
            return ToolResult(
                success=True,
                message="当前小说暂无角色",
                data={"characters": [], "total": 0},
            )

        # 构建返回数据
        characters_data = []
        for char in filtered:
            char_info = {
                "name": char.name,
                "identity": char.identity or "",
                "personality": char.personality or "",
                "goals": char.goals or "",
                "abilities": char.abilities or "",
                "relationship_to_protagonist": char.relationship_to_protagonist or "",
            }
            if char.extra:
                char_info["extra"] = char.extra
            characters_data.append(char_info)

        logger.info(
            "查询角色成功: project=%s, count=%d",
            project_id,
            len(characters_data),
        )

        return ToolResult(
            success=True,
            message=f"找到 {len(characters_data)} 个角色",
            data={"characters": characters_data, "total": len(characters_data)},
        )

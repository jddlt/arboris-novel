"""查询关系列表工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import select, or_

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import BlueprintRelationship
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class GetRelationshipsExecutor(BaseToolExecutor):
    """查询角色关系列表（只读工具，自动执行）。"""

    is_read_only = True

    @classmethod
    def get_name(cls) -> str:
        return "get_relationships"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="get_relationships",
            description="查询小说中的角色关系列表。可以获取所有关系或按角色名称筛选。用于获取角色关系的最新信息。",
            parameters={
                "type": "object",
                "properties": {
                    "character": {
                        "type": "string",
                        "description": "按角色名称筛选（会匹配关系的双方），留空则返回所有关系",
                    },
                },
                "required": [],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        character = params.get("character")
        if character:
            return f"查询与「{character}」相关的关系"
        return "查询所有角色关系"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        character_filter = params.get("character", "").strip()

        stmt = select(BlueprintRelationship).where(
            BlueprintRelationship.project_id == project_id
        )

        # 按角色筛选
        if character_filter:
            stmt = stmt.where(
                or_(
                    BlueprintRelationship.character_from.ilike(f"%{character_filter}%"),
                    BlueprintRelationship.character_to.ilike(f"%{character_filter}%"),
                )
            )

        result = await self.session.execute(stmt)
        relationships = result.scalars().all()

        if not relationships:
            if character_filter:
                return ToolResult(
                    success=True,
                    message=f"未找到与「{character_filter}」相关的关系",
                    data={"relationships": [], "total": 0},
                )
            return ToolResult(
                success=True,
                message="当前小说暂无角色关系",
                data={"relationships": [], "total": 0},
            )

        # 构建返回数据
        relationships_data = [
            {
                "from": rel.character_from,
                "to": rel.character_to,
                "description": rel.description or "",
            }
            for rel in relationships
        ]

        logger.info(
            "查询关系成功: project=%s, count=%d",
            project_id,
            len(relationships_data),
        )

        return ToolResult(
            success=True,
            message=f"找到 {len(relationships_data)} 条关系",
            data={"relationships": relationships_data, "total": len(relationships_data)},
        )

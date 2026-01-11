"""添加关系工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import select, func

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import BlueprintCharacter, BlueprintRelationship
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class AddRelationshipExecutor(BaseToolExecutor):
    """添加角色关系。"""

    @classmethod
    def get_name(cls) -> str:
        return "add_relationship"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="add_relationship",
            description="添加两个角色之间的关系。关系是有方向的，从 character_from 指向 character_to。",
            parameters={
                "type": "object",
                "properties": {
                    "character_from": {
                        "type": "string",
                        "description": "关系起点角色的姓名",
                    },
                    "character_to": {
                        "type": "string",
                        "description": "关系终点角色的姓名",
                    },
                    "description": {
                        "type": "string",
                        "description": "关系描述，如：恋人、师徒、仇敌、同事等",
                    },
                },
                "required": ["character_from", "character_to", "description"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        from_char = params.get("character_from", "?")
        to_char = params.get("character_to", "?")
        desc = params.get("description", "未知关系")
        return f"添加关系：{from_char} → {to_char}（{desc}）"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        # 参数别名标准化
        if "from" in params and "character_from" not in params:
            params["character_from"] = params.pop("from")
        if "to" in params and "character_to" not in params:
            params["character_to"] = params.pop("to")
        if "from_character" in params and "character_from" not in params:
            params["character_from"] = params.pop("from_character")
        if "to_character" in params and "character_to" not in params:
            params["character_to"] = params.pop("to_character")
        if "关系描述" in params and "description" not in params:
            params["description"] = params.pop("关系描述")

        char_from = params.get("character_from")
        char_to = params.get("character_to")
        desc = params.get("description")

        if not char_from or not char_from.strip():
            return "必须指定关系起点角色"
        if not char_to or not char_to.strip():
            return "必须指定关系终点角色"
        if not desc or not desc.strip():
            return "必须提供关系描述"
        if char_from.strip() == char_to.strip():
            return "不能创建角色与自身的关系"
        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        char_from = params["character_from"].strip()
        char_to = params["character_to"].strip()
        description = params["description"].strip()

        # 验证两个角色都存在
        for char_name in [char_from, char_to]:
            stmt = select(BlueprintCharacter).where(
                BlueprintCharacter.project_id == project_id,
                BlueprintCharacter.name == char_name,
            )
            result = await self.session.execute(stmt)
            if not result.scalars().first():
                return ToolResult(
                    success=False,
                    message=f"角色「{char_name}」不存在，请先创建该角色",
                )

        # 检查关系是否已存在
        existing_stmt = select(BlueprintRelationship).where(
            BlueprintRelationship.project_id == project_id,
            BlueprintRelationship.character_from == char_from,
            BlueprintRelationship.character_to == char_to,
        )
        existing_result = await self.session.execute(existing_stmt)
        if existing_result.scalars().first():
            return ToolResult(
                success=False,
                message=f"「{char_from}」与「{char_to}」之间已存在关系，请使用 update_relationship 修改",
            )

        # 获取当前最大 position
        max_pos_stmt = select(func.max(BlueprintRelationship.position)).where(
            BlueprintRelationship.project_id == project_id
        )
        max_pos_result = await self.session.execute(max_pos_stmt)
        max_pos = max_pos_result.scalar() or 0

        # 创建关系
        relationship = BlueprintRelationship(
            project_id=project_id,
            character_from=char_from,
            character_to=char_to,
            description=description,
            position=max_pos + 1,
        )

        self.session.add(relationship)
        await self.session.flush()

        logger.info(
            "添加关系成功: project=%s, from=%s, to=%s, desc=%s",
            project_id,
            char_from,
            char_to,
            description,
        )

        return ToolResult(
            success=True,
            message=f"成功添加关系：{char_from} → {char_to}（{description}）",
            data={
                "relationship_id": relationship.id,
                "from": char_from,
                "to": char_to,
            },
            before_state=None,
            after_state={
                "id": relationship.id,
                "character_from": char_from,
                "character_to": char_to,
                "description": description,
            },
        )

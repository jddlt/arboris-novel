"""更新关系工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import select

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import BlueprintRelationship
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class UpdateRelationshipExecutor(BaseToolExecutor):
    """更新关系描述。"""

    @classmethod
    def get_name(cls) -> str:
        return "update_relationship"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="update_relationship",
            description="更新两个角色之间的关系描述。",
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
                        "description": "新的关系描述",
                    },
                },
                "required": ["character_from", "character_to", "description"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        from_char = params.get("character_from", "?")
        to_char = params.get("character_to", "?")
        desc = params.get("description", "")
        return f"修改关系：{from_char} → {to_char}（{desc}）"

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
        if "new_description" in params and "description" not in params:
            params["description"] = params.pop("new_description")

        char_from = params.get("character_from")
        char_to = params.get("character_to")
        desc = params.get("description")

        if not char_from or not char_from.strip():
            return "必须指定关系起点角色"
        if not char_to or not char_to.strip():
            return "必须指定关系终点角色"
        if not desc or not desc.strip():
            return "必须提供新的关系描述"
        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        char_from = params["character_from"].strip()
        char_to = params["character_to"].strip()
        new_description = params["description"].strip()

        # 查找关系
        stmt = select(BlueprintRelationship).where(
            BlueprintRelationship.project_id == project_id,
            BlueprintRelationship.character_from == char_from,
            BlueprintRelationship.character_to == char_to,
        )
        result = await self.session.execute(stmt)
        relationship = result.scalars().first()

        if not relationship:
            return ToolResult(
                success=False,
                message=f"「{char_from}」与「{char_to}」之间不存在关系",
            )

        before_state = {
            "id": relationship.id,
            "character_from": relationship.character_from,
            "character_to": relationship.character_to,
            "description": relationship.description,
        }

        old_description = relationship.description
        relationship.description = new_description

        await self.session.flush()

        after_state = {
            "id": relationship.id,
            "character_from": relationship.character_from,
            "character_to": relationship.character_to,
            "description": relationship.description,
        }

        logger.info(
            "更新关系成功: project=%s, from=%s, to=%s, old_desc=%s, new_desc=%s",
            project_id,
            char_from,
            char_to,
            old_description,
            new_description,
        )

        return ToolResult(
            success=True,
            message=f"成功更新关系：{char_from} → {char_to}",
            data={"relationship_id": relationship.id},
            before_state=before_state,
            after_state=after_state,
        )

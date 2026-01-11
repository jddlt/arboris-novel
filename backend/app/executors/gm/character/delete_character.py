"""删除角色工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import select, delete

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import BlueprintCharacter, BlueprintRelationship
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class DeleteCharacterExecutor(BaseToolExecutor):
    """删除角色。"""

    @classmethod
    def get_name(cls) -> str:
        return "delete_character"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="delete_character",
            description="删除一个角色。注意：这会同时删除该角色相关的所有关系。",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "要删除的角色姓名",
                    },
                },
                "required": ["name"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        name = params.get("name", "未知角色")
        return f"删除角色：{name}（将同时删除相关关系）"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        name = params.get("name")
        if not name or not name.strip():
            return "必须指定要删除的角色名称"
        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        name = params["name"].strip()

        # 查找角色
        stmt = select(BlueprintCharacter).where(
            BlueprintCharacter.project_id == project_id,
            BlueprintCharacter.name == name,
        )
        result = await self.session.execute(stmt)
        character = result.scalars().first()

        if not character:
            return ToolResult(
                success=False,
                message=f"角色「{name}」不存在",
            )

        # 保存删除前状态
        before_state = {
            "id": character.id,
            "name": character.name,
            "identity": character.identity,
            "personality": character.personality,
            "goals": character.goals,
            "abilities": character.abilities,
            "relationship_to_protagonist": character.relationship_to_protagonist,
        }

        # 查找并删除相关关系
        rel_stmt = select(BlueprintRelationship).where(
            BlueprintRelationship.project_id == project_id,
            (BlueprintRelationship.character_from == name) | (BlueprintRelationship.character_to == name),
        )
        rel_result = await self.session.execute(rel_stmt)
        related_rels = rel_result.scalars().all()

        deleted_relationships = []
        for rel in related_rels:
            deleted_relationships.append({
                "from": rel.character_from,
                "to": rel.character_to,
                "description": rel.description,
            })
            await self.session.delete(rel)

        # 删除角色
        await self.session.delete(character)
        await self.session.flush()

        rel_msg = ""
        if deleted_relationships:
            rel_msg = f"，同时删除了 {len(deleted_relationships)} 条相关关系"

        logger.info(
            "删除角色成功: project=%s, name=%s, deleted_relationships=%d",
            project_id,
            name,
            len(deleted_relationships),
        )

        return ToolResult(
            success=True,
            message=f"成功删除角色「{name}」{rel_msg}",
            data={
                "deleted_character": name,
                "deleted_relationships": deleted_relationships,
            },
            before_state=before_state,
            after_state=None,
        )

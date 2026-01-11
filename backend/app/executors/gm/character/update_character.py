"""更新角色工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import select

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import BlueprintCharacter
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class UpdateCharacterExecutor(BaseToolExecutor):
    """更新角色信息。"""

    @classmethod
    def get_name(cls) -> str:
        return "update_character"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="update_character",
            description="更新已存在角色的信息。可以修改角色的任意属性。",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "要修改的角色姓名（用于定位角色）",
                    },
                    "new_name": {
                        "type": "string",
                        "description": "新的角色姓名（如需改名）",
                    },
                    "identity": {
                        "type": "string",
                        "description": "新的角色身份定位",
                    },
                    "personality": {
                        "type": "string",
                        "description": "新的性格特点描述",
                    },
                    "goals": {
                        "type": "string",
                        "description": "新的目标或动机",
                    },
                    "abilities": {
                        "type": "string",
                        "description": "新的能力或特长",
                    },
                    "relationship_to_protagonist": {
                        "type": "string",
                        "description": "新的与主角关系描述",
                    },
                    "extra": {
                        "type": "object",
                        "description": "额外属性（JSON 对象，如背景故事、外貌描述等自定义字段）",
                    },
                },
                "required": ["name"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        name = params.get("name", "未知角色")
        new_name = params.get("new_name")
        if new_name and new_name != name:
            return f"修改角色：{name} → {new_name}"
        return f"修改角色：{name}"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        name = params.get("name")
        if not name or not name.strip():
            return "必须指定要修改的角色名称"
        new_name = params.get("new_name")
        if new_name and len(new_name) > 255:
            return "新角色名称过长，最多255个字符"
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

        # 保存修改前状态
        before_state = {
            "id": character.id,
            "name": character.name,
            "identity": character.identity,
            "personality": character.personality,
            "goals": character.goals,
            "abilities": character.abilities,
            "relationship_to_protagonist": character.relationship_to_protagonist,
            "extra": character.extra,
        }

        # 检查新名称是否冲突
        new_name = params.get("new_name")
        if new_name and new_name.strip() != name:
            new_name = new_name.strip()
            conflict_stmt = select(BlueprintCharacter).where(
                BlueprintCharacter.project_id == project_id,
                BlueprintCharacter.name == new_name,
            )
            conflict_result = await self.session.execute(conflict_stmt)
            if conflict_result.scalars().first():
                return ToolResult(
                    success=False,
                    message=f"角色名「{new_name}」已被使用",
                )
            character.name = new_name

        # 更新其他字段
        if "identity" in params:
            character.identity = params["identity"]
        if "personality" in params:
            character.personality = params["personality"]
        if "goals" in params:
            character.goals = params["goals"]
        if "abilities" in params:
            character.abilities = params["abilities"]
        if "relationship_to_protagonist" in params:
            character.relationship_to_protagonist = params["relationship_to_protagonist"]
        if "extra" in params:
            # 合并 extra 字段
            current_extra = character.extra or {}
            current_extra.update(params["extra"])
            character.extra = current_extra

        await self.session.flush()

        after_state = {
            "id": character.id,
            "name": character.name,
            "identity": character.identity,
            "personality": character.personality,
            "goals": character.goals,
            "abilities": character.abilities,
            "relationship_to_protagonist": character.relationship_to_protagonist,
            "extra": character.extra,
        }

        logger.info("更新角色成功: project=%s, name=%s", project_id, character.name)

        return ToolResult(
            success=True,
            message=f"成功更新角色「{character.name}」",
            data={"character_id": character.id, "name": character.name},
            before_state=before_state,
            after_state=after_state,
        )

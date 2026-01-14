"""添加角色工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import select, func

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import BlueprintCharacter
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class AddCharacterExecutor(BaseToolExecutor):
    """添加新角色。"""

    @classmethod
    def get_name(cls) -> str:
        return "add_character"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="add_character",
            description="添加一个新角色到小说中。用于创建主角、配角或反派等各类角色。",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "角色姓名，必须唯一",
                    },
                    "identity": {
                        "type": "string",
                        "description": "角色身份定位，如：主角、女主、反派、配角等",
                    },
                    "personality": {
                        "type": "string",
                        "description": "性格特点描述",
                    },
                    "goals": {
                        "type": "string",
                        "description": "角色的目标或动机",
                    },
                    "abilities": {
                        "type": "string",
                        "description": "角色的能力或特长",
                    },
                    "relationship_to_protagonist": {
                        "type": "string",
                        "description": "与主角的关系描述",
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
        name = params.get("name", "未命名")
        identity = params.get("identity", "")
        identity_str = f"（{identity}）" if identity else ""
        return f"添加角色：{name}{identity_str}"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        # 参数别名标准化
        if "角色名" in params and "name" not in params:
            params["name"] = params.pop("角色名")
        if "姓名" in params and "name" not in params:
            params["name"] = params.pop("姓名")
        if "role_type" in params and "identity" not in params:
            params["identity"] = params.pop("role_type")
        if "身份" in params and "identity" not in params:
            params["identity"] = params.pop("身份")

        name = params.get("name")
        if not name or not name.strip():
            return "角色名称不能为空"
        if len(name) > 255:
            return "角色名称过长，最多255个字符"
        return None

    def _to_string(self, value: Any) -> str:
        """将值转换为字符串，智能合并 dict/list 为纯文本。"""
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            # 把 dict 的值合并成文本（常见于 AI 返回结构化数据）
            parts = []
            for v in value.values():
                if isinstance(v, str) and v.strip():
                    parts.append(v.strip())
                elif v is not None:
                    parts.append(str(v))
            return ' '.join(parts) if parts else ''
        if isinstance(value, list):
            # 把 list 的元素合并成文本
            return '\n'.join(str(item) for item in value if item)
        return str(value)

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        name = params["name"].strip()

        # 检查角色是否已存在
        stmt = select(BlueprintCharacter).where(
            BlueprintCharacter.project_id == project_id,
            BlueprintCharacter.name == name,
        )
        result = await self.session.execute(stmt)
        existing = result.scalars().first()

        if existing:
            return ToolResult(
                success=False,
                message=f"角色「{name}」已存在，请使用 update_character 修改",
            )

        # 获取当前最大 position
        max_pos_stmt = select(func.max(BlueprintCharacter.position)).where(
            BlueprintCharacter.project_id == project_id
        )
        max_pos_result = await self.session.execute(max_pos_stmt)
        max_pos = max_pos_result.scalar() or 0

        # 创建新角色
        character = BlueprintCharacter(
            project_id=project_id,
            name=name,
            identity=self._to_string(params.get("identity")),
            personality=self._to_string(params.get("personality")),
            goals=self._to_string(params.get("goals")),
            abilities=self._to_string(params.get("abilities")),
            relationship_to_protagonist=self._to_string(params.get("relationship_to_protagonist")),
            extra=params.get("extra"),
            position=max_pos + 1,
        )

        self.session.add(character)
        await self.session.flush()

        logger.info("添加角色成功: project=%s, name=%s, id=%d", project_id, name, character.id)

        return ToolResult(
            success=True,
            message=f"成功添加角色「{name}」",
            data={
                "character_id": character.id,
                "name": name,
            },
            before_state=None,
            after_state={
                "id": character.id,
                "name": character.name,
                "identity": character.identity,
                "personality": character.personality,
                "goals": character.goals,
                "abilities": character.abilities,
                "relationship_to_protagonist": character.relationship_to_protagonist,
                "extra": character.extra,
            },
        )

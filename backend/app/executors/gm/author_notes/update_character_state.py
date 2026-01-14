"""更新角色状态工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy import select

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import BlueprintCharacter
from ....services.gm.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


@ToolRegistry.register
class UpdateCharacterStateExecutor(BaseToolExecutor):
    """更新角色状态（数值流小说）。"""

    @classmethod
    def get_name(cls) -> str:
        return "update_character_state"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="update_character_state",
            description="更新角色在特定章节的状态数据。适用于数值流小说（网游、修仙等），用于追踪等级、装备、技能、属性等变化。",
            parameters={
                "type": "object",
                "properties": {
                    "character_id": {
                        "type": "integer",
                        "description": "角色 ID",
                    },
                    "character_name": {
                        "type": "string",
                        "description": "角色名称（如果不知道 ID，可以用名称查找）",
                    },
                    "chapter_number": {
                        "type": "integer",
                        "description": "状态所属的章节号",
                    },
                    "data": {
                        "type": "object",
                        "description": "状态数据，如 {\"等级\": 10, \"装备\": [\"铁剑\"], \"技能\": [\"火球术\"]}",
                    },
                    "change_note": {
                        "type": "string",
                        "description": "变更说明，如「获得新装备」「升级」等",
                    },
                },
                "required": ["chapter_number", "data"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        char_name = params.get("character_name")
        char_id = params.get("character_id")
        chapter = params.get("chapter_number")
        name_str = char_name or (f"角色#{char_id}" if char_id else "未知角色")
        return f"更新{name_str}在第{chapter}章的状态"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        if not params.get("character_id") and not params.get("character_name"):
            return "必须提供 character_id 或 character_name"

        if not params.get("chapter_number"):
            return "章节号不能为空"

        if not params.get("data"):
            return "状态数据不能为空"

        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        from ....repositories.author_notes_repository import CharacterStateRepository

        character_id = params.get("character_id")
        character_name = params.get("character_name")
        chapter_number = params["chapter_number"]
        data = params["data"]
        change_note = params.get("change_note")

        # 如果只提供了名称，查找 ID
        if not character_id and character_name:
            char_stmt = select(BlueprintCharacter).where(
                BlueprintCharacter.project_id == project_id,
                BlueprintCharacter.name == character_name,
            )
            char_result = await self.session.execute(char_stmt)
            char = char_result.scalars().first()
            if not char:
                return ToolResult(
                    success=False,
                    message=f"找不到角色「{character_name}」",
                )
            character_id = char.id
            character_name = char.name
        elif character_id:
            # 获取角色名称
            char_stmt = select(BlueprintCharacter).where(BlueprintCharacter.id == character_id)
            char_result = await self.session.execute(char_stmt)
            char = char_result.scalars().first()
            if not char:
                return ToolResult(
                    success=False,
                    message=f"找不到角色 #{character_id}",
                )
            character_name = char.name

        repo = CharacterStateRepository(self.session)

        # 获取之前的状态（用于对比）
        old_state = await repo.get_state_at_chapter(character_id, chapter_number)
        before_state = None
        if old_state:
            before_state = {
                "id": old_state.id,
                "data": old_state.data,
                "change_note": old_state.change_note,
            }

        # 更新或插入状态
        state = await repo.upsert_state(
            character_id=character_id,
            chapter_number=chapter_number,
            data=data,
            change_note=change_note,
        )

        action = "更新" if old_state else "记录"
        logger.info(
            "%s角色状态成功: project=%s, character=%s, chapter=%d",
            action, project_id, character_name, chapter_number
        )

        return ToolResult(
            success=True,
            message=f"成功{action}{character_name}在第{chapter_number}章的状态",
            data={
                "state_id": state.id,
                "character_id": character_id,
                "character_name": character_name,
                "chapter_number": chapter_number,
            },
            before_state=before_state,
            after_state={
                "id": state.id,
                "character_id": character_id,
                "chapter_number": chapter_number,
                "data": state.data,
                "change_note": state.change_note,
            },
        )

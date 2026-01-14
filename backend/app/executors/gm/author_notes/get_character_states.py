"""获取角色状态工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict

from sqlalchemy import select

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import BlueprintCharacter
from ....services.gm.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


@ToolRegistry.register
class GetCharacterStatesExecutor(BaseToolExecutor):
    """获取角色状态列表（数值流小说）。"""

    is_read_only = True

    @classmethod
    def get_name(cls) -> str:
        return "get_character_states"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="get_character_states",
            description="获取角色的状态数据（适用于数值流小说如网游、修仙等）。可以获取特定角色的状态历史，或获取所有角色的最新状态。",
            parameters={
                "type": "object",
                "properties": {
                    "character_id": {
                        "type": "integer",
                        "description": "角色 ID（可选，不填则获取所有角色的最新状态）",
                    },
                    "before_chapter": {
                        "type": "integer",
                        "description": "获取此章节之前的状态（可选）",
                    },
                },
                "required": [],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        character_id = params.get("character_id")
        if character_id:
            return f"查询角色 #{character_id} 的状态"
        return "查询所有角色的最新状态"

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        from ....repositories.author_notes_repository import CharacterStateRepository

        repo = CharacterStateRepository(self.session)
        character_id = params.get("character_id")
        before_chapter = params.get("before_chapter")

        if character_id:
            # 获取特定角色的状态历史（可选：限制在某章节之前）
            if before_chapter:
                state = await repo.get_latest_state(character_id, before_chapter)
                states = [state] if state else []
            else:
                states = await repo.list_by_character(character_id)

            # 获取角色名称
            char_stmt = select(BlueprintCharacter).where(BlueprintCharacter.id == character_id)
            char_result = await self.session.execute(char_stmt)
            char = char_result.scalars().first()
            char_name = char.name if char else f"角色#{character_id}"

            states_data = []
            for state in states:
                states_data.append({
                    "id": state.id,
                    "chapter_number": state.chapter_number,
                    "data": state.data,
                    "change_note": state.change_note,
                })

            return ToolResult(
                success=True,
                message=f"找到{char_name}的 {len(states)} 条状态记录",
                data={
                    "character_id": character_id,
                    "character_name": char_name,
                    "states": states_data,
                },
            )
        else:
            # 获取所有角色的最新状态
            states = await repo.list_latest_states_for_project(project_id, before_chapter)

            # 获取角色名称映射
            char_ids = [s.character_id for s in states]
            if char_ids:
                char_stmt = select(BlueprintCharacter).where(BlueprintCharacter.id.in_(char_ids))
                char_result = await self.session.execute(char_stmt)
                char_map = {c.id: c.name for c in char_result.scalars().all()}
            else:
                char_map = {}

            states_data = []
            for state in states:
                states_data.append({
                    "id": state.id,
                    "character_id": state.character_id,
                    "character_name": char_map.get(state.character_id, f"角色#{state.character_id}"),
                    "chapter_number": state.chapter_number,
                    "data": state.data,
                    "change_note": state.change_note,
                })

            return ToolResult(
                success=True,
                message=f"找到 {len(states)} 个角色的最新状态",
                data={"states": states_data, "count": len(states)},
            )

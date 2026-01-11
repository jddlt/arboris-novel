"""更新蓝图设定工具执行器。

允许修改小说的基础设定，包括：
- 标题、类型、风格、基调
- 故事概要和详细剧情
- 世界观设定（规则、地点、阵营等）
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import NovelBlueprint
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class UpdateBlueprintExecutor(BaseToolExecutor):
    """更新蓝图设定。

    支持修改小说的基础设定和世界观。
    """

    @classmethod
    def get_name(cls) -> str:
        return "update_blueprint"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="update_blueprint",
            description="""更新小说的蓝图设定，包括基础信息和世界观。

可修改的字段：
- title: 小说标题
- genre: 题材类型（如：都市奇幻、玄幻修仙）
- style: 写作风格（如：轻松幽默、沉重压抑）
- tone: 基调（如：热血、治愈）
- target_audience: 目标读者
- one_sentence_summary: 一句话简介
- full_synopsis: 完整故事概要
- world_setting: 世界观设定（JSON 对象，包含 core_rules、locations、factions 等）

对于 world_setting，可以整体替换，也可以通过 world_setting_patch 部分更新。""",
            parameters={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "新的小说标题",
                    },
                    "genre": {
                        "type": "string",
                        "description": "新的题材类型",
                    },
                    "style": {
                        "type": "string",
                        "description": "新的写作风格",
                    },
                    "tone": {
                        "type": "string",
                        "description": "新的基调",
                    },
                    "target_audience": {
                        "type": "string",
                        "description": "新的目标读者",
                    },
                    "one_sentence_summary": {
                        "type": "string",
                        "description": "新的一句话简介",
                    },
                    "full_synopsis": {
                        "type": "string",
                        "description": "新的完整故事概要",
                    },
                    "world_setting": {
                        "type": "object",
                        "description": "新的世界观设定（整体替换）",
                    },
                    "world_setting_patch": {
                        "type": "object",
                        "description": "世界观设定的部分更新（合并到现有设定）",
                        "properties": {
                            "core_rules": {
                                "type": "string",
                                "description": "核心规则设定",
                            },
                            "locations": {
                                "type": "array",
                                "description": "主要地点列表",
                            },
                            "factions": {
                                "type": "array",
                                "description": "势力/阵营列表",
                            },
                        },
                    },
                },
                "required": [],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        fields = []
        if "title" in params:
            fields.append(f"标题→{params['title']}")
        if "genre" in params:
            fields.append(f"题材→{params['genre']}")
        if "style" in params:
            fields.append(f"风格→{params['style']}")
        if "tone" in params:
            fields.append(f"基调→{params['tone']}")
        if "one_sentence_summary" in params:
            fields.append("一句话简介")
        if "full_synopsis" in params:
            fields.append("故事概要")
        if "world_setting" in params:
            fields.append("世界观(整体)")
        if "world_setting_patch" in params:
            patch_keys = list(params["world_setting_patch"].keys())
            fields.append(f"世界观({', '.join(patch_keys)})")

        if not fields:
            return "更新蓝图设定（无修改）"
        return f"更新蓝图设定：{', '.join(fields)}"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        if not params:
            return "必须指定至少一个要修改的字段"

        title = params.get("title")
        if title is not None and len(title) > 255:
            return "标题过长，最多255个字符"

        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        # 查找蓝图
        stmt = select(NovelBlueprint).where(NovelBlueprint.project_id == project_id)
        result = await self.session.execute(stmt)
        blueprint = result.scalars().first()

        if not blueprint:
            return ToolResult(
                success=False,
                message="项目蓝图不存在",
            )

        # 保存修改前状态
        before_state = {
            "project_id": blueprint.project_id,
            "title": blueprint.title,
            "genre": blueprint.genre,
            "style": blueprint.style,
            "tone": blueprint.tone,
            "target_audience": blueprint.target_audience,
            "one_sentence_summary": blueprint.one_sentence_summary,
            "full_synopsis": blueprint.full_synopsis[:500] if blueprint.full_synopsis else None,
            "world_setting": blueprint.world_setting,
        }

        updated_fields = []

        # 更新简单字段
        simple_fields = ["title", "genre", "style", "tone", "target_audience", "one_sentence_summary", "full_synopsis"]
        for field in simple_fields:
            if field in params:
                setattr(blueprint, field, params[field])
                updated_fields.append(field)

        # 处理世界观设定
        if "world_setting" in params:
            # 整体替换 - 确保 world_setting 是 dict 而不是 JSON 字符串
            world_setting_value = params["world_setting"]
            if isinstance(world_setting_value, str):
                try:
                    world_setting_value = json.loads(world_setting_value)
                except json.JSONDecodeError:
                    return ToolResult(
                        success=False,
                        message="world_setting 格式错误，必须是有效的 JSON 对象",
                    )
            blueprint.world_setting = world_setting_value
            flag_modified(blueprint, "world_setting")
            updated_fields.append("world_setting")
        elif "world_setting_patch" in params:
            # 部分更新（合并）
            current = dict(blueprint.world_setting) if blueprint.world_setting else {}
            patch = params["world_setting_patch"]
            for key, value in patch.items():
                current[key] = value
            blueprint.world_setting = current
            flag_modified(blueprint, "world_setting")
            updated_fields.append("world_setting")

        await self.session.flush()

        # 保存修改后状态
        after_state = {
            "project_id": blueprint.project_id,
            "title": blueprint.title,
            "genre": blueprint.genre,
            "style": blueprint.style,
            "tone": blueprint.tone,
            "target_audience": blueprint.target_audience,
            "one_sentence_summary": blueprint.one_sentence_summary,
            "full_synopsis": blueprint.full_synopsis[:500] if blueprint.full_synopsis else None,
            "world_setting": blueprint.world_setting,
        }

        logger.info("更新蓝图成功: project=%s, fields=%s", project_id, updated_fields)

        return ToolResult(
            success=True,
            message=f"成功更新蓝图设定：{', '.join(updated_fields)}",
            data={"updated_fields": updated_fields},
            before_state=before_state,
            after_state=after_state,
        )

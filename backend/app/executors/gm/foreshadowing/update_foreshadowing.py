"""更新伏笔工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy.orm.attributes import flag_modified

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import NovelBlueprint
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class UpdateForeshadowingExecutor(BaseToolExecutor):
    """更新伏笔信息。"""

    @classmethod
    def get_name(cls) -> str:
        return "update_foreshadowing"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="update_foreshadowing",
            description="更新已存在的伏笔信息。",
            parameters={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "伏笔标题（用于定位伏笔）",
                    },
                    "new_title": {
                        "type": "string",
                        "description": "新的伏笔标题（可选）",
                    },
                    "description": {
                        "type": "string",
                        "description": "伏笔的详细描述",
                    },
                    "reveal_chapter": {
                        "type": "integer",
                        "description": "预计揭示章节号",
                    },
                },
                "required": ["title"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        title = params.get("title", "?")
        return f"更新伏笔：{title}"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        title = params.get("title")
        if not title or not title.strip():
            return "伏笔标题不能为空"
        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        blueprint = await self.session.get(NovelBlueprint, project_id)
        if not blueprint or not blueprint.foreshadowing:
            return ToolResult(
                success=False,
                message="项目没有伏笔数据",
            )

        # 刷新以获取最新数据
        await self.session.refresh(blueprint)

        foreshadowing_data = blueprint.foreshadowing
        threads = list(foreshadowing_data.get("threads", []))  # 创建副本

        title = params["title"].strip()

        # 查找目标伏笔
        target_index = None
        target_thread = None
        for i, thread in enumerate(threads):
            if thread.get("title") == title:
                target_index = i
                target_thread = thread.copy()
                break

        if target_thread is None:
            return ToolResult(
                success=False,
                message=f"伏笔「{title}」不存在",
            )

        before_state = target_thread.copy()

        # 更新字段
        if "new_title" in params and params["new_title"]:
            target_thread["title"] = params["new_title"].strip()
        if "description" in params:
            target_thread["description"] = params["description"]
        if "reveal_chapter" in params:
            target_thread["reveal_chapter"] = params["reveal_chapter"]

        threads[target_index] = target_thread
        blueprint.foreshadowing = {"threads": threads}
        flag_modified(blueprint, "foreshadowing")
        await self.session.flush()

        logger.info(
            "更新伏笔成功: project=%s, title=%s",
            project_id,
            title,
        )

        return ToolResult(
            success=True,
            message=f"成功更新伏笔「{target_thread['title']}」",
            data={
                "title": target_thread["title"],
            },
            before_state=before_state,
            after_state=target_thread,
        )

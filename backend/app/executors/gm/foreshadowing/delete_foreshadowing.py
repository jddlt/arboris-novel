"""删除伏笔工具执行器。"""

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
class DeleteForeshadowingExecutor(BaseToolExecutor):
    """删除伏笔。"""

    @classmethod
    def get_name(cls) -> str:
        return "delete_foreshadowing"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="delete_foreshadowing",
            description="从小说中删除一个伏笔。用于移除不再需要的伏笔线索。",
            parameters={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "要删除的伏笔标题",
                    },
                },
                "required": ["title"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        title = params.get("title", "?")
        return f"删除伏笔：{title}"

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

        # 查找并删除目标伏笔
        deleted_thread = None
        new_threads = []
        for thread in threads:
            if thread.get("title") == title:
                deleted_thread = thread
            else:
                new_threads.append(thread)

        if deleted_thread is None:
            return ToolResult(
                success=False,
                message=f"伏笔「{title}」不存在",
            )

        blueprint.foreshadowing = {"threads": new_threads}
        flag_modified(blueprint, "foreshadowing")
        await self.session.flush()

        logger.info(
            "删除伏笔成功: project=%s, title=%s",
            project_id,
            title,
        )

        return ToolResult(
            success=True,
            message=f"成功删除伏笔「{title}」",
            data={
                "title": title,
            },
            before_state=deleted_thread,
            after_state=None,
        )

"""揭示伏笔工具执行器。"""

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
class RevealForeshadowingExecutor(BaseToolExecutor):
    """标记伏笔已揭示。"""

    @classmethod
    def get_name(cls) -> str:
        return "reveal_foreshadowing"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="reveal_foreshadowing",
            description="标记一个伏笔已在某章节揭示。用于追踪伏笔回收进度。",
            parameters={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "伏笔标题",
                    },
                    "reveal_chapter": {
                        "type": "integer",
                        "description": "实际揭示的章节号",
                    },
                },
                "required": ["title", "reveal_chapter"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        title = params.get("title", "?")
        chapter = params.get("reveal_chapter", "?")
        return f"揭示伏笔：「{title}」第{chapter}章"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        title = params.get("title")
        if not title or not title.strip():
            return "伏笔标题不能为空"

        reveal_chapter = params.get("reveal_chapter")
        if reveal_chapter is None or reveal_chapter < 1:
            return "揭示章节号必须大于0"

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

        if target_thread.get("status") == "revealed":
            return ToolResult(
                success=False,
                message=f"伏笔「{title}」已经揭示过了",
            )

        before_state = target_thread.copy()

        # 标记为已揭示
        target_thread["status"] = "revealed"
        target_thread["actual_reveal_chapter"] = params["reveal_chapter"]

        threads[target_index] = target_thread
        blueprint.foreshadowing = {"threads": threads}
        flag_modified(blueprint, "foreshadowing")
        await self.session.flush()

        logger.info(
            "揭示伏笔成功: project=%s, title=%s, chapter=%d",
            project_id,
            title,
            params["reveal_chapter"],
        )

        return ToolResult(
            success=True,
            message=f"伏笔「{title}」已在第{params['reveal_chapter']}章揭示",
            data={
                "title": title,
                "reveal_chapter": params["reveal_chapter"],
            },
            before_state=before_state,
            after_state=target_thread,
        )

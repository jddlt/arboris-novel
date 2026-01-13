"""添加伏笔线索工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import NovelBlueprint
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class AddClueExecutor(BaseToolExecutor):
    """为伏笔添加线索。"""

    @classmethod
    def get_name(cls) -> str:
        return "add_clue"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="add_clue",
            description="为已存在的伏笔添加一个新线索。用于记录伏笔在各章节埋下的暗示。",
            parameters={
                "type": "object",
                "properties": {
                    "foreshadowing_title": {
                        "type": "string",
                        "description": "伏笔标题",
                    },
                    "chapter": {
                        "type": "integer",
                        "description": "线索所在章节号",
                    },
                    "content": {
                        "type": "string",
                        "description": "线索内容描述",
                    },
                },
                "required": ["foreshadowing_title", "chapter", "content"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        title = params.get("foreshadowing_title", "?")
        chapter = params.get("chapter", "?")
        return f"添加线索：「{title}」第{chapter}章"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        title = params.get("foreshadowing_title")
        if not title or not title.strip():
            return "伏笔标题不能为空"

        chapter = params.get("chapter")
        if chapter is None or chapter < 1:
            return "章节号必须大于0"

        content = params.get("content")
        if not content or not content.strip():
            return "线索内容不能为空"

        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        blueprint = await self.session.get(NovelBlueprint, project_id)
        if not blueprint or not blueprint.foreshadowing:
            return ToolResult(
                success=False,
                message="项目没有伏笔数据",
            )

        foreshadowing_data = blueprint.foreshadowing
        threads = foreshadowing_data.get("threads", [])

        title = params["foreshadowing_title"].strip()

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

        # 添加线索
        new_clue = {
            "chapter": params["chapter"],
            "content": params["content"].strip(),
        }

        clues = target_thread.get("clues", [])
        clues.append(new_clue)
        clues.sort(key=lambda c: c.get("chapter", 0))
        target_thread["clues"] = clues

        threads[target_index] = target_thread
        blueprint.foreshadowing = {"threads": threads}
        await self.session.flush()

        logger.info(
            "添加线索成功: project=%s, foreshadowing=%s, chapter=%d",
            project_id,
            title,
            params["chapter"],
        )

        return ToolResult(
            success=True,
            message=f"成功为伏笔「{title}」添加第{params['chapter']}章线索",
            data={
                "foreshadowing_title": title,
                "chapter": params["chapter"],
                "total_clues": len(clues),
            },
            before_state=None,
            after_state=new_clue,
        )

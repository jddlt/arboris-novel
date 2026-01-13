"""添加伏笔工具执行器。"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy.orm.attributes import flag_modified

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import NovelBlueprint
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class AddForeshadowingExecutor(BaseToolExecutor):
    """添加新伏笔。"""

    @classmethod
    def get_name(cls) -> str:
        return "add_foreshadowing"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="add_foreshadowing",
            description="添加一个新的伏笔到小说中。用于追踪需要埋设和回收的情节线索。",
            parameters={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "伏笔标题，简短描述这个伏笔，如：主角身世之谜",
                    },
                    "description": {
                        "type": "string",
                        "description": "伏笔的详细描述，包括内容和目的",
                    },
                    "plant_chapter": {
                        "type": "integer",
                        "description": "伏笔埋设的章节号",
                    },
                    "reveal_chapter": {
                        "type": "integer",
                        "description": "预计揭示伏笔的章节号",
                    },
                    "initial_clue": {
                        "type": "string",
                        "description": "第一个线索的内容描述（可选）",
                    },
                },
                "required": ["title", "plant_chapter", "reveal_chapter"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        title = params.get("title", "未命名")
        plant = params.get("plant_chapter", "?")
        reveal = params.get("reveal_chapter", "?")
        return f"添加伏笔：{title}（第{plant}章埋设 → 第{reveal}章揭示）"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        title = params.get("title")
        if not title or not title.strip():
            return "伏笔标题不能为空"

        plant_chapter = params.get("plant_chapter")
        reveal_chapter = params.get("reveal_chapter")
        if plant_chapter is None or plant_chapter < 1:
            return "埋设章节号必须大于0"
        if reveal_chapter is None or reveal_chapter < plant_chapter:
            return "揭示章节号必须大于或等于埋设章节号"

        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        # 刷新 blueprint 以确保获取最新数据（处理同一事务中多次操作的情况）
        blueprint = await self.session.get(NovelBlueprint, project_id)
        if blueprint:
            await self.session.refresh(blueprint)
        else:
            blueprint = NovelBlueprint(project_id=project_id)
            self.session.add(blueprint)

        foreshadowing_data = blueprint.foreshadowing or {}
        threads = list(foreshadowing_data.get("threads", []))  # 创建副本避免引用问题

        title = params["title"].strip()

        # 检查标题是否已存在
        for thread in threads:
            if thread.get("title") == title:
                return ToolResult(
                    success=False,
                    message=f"伏笔「{title}」已存在，请使用 update_foreshadowing 修改",
                )

        # 创建新伏笔
        new_thread = {
            "id": str(uuid.uuid4()),
            "title": title,
            "description": params.get("description", ""),
            "plant_chapter": params["plant_chapter"],
            "reveal_chapter": params["reveal_chapter"],
            "actual_reveal_chapter": None,
            "clues": [],
            "status": "active",
        }

        # 如果有初始线索
        if params.get("initial_clue"):
            new_thread["clues"].append({
                "chapter": params["plant_chapter"],
                "content": params["initial_clue"],
            })

        threads.append(new_thread)
        blueprint.foreshadowing = {"threads": threads}
        flag_modified(blueprint, "foreshadowing")  # 确保 SQLAlchemy 检测到变更
        await self.session.flush()

        logger.info(
            "添加伏笔成功: project=%s, title=%s",
            project_id,
            title,
        )

        return ToolResult(
            success=True,
            message=f"成功添加伏笔「{title}」（第{params['plant_chapter']}章埋设 → 第{params['reveal_chapter']}章揭示）",
            data={
                "foreshadowing_id": new_thread["id"],
                "title": title,
            },
            before_state=None,
            after_state=new_thread,
        )

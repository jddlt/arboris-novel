"""查询伏笔列表工具执行器。"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import select

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import NovelBlueprint
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class GetForeshadowingExecutor(BaseToolExecutor):
    """查询伏笔列表（只读工具，自动执行）。"""

    is_read_only = True

    @classmethod
    def get_name(cls) -> str:
        return "get_foreshadowing"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="get_foreshadowing",
            description="查询小说中的伏笔列表。可以获取所有伏笔或按状态筛选。用于获取伏笔的最新信息。",
            parameters={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["active", "revealed", "all"],
                        "description": "按状态筛选：active=活跃伏笔，revealed=已揭示，all=全部（默认）",
                    },
                    "title": {
                        "type": "string",
                        "description": "按伏笔标题筛选（模糊匹配）",
                    },
                },
                "required": [],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        status = params.get("status")
        title = params.get("title")

        if title:
            return f"查询伏笔：{title}"
        elif status == "active":
            return "查询活跃伏笔"
        elif status == "revealed":
            return "查询已揭示伏笔"
        return "查询所有伏笔"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        status_filter = params.get("status", "all")
        title_filter = params.get("title", "").strip()

        # 获取蓝图
        stmt = select(NovelBlueprint).where(
            NovelBlueprint.project_id == project_id
        )
        result = await self.session.execute(stmt)
        blueprint = result.scalars().first()

        if not blueprint or not blueprint.foreshadowing:
            return ToolResult(
                success=True,
                message="当前小说暂无伏笔",
                data={"foreshadowing": [], "total": 0, "active_count": 0, "revealed_count": 0},
            )

        # 解析伏笔数据
        foreshadowing_data = blueprint.foreshadowing
        if isinstance(foreshadowing_data, str):
            try:
                foreshadowing_data = json.loads(foreshadowing_data)
            except json.JSONDecodeError:
                return ToolResult(
                    success=False,
                    message="伏笔数据格式错误",
                )

        threads = foreshadowing_data.get("threads", [])
        if not threads:
            return ToolResult(
                success=True,
                message="当前小说暂无伏笔",
                data={"foreshadowing": [], "total": 0, "active_count": 0, "revealed_count": 0},
            )

        # 应用筛选
        filtered = []
        for thread in threads:
            thread_status = thread.get("status", "active")
            thread_title = thread.get("title", "")

            # 状态筛选
            if status_filter != "all" and thread_status != status_filter:
                continue

            # 标题筛选
            if title_filter and title_filter.lower() not in thread_title.lower():
                continue

            filtered.append(thread)

        # 统计
        active_count = sum(1 for t in threads if t.get("status") == "active")
        revealed_count = sum(1 for t in threads if t.get("status") == "revealed")

        if not filtered:
            return ToolResult(
                success=True,
                message="未找到匹配的伏笔",
                data={
                    "foreshadowing": [],
                    "total": 0,
                    "active_count": active_count,
                    "revealed_count": revealed_count,
                },
            )

        # 构建返回数据
        foreshadowing_list = []
        for thread in filtered:
            item = {
                "title": thread.get("title", "未命名伏笔"),
                "status": thread.get("status", "active"),
                "plant_chapter": thread.get("plant_chapter"),
                "reveal_chapter": thread.get("reveal_chapter"),
                "description": thread.get("description", ""),
                "clues_count": len(thread.get("clues", [])),
            }

            # 如果已揭示，添加实际揭示章节
            if thread.get("status") == "revealed":
                item["actual_reveal_chapter"] = thread.get("actual_reveal_chapter")

            # 添加线索摘要
            clues = thread.get("clues", [])
            if clues:
                item["clues"] = [
                    {"chapter": c.get("chapter"), "content": c.get("content", "")[:100]}
                    for c in clues[:5]  # 最多显示5条线索
                ]

            foreshadowing_list.append(item)

        logger.info(
            "查询伏笔成功: project=%s, count=%d",
            project_id,
            len(foreshadowing_list),
        )

        return ToolResult(
            success=True,
            message=f"找到 {len(foreshadowing_list)} 条伏笔（活跃 {active_count}，已揭示 {revealed_count}）",
            data={
                "foreshadowing": foreshadowing_list,
                "total": len(foreshadowing_list),
                "active_count": active_count,
                "revealed_count": revealed_count,
            },
        )

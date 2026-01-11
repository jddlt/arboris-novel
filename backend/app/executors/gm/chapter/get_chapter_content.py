"""获取章节内容工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class GetChapterContentExecutor(BaseToolExecutor):
    """获取指定章节的完整内容。

    支持获取单个或多个章节的完整正文，用于分析、对比和修改。
    """

    @classmethod
    def get_name(cls) -> str:
        return "get_chapter_content"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="get_chapter_content",
            description="获取指定章节的完整内容。可以获取单个章节或多个章节的正文，用于分析内容、检查冲突、准备修改等。",
            parameters={
                "type": "object",
                "properties": {
                    "chapter_numbers": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "要获取的章节号列表，如 [4, 9] 表示获取第4章和第9章",
                    },
                },
                "required": ["chapter_numbers"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        chapter_numbers = params.get("chapter_numbers", [])
        if len(chapter_numbers) == 1:
            return f"获取第 {chapter_numbers[0]} 章内容"
        return f"获取第 {', '.join(map(str, chapter_numbers))} 章内容"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        chapter_numbers = params.get("chapter_numbers")
        if not chapter_numbers:
            return "必须指定章节号"
        if not isinstance(chapter_numbers, list):
            return "chapter_numbers 必须是数组"
        if len(chapter_numbers) > 5:
            return "一次最多获取5个章节的内容"
        for num in chapter_numbers:
            if not isinstance(num, int) or num < 1:
                return f"无效的章节号: {num}"
        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        from ....repositories.novel_repository import NovelRepository

        chapter_numbers = params["chapter_numbers"]

        repo = NovelRepository(self.session)
        project = await repo.get_by_id(project_id)

        if not project:
            return ToolResult(
                success=False,
                message="项目不存在",
            )

        # 获取请求的章节
        chapters_data = []
        not_found = []
        no_content = []

        for num in chapter_numbers:
            chapter = next(
                (ch for ch in project.chapters if ch.chapter_number == num),
                None
            )

            if not chapter:
                not_found.append(num)
                continue

            if not chapter.content:
                no_content.append(num)
                continue

            # 获取大纲信息
            outline = next(
                (o for o in project.outlines if o.chapter_number == num),
                None
            )

            chapters_data.append({
                "chapter_number": num,
                "title": outline.title if outline else f"第{num}章",
                "outline_summary": outline.summary if outline else None,
                "content": chapter.content,
                "word_count": len(chapter.content),
                "status": chapter.status,
            })

        # 构建结果消息
        messages = []
        if chapters_data:
            messages.append(f"成功获取 {len(chapters_data)} 个章节的内容")
        if not_found:
            messages.append(f"第 {', '.join(map(str, not_found))} 章不存在")
        if no_content:
            messages.append(f"第 {', '.join(map(str, no_content))} 章尚未生成内容")

        logger.info(
            "获取章节内容: project=%s, requested=%s, found=%d",
            project_id,
            chapter_numbers,
            len(chapters_data),
        )

        return ToolResult(
            success=len(chapters_data) > 0,
            message="; ".join(messages) if messages else "未找到任何章节",
            data={"chapters": chapters_data},
        )

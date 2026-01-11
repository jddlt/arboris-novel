"""更新章节内容工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class UpdateChapterContentExecutor(BaseToolExecutor):
    """更新指定章节的内容。

    可以完全替换章节内容，或修改部分内容。
    """

    @classmethod
    def get_name(cls) -> str:
        return "update_chapter_content"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="update_chapter_content",
            description="更新指定章节的正文内容。可用于修复剧情冲突、优化文字表达、调整情节等。修改后内容会完全替换原内容。",
            parameters={
                "type": "object",
                "properties": {
                    "chapter_number": {
                        "type": "integer",
                        "description": "要修改的章节号",
                    },
                    "new_content": {
                        "type": "string",
                        "description": "章节的新内容（完整正文）",
                    },
                    "modification_reason": {
                        "type": "string",
                        "description": "修改原因说明，用于记录变更历史",
                    },
                },
                "required": ["chapter_number", "new_content"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        chapter_number = params.get("chapter_number", "?")
        new_content = params.get("new_content", "")
        word_count = len(new_content)
        reason = params.get("modification_reason", "")

        preview = f"修改第 {chapter_number} 章内容（{word_count} 字）"
        if reason:
            if len(reason) > 30:
                reason = reason[:30] + "..."
            preview += f"：{reason}"
        return preview

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        chapter_number = params.get("chapter_number")
        if chapter_number is None:
            return "必须指定有效的章节号"
        try:
            chapter_number = int(chapter_number)
            if chapter_number < 1:
                return "章节号必须大于0"
        except (ValueError, TypeError):
            return "章节号必须是有效的整数"

        new_content = params.get("new_content")
        if not new_content or not isinstance(new_content, str):
            return "必须提供新的章节内容"

        if len(new_content.strip()) < 100:
            return "章节内容过短，至少需要100字"

        if len(new_content) > 50000:
            return "章节内容过长，最多50000字"

        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        from ....repositories.novel_repository import NovelRepository

        chapter_number = int(params["chapter_number"])
        new_content = params["new_content"].strip()
        modification_reason = params.get("modification_reason", "")

        repo = NovelRepository(self.session)
        project = await repo.get_by_id(project_id)

        if not project:
            return ToolResult(
                success=False,
                message="项目不存在",
            )

        # 查找章节
        chapter = next(
            (ch for ch in project.chapters if ch.chapter_number == chapter_number),
            None
        )

        if not chapter:
            return ToolResult(
                success=False,
                message=f"第 {chapter_number} 章不存在",
            )

        # 保存修改前状态
        before_state = {
            "chapter_number": chapter_number,
            "content": chapter.content,
            "word_count": len(chapter.content) if chapter.content else 0,
        }

        # 更新内容
        old_content = chapter.content
        chapter.content = new_content

        # 保存修改后状态
        after_state = {
            "chapter_number": chapter_number,
            "content": new_content,
            "word_count": len(new_content),
            "modification_reason": modification_reason,
        }

        await self.session.commit()

        logger.info(
            "更新章节内容: project=%s, chapter=%d, old_words=%d, new_words=%d, reason=%s",
            project_id,
            chapter_number,
            len(old_content) if old_content else 0,
            len(new_content),
            modification_reason[:50] if modification_reason else "无",
        )

        return ToolResult(
            success=True,
            message=f"已更新第 {chapter_number} 章内容（{len(new_content)} 字）",
            data={
                "chapter_number": chapter_number,
                "new_word_count": len(new_content),
                "old_word_count": len(old_content) if old_content else 0,
            },
            before_state=before_state,
            after_state=after_state,
        )

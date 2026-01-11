"""清空章节内容工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import select

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import Chapter, ChapterVersion
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class ClearChapterContentExecutor(BaseToolExecutor):
    """清空指定章节的内容，将其重置为未生成状态。

    这会删除该章节的所有版本，将状态重置为 not_generated。
    """

    @classmethod
    def get_name(cls) -> str:
        return "clear_chapter_content"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="clear_chapter_content",
            description="清空指定章节的正文内容，将其重置为未生成状态。这会删除该章节的所有生成版本。用于需要重新生成章节的场景。",
            parameters={
                "type": "object",
                "properties": {
                    "chapter_number": {
                        "type": "integer",
                        "description": "要清空的章节号",
                    },
                    "reason": {
                        "type": "string",
                        "description": "清空原因说明（可选）",
                    },
                },
                "required": ["chapter_number"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        chapter_number = params.get("chapter_number", "?")
        reason = params.get("reason", "")
        preview = f"清空第 {chapter_number} 章内容"
        if reason:
            if len(reason) > 30:
                reason = reason[:30] + "..."
            preview += f"：{reason}"
        return preview

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        chapter_number = params.get("chapter_number")
        if chapter_number is None:
            return "必须指定章节号"
        try:
            chapter_number = int(chapter_number)
            if chapter_number < 1:
                return "章节号必须大于0"
        except (ValueError, TypeError):
            return "章节号必须是有效的整数"
        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        chapter_number = int(params["chapter_number"])
        reason = params.get("reason", "")

        # 查找章节
        stmt = select(Chapter).where(
            Chapter.project_id == project_id,
            Chapter.chapter_number == chapter_number,
        )
        result = await self.session.execute(stmt)
        chapter = result.scalars().first()

        if not chapter:
            return ToolResult(
                success=False,
                message=f"第 {chapter_number} 章不存在",
            )

        if chapter.status == "not_generated":
            return ToolResult(
                success=False,
                message=f"第 {chapter_number} 章尚未生成内容，无需清空",
            )

        # 保存修改前状态
        before_state = {
            "chapter_number": chapter_number,
            "status": chapter.status,
            "word_count": chapter.word_count,
            "selected_version_id": chapter.selected_version_id,
            "versions_count": len(chapter.versions) if chapter.versions else 0,
        }

        # 删除所有版本
        version_count = 0
        if chapter.versions:
            version_count = len(chapter.versions)
            for version in chapter.versions:
                await self.session.delete(version)

        # 重置章节状态
        old_word_count = chapter.word_count
        chapter.status = "not_generated"
        chapter.word_count = 0
        chapter.selected_version_id = None
        chapter.real_summary = None

        await self.session.flush()

        # 保存修改后状态
        after_state = {
            "chapter_number": chapter_number,
            "status": "not_generated",
            "word_count": 0,
            "selected_version_id": None,
            "versions_count": 0,
        }

        logger.info(
            "清空章节内容: project=%s, chapter=%d, old_word_count=%d, versions_deleted=%d, reason=%s",
            project_id,
            chapter_number,
            old_word_count,
            version_count,
            reason[:50] if reason else "无",
        )

        return ToolResult(
            success=True,
            message=f"已清空第 {chapter_number} 章内容（原 {old_word_count} 字，{version_count} 个版本）",
            data={
                "chapter_number": chapter_number,
                "old_word_count": old_word_count,
                "versions_deleted": version_count,
            },
            before_state=before_state,
            after_state=after_state,
        )

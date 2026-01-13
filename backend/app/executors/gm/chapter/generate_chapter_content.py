"""生成章节内容工具执行器。

GM Agent 自己生成章节内容后，调用此工具将内容保存到数据库。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class GenerateChapterContentExecutor(BaseToolExecutor):
    """保存 Agent 生成的章节内容到数据库。

    GM Agent 根据上下文生成章节内容后，调用此工具将内容保存。
    用户预览后点击"应用"，内容才会写入数据库。
    """

    @classmethod
    def get_name(cls) -> str:
        return "generate_chapter_content"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="generate_chapter_content",
            description="保存生成的章节内容。当你为用户生成了章节正文后，调用此工具将内容保存到数据库。",
            parameters={
                "type": "object",
                "properties": {
                    "chapter_number": {
                        "type": "integer",
                        "description": "章节号",
                    },
                    "title": {
                        "type": "string",
                        "description": "章节标题",
                    },
                    "content": {
                        "type": "string",
                        "description": "生成的章节正文内容",
                    },
                },
                "required": ["chapter_number", "title", "content"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        chapter_number = params.get("chapter_number", "?")
        content = params.get("content", "")
        word_count = len(content)
        preview = content[:100] + "..." if len(content) > 100 else content
        return f"保存第 {chapter_number} 章内容（{word_count} 字）\n\n{preview}"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        # 参数别名标准化
        if "chapter_index" in params and "chapter_number" not in params:
            params["chapter_number"] = params.pop("chapter_index")
        if "章节号" in params and "chapter_number" not in params:
            params["chapter_number"] = params.pop("章节号")
        if "正文" in params and "content" not in params:
            params["content"] = params.pop("正文")
        if "内容" in params and "content" not in params:
            params["content"] = params.pop("内容")
        if "标题" in params and "title" not in params:
            params["title"] = params.pop("标题")

        chapter_number = params.get("chapter_number")
        if chapter_number is None:
            return "必须指定章节号"
        try:
            num = int(chapter_number)
            params["chapter_number"] = num
            if num < 1:
                return f"无效的章节号: {chapter_number}"
        except (ValueError, TypeError):
            return f"无效的章节号: {chapter_number}"

        content = params.get("content")
        if not content:
            return "必须提供章节内容"
        if not isinstance(content, str):
            return "章节内容必须是字符串"
        if len(content) < 100:
            return "章节内容过短（至少100字）"

        title = params.get("title")
        if not title:
            return "必须提供章节标题"
        if not isinstance(title, str):
            return "章节标题必须是字符串"

        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        from ....repositories.novel_repository import NovelRepository
        from ....services.novel_service import NovelService

        chapter_number = int(params["chapter_number"])
        content = params["content"]
        title = params["title"]

        repo = NovelRepository(self.session)
        project = await repo.get_by_id(project_id)

        if not project:
            return ToolResult(
                success=False,
                message="项目不存在",
            )

        # 检查或创建大纲
        outline = next(
            (o for o in project.outlines if o.chapter_number == chapter_number),
            None
        )
        if outline:
            # 更新大纲标题
            outline.title = title
        else:
            # 如果大纲不存在，自动创建
            from ....models.novel import BlueprintOutline
            outline = BlueprintOutline(
                blueprint_id=project.blueprint.id,
                chapter_number=chapter_number,
                title=title,
                summary=f"由 GM Agent 生成的第 {chapter_number} 章",
            )
            self.session.add(outline)

        # 获取或创建章节记录
        novel_service = NovelService(self.session)
        chapter = await novel_service.get_or_create_chapter(project_id, chapter_number)

        # 记录执行前状态
        old_content = chapter.selected_version.content if chapter.selected_version else None
        before_state = {
            "chapter_number": chapter_number,
            "had_content": bool(old_content),
            "previous_status": chapter.status,
            "previous_content": old_content[:500] if old_content else None,
        }

        # 保存内容（创建单个版本）
        await novel_service.replace_chapter_versions(chapter, [content], [{"source": "gm_agent"}])

        # 自动选择第一个版本
        if chapter.versions:
            await novel_service.select_chapter_version(chapter, 0)

        logger.info(
            "GM Agent 生成章节内容: project=%s, chapter=%s, title=%s, word_count=%d",
            project_id,
            chapter_number,
            title,
            len(content),
        )

        # 构建执行后状态
        after_state = {
            "chapter_number": chapter_number,
            "title": title,
            "word_count": len(content),
            "status": chapter.status,
        }

        return ToolResult(
            success=True,
            message=f"已保存「{title}」（第 {chapter_number} 章，{len(content)} 字）",
            data={
                "chapter_number": chapter_number,
                "title": title,
                "word_count": len(content),
            },
            before_state=before_state,
            after_state=after_state,
        )

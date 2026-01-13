"""获取章节版本列表工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class GetChapterVersionsExecutor(BaseToolExecutor):
    """获取指定章节的所有版本信息。

    用于查看章节有哪些可选版本，帮助用户决策选择哪个版本。
    支持获取完整内容用于对比分析。
    """

    # 查询类工具，自动执行
    is_read_only = True

    @classmethod
    def get_name(cls) -> str:
        return "get_chapter_versions"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="get_chapter_versions",
            description="获取指定章节的所有版本列表。用于查看待选择版本的详细信息，帮助分析每个版本的内容差异并给出挑选建议。设置 include_full_content=true 可获取完整内容进行深度对比。",
            parameters={
                "type": "object",
                "properties": {
                    "chapter_number": {
                        "type": "integer",
                        "description": "章节号",
                    },
                    "include_full_content": {
                        "type": "boolean",
                        "description": "是否包含完整内容（默认 false，只返回预览）。设为 true 时返回每个版本的完整正文，用于深度对比分析。",
                    },
                },
                "required": ["chapter_number"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        chapter_number = params.get("chapter_number", "?")
        full = params.get("include_full_content", False)
        if full:
            return f"获取第 {chapter_number} 章版本（含完整内容）"
        return f"获取第 {chapter_number} 章版本列表"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        chapter_number = params.get("chapter_number")
        if chapter_number is None:
            return "必须指定章节号"
        try:
            num = int(chapter_number)
            if num < 1:
                return f"无效的章节号: {chapter_number}"
        except (ValueError, TypeError):
            return f"无效的章节号: {chapter_number}"
        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        from ....repositories.novel_repository import NovelRepository

        chapter_number = int(params["chapter_number"])
        include_full_content = params.get("include_full_content", False)

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

        if not chapter.versions:
            return ToolResult(
                success=True,
                message=f"第 {chapter_number} 章暂无任何版本",
                data={"versions": [], "selected_version_id": None},
            )

        # 获取大纲信息
        outline = next(
            (o for o in project.outlines if o.chapter_number == chapter_number),
            None
        )

        # 构建版本信息
        versions_data = []
        for i, version in enumerate(chapter.versions):
            content = version.content or ""

            version_info = {
                "index": i,
                "version_id": version.id,
                "label": version.version_label or f"版本 {i + 1}",
                "provider": version.provider,
                "word_count": len(content),
                "created_at": version.created_at.isoformat() if version.created_at else None,
                "is_selected": chapter.selected_version_id == version.id,
            }

            if include_full_content:
                # 返回完整内容用于对比分析
                version_info["content"] = content
            else:
                # 只返回预览
                preview = content[:300] + "..." if len(content) > 300 else content
                version_info["preview"] = preview

            versions_data.append(version_info)

        selected_info = None
        if chapter.selected_version:
            selected_info = {
                "version_id": chapter.selected_version.id,
                "label": chapter.selected_version.version_label or "已选版本",
            }

        logger.info(
            "获取章节版本: project=%s, chapter=%d, version_count=%d, full_content=%s",
            project_id,
            chapter_number,
            len(versions_data),
            include_full_content,
        )

        # 构建消息
        if selected_info:
            message = f"第 {chapter_number} 章共 {len(versions_data)} 个版本，已选择: {selected_info['label']}"
        else:
            message = f"第 {chapter_number} 章共 {len(versions_data)} 个版本，尚未选择"

        result_data = {
            "chapter_number": chapter_number,
            "versions": versions_data,
            "selected_version": selected_info,
            "status": chapter.status,
        }

        # 如果有大纲，附加大纲信息帮助 Agent 评估版本是否符合规划
        if outline:
            result_data["outline"] = {
                "title": outline.title,
                "summary": outline.summary,
            }

        return ToolResult(
            success=True,
            message=message,
            data=result_data,
        )

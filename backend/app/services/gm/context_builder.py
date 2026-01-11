"""GM Agent 上下文构建器。

负责为 GM Agent 构建对话上下文，包括小说蓝图、角色、关系、大纲等信息。
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ContextBuilder:
    """上下文构建器 - 为 GM Agent 组装 System Prompt 上下文。

    将小说的各项设定（蓝图、角色、关系、大纲、章节摘要）
    格式化为结构化文本，注入到 LLM 的 System Prompt 中。

    Example:
        ```python
        builder = ContextBuilder(session)
        context = await builder.build(project_id)
        # context 包含格式化的小说信息
        ```
    """

    # 上下文各部分的最大字符数限制
    MAX_SYNOPSIS_LENGTH = 2000
    MAX_WORLD_SETTING_LENGTH = 3000
    MAX_CHARACTERS_LENGTH = 4000
    MAX_RELATIONSHIPS_LENGTH = 1500
    MAX_OUTLINES_LENGTH = 5000
    MAX_SUMMARIES_LENGTH = 3000

    def __init__(self, session: "AsyncSession"):
        """初始化上下文构建器。

        Args:
            session: SQLAlchemy 异步会话
        """
        self.session = session

    async def build(self, project_id: str) -> str:
        """构建完整的 GM 上下文。

        Args:
            project_id: 小说项目 ID

        Returns:
            格式化的上下文字符串
        """
        from ...repositories.novel_repository import NovelRepository

        repo = NovelRepository(self.session)
        project = await repo.get_by_id(project_id)

        if not project:
            return "\n\n[警告] 项目不存在\n"

        sections = []

        # 1. 基础信息
        basic_info = self._build_basic_info(project)
        if basic_info:
            sections.append(basic_info)

        # 2. 世界观设定
        world_setting = self._build_world_setting(project)
        if world_setting:
            sections.append(world_setting)

        # 3. 角色信息
        characters = self._build_characters(project)
        if characters:
            sections.append(characters)

        # 4. 关系网络
        relationships = self._build_relationships(project)
        if relationships:
            sections.append(relationships)

        # 5. 章节大纲
        outlines = self._build_outlines(project)
        if outlines:
            sections.append(outlines)

        # 6. 已完成章节摘要
        summaries = self._build_chapter_summaries(project)
        if summaries:
            sections.append(summaries)

        context = "\n\n".join(sections)
        logger.debug(
            "已构建 GM 上下文: project_id=%s, 长度=%d 字符",
            project_id,
            len(context),
        )
        return context

    def _build_basic_info(self, project) -> Optional[str]:
        """构建基础信息部分。"""
        blueprint = project.blueprint
        if not blueprint:
            return None

        lines = ["## 小说基础信息", ""]
        lines.append(f"- **标题**: {blueprint.title or project.title}")

        if blueprint.genre:
            lines.append(f"- **题材**: {blueprint.genre}")
        if blueprint.style:
            lines.append(f"- **风格**: {blueprint.style}")
        if blueprint.tone:
            lines.append(f"- **基调**: {blueprint.tone}")
        if blueprint.target_audience:
            lines.append(f"- **目标读者**: {blueprint.target_audience}")
        if blueprint.one_sentence_summary:
            lines.append(f"- **一句话简介**: {blueprint.one_sentence_summary}")

        if blueprint.full_synopsis:
            synopsis = blueprint.full_synopsis
            if len(synopsis) > self.MAX_SYNOPSIS_LENGTH:
                synopsis = synopsis[:self.MAX_SYNOPSIS_LENGTH] + "...(已截断)"
            lines.append("")
            lines.append("### 故事大纲")
            lines.append(synopsis)

        return "\n".join(lines)

    def _build_world_setting(self, project) -> Optional[str]:
        """构建世界观设定部分。"""
        blueprint = project.blueprint
        if not blueprint or not blueprint.world_setting:
            return None

        world_setting = blueprint.world_setting
        if isinstance(world_setting, dict):
            content = json.dumps(world_setting, ensure_ascii=False, indent=2)
        else:
            content = str(world_setting)

        if len(content) > self.MAX_WORLD_SETTING_LENGTH:
            content = content[:self.MAX_WORLD_SETTING_LENGTH] + "\n...(已截断)"

        return f"## 世界观设定\n\n```json\n{content}\n```"

    def _build_characters(self, project) -> Optional[str]:
        """构建角色信息部分。"""
        characters = project.characters
        if not characters:
            return None

        lines = ["## 角色列表", ""]

        for char in characters:
            char_lines = [f"### {char.name}"]

            if char.identity:
                char_lines.append(f"- **定位**: {char.identity}")
            if char.personality:
                char_lines.append(f"- **性格**: {char.personality}")
            if char.relationship_to_protagonist:
                bg = char.relationship_to_protagonist
                if len(bg) > 200:
                    bg = bg[:200] + "..."
                char_lines.append(f"- **与主角关系**: {bg}")
            if char.abilities:
                char_lines.append(f"- **能力**: {char.abilities}")
            if char.goals:
                char_lines.append(f"- **目标**: {char.goals}")
            if char.extra:
                # 展示 extra 中的自定义字段
                for key, value in char.extra.items():
                    if isinstance(value, str) and len(value) > 100:
                        value = value[:100] + "..."
                    char_lines.append(f"- **{key}**: {value}")

            lines.extend(char_lines)
            lines.append("")

        result = "\n".join(lines)
        if len(result) > self.MAX_CHARACTERS_LENGTH:
            result = result[:self.MAX_CHARACTERS_LENGTH] + "\n...(角色过多，已截断)"

        return result

    def _build_relationships(self, project) -> Optional[str]:
        """构建关系网络部分。"""
        # NovelProject 中关系字段名为 relationships_
        relationships = project.relationships_
        if not relationships:
            return None

        lines = ["## 角色关系", ""]

        for rel in relationships:
            # BlueprintRelationship 模型使用 character_from 和 character_to
            rel_line = f"- **{rel.character_from}** → **{rel.character_to}**"
            if rel.description:
                rel_line += f": {rel.description}"
            lines.append(rel_line)

        result = "\n".join(lines)
        if len(result) > self.MAX_RELATIONSHIPS_LENGTH:
            result = result[:self.MAX_RELATIONSHIPS_LENGTH] + "\n...(关系过多，已截断)"

        return result

    def _build_outlines(self, project) -> Optional[str]:
        """构建章节大纲部分。"""
        outlines = project.outlines
        if not outlines:
            return None

        # 获取已完成章节编号集合
        completed_chapters = set()
        if project.chapters:
            for ch in project.chapters:
                if ch.status == "successful" and ch.content:
                    completed_chapters.add(ch.chapter_number)

        lines = ["## 章节大纲（规划）", ""]
        lines.append(f"**说明**: 以下是章节规划大纲，不是已写完的内容。")
        lines.append(f"**当前进度**: 共规划 {len(outlines)} 章，已完成 {len(completed_chapters)} 章")
        lines.append("")

        for outline in outlines:
            title = outline.title or f"第{outline.chapter_number}章"
            summary = outline.summary or "(暂无摘要)"
            if len(summary) > 150:
                summary = summary[:150] + "..."

            # 标注完成状态
            status_mark = "✅" if outline.chapter_number in completed_chapters else "📝"
            lines.append(f"- {status_mark} **第{outline.chapter_number}章 - {title}**: {summary}")

        result = "\n".join(lines)
        if len(result) > self.MAX_OUTLINES_LENGTH:
            result = result[:self.MAX_OUTLINES_LENGTH] + "\n...(大纲过多，已截断)"

        return result

    def _build_chapter_summaries(self, project) -> Optional[str]:
        """构建已完成章节摘要部分。"""
        chapters = project.chapters
        if not chapters:
            return None

        # 只包含已完成且有摘要的章节
        completed = [
            ch for ch in chapters
            if ch.status == "successful" and ch.real_summary
        ]

        if not completed:
            return None

        lines = ["## 已完成章节摘要", ""]

        for ch in completed:
            summary = ch.real_summary
            if len(summary) > 200:
                summary = summary[:200] + "..."
            lines.append(f"- **第{ch.chapter_number}章**: {summary}")

        result = "\n".join(lines)
        if len(result) > self.MAX_SUMMARIES_LENGTH:
            result = result[:self.MAX_SUMMARIES_LENGTH] + "\n...(摘要过多，已截断)"

        return result

    async def build_minimal(self, project_id: str) -> str:
        """构建最小上下文（仅基础信息和角色）。

        用于 token 受限场景。

        Args:
            project_id: 项目 ID

        Returns:
            精简的上下文字符串
        """
        from ...repositories.novel_repository import NovelRepository

        repo = NovelRepository(self.session)
        project = await repo.get_by_id(project_id)

        if not project:
            return ""

        sections = []

        basic_info = self._build_basic_info(project)
        if basic_info:
            sections.append(basic_info)

        characters = self._build_characters(project)
        if characters:
            sections.append(characters)

        return "\n\n".join(sections)

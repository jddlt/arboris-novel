"""GM Agent 上下文构建器。

负责为 GM Agent 构建对话上下文，包括小说蓝图、角色、关系、大纲等信息。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class ContextSnapshot:
    """上下文快照，用于对比变更。"""

    # 角色：{name: {identity, personality, ...}}
    characters: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # 关系：{(from, to): description}
    relationships: Dict[Tuple[str, str], str] = field(default_factory=dict)
    # 章节大纲：{chapter_number: {title, summary, volume_number}}
    outlines: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    # 卷：{volume_number: {title, summary, ...}}
    volumes: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    # 伏笔：{thread_id: {title, status, ...}}
    foreshadowing: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class ContextDiff:
    """上下文变更记录。"""

    # 角色变更
    characters_added: List[str] = field(default_factory=list)
    characters_removed: List[str] = field(default_factory=list)
    characters_modified: List[str] = field(default_factory=list)

    # 关系变更
    relationships_added: List[Tuple[str, str]] = field(default_factory=list)
    relationships_removed: List[Tuple[str, str]] = field(default_factory=list)
    relationships_modified: List[Tuple[str, str]] = field(default_factory=list)

    # 大纲变更
    outlines_added: List[int] = field(default_factory=list)
    outlines_removed: List[int] = field(default_factory=list)
    outlines_modified: List[int] = field(default_factory=list)

    # 卷变更
    volumes_added: List[int] = field(default_factory=list)
    volumes_removed: List[int] = field(default_factory=list)
    volumes_modified: List[int] = field(default_factory=list)

    def has_changes(self) -> bool:
        """是否有任何变更。"""
        return bool(
            self.characters_added or self.characters_removed or self.characters_modified
            or self.relationships_added or self.relationships_removed or self.relationships_modified
            or self.outlines_added or self.outlines_removed or self.outlines_modified
            or self.volumes_added or self.volumes_removed or self.volumes_modified
        )

    def to_markdown(self) -> str:
        """生成 Markdown 格式的变更说明。"""
        if not self.has_changes():
            return ""

        lines = ["## 📝 上下文变更（自上次查询后）", ""]

        # 角色变更
        if self.characters_added or self.characters_removed or self.characters_modified:
            lines.append("### 角色变更")
            if self.characters_added:
                lines.append(f"- ➕ 新增: {', '.join(self.characters_added)}")
            if self.characters_removed:
                lines.append(f"- ➖ 删除: {', '.join(self.characters_removed)}")
            if self.characters_modified:
                lines.append(f"- ✏️ 修改: {', '.join(self.characters_modified)}")
            lines.append("")

        # 关系变更
        if self.relationships_added or self.relationships_removed or self.relationships_modified:
            lines.append("### 关系变更")
            if self.relationships_added:
                rel_strs = [f"{a}→{b}" for a, b in self.relationships_added]
                lines.append(f"- ➕ 新增: {', '.join(rel_strs)}")
            if self.relationships_removed:
                rel_strs = [f"{a}→{b}" for a, b in self.relationships_removed]
                lines.append(f"- ➖ 删除: {', '.join(rel_strs)}")
            if self.relationships_modified:
                rel_strs = [f"{a}→{b}" for a, b in self.relationships_modified]
                lines.append(f"- ✏️ 修改: {', '.join(rel_strs)}")
            lines.append("")

        # 大纲变更
        if self.outlines_added or self.outlines_removed or self.outlines_modified:
            lines.append("### 章节大纲变更")
            if self.outlines_added:
                ch_strs = [f"第{n}章" for n in sorted(self.outlines_added)]
                lines.append(f"- ➕ 新增: {', '.join(ch_strs)}")
            if self.outlines_removed:
                ch_strs = [f"第{n}章" for n in sorted(self.outlines_removed)]
                lines.append(f"- ➖ 删除: {', '.join(ch_strs)}")
            if self.outlines_modified:
                ch_strs = [f"第{n}章" for n in sorted(self.outlines_modified)]
                lines.append(f"- ✏️ 修改: {', '.join(ch_strs)}")
            lines.append("")

        # 卷变更
        if self.volumes_added or self.volumes_removed or self.volumes_modified:
            lines.append("### 卷结构变更")
            if self.volumes_added:
                vol_strs = [f"第{n}卷" for n in sorted(self.volumes_added)]
                lines.append(f"- ➕ 新增: {', '.join(vol_strs)}")
            if self.volumes_removed:
                vol_strs = [f"第{n}卷" for n in sorted(self.volumes_removed)]
                lines.append(f"- ➖ 删除: {', '.join(vol_strs)}")
            if self.volumes_modified:
                vol_strs = [f"第{n}卷" for n in sorted(self.volumes_modified)]
                lines.append(f"- ✏️ 修改: {', '.join(vol_strs)}")
            lines.append("")

        return "\n".join(lines)


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
    MAX_OUTLINES_LENGTH = 8000  # 支持约 40-50 章大纲
    MAX_SUMMARIES_LENGTH = 3000
    MAX_VOLUMES_LENGTH = 2000
    MAX_FORESHADOWING_LENGTH = 3000
    MAX_AUTHOR_NOTES_LENGTH = 3000
    MAX_CHARACTER_STATES_LENGTH = 2000

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

        # 0. 创作进度统计（让 Agent 了解小说完成情况）
        # progress = self._build_progress_stats(project)
        # if progress:
        #     sections.append(progress)

        # 1. 基础信息
        basic_info = self._build_basic_info(project)
        if basic_info:
            sections.append(basic_info)

        # 2. 卷结构
        volumes = self._build_volumes(project)
        if volumes:
            sections.append(volumes)

        # 3. 世界观设定
        world_setting = self._build_world_setting(project)
        if world_setting:
            sections.append(world_setting)

        # 4. 角色信息
        characters = self._build_characters(project)
        if characters:
            sections.append(characters)

        # 5. 关系网络
        relationships = self._build_relationships(project)
        if relationships:
            sections.append(relationships)

        # 6. 章节大纲
        outlines = self._build_outlines(project)
        if outlines:
            sections.append(outlines)

        # 7. 已完成章节摘要
        summaries = self._build_chapter_summaries(project)
        if summaries:
            sections.append(summaries)

        # 8. 伏笔系统
        foreshadowing = self._build_foreshadowing(project)
        if foreshadowing:
            sections.append(foreshadowing)

        # 9. 作者备忘录
        author_notes = await self._build_author_notes(project_id)
        if author_notes:
            sections.append(author_notes)

        # 10. 角色状态（数值流）
        character_states = await self._build_character_states(project_id)
        if character_states:
            sections.append(character_states)

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

    def _build_progress_stats(self, project) -> Optional[str]:
        """构建创作进度统计部分。

        让 Agent 了解小说的完成情况，以便给出针对性的建议。
        """
        # 统计各项数据
        character_count = len(project.characters) if project.characters else 0
        relationship_count = len(project.relationships_) if project.relationships_ else 0
        outline_count = len(project.outlines) if project.outlines else 0
        volume_count = len(project.volumes) if project.volumes else 0

        # 统计已有正文的章节
        chapters_with_content = 0
        total_word_count = 0
        if project.outlines:
            for outline in project.outlines:
                if outline.content and outline.content.strip():
                    chapters_with_content += 1
                    total_word_count += len(outline.content)

        # 统计伏笔（伏笔在 blueprint.foreshadowing 中，是 JSON 格式）
        foreshadowing_count = 0
        revealed_count = 0
        blueprint = project.blueprint
        if blueprint and blueprint.foreshadowing:
            foreshadowing_data = blueprint.foreshadowing
            if isinstance(foreshadowing_data, list):
                for f in foreshadowing_data:
                    foreshadowing_count += 1
                    if isinstance(f, dict) and f.get("status") == "revealed":
                        revealed_count += 1

        # 判断创作阶段
        if character_count == 0 and outline_count == 0:
            stage = "🌱 初创期"
            stage_hint = "小说刚刚开始，建议先完善角色和基础设定"
        elif outline_count == 0:
            stage = "🎭 设定期"
            stage_hint = "角色已有雏形，建议开始规划章节大纲"
        elif chapters_with_content == 0:
            stage = "📋 规划期"
            stage_hint = "大纲已有规划，可以开始创作正文"
        elif chapters_with_content < outline_count * 0.3:
            stage = "✍️ 起步期"
            stage_hint = f"已完成 {chapters_with_content}/{outline_count} 章正文"
        elif chapters_with_content < outline_count * 0.7:
            stage = "📖 创作中期"
            stage_hint = f"已完成 {chapters_with_content}/{outline_count} 章正文，进展顺利"
        else:
            stage = "🏁 收尾期"
            stage_hint = f"已完成 {chapters_with_content}/{outline_count} 章正文，接近完成"

        # 构建输出
        lines = ["## 📊 创作进度", ""]
        lines.append(f"**当前阶段**: {stage}")
        lines.append(f"**阶段提示**: {stage_hint}")
        lines.append("")

        # 统计表格
        lines.append("| 维度 | 数量 | 状态 |")
        lines.append("|------|------|------|")

        # 角色
        if character_count == 0:
            lines.append("| 角色 | 0 | ⚠️ 需要创建 |")
        elif character_count < 3:
            lines.append(f"| 角色 | {character_count} | ⚠️ 建议补充 |")
        else:
            lines.append(f"| 角色 | {character_count} | ✅ |")

        # 关系
        if character_count > 1 and relationship_count == 0:
            lines.append("| 关系 | 0 | ⚠️ 建议建立 |")
        else:
            lines.append(f"| 关系 | {relationship_count} | ✅ |")

        # 大纲
        if outline_count == 0:
            lines.append("| 大纲 | 0 | ⚠️ 需要规划 |")
        else:
            lines.append(f"| 大纲 | {outline_count} 章 | ✅ |")

        # 正文
        if outline_count > 0:
            if chapters_with_content == 0:
                lines.append("| 正文 | 0 | ⚠️ 待创作 |")
            else:
                pct = int(chapters_with_content / outline_count * 100)
                lines.append(f"| 正文 | {chapters_with_content}/{outline_count} 章 ({pct}%) | ✅ |")

        # 伏笔
        if foreshadowing_count > 0:
            unrevealed = foreshadowing_count - revealed_count
            if unrevealed > 0:
                lines.append(f"| 伏笔 | {foreshadowing_count} 个 ({unrevealed} 待回收) | ⚠️ |")
            else:
                lines.append(f"| 伏笔 | {foreshadowing_count} 个 | ✅ |")

        # 字数
        if total_word_count > 0:
            if total_word_count >= 10000:
                lines.append(f"| 总字数 | {total_word_count // 10000}.{(total_word_count % 10000) // 1000}万字 | - |")
            else:
                lines.append(f"| 总字数 | {total_word_count} 字 | - |")

        return "\n".join(lines)

    def _build_volumes(self, project) -> Optional[str]:
        """构建卷结构部分。"""
        volumes_list = project.volumes
        if not volumes_list:
            return None

        lines = ["## 卷结构", ""]
        lines.append(f"**说明**: 本小说共规划 {len(volumes_list)} 卷")
        lines.append("")

        for vol in volumes_list:
            volume_number = vol.volume_number
            title = vol.title or f"第{volume_number}卷"
            status = vol.status or "planned"
            status_mark = {"completed": "✅", "in_progress": "📝", "planned": "📋"}.get(status, "📋")

            # 统计该卷下的章节数量
            chapter_count = len(vol.outlines) if vol.outlines else 0

            lines.append(f"### {status_mark} 第{volume_number}卷：{title}")
            lines.append(f"- **已分配章节数**: {chapter_count}")

            if vol.summary:
                summary = vol.summary
                if len(summary) > 200:
                    summary = summary[:200] + "..."
                lines.append(f"- **卷概要**: {summary}")

            if vol.core_conflict:
                lines.append(f"- **核心冲突**: {vol.core_conflict}")

            if vol.climax:
                lines.append(f"- **高潮点**: {vol.climax}")

            lines.append("")

        result = "\n".join(lines)
        if len(result) > self.MAX_VOLUMES_LENGTH:
            result = result[:self.MAX_VOLUMES_LENGTH] + "\n...(卷信息过多，已截断)"

        return result

    def _build_foreshadowing(self, project) -> Optional[str]:
        """构建伏笔系统部分。"""
        blueprint = project.blueprint
        if not blueprint or not blueprint.foreshadowing:
            return None

        foreshadowing_data = blueprint.foreshadowing
        if isinstance(foreshadowing_data, str):
            try:
                foreshadowing_data = json.loads(foreshadowing_data)
            except json.JSONDecodeError:
                return None

        threads = foreshadowing_data.get("threads", [])
        if not threads:
            return None

        # 分类伏笔
        active_threads = [t for t in threads if t.get("status") == "active"]
        revealed_threads = [t for t in threads if t.get("status") == "revealed"]

        lines = ["## 伏笔系统", ""]
        lines.append(f"**统计**: 活跃伏笔 {len(active_threads)} 条，已揭示 {len(revealed_threads)} 条")
        lines.append("")

        if active_threads:
            lines.append("### 🔮 活跃伏笔（待回收）")
            for thread in active_threads:
                title = thread.get("title", "未命名伏笔")
                plant_chapter = thread.get("plant_chapter", "?")
                reveal_chapter = thread.get("reveal_chapter", "?")
                lines.append(f"- **{title}**")
                lines.append(f"  - 埋设: 第{plant_chapter}章 → 预计揭示: 第{reveal_chapter}章")

                clues = thread.get("clues", [])
                if clues:
                    clue_texts = [f"第{c.get('chapter', '?')}章" for c in clues[:3]]
                    lines.append(f"  - 已埋线索: {', '.join(clue_texts)}")

                if thread.get("description"):
                    desc = thread["description"]
                    if len(desc) > 100:
                        desc = desc[:100] + "..."
                    lines.append(f"  - 描述: {desc}")
            lines.append("")

        if revealed_threads:
            lines.append("### ✅ 已揭示伏笔")
            for thread in revealed_threads[:5]:  # 只显示最近5条
                title = thread.get("title", "未命名伏笔")
                actual_reveal = thread.get("actual_reveal_chapter", thread.get("reveal_chapter", "?"))
                lines.append(f"- **{title}** (第{actual_reveal}章揭示)")
            lines.append("")

        result = "\n".join(lines)
        if len(result) > self.MAX_FORESHADOWING_LENGTH:
            result = result[:self.MAX_FORESHADOWING_LENGTH] + "\n...(伏笔过多，已截断)"

        return result

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

        # 获取章节状态：完成、待选择、未开始
        completed_chapters = set()
        pending_selection_chapters = set()
        if project.chapters:
            for ch in project.chapters:
                if ch.status == "successful" and ch.selected_version:
                    completed_chapters.add(ch.chapter_number)
                elif ch.versions and len(ch.versions) > 0 and not ch.selected_version:
                    # 有版本但未选择
                    pending_selection_chapters.add(ch.chapter_number)

        total_outlines = len(outlines)
        lines = ["## 章节大纲（规划）", ""]
        lines.append(f"**说明**: 以下是章节规划大纲，不是已写完的内容。")
        lines.append(f"**当前进度**: 共规划 {total_outlines} 章，已完成 {len(completed_chapters)} 章，待选择版本 {len(pending_selection_chapters)} 章")
        lines.append("")

        # 逐条构建，检测是否会超出限制
        displayed_count = 0
        for outline in outlines:
            title = outline.title or f"第{outline.chapter_number}章"
            summary = outline.summary or "(暂无摘要)"
            if len(summary) > 150:
                summary = summary[:150] + "..."

            # 标注完成状态：✅已完成 ⏳待选择版本 📝未开始
            if outline.chapter_number in completed_chapters:
                status_mark = "✅"
            elif outline.chapter_number in pending_selection_chapters:
                status_mark = "⏳"
            else:
                status_mark = "📝"

            new_line = f"- {status_mark} **第{outline.chapter_number}章 - {title}**: {summary}"

            # 检查添加这行后是否会超出限制（预留截断提示的空间）
            current_result = "\n".join(lines + [new_line])
            if len(current_result) > self.MAX_OUTLINES_LENGTH - 300:
                # 即将超出限制，添加截断提示并停止
                truncated_from = outline.chapter_number
                truncated_to = outlines[-1].chapter_number
                lines.append("")
                lines.append(f"⚠️ **大纲已截断**: 第{truncated_from}章 至 第{truncated_to}章 未显示（共 {total_outlines - displayed_count} 章）")
                lines.append(f"💡 **提示**: 上方已显示第1章至第{displayed_count}章。如需查看后续章节大纲，请直接向用户询问具体章节范围，或使用 `search_content` 工具搜索相关剧情。")
                break

            lines.append(new_line)
            displayed_count += 1

        return "\n".join(lines)

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

    async def _build_author_notes(self, project_id: str) -> Optional[str]:
        """构建作者备忘录部分。

        Args:
            project_id: 项目 ID

        Returns:
            格式化的备忘录文本
        """
        from ...repositories.author_notes_repository import AuthorNoteRepository
        from ...models.novel import Volume
        from sqlalchemy import select

        repo = AuthorNoteRepository(self.session)
        notes = await repo.list_by_project(project_id, active_only=True)

        if not notes:
            return None

        # 获取卷名称映射
        volume_ids = [n.volume_id for n in notes if n.volume_id]
        volume_names = {}
        if volume_ids:
            vol_stmt = select(Volume).where(Volume.id.in_(volume_ids))
            vol_result = await self.session.execute(vol_stmt)
            volume_names = {v.id: v.title for v in vol_result.scalars().all()}

        # 按类型分组
        notes_by_type = {}
        for note in notes:
            note_type = note.type
            if note_type not in notes_by_type:
                notes_by_type[note_type] = []
            notes_by_type[note_type].append(note)

        # 类型显示名称映射
        from ...executors.gm.author_notes.add_author_note import NOTE_TYPE_DISPLAY

        lines = ["## 作者备忘录", ""]
        lines.append("**说明**: 以下是作者的私人笔记，用于指导写作方向，请在创作时考虑这些信息。")
        lines.append("")

        for note_type, type_notes in notes_by_type.items():
            type_name = NOTE_TYPE_DISPLAY.get(note_type, note_type)
            lines.append(f"### {type_name}")

            for note in type_notes[:10]:  # 每类最多 10 条
                title = note.title
                content = note.content
                if len(content) > 150:
                    content = content[:150] + "..."

                lines.append(f"- **{title}**")

                # 显示关联信息
                scope_parts = []
                if note.chapter_number:
                    scope_parts.append(f"第{note.chapter_number}章")
                if note.volume_id:
                    vol_name = volume_names.get(note.volume_id, f"卷#{note.volume_id}")
                    scope_parts.append(f"{vol_name}")
                if scope_parts:
                    lines.append(f"  - 关联: {', '.join(scope_parts)}")

                lines.append(f"  - {content}")

            if len(type_notes) > 10:
                lines.append(f"  _(还有 {len(type_notes) - 10} 条未显示)_")
            lines.append("")

        result = "\n".join(lines)
        if len(result) > self.MAX_AUTHOR_NOTES_LENGTH:
            result = result[:self.MAX_AUTHOR_NOTES_LENGTH] + "\n...(备忘录过多，已截断)"

        return result

    async def _build_character_states(self, project_id: str) -> Optional[str]:
        """构建角色状态部分（数值流小说）。

        Args:
            project_id: 项目 ID

        Returns:
            格式化的角色状态文本
        """
        from ...repositories.author_notes_repository import CharacterStateRepository
        from ...models.novel import BlueprintCharacter
        from sqlalchemy import select

        state_repo = CharacterStateRepository(self.session)
        states = await state_repo.list_latest_states_for_project(project_id)

        if not states:
            return None

        # 获取角色名称映射
        char_ids = [s.character_id for s in states]
        char_stmt = select(BlueprintCharacter).where(BlueprintCharacter.id.in_(char_ids))
        char_result = await self.session.execute(char_stmt)
        characters = {c.id: c.name for c in char_result.scalars().all()}

        lines = ["## 角色当前状态", ""]
        lines.append("**说明**: 以下是各角色的最新状态数据，请在创作时确保数值和设定的一致性。")
        lines.append("")

        for state in states:
            char_name = characters.get(state.character_id, f"角色#{state.character_id}")
            lines.append(f"### {char_name} (截至第{state.chapter_number}章)")

            # 格式化状态数据
            data = state.data
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, str) and len(value) > 100:
                        value = value[:100] + "..."
                    lines.append(f"- **{key}**: {value}")
            else:
                lines.append(f"- {data}")

            if state.change_note:
                note = state.change_note
                if len(note) > 100:
                    note = note[:100] + "..."
                lines.append(f"- _变更说明: {note}_")

            lines.append("")

        result = "\n".join(lines)
        if len(result) > self.MAX_CHARACTER_STATES_LENGTH:
            result = result[:self.MAX_CHARACTER_STATES_LENGTH] + "\n...(状态数据过多，已截断)"

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

    # ========================================================================
    # 快照与变更检测
    # ========================================================================

    async def build_snapshot(self, project_id: str) -> ContextSnapshot:
        """构建上下文快照（用于变更对比）。

        Args:
            project_id: 项目 ID

        Returns:
            ContextSnapshot 结构化快照
        """
        from ...repositories.novel_repository import NovelRepository

        repo = NovelRepository(self.session)
        project = await repo.get_by_id(project_id)

        snapshot = ContextSnapshot()

        if not project:
            return snapshot

        # 角色快照
        if project.characters:
            for char in project.characters:
                snapshot.characters[char.name] = {
                    "identity": char.identity or "",
                    "personality": char.personality or "",
                    "goals": char.goals or "",
                    "abilities": char.abilities or "",
                    "relationship_to_protagonist": char.relationship_to_protagonist or "",
                }

        # 关系快照
        if project.relationships_:
            for rel in project.relationships_:
                key = (rel.character_from, rel.character_to)
                snapshot.relationships[key] = rel.description or ""

        # 大纲快照
        if project.outlines:
            for outline in project.outlines:
                snapshot.outlines[outline.chapter_number] = {
                    "title": outline.title or "",
                    "summary": outline.summary or "",
                    "volume_number": outline.volume.volume_number if outline.volume else None,
                }

        # 卷快照
        if project.volumes:
            for vol in project.volumes:
                snapshot.volumes[vol.volume_number] = {
                    "title": vol.title or "",
                    "summary": vol.summary or "",
                    "status": vol.status or "",
                    "chapter_count": len(vol.outlines) if vol.outlines else 0,
                }

        return snapshot

    @staticmethod
    def compare_snapshots(
        old_snapshot: Optional[ContextSnapshot],
        new_snapshot: ContextSnapshot,
    ) -> ContextDiff:
        """对比两个快照，返回变更记录。

        Args:
            old_snapshot: 旧快照（首次调用时为 None）
            new_snapshot: 新快照

        Returns:
            ContextDiff 变更记录
        """
        diff = ContextDiff()

        if old_snapshot is None:
            # 首次调用，无变更
            return diff

        # 对比角色
        old_chars = set(old_snapshot.characters.keys())
        new_chars = set(new_snapshot.characters.keys())

        diff.characters_added = list(new_chars - old_chars)
        diff.characters_removed = list(old_chars - new_chars)

        # 检查修改（存在于两者中的角色）
        for name in old_chars & new_chars:
            if old_snapshot.characters[name] != new_snapshot.characters[name]:
                diff.characters_modified.append(name)

        # 对比关系
        old_rels = set(old_snapshot.relationships.keys())
        new_rels = set(new_snapshot.relationships.keys())

        diff.relationships_added = list(new_rels - old_rels)
        diff.relationships_removed = list(old_rels - new_rels)

        for key in old_rels & new_rels:
            if old_snapshot.relationships[key] != new_snapshot.relationships[key]:
                diff.relationships_modified.append(key)

        # 对比大纲
        old_outlines = set(old_snapshot.outlines.keys())
        new_outlines = set(new_snapshot.outlines.keys())

        diff.outlines_added = list(new_outlines - old_outlines)
        diff.outlines_removed = list(old_outlines - new_outlines)

        for ch_num in old_outlines & new_outlines:
            if old_snapshot.outlines[ch_num] != new_snapshot.outlines[ch_num]:
                diff.outlines_modified.append(ch_num)

        # 对比卷
        old_vols = set(old_snapshot.volumes.keys())
        new_vols = set(new_snapshot.volumes.keys())

        diff.volumes_added = list(new_vols - old_vols)
        diff.volumes_removed = list(old_vols - new_vols)

        for vol_num in old_vols & new_vols:
            if old_snapshot.volumes[vol_num] != new_snapshot.volumes[vol_num]:
                diff.volumes_modified.append(vol_num)

        return diff

    async def build_with_diff(
        self,
        project_id: str,
        previous_snapshot: Optional[ContextSnapshot] = None,
    ) -> Tuple[str, ContextSnapshot, Optional[str]]:
        """构建上下文，同时返回快照和变更说明。

        Args:
            project_id: 项目 ID
            previous_snapshot: 上一次的快照（用于对比）

        Returns:
            tuple: (context_text, new_snapshot, diff_markdown)
            - context_text: 完整上下文文本
            - new_snapshot: 新的快照（调用方应保存用于下次对比）
            - diff_markdown: 变更说明（无变更时为 None）
        """
        # 构建新快照
        new_snapshot = await self.build_snapshot(project_id)

        # 构建上下文文本
        context = await self.build(project_id)

        # 对比变更
        diff = self.compare_snapshots(previous_snapshot, new_snapshot)

        diff_markdown = diff.to_markdown() if diff.has_changes() else None

        return context, new_snapshot, diff_markdown

"""作者备忘录和角色状态仓储层。"""

from typing import List, Optional

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from ..models.author_notes import AuthorNote, AuthorNoteType, CharacterState, StateTemplate, GenerationContext


class AuthorNoteRepository(BaseRepository[AuthorNote]):
    """作者备忘录仓储。"""

    model = AuthorNote

    async def list_by_project(
        self,
        project_id: str,
        note_type: Optional[str] = None,
        active_only: bool = True,
    ) -> List[AuthorNote]:
        """获取项目的备忘录列表。

        Args:
            project_id: 项目 ID
            note_type: 备忘录类型（可选过滤）
            active_only: 是否只返回有效的备忘录

        Returns:
            备忘录列表
        """
        conditions = [AuthorNote.project_id == project_id]

        if note_type:
            conditions.append(AuthorNote.type == note_type)

        if active_only:
            conditions.append(AuthorNote.is_active == True)

        stmt = (
            select(AuthorNote)
            .where(and_(*conditions))
            .order_by(desc(AuthorNote.priority), desc(AuthorNote.created_at))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_chapter(
        self,
        project_id: str,
        chapter_number: int,
    ) -> List[AuthorNote]:
        """获取指定章节的备忘录。

        Args:
            project_id: 项目 ID
            chapter_number: 章节号

        Returns:
            章节备忘录列表
        """
        stmt = (
            select(AuthorNote)
            .where(
                and_(
                    AuthorNote.project_id == project_id,
                    AuthorNote.type == AuthorNoteType.CHAPTER,
                    AuthorNote.chapter_number == chapter_number,
                    AuthorNote.is_active == True,
                )
            )
            .order_by(desc(AuthorNote.created_at))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_volume(
        self,
        project_id: str,
        volume_id: int,
    ) -> List[AuthorNote]:
        """获取指定卷的备忘录。

        Args:
            project_id: 项目 ID
            volume_id: 卷 ID

        Returns:
            卷备忘录列表
        """
        stmt = (
            select(AuthorNote)
            .where(
                and_(
                    AuthorNote.project_id == project_id,
                    AuthorNote.volume_id == volume_id,
                    AuthorNote.is_active == True,
                )
            )
            .order_by(desc(AuthorNote.priority), desc(AuthorNote.created_at))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_chapter_generation(
        self,
        project_id: str,
        chapter_number: int,
        volume_id: Optional[int] = None,
    ) -> List[AuthorNote]:
        """获取章节生成时应自动注入的备忘录。

        包括：
        1. 全局备忘录（type=global）
        2. 绑定到当前章节的备忘录
        3. 绑定到当前卷的备忘录（如果有 volume_id）

        Args:
            project_id: 项目 ID
            chapter_number: 章节号
            volume_id: 卷 ID（可选）

        Returns:
            应注入的备忘录列表
        """
        from sqlalchemy import or_

        # 构建条件：全局 OR 当前章节 OR 当前卷
        conditions = [
            AuthorNote.project_id == project_id,
            AuthorNote.is_active == True,
        ]

        scope_conditions = [
            AuthorNote.type == AuthorNoteType.GLOBAL,  # 全局备忘录
            AuthorNote.chapter_number == chapter_number,  # 绑定到当前章节
        ]

        if volume_id:
            scope_conditions.append(AuthorNote.volume_id == volume_id)  # 绑定到当前卷

        stmt = (
            select(AuthorNote)
            .where(
                and_(
                    *conditions,
                    or_(*scope_conditions)
                )
            )
            .order_by(desc(AuthorNote.priority), desc(AuthorNote.created_at))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_character(
        self,
        character_id: int,
    ) -> List[AuthorNote]:
        """获取指定角色的秘密备忘。

        Args:
            character_id: 角色 ID

        Returns:
            角色秘密列表
        """
        stmt = (
            select(AuthorNote)
            .where(
                and_(
                    AuthorNote.character_id == character_id,
                    AuthorNote.type == AuthorNoteType.CHARACTER_SECRET,
                    AuthorNote.is_active == True,
                )
            )
            .order_by(desc(AuthorNote.created_at))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_ids(self, note_ids: List[int]) -> List[AuthorNote]:
        """根据 ID 列表获取备忘录。

        Args:
            note_ids: 备忘录 ID 列表

        Returns:
            备忘录列表
        """
        if not note_ids:
            return []

        stmt = select(AuthorNote).where(AuthorNote.id.in_(note_ids))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class CharacterStateRepository(BaseRepository[CharacterState]):
    """角色状态快照仓储。"""

    model = CharacterState

    async def get_latest_state(
        self,
        character_id: int,
        before_chapter: Optional[int] = None,
    ) -> Optional[CharacterState]:
        """获取角色的最新状态。

        Args:
            character_id: 角色 ID
            before_chapter: 在此章节之前的状态（可选）

        Returns:
            最新的状态快照
        """
        conditions = [CharacterState.character_id == character_id]

        if before_chapter is not None:
            conditions.append(CharacterState.chapter_number < before_chapter)

        stmt = (
            select(CharacterState)
            .where(and_(*conditions))
            .order_by(desc(CharacterState.chapter_number))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_state_at_chapter(
        self,
        character_id: int,
        chapter_number: int,
    ) -> Optional[CharacterState]:
        """获取角色在指定章节的状态。

        Args:
            character_id: 角色 ID
            chapter_number: 章节号

        Returns:
            状态快照
        """
        stmt = select(CharacterState).where(
            and_(
                CharacterState.character_id == character_id,
                CharacterState.chapter_number == chapter_number,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_character(
        self,
        character_id: int,
    ) -> List[CharacterState]:
        """获取角色的所有状态历史。

        Args:
            character_id: 角色 ID

        Returns:
            状态快照列表（按章节升序）
        """
        stmt = (
            select(CharacterState)
            .where(CharacterState.character_id == character_id)
            .order_by(CharacterState.chapter_number)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_latest_states_for_project(
        self,
        project_id: str,
        before_chapter: Optional[int] = None,
    ) -> List[CharacterState]:
        """获取项目中所有角色的最新状态。

        Args:
            project_id: 项目 ID
            before_chapter: 在此章节之前的状态（可选）

        Returns:
            各角色的最新状态列表
        """
        from ..models.novel import BlueprintCharacter

        # 先获取项目的所有角色 ID
        char_stmt = select(BlueprintCharacter.id).where(
            BlueprintCharacter.project_id == project_id
        )
        char_result = await self.session.execute(char_stmt)
        character_ids = [row[0] for row in char_result.all()]

        if not character_ids:
            return []

        # 获取每个角色的最新状态
        states = []
        for char_id in character_ids:
            state = await self.get_latest_state(char_id, before_chapter)
            if state:
                states.append(state)

        return states

    async def upsert_state(
        self,
        character_id: int,
        chapter_number: int,
        data: dict,
        change_note: Optional[str] = None,
    ) -> CharacterState:
        """更新或插入角色状态。

        Args:
            character_id: 角色 ID
            chapter_number: 章节号
            data: 状态数据
            change_note: 变更说明

        Returns:
            状态快照
        """
        existing = await self.get_state_at_chapter(character_id, chapter_number)

        if existing:
            existing.data = data
            existing.change_note = change_note
            await self.session.flush()
            return existing
        else:
            new_state = CharacterState(
                character_id=character_id,
                chapter_number=chapter_number,
                data=data,
                change_note=change_note,
            )
            return await self.add(new_state)

    async def get_by_ids(self, state_ids: List[int]) -> List[CharacterState]:
        """根据 ID 列表获取状态快照。

        Args:
            state_ids: 状态 ID 列表

        Returns:
            状态快照列表
        """
        if not state_ids:
            return []

        stmt = select(CharacterState).where(CharacterState.id.in_(state_ids))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class StateTemplateRepository(BaseRepository[StateTemplate]):
    """状态模板仓储。"""

    model = StateTemplate

    async def list_all(self) -> List[StateTemplate]:
        """获取所有模板。"""
        stmt = select(StateTemplate).order_by(StateTemplate.is_system.desc(), StateTemplate.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_name(self, name: str) -> Optional[StateTemplate]:
        """根据名称获取模板。"""
        return await self.get(name=name)


class GenerationContextRepository(BaseRepository[GenerationContext]):
    """生成上下文仓储。"""

    model = GenerationContext

    async def get_latest_for_chapter(self, chapter_id: int) -> Optional[GenerationContext]:
        """获取章节的最新生成上下文。"""
        stmt = (
            select(GenerationContext)
            .where(GenerationContext.chapter_id == chapter_id)
            .order_by(desc(GenerationContext.created_at))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

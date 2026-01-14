"""作者备忘录和角色状态 API 路由。"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...models.author_notes import AuthorNote, CharacterState, StateTemplate
from ...models.novel import BlueprintCharacter
from ...repositories.author_notes_repository import (
    AuthorNoteRepository,
    CharacterStateRepository,
    StateTemplateRepository,
)
from ...schemas.author_notes import (
    AuthorNoteCreate,
    AuthorNoteListResponse,
    AuthorNoteResponse,
    AuthorNoteUpdate,
    BatchDeleteRequest,
    BatchUpdateActiveRequest,
    CharacterStateCreate,
    CharacterStateResponse,
    CharacterStatesListResponse,
    CharacterStateUpdate,
    CharacterStateWithName,
    GenerationContextOptions,
    SelectableNote,
    SelectableState,
    StateTemplateCreate,
    StateTemplateListResponse,
    StateTemplateResponse,
)
from ...schemas.user import UserInDB
from ...services.novel_service import NovelService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/novels/{project_id}/notes", tags=["Author Notes"])


# ==================== 权限验证辅助函数 ====================

async def verify_project_access(
    project_id: str,
    session: AsyncSession,
    current_user: UserInDB,
) -> None:
    """验证用户对项目的访问权限。"""
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)


# ==================== 备忘录 CRUD ====================

@router.get("", response_model=AuthorNoteListResponse)
async def list_notes(
    project_id: str,
    note_type: Optional[str] = Query(None, description="按类型过滤"),
    active_only: bool = Query(True, description="是否只返回有效的备忘录"),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> AuthorNoteListResponse:
    """获取项目的备忘录列表。"""
    await verify_project_access(project_id, session, current_user)

    repo = AuthorNoteRepository(session)
    notes = await repo.list_by_project(project_id, note_type, active_only)

    return AuthorNoteListResponse(
        notes=[AuthorNoteResponse.model_validate(n) for n in notes],
        total=len(notes),
    )


@router.post("", response_model=AuthorNoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    project_id: str,
    data: AuthorNoteCreate,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> AuthorNoteResponse:
    """创建备忘录。"""
    await verify_project_access(project_id, session, current_user)

    note = AuthorNote(
        project_id=project_id,
        type=data.type.value,
        title=data.title,
        content=data.content,
        chapter_number=data.chapter_number,
        volume_id=data.volume_id,
        character_id=data.character_id,
        priority=data.priority,
    )

    repo = AuthorNoteRepository(session)
    await repo.add(note)
    await session.commit()

    logger.info("用户 %s 在项目 %s 创建备忘录 %s", current_user.id, project_id, note.id)
    return AuthorNoteResponse.model_validate(note)


@router.get("/{note_id}", response_model=AuthorNoteResponse)
async def get_note(
    project_id: str,
    note_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> AuthorNoteResponse:
    """获取单个备忘录。"""
    await verify_project_access(project_id, session, current_user)

    repo = AuthorNoteRepository(session)
    note = await repo.get(id=note_id, project_id=project_id)

    if not note:
        raise HTTPException(status_code=404, detail="备忘录不存在")

    return AuthorNoteResponse.model_validate(note)


@router.patch("/{note_id}", response_model=AuthorNoteResponse)
async def update_note(
    project_id: str,
    note_id: int,
    data: AuthorNoteUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> AuthorNoteResponse:
    """更新备忘录。"""
    await verify_project_access(project_id, session, current_user)

    repo = AuthorNoteRepository(session)
    note = await repo.get(id=note_id, project_id=project_id)

    if not note:
        raise HTTPException(status_code=404, detail="备忘录不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(note, key, value)

    await session.commit()

    logger.info("用户 %s 更新备忘录 %s", current_user.id, note_id)
    return AuthorNoteResponse.model_validate(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    project_id: str,
    note_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> None:
    """删除备忘录。"""
    await verify_project_access(project_id, session, current_user)

    repo = AuthorNoteRepository(session)
    note = await repo.get(id=note_id, project_id=project_id)

    if not note:
        raise HTTPException(status_code=404, detail="备忘录不存在")

    await repo.delete(note)
    await session.commit()

    logger.info("用户 %s 删除备忘录 %s", current_user.id, note_id)


@router.post("/batch-delete", status_code=status.HTTP_204_NO_CONTENT)
async def batch_delete_notes(
    project_id: str,
    data: BatchDeleteRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> None:
    """批量删除备忘录。"""
    await verify_project_access(project_id, session, current_user)

    repo = AuthorNoteRepository(session)
    notes = await repo.get_by_ids(data.ids)

    for note in notes:
        if note.project_id == project_id:
            await repo.delete(note)

    await session.commit()
    logger.info("用户 %s 批量删除备忘录 %s", current_user.id, data.ids)


@router.post("/batch-update-active")
async def batch_update_active(
    project_id: str,
    data: BatchUpdateActiveRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> dict:
    """批量更新备忘录激活状态。"""
    await verify_project_access(project_id, session, current_user)

    repo = AuthorNoteRepository(session)
    notes = await repo.get_by_ids(data.ids)

    updated = 0
    for note in notes:
        if note.project_id == project_id:
            note.is_active = data.is_active
            updated += 1

    await session.commit()
    logger.info("用户 %s 批量更新备忘录状态 %s -> %s", current_user.id, data.ids, data.is_active)
    return {"updated": updated}


# ==================== 角色状态 CRUD ====================

states_router = APIRouter(prefix="/api/novels/{project_id}/states", tags=["Character States"])


@states_router.get("", response_model=CharacterStatesListResponse)
async def list_states(
    project_id: str,
    chapter_number: Optional[int] = Query(None, description="获取指定章节之前的最新状态"),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> CharacterStatesListResponse:
    """获取项目中所有角色的最新状态。"""
    await verify_project_access(project_id, session, current_user)

    repo = CharacterStateRepository(session)
    states = await repo.list_latest_states_for_project(project_id, chapter_number)

    # 获取角色名称
    from sqlalchemy import select
    char_stmt = select(BlueprintCharacter).where(BlueprintCharacter.project_id == project_id)
    result = await session.execute(char_stmt)
    characters = {c.id: c.name for c in result.scalars().all()}

    response_states = []
    for state in states:
        char_name = characters.get(state.character_id, "未知角色")
        response_states.append(
            CharacterStateWithName(
                id=state.id,
                character_id=state.character_id,
                chapter_number=state.chapter_number,
                data=state.data,
                change_note=state.change_note,
                created_at=state.created_at,
                character_name=char_name,
            )
        )

    return CharacterStatesListResponse(states=response_states)


@states_router.get("/character/{character_id}", response_model=List[CharacterStateResponse])
async def list_character_states(
    project_id: str,
    character_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> List[CharacterStateResponse]:
    """获取指定角色的状态历史。"""
    await verify_project_access(project_id, session, current_user)

    repo = CharacterStateRepository(session)
    states = await repo.list_by_character(character_id)

    return [CharacterStateResponse.model_validate(s) for s in states]


@states_router.post("", response_model=CharacterStateResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_state(
    project_id: str,
    data: CharacterStateCreate,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> CharacterStateResponse:
    """创建或更新角色状态。"""
    await verify_project_access(project_id, session, current_user)

    repo = CharacterStateRepository(session)
    state = await repo.upsert_state(
        character_id=data.character_id,
        chapter_number=data.chapter_number,
        data=data.data,
        change_note=data.change_note,
    )
    await session.commit()

    logger.info(
        "用户 %s 更新角色 %s 在第 %s 章的状态",
        current_user.id,
        data.character_id,
        data.chapter_number,
    )
    return CharacterStateResponse.model_validate(state)


@states_router.patch("/{state_id}", response_model=CharacterStateResponse)
async def update_state(
    project_id: str,
    state_id: int,
    data: CharacterStateUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> CharacterStateResponse:
    """更新角色状态。"""
    await verify_project_access(project_id, session, current_user)

    repo = CharacterStateRepository(session)
    state = await repo.get(id=state_id)

    if not state:
        raise HTTPException(status_code=404, detail="状态不存在")

    if data.data is not None:
        state.data = data.data
    if data.change_note is not None:
        state.change_note = data.change_note

    await session.commit()

    logger.info("用户 %s 更新状态 %s", current_user.id, state_id)
    return CharacterStateResponse.model_validate(state)


@states_router.delete("/{state_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_state(
    project_id: str,
    state_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> None:
    """删除角色状态。"""
    await verify_project_access(project_id, session, current_user)

    repo = CharacterStateRepository(session)
    state = await repo.get(id=state_id)

    if not state:
        raise HTTPException(status_code=404, detail="状态不存在")

    await repo.delete(state)
    await session.commit()

    logger.info("用户 %s 删除状态 %s", current_user.id, state_id)


# ==================== 生成上下文选项 ====================

context_router = APIRouter(prefix="/api/novels/{project_id}/generation-context", tags=["Generation Context"])


@context_router.get("/options", response_model=GenerationContextOptions)
async def get_generation_context_options(
    project_id: str,
    chapter_number: int = Query(..., description="要生成的章节号"),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> GenerationContextOptions:
    """获取生成章节时可选择的上下文。

    返回所有可勾选的备忘录和角色状态，以及推荐勾选的项。
    """
    await verify_project_access(project_id, session, current_user)

    note_repo = AuthorNoteRepository(session)
    state_repo = CharacterStateRepository(session)

    # 获取所有备忘录
    notes = await note_repo.list_by_project(project_id, active_only=True)

    # 获取角色信息
    from sqlalchemy import select
    char_stmt = select(BlueprintCharacter).where(BlueprintCharacter.project_id == project_id)
    result = await session.execute(char_stmt)
    characters = {c.id: c.name for c in result.scalars().all()}

    # 转换为可选择格式
    selectable_notes = []
    recommended_note_ids = []

    for note in notes:
        is_recommended = False

        # 推荐逻辑：
        # 1. 上一章的备忘自动推荐
        if note.type == "chapter" and note.chapter_number == chapter_number - 1:
            is_recommended = True
        # 2. 写作风格总是推荐
        elif note.type == "style":
            is_recommended = True
        # 3. 高优先级的全局备忘推荐
        elif note.type == "global" and note.priority > 0:
            is_recommended = True

        if is_recommended:
            recommended_note_ids.append(note.id)

        selectable_notes.append(
            SelectableNote(
                id=note.id,
                type=note.type,
                title=note.title,
                content=note.content,
                chapter_number=note.chapter_number,
                volume_id=note.volume_id,
                character_name=characters.get(note.character_id) if note.character_id else None,
                is_recommended=is_recommended,
            )
        )

    # 获取角色最新状态
    states = await state_repo.list_latest_states_for_project(project_id, chapter_number)

    selectable_states = []
    recommended_state_ids = []

    for state in states:
        char_name = characters.get(state.character_id, "未知角色")

        # 生成状态摘要
        summary_parts = []
        data = state.data or {}
        if "level" in data or "等级" in data:
            level = data.get("level") or data.get("等级")
            summary_parts.append(f"Lv{level}")
        if "境界" in data:
            summary_parts.append(data["境界"])
        # 可以添加更多摘要规则

        summary = " ".join(summary_parts) if summary_parts else f"第{state.chapter_number}章状态"

        # 所有状态都推荐勾选
        recommended_state_ids.append(state.id)

        selectable_states.append(
            SelectableState(
                id=state.id,
                character_id=state.character_id,
                character_name=char_name,
                chapter_number=state.chapter_number,
                data=state.data,
                summary=summary,
            )
        )

    return GenerationContextOptions(
        notes=selectable_notes,
        states=selectable_states,
        recommended_note_ids=recommended_note_ids,
        recommended_state_ids=recommended_state_ids,
    )


# ==================== 状态模板 ====================

template_router = APIRouter(prefix="/api/state-templates", tags=["State Templates"])


@template_router.get("", response_model=StateTemplateListResponse)
async def list_templates(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> StateTemplateListResponse:
    """获取所有状态模板。"""
    repo = StateTemplateRepository(session)
    templates = await repo.list_all()
    return StateTemplateListResponse(
        templates=[StateTemplateResponse.model_validate(t) for t in templates]
    )


@template_router.post("", response_model=StateTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: StateTemplateCreate,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> StateTemplateResponse:
    """创建自定义状态模板（仅管理员）。"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可创建模板")

    template = StateTemplate(
        name=data.name,
        display_name=data.display_name,
        description=data.description,
        schema=data.schema,
        is_system=False,
    )

    repo = StateTemplateRepository(session)
    await repo.add(template)
    await session.commit()

    return StateTemplateResponse.model_validate(template)

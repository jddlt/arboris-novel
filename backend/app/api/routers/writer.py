import json
import logging
import os
from typing import Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...models.novel import Chapter, ChapterOutline
from ...schemas.novel import (
    DeleteChapterRequest,
    EditChapterRequest,
    EvaluateChapterRequest,
    GenerateChapterRequest,
    GenerateOutlineRequest,
    NovelProject as NovelProjectSchema,
    RefineVersionRequest,
    SelectVersionRequest,
    UpdateChapterOutlineRequest,
)
from ...schemas.user import UserInDB
from ...services.chapter_context_service import ChapterContextService
from ...services.chapter_ingest_service import ChapterIngestionService
from ...services.llm_service import LLMService
from ...services.novel_service import NovelService
from ...services.prompt_service import PromptService
from ...services.vector_store_service import VectorStoreService
from ...utils.json_utils import remove_think_tags, unwrap_markdown_json, strip_markdown_fences
from ...repositories.system_config_repository import SystemConfigRepository
from ...repositories.author_notes_repository import AuthorNoteRepository, CharacterStateRepository
from ...models.author_notes import GenerationContext

router = APIRouter(prefix="/api/writer", tags=["Writer"])
logger = logging.getLogger(__name__)


async def _load_project_schema(service: NovelService, project_id: str, user_id: int) -> NovelProjectSchema:
    return await service.get_project_schema(project_id, user_id)


def _extract_tail_excerpt(text: Optional[str], limit: int = 500) -> str:
    """截取章节结尾文本，默认保留 500 字。"""
    if not text:
        return ""
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[-limit:]


@router.post("/novels/{project_id}/chapters/generate", response_model=NovelProjectSchema)
async def generate_chapter(
    project_id: str,
    request: GenerateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info("用户 %s 开始为项目 %s 生成第 %s 章", current_user.id, project_id, request.chapter_number)
    outline = await novel_service.get_outline(project_id, request.chapter_number)
    if not outline:
        logger.warning("项目 %s 未找到第 %s 章纲要，生成流程终止", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="蓝图中未找到对应章节纲要")

    chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)
    chapter.real_summary = None
    chapter.selected_version_id = None
    chapter.status = "generating"
    await session.commit()

    outlines_map = {item.chapter_number: item for item in project.outlines}
    # 收集所有可用的历史章节摘要，便于在 Prompt 中提供前情背景
    completed_chapters = []
    latest_prev_number = -1
    previous_summary_text = ""
    previous_tail_excerpt = ""
    for existing in project.chapters:
        if existing.chapter_number >= request.chapter_number:
            continue
        if existing.selected_version is None or not existing.selected_version.content:
            continue
        if not existing.real_summary:
            summary = await llm_service.get_summary(
                existing.selected_version.content,
                temperature=0.15,
                user_id=current_user.id,
                timeout=180.0,
            )
            existing.real_summary = remove_think_tags(summary)
            await session.commit()
        completed_chapters.append(
            {
                "chapter_number": existing.chapter_number,
                "title": (ch_outline.title if (ch_outline := outlines_map.get(existing.chapter_number)) else f"第{existing.chapter_number}章"),
                "summary": existing.real_summary,
            }
        )
        if existing.chapter_number > latest_prev_number:
            latest_prev_number = existing.chapter_number
            previous_summary_text = existing.real_summary or ""
            previous_tail_excerpt = _extract_tail_excerpt(existing.selected_version.content)

    project_schema = await novel_service._serialize_project(project)
    if not project_schema.blueprint:
        raise HTTPException(status_code=400, detail="项目蓝图不存在，请先生成蓝图")
    blueprint_dict = project_schema.blueprint.model_dump()

    if "relationships" in blueprint_dict and blueprint_dict["relationships"]:
        for relation in blueprint_dict["relationships"]:
            if "character_from" in relation:
                relation["from"] = relation.pop("character_from")
            if "character_to" in relation:
                relation["to"] = relation.pop("character_to")

    # 蓝图中禁止携带章节级别的细节信息，避免重复传输大段场景或对话内容
    banned_blueprint_keys = {
        "chapter_outline",
        "chapter_summaries",
        "chapter_details",
        "chapter_dialogues",
        "chapter_events",
        "conversation_history",
        "character_timelines",
    }
    for key in banned_blueprint_keys:
        if key in blueprint_dict:
            blueprint_dict.pop(key, None)

    writer_prompt = await prompt_service.get_prompt("writing")
    if not writer_prompt:
        logger.error("未配置名为 'writing' 的写作提示词，无法生成章节内容")
        raise HTTPException(status_code=500, detail="缺少写作提示词，请联系管理员配置 'writing' 提示词")

    # 初始化向量检索服务，若未配置则自动降级为纯提示词生成
    vector_store: Optional[VectorStoreService]
    if not settings.vector_store_enabled:
        vector_store = None
    else:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，RAG 检索被禁用: %s", exc)
            vector_store = None
    context_service = ChapterContextService(llm_service=llm_service, vector_store=vector_store)

    outline_title = outline.title or f"第{outline.chapter_number}章"
    outline_summary = outline.summary or "暂无摘要"
    query_parts = [outline_title, outline_summary]
    if request.writing_notes:
        query_parts.append(request.writing_notes)
    rag_query = "\n".join(part for part in query_parts if part)
    rag_context = await context_service.retrieve_for_generation(
        project_id=project_id,
        query_text=rag_query or outline.title or outline.summary or "",
        user_id=current_user.id,
    )
    chunk_count = len(rag_context.chunks) if rag_context and rag_context.chunks else 0
    summary_count = len(rag_context.summaries) if rag_context and rag_context.summaries else 0
    logger.info(
        "项目 %s 第 %s 章检索到 %s 个剧情片段和 %s 条摘要",
        project_id,
        request.chapter_number,
        chunk_count,
        summary_count,
    )
    # print("rag_context:",rag_context)
    # 将蓝图、前情、RAG 检索结果拼装成结构化段落，供模型理解
    blueprint_text = json.dumps(blueprint_dict, ensure_ascii=False, indent=2)

    # 提取伏笔信息，单独注入让 AI 更好掌控全局
    foreshadowing_data = blueprint_dict.get("foreshadowing", {})
    foreshadowing_text = json.dumps(foreshadowing_data, ensure_ascii=False, indent=2) if foreshadowing_data else "暂无伏笔"

    # 找出当前章节所在的卷（通过 outline.volume 关联）
    current_volume_info = "未分配到卷"
    if outline.volume:
        vol = outline.volume
        current_volume_info = f"第{vol.volume_number}卷「{vol.title}」- 概要：{vol.summary or '未定义'}"

    # 找出与当前章节相关的伏笔（需要在本章埋设或揭示的）
    relevant_foreshadowing = []
    if foreshadowing_data and "threads" in foreshadowing_data:
        for thread in foreshadowing_data["threads"]:
            plant_ch = thread.get("plant_chapter", 0)
            reveal_ch = thread.get("reveal_chapter", 0)
            # 本章需要埋设或揭示的伏笔
            if plant_ch == request.chapter_number:
                relevant_foreshadowing.append(f"【埋设】{thread.get('title', '')}：{thread.get('description', '')}")
            elif reveal_ch == request.chapter_number:
                relevant_foreshadowing.append(f"【揭示】{thread.get('title', '')}：{thread.get('description', '')}")
            # 已埋设但未揭示的活跃伏笔（提醒 AI 可以添加线索）
            elif plant_ch < request.chapter_number < reveal_ch and thread.get("status") == "active":
                relevant_foreshadowing.append(f"【活跃-可添加线索】{thread.get('title', '')}")
    relevant_foreshadowing_text = "\n".join(relevant_foreshadowing) if relevant_foreshadowing else "本章无特定伏笔任务"

    completed_lines = [
        f"- 第{item['chapter_number']}章 - {item['title']}:{item['summary']}"
        for item in completed_chapters
    ]
    previous_summary_text = previous_summary_text or "暂无可用摘要"
    previous_tail_excerpt = previous_tail_excerpt or "暂无上一章结尾内容"
    completed_section = "\n".join(completed_lines) if completed_lines else "暂无前情摘要"
    rag_chunks_text = "\n\n".join(rag_context.chunk_texts()) if rag_context.chunks else "未检索到章节片段"
    rag_summaries_text = "\n".join(rag_context.summary_lines()) if rag_context.summaries else "未检索到章节摘要"
    writing_notes = request.writing_notes or "无额外写作指令"

    # 收集后续章节的大纲预览（下一章 + 后续2章），帮助 AI 控制节奏、避免写过头
    upcoming_outlines = []
    for future_num in range(request.chapter_number + 1, request.chapter_number + 4):
        future_outline = outlines_map.get(future_num)
        if future_outline:
            upcoming_outlines.append(
                f"- 第{future_num}章 - {future_outline.title or '未命名'}：{future_outline.summary or '暂无摘要'}"
            )
    upcoming_section = "\n".join(upcoming_outlines) if upcoming_outlines else "无后续章节大纲"

    # ==================== 作者备忘录和角色状态注入 ====================
    author_notes_text = ""
    character_states_text = ""
    note_repo = AuthorNoteRepository(session)

    # 自动获取本章、本卷、全局的备忘录
    current_volume_id = outline.volume.id if outline.volume else None
    auto_notes = await note_repo.list_for_chapter_generation(
        project_id=project_id,
        chapter_number=request.chapter_number,
        volume_id=current_volume_id,
    )

    # 合并用户手动选中的备忘录（如果有）
    all_note_ids = set()
    if request.selected_note_ids:
        all_note_ids.update(request.selected_note_ids)
    # 添加自动获取的备忘录 ID
    for note in auto_notes:
        all_note_ids.add(note.id)

    # 获取所有需要注入的备忘录
    if all_note_ids:
        all_notes = await note_repo.get_by_ids(list(all_note_ids))
        if all_notes:
            notes_lines = []
            for note in all_notes:
                note_label = f"[{note.type}]"
                if note.volume_id:
                    note_label += f" 卷#{note.volume_id}"
                if note.chapter_number:
                    note_label += f" 第{note.chapter_number}章"
                notes_lines.append(f"{note_label} {note.title}：{note.content}")
            author_notes_text = "\n".join(notes_lines)
            logger.info(
                "项目 %s 第 %s 章注入 %s 条作者备忘（自动 %d 条 + 手动选择 %d 条）",
                project_id,
                request.chapter_number,
                len(all_notes),
                len(auto_notes),
                len(request.selected_note_ids or []),
            )

    # 获取选中的角色状态
    if request.selected_state_ids:
        state_repo = CharacterStateRepository(session)
        selected_states = await state_repo.get_by_ids(request.selected_state_ids)
        if selected_states:
            # 获取角色名称
            from sqlalchemy import select as sql_select
            from ...models.novel import BlueprintCharacter
            char_ids = [s.character_id for s in selected_states]
            char_stmt = sql_select(BlueprintCharacter).where(BlueprintCharacter.id.in_(char_ids))
            char_result = await session.execute(char_stmt)
            char_map = {c.id: c.name for c in char_result.scalars().all()}

            states_lines = []
            for state in selected_states:
                char_name = char_map.get(state.character_id, "未知角色")
                state_data = state.data or {}
                # 格式化状态数据
                state_parts = []
                for key, value in state_data.items():
                    if isinstance(value, list):
                        state_parts.append(f"{key}: {', '.join(str(v) for v in value)}")
                    elif isinstance(value, dict):
                        state_parts.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
                    else:
                        state_parts.append(f"{key}: {value}")
                state_str = " | ".join(state_parts) if state_parts else "无状态数据"
                states_lines.append(f"【{char_name}】(第{state.chapter_number}章): {state_str}")
            character_states_text = "\n".join(states_lines)
            logger.info(
                "项目 %s 第 %s 章注入 %s 条角色状态",
                project_id,
                request.chapter_number,
                len(selected_states),
            )

    # 记录生成上下文（用于复现）
    if request.selected_note_ids or request.selected_state_ids:
        gen_context = GenerationContext(
            chapter_id=chapter.id,
            selected_note_ids=request.selected_note_ids,
            selected_state_ids=request.selected_state_ids,
            extra_instruction=request.writing_notes,
        )
        session.add(gen_context)
        await session.flush()

    prompt_sections = [
        ("[世界蓝图](JSON)", blueprint_text),
        ("[当前所在卷]", current_volume_info),
        ("[本章伏笔任务]", relevant_foreshadowing_text),
        # 注入作者备忘录和角色状态
        ("[作者备忘录]", author_notes_text if author_notes_text else None),
        ("[角色当前状态]", character_states_text if character_states_text else None),
        # ("[前情摘要]", completed_section),
        ("[上一章摘要]", previous_summary_text),
        ("[上一章结尾]", previous_tail_excerpt),
        ("[检索到的剧情上下文](Markdown)", rag_chunks_text),
        ("[检索到的章节摘要]", rag_summaries_text),
        (
            "[当前章节目标]",
            f"标题：{outline_title}\n摘要：{outline_summary}\n写作要求：{writing_notes}",
        ),
        (
            "[后续章节预览](请勿在本章写入这些内容，仅作参考)",
            upcoming_section,
        ),
    ]
    prompt_input = "\n\n".join(f"{title}\n{content}" for title, content in prompt_sections if content)
    logger.debug("章节写作提示词：%s\n%s", writer_prompt, prompt_input)

    # 不同版本使用不同temperature增加多样性：保守→平衡→创意
    VERSION_TEMPERATURES = [0.7, 0.85, 1.0]

    async def _generate_single_version(idx: int) -> Dict:
        version_temp = VERSION_TEMPERATURES[idx % len(VERSION_TEMPERATURES)]
        try:
            response = await llm_service.get_llm_response(
                system_prompt=writer_prompt,
                conversation_history=[{"role": "user", "content": prompt_input}],
                temperature=version_temp,
                user_id=current_user.id,
                timeout=600.0,
            )
            cleaned = remove_think_tags(response)
            normalized = unwrap_markdown_json(cleaned)
            try:
                return json.loads(normalized)
            except json.JSONDecodeError as parse_err:
                logger.warning(
                    "项目 %s 第 %s 章第 %s 个版本 JSON 解析失败，将原始内容作为纯文本处理: %s",
                    project_id,
                    request.chapter_number,
                    idx + 1,
                    parse_err,
                )
                return {"content": normalized}
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "项目 %s 生成第 %s 章第 %s 个版本时发生异常: %s",
                project_id,
                request.chapter_number,
                idx + 1,
                exc,
            )
            raise HTTPException(
                status_code=500,
                detail=f"生成章节第 {idx + 1} 个版本时失败: {str(exc)[:200]}"
            )

    version_count = await _resolve_version_count(session)
    temps_preview = [VERSION_TEMPERATURES[i % len(VERSION_TEMPERATURES)] for i in range(version_count)]
    logger.info(
        "项目 %s 第 %s 章计划生成 %s 个版本，temperature梯度: %s",
        project_id,
        request.chapter_number,
        version_count,
        temps_preview,
    )
    raw_versions = []
    for idx in range(version_count):
        raw_versions.append(await _generate_single_version(idx))
    contents: List[str] = []
    metadata: List[Dict] = []
    for variant in raw_versions:
        if isinstance(variant, dict):
            if "content" in variant and isinstance(variant["content"], str):
                contents.append(strip_markdown_fences(variant["content"]))
            elif "chapter_content" in variant:
                contents.append(strip_markdown_fences(str(variant["chapter_content"])))
            elif "full_content" in variant:
                contents.append(strip_markdown_fences(str(variant["full_content"])))
            else:
                contents.append(strip_markdown_fences(json.dumps(variant, ensure_ascii=False)))
            metadata.append(variant)
        else:
            contents.append(strip_markdown_fences(str(variant)))
            metadata.append({"raw": variant})

    await novel_service.replace_chapter_versions(chapter, contents, metadata)
    logger.info(
        "项目 %s 第 %s 章生成完成，已写入 %s 个版本",
        project_id,
        request.chapter_number,
        len(contents),
    )
    return await _load_project_schema(novel_service, project_id, current_user.id)


async def _resolve_version_count(session: AsyncSession) -> int:
    repo = SystemConfigRepository(session)
    record = await repo.get_by_key("writer.chapter_versions")
    if record:
        try:
            value = int(record.value)
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    env_value = os.getenv("WRITER_CHAPTER_VERSION_COUNT")
    if env_value:
        try:
            value = int(env_value)
            if value > 0:
                return value
        except ValueError:
            pass
    return 3


@router.post("/novels/{project_id}/chapters/select", response_model=NovelProjectSchema)
async def select_chapter_version(
    project_id: str,
    request: SelectVersionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter:
        logger.warning("项目 %s 未找到第 %s 章，无法选择版本", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节不存在")

    selected = await novel_service.select_chapter_version(chapter, request.version_index)
    logger.info(
        "用户 %s 选择了项目 %s 第 %s 章的第 %s 个版本",
        current_user.id,
        project_id,
        request.chapter_number,
        request.version_index,
    )
    if selected and selected.content:
        summary = await llm_service.get_summary(
            selected.content,
            temperature=0.15,
            user_id=current_user.id,
            timeout=180.0,
        )
        chapter.real_summary = remove_think_tags(summary)
        await session.commit()

        # 选定版本后同步向量库，确保后续章节可检索到最新内容
        vector_store: Optional[VectorStoreService]
        if not settings.vector_store_enabled:
            vector_store = None
        else:
            try:
                vector_store = VectorStoreService()
            except RuntimeError as exc:
                logger.warning("向量库初始化失败，跳过章节向量同步: %s", exc)
                vector_store = None

        if vector_store:
            ingestion_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)
            outline = next((item for item in project.outlines if item.chapter_number == chapter.chapter_number), None)
            chapter_title = outline.title if outline and outline.title else f"第{chapter.chapter_number}章"
            await ingestion_service.ingest_chapter(
                project_id=project_id,
                chapter_number=chapter.chapter_number,
                title=chapter_title,
                content=selected.content,
                summary=chapter.real_summary,
                user_id=current_user.id,
            )
            logger.info(
                "项目 %s 第 %s 章已同步至向量库",
                project_id,
                chapter.chapter_number,
            )

    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/evaluate", response_model=NovelProjectSchema)
async def evaluate_chapter(
    project_id: str,
    request: EvaluateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter:
        logger.warning("项目 %s 未找到第 %s 章，无法执行评估", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节不存在")
    if not chapter.versions:
        logger.warning("项目 %s 第 %s 章无可评估版本", project_id, request.chapter_number)
        raise HTTPException(status_code=400, detail="无可评估的章节版本")

    evaluator_prompt = await prompt_service.get_prompt("evaluation")
    if not evaluator_prompt:
        logger.error("缺少评估提示词，项目 %s 第 %s 章评估失败", project_id, request.chapter_number)
        raise HTTPException(status_code=500, detail="缺少评估提示词，请联系管理员配置 'evaluation' 提示词")

    project_schema = await novel_service._serialize_project(project)
    if not project_schema.blueprint:
        raise HTTPException(status_code=400, detail="项目蓝图不存在，请先生成蓝图")
    blueprint_dict = project_schema.blueprint.model_dump()

    versions_to_evaluate = [
        {"version_id": idx + 1, "content": version.content}
        for idx, version in enumerate(sorted(chapter.versions, key=lambda item: item.created_at))
    ]
    # print("blueprint_dict:",blueprint_dict)
    evaluator_payload = {
        "novel_blueprint": blueprint_dict,
        "content_to_evaluate": {
            "chapter_number": chapter.chapter_number,
            "versions": versions_to_evaluate,
        },
    }

    evaluation_raw = await llm_service.get_llm_response(
        system_prompt=evaluator_prompt,
        conversation_history=[{"role": "user", "content": json.dumps(evaluator_payload, ensure_ascii=False)}],
        temperature=0.3,
        user_id=current_user.id,
        timeout=360.0,
    )
    evaluation_clean = remove_think_tags(evaluation_raw)
    await novel_service.add_chapter_evaluation(chapter, None, evaluation_clean)
    logger.info("项目 %s 第 %s 章评估完成", project_id, request.chapter_number)

    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/outline", response_model=NovelProjectSchema)
async def generate_chapter_outline(
    project_id: str,
    request: GenerateOutlineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info(
        "用户 %s 请求生成项目 %s 的章节大纲，起始章节 %s，数量 %s",
        current_user.id,
        project_id,
        request.start_chapter,
        request.num_chapters,
    )
    outline_prompt = await prompt_service.get_prompt("outline")
    if not outline_prompt:
        logger.error("缺少大纲提示词，项目 %s 大纲生成失败", project_id)
        raise HTTPException(status_code=500, detail="缺少大纲提示词，请联系管理员配置 'outline' 提示词")

    project_schema = await novel_service.get_project_schema(project_id, current_user.id)
    if not project_schema.blueprint:
        raise HTTPException(status_code=400, detail="项目蓝图不存在，请先生成蓝图")
    blueprint_dict = project_schema.blueprint.model_dump()

    payload = {
        "novel_blueprint": blueprint_dict,
        "wait_to_generate": {
            "start_chapter": request.start_chapter,
            "num_chapters": request.num_chapters,
        },
    }

    response = await llm_service.get_llm_response(
        system_prompt=outline_prompt,
        conversation_history=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        temperature=0.7,
        user_id=current_user.id,
        timeout=360.0,
    )
    normalized = unwrap_markdown_json(remove_think_tags(response))
    try:
        data = json.loads(normalized)
    except json.JSONDecodeError as exc:
        logger.error(
            "项目 %s 大纲生成 JSON 解析失败: %s, 原始内容预览: %s",
            project_id,
            exc,
            normalized[:500],
        )
        raise HTTPException(
            status_code=500,
            detail=f"章节大纲生成失败，AI 返回的内容格式不正确: {str(exc)}"
        ) from exc

    new_outlines = data.get("chapters", [])
    for item in new_outlines:
        stmt = (
            select(ChapterOutline)
            .where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == item.get("chapter_number"),
            )
        )
        result = await session.execute(stmt)
        record = result.scalars().first()
        if record:
            record.title = item.get("title", record.title)
            record.summary = item.get("summary", record.summary)
        else:
            session.add(
                ChapterOutline(
                    project_id=project_id,
                    chapter_number=item.get("chapter_number"),
                    title=item.get("title", ""),
                    summary=item.get("summary"),
                )
            )
    await session.commit()
    logger.info("项目 %s 章节大纲生成完成", project_id)

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/update-outline", response_model=NovelProjectSchema)
async def update_chapter_outline(
    project_id: str,
    request: UpdateChapterOutlineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info(
        "用户 %s 更新项目 %s 第 %s 章大纲",
        current_user.id,
        project_id,
        request.chapter_number,
    )

    stmt = (
        select(ChapterOutline)
        .where(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == request.chapter_number,
        )
    )
    result = await session.execute(stmt)
    outline = result.scalars().first()
    if not outline:
        outline = ChapterOutline(
            project_id=project_id,
            chapter_number=request.chapter_number,
        )
        session.add(outline)

    outline.title = request.title
    outline.summary = request.summary
    await session.commit()
    logger.info("项目 %s 第 %s 章大纲已更新", project_id, request.chapter_number)

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/delete", response_model=NovelProjectSchema)
async def delete_chapters(
    project_id: str,
    request: DeleteChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    if not request.chapter_numbers:
        logger.warning("项目 %s 删除章节时未提供章节号", project_id)
        raise HTTPException(status_code=400, detail="请提供要删除的章节号列表")
    novel_service = NovelService(session)
    llm_service = LLMService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info(
        "用户 %s 删除项目 %s 的章节 %s",
        current_user.id,
        project_id,
        request.chapter_numbers,
    )
    await novel_service.delete_chapters(project_id, request.chapter_numbers)

    # 删除章节时同步清理向量库，避免过时内容被检索
    vector_store: Optional[VectorStoreService]
    if not settings.vector_store_enabled:
        vector_store = None
    else:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，跳过章节向量删除: %s", exc)
            vector_store = None

    if vector_store:
        ingestion_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)
        await ingestion_service.delete_chapters(project_id, request.chapter_numbers)
        logger.info(
            "项目 %s 已从向量库移除章节 %s",
            project_id,
            request.chapter_numbers,
        )

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/edit", response_model=NovelProjectSchema)
async def edit_chapter(
    project_id: str,
    request: EditChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter or chapter.selected_version is None:
        logger.warning("项目 %s 第 %s 章尚未生成或未选择版本，无法编辑", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节尚未生成或未选择版本")

    chapter.selected_version.content = request.content
    chapter.word_count = len(request.content)
    logger.info("用户 %s 更新了项目 %s 第 %s 章内容", current_user.id, project_id, request.chapter_number)

    if request.content.strip():
        summary = await llm_service.get_summary(
            request.content,
            temperature=0.15,
            user_id=current_user.id,
            timeout=180.0,
        )
        chapter.real_summary = remove_think_tags(summary)
    await session.commit()

    vector_store: Optional[VectorStoreService]
    if not settings.vector_store_enabled:
        vector_store = None
    else:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，跳过章节向量更新: %s", exc)
            vector_store = None

    if vector_store and chapter.selected_version and chapter.selected_version.content:
        ingestion_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)
        outline = next((item for item in project.outlines if item.chapter_number == chapter.chapter_number), None)
        chapter_title = outline.title if outline and outline.title else f"第{chapter.chapter_number}章"
        await ingestion_service.ingest_chapter(
            project_id=project_id,
            chapter_number=chapter.chapter_number,
            title=chapter_title,
            content=chapter.selected_version.content,
            summary=chapter.real_summary,
            user_id=current_user.id,
        )
        logger.info("项目 %s 第 %s 章更新内容已同步至向量库", project_id, chapter.chapter_number)

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/refine", response_model=NovelProjectSchema)
async def refine_chapter_version(
    project_id: str,
    request: RefineVersionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """基于现有版本内容，根据用户指令微调生成新版本。"""
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info(
        "用户 %s 请求微调项目 %s 第 %s 章的版本 %s",
        current_user.id,
        project_id,
        request.chapter_number,
        request.version_index,
    )

    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter:
        logger.warning("项目 %s 未找到第 %s 章，无法微调", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节不存在")

    if not chapter.versions:
        logger.warning("项目 %s 第 %s 章无版本可微调", project_id, request.chapter_number)
        raise HTTPException(status_code=400, detail="无可微调的版本")

    sorted_versions = sorted(chapter.versions, key=lambda v: v.created_at)
    if request.version_index < 0 or request.version_index >= len(sorted_versions):
        logger.warning(
            "项目 %s 第 %s 章版本索引 %s 越界，总共 %s 个版本",
            project_id,
            request.chapter_number,
            request.version_index,
            len(sorted_versions),
        )
        raise HTTPException(status_code=400, detail="版本索引越界")

    original_version = sorted_versions[request.version_index]
    original_content = original_version.content or ""

    # 获取微调提示词，若不存在则使用默认模板
    refine_prompt = await prompt_service.get_prompt("refine")
    if not refine_prompt:
        refine_prompt = """你是一位专业的小说编辑，需要根据用户的指令对章节内容进行微调。

请保持原文的整体结构和风格，只根据用户的具体要求进行修改。

输出格式要求：
- 直接输出修改后的完整章节内容
- 不要添加任何解释或说明
- 保持原文的叙事视角和时态"""

    refine_input = f"""[原始章节内容]
{original_content}

[用户微调指令]
{request.refinement_prompt}

请根据上述指令对章节内容进行微调，输出完整的修改后内容。"""

    try:
        response = await llm_service.get_llm_response(
            system_prompt=refine_prompt,
            conversation_history=[{"role": "user", "content": refine_input}],
            temperature=0.7,
            user_id=current_user.id,
            timeout=600.0,
        )
        refined_content = strip_markdown_fences(remove_think_tags(response))
    except Exception as exc:
        logger.exception(
            "项目 %s 第 %s 章微调版本时发生异常: %s",
            project_id,
            request.chapter_number,
            exc,
        )
        raise HTTPException(
            status_code=500,
            detail=f"微调版本失败: {str(exc)[:200]}"
        )

    # 将新版本追加到章节版本列表
    await novel_service.add_chapter_version(chapter, refined_content, {"refined_from": request.version_index})
    logger.info(
        "项目 %s 第 %s 章微调完成，已新增版本",
        project_id,
        request.chapter_number,
    )

    return await _load_project_schema(novel_service, project_id, current_user.id)

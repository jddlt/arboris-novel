"""GM Agent API 路由。

提供 GM Agent 对话和操作管理的 HTTP 接口。
"""

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...schemas.user import UserInDB
from ...services.gm.gm_service import GMService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/novels/{project_id}/gm", tags=["GM Agent"])


# ==================== Request/Response Schemas ====================


class ImagePayload(BaseModel):
    """图片数据。"""

    base64: str = Field(..., description="图片的 base64 编码数据")
    mime_type: str = Field(..., description="图片 MIME 类型，如 image/png, image/jpeg")


class GMChatRequest(BaseModel):
    """GM 对话请求。"""

    message: str = Field("", max_length=10000, description="用户消息")
    conversation_id: Optional[str] = Field(None, description="对话 ID，不传则创建新对话")
    enable_web_search: bool = Field(False, description="是否启用联网搜索（仅 Gemini 模型支持）")
    images: Optional[List[ImagePayload]] = Field(None, max_length=4, description="附带的图片列表（最多4张）")


class PendingActionResponse(BaseModel):
    """待执行操作响应。"""

    action_id: str
    tool_name: str
    params: Dict[str, Any]
    preview: str
    status: str = "pending"


class GMChatResponse(BaseModel):
    """GM 对话响应。"""

    conversation_id: str
    message: str
    pending_actions: List[PendingActionResponse]


class ApplyActionsRequest(BaseModel):
    """应用操作请求。"""

    action_ids: List[str] = Field(..., min_length=1, description="要执行的操作 ID 列表")


class ActionResultResponse(BaseModel):
    """单个操作执行结果。"""

    action_id: str
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class ApplyActionsResponse(BaseModel):
    """应用操作响应。"""

    applied: List[str]
    results: List[ActionResultResponse]


class DiscardActionsRequest(BaseModel):
    """放弃操作请求。"""

    action_ids: List[str] = Field(..., min_length=1, description="要放弃的操作 ID 列表")


class DiscardActionsResponse(BaseModel):
    """放弃操作响应。"""

    discarded_count: int


class ConversationSummary(BaseModel):
    """对话摘要。"""

    id: str
    title: str
    message_count: int
    is_archived: bool
    created_at: str
    updated_at: str


class ConversationDetail(BaseModel):
    """对话详情。"""

    id: str
    project_id: str
    title: str
    messages: List[Dict[str, Any]]
    is_archived: bool
    created_at: str
    updated_at: str


# ==================== API Endpoints ====================


@router.post("/chat", response_model=GMChatResponse)
async def chat_with_gm(
    project_id: str,
    request: GMChatRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> GMChatResponse:
    """与 GM Agent 对话。

    发送消息给 GM，GM 会分析意图并返回响应。
    如果 GM 决定执行修改操作，会返回待确认的操作列表。

    Args:
        project_id: 小说项目 ID
        request: 对话请求

    Returns:
        GM 响应，包含消息和待执行操作
    """
    from ...services.novel_service import NovelService

    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    gm_service = GMService(session)

    logger.info(
        "GM 对话请求: project_id=%s, user_id=%s, conversation_id=%s, message_len=%d",
        project_id,
        current_user.id,
        request.conversation_id,
        len(request.message),
    )

    response = await gm_service.chat(
        project_id=project_id,
        message=request.message,
        conversation_id=request.conversation_id,
        user_id=current_user.id,
        enable_web_search=request.enable_web_search,
    )

    return GMChatResponse(
        conversation_id=response.conversation_id,
        message=response.message,
        pending_actions=[
            PendingActionResponse(
                action_id=a.action_id,
                tool_name=a.tool_name,
                params=a.params,
                preview=a.preview,
                status=a.status,
            )
            for a in response.pending_actions
        ],
    )


@router.post("/chat/stream")
async def stream_chat_with_gm(
    project_id: str,
    request: GMChatRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> StreamingResponse:
    """与 GM Agent 流式对话（SSE）。

    使用 Server-Sent Events 流式返回 GM 响应，适用于需要实时显示的场景。

    事件类型：
    - start: {"conversation_id": "..."} 对话开始
    - content: {"content": "..."} 内容片段
    - pending_actions: {"actions": [...]} 待执行操作
    - done: {"conversation_id": "...", "message": "..."} 完成
    - error: {"error": "..."} 错误

    Args:
        project_id: 小说项目 ID
        request: 对话请求

    Returns:
        SSE 流式响应
    """
    from ...services.novel_service import NovelService

    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    gm_service = GMService(session)

    logger.info(
        "GM 流式对话请求: project_id=%s, user_id=%s, conversation_id=%s, message_len=%d, images=%d",
        project_id,
        current_user.id,
        request.conversation_id,
        len(request.message),
        len(request.images) if request.images else 0,
    )

    # 转换图片数据为字典格式
    images_data = None
    if request.images:
        images_data = [{"base64": img.base64, "mime_type": img.mime_type} for img in request.images]

    async def event_generator():
        """SSE 事件生成器。"""
        try:
            async for event in gm_service.stream_chat(
                project_id=project_id,
                message=request.message,
                conversation_id=request.conversation_id,
                user_id=current_user.id,
                enable_web_search=request.enable_web_search,
                images=images_data,
            ):
                event_type = event.get("type", "message")
                event_data = json.dumps(event, ensure_ascii=False)
                yield f"event: {event_type}\ndata: {event_data}\n\n"
        except Exception as e:
            logger.error("SSE 流异常: %s", e, exc_info=True)
            error_event = json.dumps({"type": "error", "error": str(e)}, ensure_ascii=False)
            yield f"event: error\ndata: {error_event}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )


@router.post("/apply", response_model=ApplyActionsResponse)
async def apply_actions(
    project_id: str,
    request: ApplyActionsRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ApplyActionsResponse:
    """执行待确认的操作。

    用户确认后调用此接口，真正执行 GM 提议的修改操作。
    操作执行后会记录历史，支持后续撤销。

    Args:
        project_id: 小说项目 ID
        request: 操作 ID 列表

    Returns:
        执行结果
    """
    from ...services.novel_service import NovelService

    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    gm_service = GMService(session)

    logger.info(
        "GM 执行操作: project_id=%s, user_id=%s, action_count=%d",
        project_id,
        current_user.id,
        len(request.action_ids),
    )

    result = await gm_service.apply_actions(
        project_id=project_id,
        action_ids=request.action_ids,
    )

    return ApplyActionsResponse(
        applied=result.applied,
        results=[
            ActionResultResponse(
                action_id=r.action_id,
                success=r.success,
                message=r.message,
                data=r.data,
            )
            for r in result.results
        ],
    )


@router.post("/discard", response_model=DiscardActionsResponse)
async def discard_actions(
    project_id: str,
    request: DiscardActionsRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> DiscardActionsResponse:
    """放弃待确认的操作。

    用户不想执行某些操作时调用此接口。

    Args:
        project_id: 小说项目 ID
        request: 操作 ID 列表

    Returns:
        放弃的操作数量
    """
    from ...services.novel_service import NovelService

    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    gm_service = GMService(session)

    logger.info(
        "GM 放弃操作: project_id=%s, user_id=%s, action_count=%d",
        project_id,
        current_user.id,
        len(request.action_ids),
    )

    count = await gm_service.discard_actions(action_ids=request.action_ids)

    return DiscardActionsResponse(discarded_count=count)


class ActionResultItem(BaseModel):
    """单个操作执行结果。"""

    action_id: str = Field(..., description="操作 ID")
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="执行结果消息")


class ContinueChatRequest(BaseModel):
    """继续对话请求。"""

    conversation_id: str = Field(..., description="对话 ID")
    action_results: List[ActionResultItem] = Field(..., description="操作执行结果列表")
    enable_web_search: bool = Field(False, description="是否启用联网搜索")


@router.post("/chat/continue")
async def continue_chat_with_gm(
    project_id: str,
    request: ContinueChatRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> StreamingResponse:
    """在应用操作后继续对话（SSE）。

    当 Agent 返回 awaiting_confirmation=True 且用户应用了操作后，
    调用此接口让 Agent 继续思考和执行任务。

    Args:
        project_id: 小说项目 ID
        request: 继续对话请求

    Returns:
        SSE 流式响应
    """
    from ...services.novel_service import NovelService

    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    gm_service = GMService(session)

    logger.info(
        "GM 继续对话: project_id=%s, user_id=%s, conversation_id=%s, results=%d",
        project_id,
        current_user.id,
        request.conversation_id,
        len(request.action_results),
    )

    # 转换为字典列表
    action_results = [r.model_dump() for r in request.action_results]

    async def event_generator():
        """SSE 事件生成器。"""
        try:
            async for event in gm_service.continue_chat(
                project_id=project_id,
                conversation_id=request.conversation_id,
                action_results=action_results,
                user_id=current_user.id,
                enable_web_search=request.enable_web_search,
            ):
                event_type = event.get("type", "message")
                event_data = json.dumps(event, ensure_ascii=False)
                yield f"event: {event_type}\ndata: {event_data}\n\n"
        except Exception as e:
            logger.error("SSE 流异常: %s", e, exc_info=True)
            error_event = json.dumps({"type": "error", "error": str(e)}, ensure_ascii=False)
            yield f"event: error\ndata: {error_event}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations", response_model=List[ConversationSummary])
async def list_conversations(
    project_id: str,
    include_archived: bool = False,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> List[ConversationSummary]:
    """获取项目的 GM 对话列表。

    Args:
        project_id: 小说项目 ID
        include_archived: 是否包含已归档对话

    Returns:
        对话列表
    """
    from ...services.novel_service import NovelService

    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    gm_service = GMService(session)

    conversations = await gm_service.get_conversations(
        project_id=project_id,
        include_archived=include_archived,
    )

    return [ConversationSummary(**c) for c in conversations]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    project_id: str,
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ConversationDetail:
    """获取对话详情。

    Args:
        project_id: 小说项目 ID
        conversation_id: 对话 ID

    Returns:
        对话详情，包含完整消息历史
    """
    from ...services.novel_service import NovelService

    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    gm_service = GMService(session)

    detail = await gm_service.get_conversation_detail(conversation_id)

    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"对话 {conversation_id} 不存在",
        )

    if detail["project_id"] != project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此对话",
        )

    return ConversationDetail(**detail)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_conversation(
    project_id: str,
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> None:
    """归档对话。

    不会真正删除对话，只是标记为已归档。

    Args:
        project_id: 小说项目 ID
        conversation_id: 对话 ID
    """
    from ...services.novel_service import NovelService

    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    gm_service = GMService(session)

    detail = await gm_service.get_conversation_detail(conversation_id)

    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"对话 {conversation_id} 不存在",
        )

    if detail["project_id"] != project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作此对话",
        )

    await gm_service.gm_repo.conversations.archive(conversation_id)
    await session.commit()

    logger.info(
        "GM 归档对话: project_id=%s, user_id=%s, conversation_id=%s",
        project_id,
        current_user.id,
        conversation_id,
    )

"""GM Agent API 路由。

提供 GM Agent 对话和操作管理的 HTTP 接口。
对话功能已迁移至 WebSocket。
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user, get_current_user_ws
from ...db.session import get_session
from ...schemas.user import UserInDB
from ...services.gm.gm_service import GMService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/novels/{project_id}/gm", tags=["GM Agent"])


# ==================== Request/Response Schemas ====================


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


class TruncateConversationRequest(BaseModel):
    """截断对话请求。"""

    keep_count: int = Field(..., ge=0, description="保留的消息数量（从开头算起）")


class TruncateConversationResponse(BaseModel):
    """截断对话响应。"""

    deleted_count: int


@router.post("/conversations/{conversation_id}/truncate", response_model=TruncateConversationResponse)
async def truncate_conversation(
    project_id: str,
    conversation_id: str,
    request: TruncateConversationRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> TruncateConversationResponse:
    """截断对话消息（回溯功能）。

    保留前 N 条消息，删除后续所有消息。用于对话回溯。

    Args:
        project_id: 小说项目 ID
        conversation_id: 对话 ID
        request: 截断参数

    Returns:
        被删除的消息数量
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

    deleted_count = await gm_service.gm_repo.conversations.truncate_messages(
        conversation_id, request.keep_count
    )
    await session.commit()

    logger.info(
        "GM 截断对话: project_id=%s, user_id=%s, conversation_id=%s, keep=%d, deleted=%d",
        project_id,
        current_user.id,
        conversation_id,
        request.keep_count,
        deleted_count,
    )

    return TruncateConversationResponse(deleted_count=deleted_count)


# ==================== WebSocket Endpoint ====================


@router.websocket("/ws")
async def gm_websocket(
    websocket: "WebSocket",
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: Optional[UserInDB] = Depends(get_current_user_ws),
):
    """GM Agent WebSocket 端点。

    支持同步确认的双向通信。

    认证：通过 URL 参数 ?token=xxx 传递 JWT token。

    消息协议：
    客户端 -> 服务端：
    - {"type": "user_message", "message": "...", "conversation_id": "...", "images": [...]}
    - {"type": "confirm_response", "approved": ["id1"], "rejected": ["id2"]}
    - {"type": "cancel"}

    服务端 -> 客户端：
    - {"type": "connected", "project_id": "..."}
    - {"type": "content", "content": "..."}
    - {"type": "tool_executing", "tool_name": "...", "params": {...}}
    - {"type": "tool_result", "tool_name": "...", "success": true, "message": "..."}
    - {"type": "confirm_actions", "actions": [...], "timeout_ms": 60000}
    - {"type": "tool_executed", "action_id": "...", "success": true, "message": "..."}
    - {"type": "done", "conversation_id": "...", "message": "..."}
    - {"type": "error", "error": "..."}
    """
    from ...schemas.gm_websocket import make_connected, make_error
    from ...services.novel_service import NovelService

    await websocket.accept()

    # 认证检查
    if not current_user:
        logger.warning("GM WebSocket 认证失败: project_id=%s", project_id)
        await websocket.send_json(make_error("未授权：请提供有效的 token", recoverable=False))
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # 权限检查：确保用户拥有该项目
    try:
        novel_service = NovelService(session)
        await novel_service.ensure_project_owner(project_id, current_user.id)
    except HTTPException as e:
        logger.warning("GM WebSocket 权限不足: project_id=%s, user_id=%s", project_id, current_user.id)
        await websocket.send_json(make_error(f"无权访问此项目: {e.detail}", recoverable=False))
        await websocket.close(code=4003, reason="Forbidden")
        return

    logger.info("GM WebSocket 连接: project_id=%s, user_id=%s", project_id, current_user.id)

    gm_service = GMService(session)

    try:
        # 发送连接成功消息
        await websocket.send_json(make_connected(project_id))

        # 主循环：等待客户端消息
        while True:
            try:
                data = await websocket.receive_json()
            except Exception as e:
                logger.warning("WebSocket 接收消息失败: %s", e)
                break

            msg_type = data.get("type")

            if msg_type == "user_message":
                # 处理用户消息
                message = data.get("message", "")
                conversation_id = data.get("conversation_id")
                images = data.get("images")
                enable_web_search = data.get("enable_web_search", False)

                if not message.strip():
                    await websocket.send_json(make_error("消息不能为空"))
                    continue

                # 调用 WebSocket 版本的对话方法
                await gm_service.websocket_chat(
                    websocket=websocket,
                    project_id=project_id,
                    message=message,
                    conversation_id=conversation_id,
                    user_id=current_user.id,  # 现在有用户 ID 了
                    images=images,
                    enable_web_search=enable_web_search,
                )

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            else:
                logger.warning("未知消息类型: %s", msg_type)

    except WebSocketDisconnect:
        logger.info("GM WebSocket 断开: project_id=%s, user_id=%s", project_id, current_user.id)
    except Exception as e:
        logger.error("GM WebSocket 异常: project_id=%s, error=%s", project_id, e, exc_info=True)
        try:
            await websocket.send_json(make_error(str(e)))
        except Exception:
            pass

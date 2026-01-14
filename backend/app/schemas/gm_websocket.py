"""GM Agent WebSocket 消息协议定义。

定义前后端 WebSocket 通信的消息类型和数据结构。
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


# ============================================================================
# 消息类型枚举
# ============================================================================


class WSClientMessageType(str, Enum):
    """客户端发送的消息类型。"""

    USER_MESSAGE = "user_message"  # 用户发送对话消息
    CONFIRM_RESPONSE = "confirm_response"  # 用户确认/拒绝操作
    CANCEL = "cancel"  # 用户取消当前任务
    PING = "ping"  # 心跳


class WSServerMessageType(str, Enum):
    """服务端发送的消息类型。"""

    CONNECTED = "connected"  # 连接成功
    ROUND_START = "round_start"  # 新一轮 Agent 循环开始（用于前端重置流式状态）
    CONTENT = "content"  # AI 文本内容（流式）
    TOOL_CALL = "tool_call"  # AI 发起工具调用（流式，立即通知）
    TOOL_EXECUTING = "tool_executing"  # 正在执行只读工具
    TOOL_RESULT = "tool_result"  # 只读工具执行结果
    CONFIRM_ACTIONS = "confirm_actions"  # 请求用户确认修改操作
    TOOL_EXECUTED = "tool_executed"  # 修改工具执行完成
    DONE = "done"  # 任务完成
    ERROR = "error"  # 错误
    PONG = "pong"  # 心跳响应


# ============================================================================
# 客户端消息 Payload
# ============================================================================


class ImagePayload(BaseModel):
    """图片数据。"""

    base64: str = Field(..., description="Base64 编码的图片数据")
    mime_type: str = Field(..., description="MIME 类型，如 image/png")


class UserMessagePayload(BaseModel):
    """用户消息 payload。"""

    message: str = Field(..., description="用户消息内容")
    conversation_id: Optional[str] = Field(None, description="对话 ID，不传则创建新对话")
    images: Optional[List[ImagePayload]] = Field(None, description="附带的图片列表")


class ConfirmResponsePayload(BaseModel):
    """用户确认响应 payload。"""

    approved: List[str] = Field(default_factory=list, description="批准执行的 action_id 列表")
    rejected: List[str] = Field(default_factory=list, description="拒绝执行的 action_id 列表")


class ClientMessage(BaseModel):
    """客户端消息统一格式。"""

    type: WSClientMessageType
    payload: Optional[Union[UserMessagePayload, ConfirmResponsePayload]] = None


# ============================================================================
# 服务端消息 Payload
# ============================================================================


class ConnectedPayload(BaseModel):
    """连接成功 payload。"""

    project_id: str
    conversation_id: Optional[str] = None


class ContentPayload(BaseModel):
    """流式内容 payload。"""

    content: str


class ToolExecutingPayload(BaseModel):
    """工具执行中 payload。"""

    tool_name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    preview: Optional[str] = None


class ToolResultPayload(BaseModel):
    """工具执行结果 payload。"""

    tool_name: str
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class ActionPreview(BaseModel):
    """待确认操作预览。"""

    action_id: str = Field(..., description="操作唯一 ID")
    tool_name: str = Field(..., description="工具名称")
    params: Dict[str, Any] = Field(default_factory=dict, description="工具参数")
    preview: str = Field(..., description="操作预览文本")
    is_dangerous: bool = Field(False, description="是否为危险操作")


class ConfirmActionsPayload(BaseModel):
    """请求确认操作 payload。"""

    actions: List[ActionPreview] = Field(..., description="待确认的操作列表")
    timeout_ms: int = Field(60000, description="确认超时时间（毫秒）")


class ToolExecutedPayload(BaseModel):
    """工具已执行 payload。"""

    action_id: str
    tool_name: str
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class DonePayload(BaseModel):
    """任务完成 payload。"""

    conversation_id: str
    message: str = ""
    tool_execution_summary: Optional[Dict[str, int]] = Field(
        None, description="工具执行统计，如 {success: 3, failed: 1}"
    )


class ErrorPayload(BaseModel):
    """错误 payload。"""

    error: str
    code: Optional[str] = None
    recoverable: bool = True


class ServerMessage(BaseModel):
    """服务端消息统一格式。"""

    type: WSServerMessageType
    payload: Optional[
        Union[
            ConnectedPayload,
            ContentPayload,
            ToolExecutingPayload,
            ToolResultPayload,
            ConfirmActionsPayload,
            ToolExecutedPayload,
            DonePayload,
            ErrorPayload,
        ]
    ] = None


# ============================================================================
# 辅助函数
# ============================================================================


def make_server_message(msg_type: WSServerMessageType, **kwargs) -> Dict[str, Any]:
    """创建服务端消息（用于 websocket.send_json）。"""
    return {"type": msg_type.value, **kwargs}


def make_connected(project_id: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
    """创建连接成功消息。"""
    return make_server_message(
        WSServerMessageType.CONNECTED,
        project_id=project_id,
        conversation_id=conversation_id,
    )


def make_content(content: str) -> Dict[str, Any]:
    """创建流式内容消息。"""
    return make_server_message(WSServerMessageType.CONTENT, content=content)


def make_tool_call(tool_name: str, params: Dict[str, Any], call_id: str) -> Dict[str, Any]:
    """创建工具调用消息（流式，立即通知前端 AI 发起了工具调用）。"""
    return make_server_message(
        WSServerMessageType.TOOL_CALL,
        tool_name=tool_name,
        params=params,
        call_id=call_id,
    )


def make_tool_executing(tool_name: str, params: Dict[str, Any], preview: str = "") -> Dict[str, Any]:
    """创建工具执行中消息。"""
    return make_server_message(
        WSServerMessageType.TOOL_EXECUTING,
        tool_name=tool_name,
        params=params,
        preview=preview,
    )


def make_tool_result(tool_name: str, success: bool, message: str, data: Optional[Dict] = None) -> Dict[str, Any]:
    """创建工具执行结果消息。"""
    msg = make_server_message(
        WSServerMessageType.TOOL_RESULT,
        tool_name=tool_name,
        success=success,
        message=message,
    )
    if data:
        msg["data"] = data
    return msg


def make_confirm_actions(
    actions: List[Dict[str, Any]],
    timeout_ms: int = 60000,
    awaiting_confirmation: bool = True,
) -> Dict[str, Any]:
    """创建确认请求消息。

    Args:
        actions: 待确认的操作列表
        timeout_ms: 确认超时时间（毫秒），0 表示无超时
        awaiting_confirmation: 是否需要在确认后继续 Agent 循环
    """
    return make_server_message(
        WSServerMessageType.CONFIRM_ACTIONS,
        actions=actions,
        timeout_ms=timeout_ms,
        awaiting_confirmation=awaiting_confirmation,
    )


def make_tool_executed(
    action_id: str, tool_name: str, success: bool, message: str, data: Optional[Dict] = None
) -> Dict[str, Any]:
    """创建工具已执行消息。"""
    msg = make_server_message(
        WSServerMessageType.TOOL_EXECUTED,
        action_id=action_id,
        tool_name=tool_name,
        success=success,
        message=message,
    )
    if data:
        msg["data"] = data
    return msg


def make_done(conversation_id: str, message: str = "", summary: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """创建任务完成消息。"""
    msg = make_server_message(
        WSServerMessageType.DONE,
        conversation_id=conversation_id,
        message=message,
    )
    if summary:
        msg["tool_execution_summary"] = summary
    return msg


def make_error(error: str, code: Optional[str] = None, recoverable: bool = True) -> Dict[str, Any]:
    """创建错误消息。"""
    return make_server_message(
        WSServerMessageType.ERROR,
        error=error,
        code=code,
        recoverable=recoverable,
    )


def make_round_start(round_number: int) -> Dict[str, Any]:
    """创建新一轮开始消息。"""
    return make_server_message(
        WSServerMessageType.ROUND_START,
        round=round_number,
    )

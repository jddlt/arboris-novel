"""任务状态信号工具。

用于 AI 明确告知系统当前任务是否需要等待用户确认后继续。
"""

from typing import Any, Dict, Optional

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....services.gm.tool_registry import ToolRegistry


@ToolRegistry.register
class SignalTaskStatusExecutor(BaseToolExecutor):
    """任务状态信号执行器。

    这是一个特殊的只读工具，AI 调用它来明确告知：
    - "awaiting": 需要用户确认操作后，AI 将继续执行后续任务
    - "complete": 任务已完成，用户确认操作后不需要继续

    执行结果会被 gm_service 捕获并用于设置 awaiting_confirmation 字段。
    """

    is_read_only = True  # 标记为只读，自动执行

    @classmethod
    def get_name(cls) -> str:
        return "signal_task_status"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="signal_task_status",
            description=(
                "在返回修改操作后，使用此工具明确告知任务状态。"
                "status='awaiting' 表示用户确认操作后需要继续执行后续任务；"
                "status='complete' 表示任务已完成，用户只需确认操作即可。"
                "注意：只有当本轮返回了修改操作时才需要调用此工具。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["awaiting", "complete"],
                        "description": "任务状态：awaiting=等待确认后继续，complete=任务完成",
                    },
                    "reason": {
                        "type": "string",
                        "description": "简要说明原因（可选）",
                    },
                },
                "required": ["status"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        status = params.get("status", "unknown")
        if status == "awaiting":
            return "等待确认后继续执行"
        elif status == "complete":
            return "任务完成"
        return f"状态: {status}"

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        """执行信号工具。

        实际上这个工具不做任何数据库操作，只是返回状态信息。
        gm_service 会捕获这个结果来设置 awaiting_confirmation。
        """
        status = params.get("status", "complete")
        reason = params.get("reason", "")

        return ToolResult(
            success=True,
            message=f"任务状态已设置为: {status}" + (f" ({reason})" if reason else ""),
            data={"status": status, "reason": reason},
        )

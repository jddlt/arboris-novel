"""GM Agent 工具执行器模块。

该模块包含所有GM工具的执行器实现。
每个工具独立一个文件，通过装饰器自动注册到工具注册表。
"""

from .gm.base import BaseToolExecutor, ToolDefinition, ToolResult

__all__ = [
    "BaseToolExecutor",
    "ToolDefinition",
    "ToolResult",
]

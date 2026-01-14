"""GM Agent 工具执行器子模块。

所有工具执行器都在此模块下按类别组织。
"""

from .base import BaseToolExecutor, ToolDefinition, ToolResult

# 导入所有执行器子模块以触发注册
from . import character
from . import relationship
from . import outline
from . import search
from . import chapter
from . import blueprint
from . import volume
from . import foreshadowing
from . import signal
from . import author_notes

__all__ = [
    "BaseToolExecutor",
    "ToolDefinition",
    "ToolResult",
]

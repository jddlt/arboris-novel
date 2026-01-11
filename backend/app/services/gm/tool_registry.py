"""GM Agent 工具注册表。

管理所有可用的工具执行器，提供工具发现和获取功能。
使用装饰器模式实现自动注册。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List, Type

if TYPE_CHECKING:
    from ...executors.gm.base import BaseToolExecutor

logger = logging.getLogger(__name__)


class ToolRegistry:
    """工具注册表 - 管理所有可用的 GM 工具。

    通过类装饰器 @ToolRegistry.register 自动注册工具执行器。
    支持工具发现、获取和定义导出。

    Example:
        ```python
        @ToolRegistry.register
        class AddCharacterExecutor(BaseToolExecutor):
            ...

        # 获取所有工具定义（用于 Function Calling）
        tools = ToolRegistry.get_all_definitions()

        # 获取特定工具执行器
        executor_class = ToolRegistry.get_executor("add_character")
        ```
    """

    _executors: Dict[str, Type["BaseToolExecutor"]] = {}
    _initialized: bool = False

    @classmethod
    def register(cls, executor_class: Type["BaseToolExecutor"]) -> Type["BaseToolExecutor"]:
        """装饰器：注册工具执行器。

        Args:
            executor_class: 工具执行器类

        Returns:
            原样返回执行器类（装饰器模式）

        Raises:
            ValueError: 工具名称重复时抛出
        """
        tool_name = executor_class.get_name()

        if tool_name in cls._executors:
            existing = cls._executors[tool_name]
            if existing is not executor_class:
                raise ValueError(
                    f"工具名称冲突: '{tool_name}' 已被 {existing.__name__} 注册，"
                    f"不能再被 {executor_class.__name__} 注册"
                )
            # 重复注册同一个类，忽略
            return executor_class

        cls._executors[tool_name] = executor_class
        logger.debug("已注册工具: %s (%s)", tool_name, executor_class.__name__)
        return executor_class

    @classmethod
    def get_executor(cls, tool_name: str) -> Type["BaseToolExecutor"]:
        """获取工具执行器类。

        Args:
            tool_name: 工具名称

        Returns:
            工具执行器类

        Raises:
            ValueError: 工具不存在时抛出
        """
        cls._ensure_initialized()

        if tool_name not in cls._executors:
            available = ", ".join(cls._executors.keys()) or "(无)"
            raise ValueError(f"未知工具: '{tool_name}'，可用工具: {available}")
        return cls._executors[tool_name]

    @classmethod
    def get_all_definitions(cls) -> List[Dict]:
        """获取所有工具的 Function Calling 定义。

        返回格式符合 OpenAI Function Calling 规范。

        Returns:
            工具定义列表
        """
        cls._ensure_initialized()

        definitions = []
        for executor_class in cls._executors.values():
            tool_def = executor_class.get_definition()
            definitions.append({
                "type": "function",
                "function": {
                    "name": tool_def.name,
                    "description": tool_def.description,
                    "parameters": tool_def.parameters,
                }
            })
        return definitions

    @classmethod
    def get_tool_names(cls) -> List[str]:
        """获取所有已注册的工具名称。

        Returns:
            工具名称列表
        """
        cls._ensure_initialized()
        return list(cls._executors.keys())

    @classmethod
    def get_executor_count(cls) -> int:
        """获取已注册工具数量。

        Returns:
            工具数量
        """
        cls._ensure_initialized()
        return len(cls._executors)

    @classmethod
    def is_registered(cls, tool_name: str) -> bool:
        """检查工具是否已注册。

        Args:
            tool_name: 工具名称

        Returns:
            是否已注册
        """
        return tool_name in cls._executors

    @classmethod
    def _ensure_initialized(cls) -> None:
        """确保所有工具执行器模块已加载。

        通过导入执行器模块触发 @register 装饰器执行。
        """
        if cls._initialized:
            return

        # 导入所有执行器模块以触发注册
        try:
            from ...executors import gm  # noqa: F401
            cls._initialized = True
            logger.info("工具注册表初始化完成，共 %d 个工具", len(cls._executors))
        except ImportError as e:
            logger.warning("工具执行器模块导入失败: %s", e)

    @classmethod
    def reset(cls) -> None:
        """重置注册表（仅用于测试）。"""
        cls._executors.clear()
        cls._initialized = False

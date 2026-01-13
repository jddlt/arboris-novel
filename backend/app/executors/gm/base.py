"""GM Agent 工具执行器基类与核心数据结构。

定义所有工具执行器必须实现的接口，以及工具执行结果的标准格式。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class ToolResult:
    """工具执行结果。

    Attributes:
        success: 执行是否成功
        message: 执行结果消息，用于向用户展示
        data: 执行产生的数据，如新创建的角色信息
        before_state: 操作前的状态快照，用于撤销
        after_state: 操作后的状态快照
    """

    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None


@dataclass
class ToolDefinition:
    """工具定义，用于 LLM Function Calling。

    Attributes:
        name: 工具名称，需全局唯一
        description: 工具描述，帮助 LLM 理解何时使用此工具
        parameters: JSON Schema 格式的参数定义
    """

    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)


class BaseToolExecutor(ABC):
    """工具执行器基类。

    所有 GM Agent 工具必须继承此类并实现抽象方法。
    通过 @ToolRegistry.register 装饰器自动注册到工具注册表。

    Attributes:
        is_read_only: 类属性，标识工具是否为只读查询类工具。
            只读工具会在 Agent 思考过程中自动执行，结果反馈给 LLM。
            非只读工具需要用户确认后才执行。

    Example:
        ```python
        @ToolRegistry.register
        class AddCharacterExecutor(BaseToolExecutor):
            @classmethod
            def get_name(cls) -> str:
                return "add_character"

            @classmethod
            def get_definition(cls) -> ToolDefinition:
                return ToolDefinition(
                    name="add_character",
                    description="添加新角色",
                    parameters={...}
                )

            def generate_preview(self, params: Dict[str, Any]) -> str:
                return f"新增角色「{params['name']}」"

            async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
                # 执行逻辑
                ...

        @ToolRegistry.register
        class GetChapterContentExecutor(BaseToolExecutor):
            is_read_only = True  # 查询类工具，自动执行
            ...
        ```
    """

    # 是否为只读查询工具，子类可覆盖
    # True: 自动执行，结果反馈给 LLM 继续思考
    # False: 需要用户确认后执行
    is_read_only: bool = False

    def __init__(self, session: "AsyncSession"):
        """初始化执行器。

        Args:
            session: SQLAlchemy 异步会话，用于数据库操作
        """
        self.session = session

    @classmethod
    @abstractmethod
    def get_name(cls) -> str:
        """返回工具名称。

        名称需全局唯一，建议使用 snake_case 格式。

        Returns:
            工具名称字符串
        """
        pass

    @classmethod
    @abstractmethod
    def get_definition(cls) -> ToolDefinition:
        """返回工具的 Function Calling 定义。

        定义包含工具名称、描述和参数 JSON Schema。

        Returns:
            ToolDefinition 实例
        """
        pass

    @abstractmethod
    def generate_preview(self, params: Dict[str, Any]) -> str:
        """生成操作预览文本。

        预览文本用于前端展示，帮助用户理解操作内容。
        应简洁明了，通常一行文字。

        Args:
            params: 工具调用参数

        Returns:
            预览文本字符串
        """
        pass

    @abstractmethod
    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        """执行工具逻辑。

        这是工具的核心方法，实现具体的业务逻辑。
        需要保存 before_state 和 after_state 以支持撤销。

        Args:
            project_id: 小说项目 ID
            params: 工具调用参数，已通过 validate_params 校验

        Returns:
            ToolResult 包含执行结果
        """
        pass

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        """校验参数有效性。

        在 execute 之前调用，用于提前发现参数问题。
        默认实现不做校验，子类可覆盖此方法。

        Args:
            params: 工具调用参数

        Returns:
            错误信息字符串，如果校验通过返回 None
        """
        return None

    # ========== 辅助方法（子类可复用） ==========

    async def _get_project(self, project_id: str):
        """获取小说项目。

        Args:
            project_id: 项目 ID

        Returns:
            NovelProject 实例

        Raises:
            HTTPException: 项目不存在时抛出 404
        """
        from fastapi import HTTPException

        from ...repositories.novel_repository import NovelRepository

        repo = NovelRepository(self.session)
        project = await repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")
        return project

    async def _get_blueprint(self, project_id: str):
        """获取小说蓝图。

        Args:
            project_id: 项目 ID

        Returns:
            NovelBlueprint 实例

        Raises:
            HTTPException: 蓝图不存在时抛出 404
        """
        from fastapi import HTTPException

        project = await self._get_project(project_id)
        if not project.blueprint:
            raise HTTPException(status_code=404, detail="项目蓝图不存在，请先创建蓝图")
        return project.blueprint

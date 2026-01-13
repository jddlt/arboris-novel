"""伏笔管理工具执行器。"""

from .add_foreshadowing import AddForeshadowingExecutor
from .update_foreshadowing import UpdateForeshadowingExecutor
from .delete_foreshadowing import DeleteForeshadowingExecutor
from .add_clue import AddClueExecutor
from .reveal_foreshadowing import RevealForeshadowingExecutor
from .get_foreshadowing import GetForeshadowingExecutor

__all__ = [
    "AddForeshadowingExecutor",
    "UpdateForeshadowingExecutor",
    "DeleteForeshadowingExecutor",
    "AddClueExecutor",
    "RevealForeshadowingExecutor",
    "GetForeshadowingExecutor",
]

"""添加卷工具执行器。"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import select

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....models.novel import Volume
from ....services.gm.tool_registry import ToolRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# 中文数字映射
CN_NUM_MAP = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
    "十六": 16, "十七": 17, "十八": 18, "十九": 19, "二十": 20,
}


def parse_chinese_number(cn_num: str) -> Optional[int]:
    """解析中文数字。"""
    if cn_num in CN_NUM_MAP:
        return CN_NUM_MAP[cn_num]
    # 处理 "二十一" 到 "二十九" 等
    if cn_num.startswith("二十") and len(cn_num) == 3:
        last = cn_num[2]
        if last in CN_NUM_MAP:
            return 20 + CN_NUM_MAP[last]
    return None


@ToolRegistry.register
class AddVolumeExecutor(BaseToolExecutor):
    """添加新卷。"""

    @classmethod
    def get_name(cls) -> str:
        return "add_volume"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="add_volume",
            description="添加一个新卷到小说结构中。用于规划长篇小说的卷/篇章划分。",
            parameters={
                "type": "object",
                "properties": {
                    "volume_number": {
                        "type": "integer",
                        "description": "卷序号，从1开始",
                    },
                    "title": {
                        "type": "string",
                        "description": "卷标题，如：序章·命运的起点",
                    },
                    "summary": {
                        "type": "string",
                        "description": "卷概要，描述本卷的主要内容",
                    },
                    "core_conflict": {
                        "type": "string",
                        "description": "本卷的核心冲突",
                    },
                    "climax": {
                        "type": "string",
                        "description": "本卷的高潮点描述",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["planned", "in_progress", "completed"],
                        "description": "卷状态：planned(规划中)、in_progress(写作中)、completed(已完成)",
                    },
                },
                "required": ["volume_number", "title"],
            },
        )

    def _normalize_params(self, params: Dict[str, Any]) -> None:
        """参数别名标准化 - 模型可能使用不同的参数名或格式。"""
        # 1. 处理参数别名
        if "order" in params and "volume_number" not in params:
            params["volume_number"] = params.pop("order")
        if "卷号" in params and "volume_number" not in params:
            params["volume_number"] = params.pop("卷号")
        if "序号" in params and "volume_number" not in params:
            params["volume_number"] = params.pop("序号")
        if "标题" in params and "title" not in params:
            params["title"] = params.pop("标题")
        if "概要" in params and "summary" not in params:
            params["summary"] = params.pop("概要")
        if "描述" in params and "summary" not in params:
            params["summary"] = params.pop("描述")

        # 2. 如果 volume_number 缺失，尝试从 title 中提取
        # 例如: "第一卷：悼亡者之瞳" -> volume_number=1, title="悼亡者之瞳"
        if params.get("volume_number") is None and params.get("title"):
            title = str(params["title"])

            # 匹配 "第X卷" 格式（中文数字）
            cn_match = re.match(r"^第([一二三四五六七八九十]+)卷[：:·\s\-—]*(.*)$", title)
            if cn_match:
                cn_num = cn_match.group(1)
                parsed = parse_chinese_number(cn_num)
                if parsed:
                    params["volume_number"] = parsed
                    remaining_title = cn_match.group(2).strip()
                    if remaining_title:
                        params["title"] = remaining_title
                    logger.info("从标题提取卷号: %s -> volume_number=%d, title=%s",
                               title, parsed, params["title"])
                    return

            # 匹配 "第X卷" 格式（阿拉伯数字）
            num_match = re.match(r"^第(\d+)卷[：:·\s\-—]*(.*)$", title)
            if num_match:
                params["volume_number"] = int(num_match.group(1))
                remaining_title = num_match.group(2).strip()
                if remaining_title:
                    params["title"] = remaining_title
                logger.info("从标题提取卷号: %s -> volume_number=%d, title=%s",
                           title, params["volume_number"], params["title"])

    def generate_preview(self, params: Dict[str, Any]) -> str:
        self._normalize_params(params)
        volume_number = params.get("volume_number")
        try:
            volume_number = int(volume_number) if volume_number is not None else "?"
        except (ValueError, TypeError):
            volume_number = "?"
        title = params.get("title", "未命名")
        return f"添加卷：第{volume_number}卷 - {title}"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        self._normalize_params(params)

        volume_number = params.get("volume_number")
        try:
            volume_number = int(volume_number)
            if volume_number < 1:
                return "卷序号必须大于0"
        except (ValueError, TypeError):
            return "卷序号必须是有效的整数"

        title = params.get("title")
        if not title or not str(title).strip():
            return "卷标题不能为空"

        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        volume_number = int(params["volume_number"])
        title = str(params["title"]).strip()

        # 检查卷序号是否已存在
        existing = await self.session.execute(
            select(Volume).where(
                Volume.project_id == project_id,
                Volume.volume_number == volume_number,
            )
        )
        if existing.scalars().first():
            return ToolResult(
                success=False,
                message=f"第{volume_number}卷已存在，请使用 update_volume 修改",
            )

        # 创建新卷
        new_volume = Volume(
            project_id=project_id,
            volume_number=volume_number,
            title=title,
            summary=params.get("summary", ""),
            core_conflict=params.get("core_conflict", ""),
            climax=params.get("climax", ""),
            status=params.get("status", "planned"),
        )

        self.session.add(new_volume)
        await self.session.flush()

        logger.info(
            "添加卷成功: project=%s, volume_number=%d, title=%s",
            project_id,
            volume_number,
            title,
        )

        return ToolResult(
            success=True,
            message=f"成功添加第{volume_number}卷：{title}",
            data={
                "volume_id": new_volume.id,
                "volume_number": volume_number,
                "title": title,
            },
            before_state=None,
            after_state={
                "id": new_volume.id,
                "volume_number": volume_number,
                "title": title,
                "summary": new_volume.summary,
                "core_conflict": new_volume.core_conflict,
                "climax": new_volume.climax,
                "status": new_volume.status,
            },
        )

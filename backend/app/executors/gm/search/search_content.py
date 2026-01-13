"""搜索小说内容工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....services.gm.tool_registry import ToolRegistry
from ....services.vector_store_service import (
    VectorStoreService,
    RetrievedChunk,
    RetrievedSummary,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class SearchContentExecutor(BaseToolExecutor):
    """搜索小说内容（基于 RAG 向量检索）。"""

    # 查询类工具，自动执行
    is_read_only = True

    @classmethod
    def get_name(cls) -> str:
        return "search_content"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="search_content",
            description="搜索小说内容，基于语义相似度查找相关的剧情片段和章节摘要。支持时间衰减权重，优先返回最新章节的匹配结果。用于回顾特定情节、确认设定一致性、查找人物最新状态等。",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询，描述要查找的内容，如：「主角与反派的第一次交锋」「女主的身世背景」「主角当前的装备」",
                    },
                    "search_type": {
                        "type": "string",
                        "enum": ["chunks", "summaries", "both"],
                        "description": "搜索类型：chunks=剧情片段，summaries=章节摘要，both=两者都搜",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回的最大结果数量，默认5",
                    },
                    "recency_weight": {
                        "type": "number",
                        "description": "时间衰减权重（0-1），越高则越优先返回最新章节的结果。0=纯语义排序，1=纯按章节倒序。默认0.3",
                    },
                },
                "required": ["query"],
            },
        )

    def generate_preview(self, params: Dict[str, Any]) -> str:
        query = params.get("query", "")
        if len(query) > 30:
            query = query[:30] + "..."
        return f"搜索内容：{query}"

    async def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        query = params.get("query")
        if not query or not query.strip():
            return "必须提供搜索查询"
        if len(query) > 500:
            return "查询内容过长，最多500个字符"
        return None

    async def execute(self, project_id: str, params: Dict[str, Any]) -> ToolResult:
        from ....services.llm_service import LLMService

        query = params["query"].strip()
        search_type = params.get("search_type", "both")

        # 确保 top_k 是整数
        try:
            top_k = int(params.get("top_k", 5))
        except (ValueError, TypeError):
            top_k = 5

        if top_k < 1:
            top_k = 5
        if top_k > 20:
            top_k = 20

        # 获取时间衰减权重（0-1），默认 0.3
        try:
            recency_weight = float(params.get("recency_weight", 0.3))
        except (ValueError, TypeError):
            recency_weight = 0.3
        recency_weight = max(0.0, min(1.0, recency_weight))

        # 生成查询向量
        llm_service = LLMService(self.session)
        try:
            embedding = await llm_service.get_embedding(query)
        except Exception as e:
            logger.warning("生成查询向量失败: %s", e)
            return ToolResult(
                success=False,
                message=f"搜索失败：无法生成查询向量 - {str(e)}",
            )

        if not embedding:
            return ToolResult(
                success=False,
                message="搜索失败：向量服务未配置或不可用",
            )

        # 执行向量检索（获取更多结果用于重排序）
        fetch_k = top_k * 3 if recency_weight > 0 else top_k
        vector_store = VectorStoreService()
        results: Dict[str, Any] = {
            "query": query,
            "recency_weight": recency_weight,
            "chunks": [],
            "summaries": [],
        }

        if search_type in ("chunks", "both"):
            try:
                chunks = await vector_store.query_chunks(
                    project_id=project_id,
                    embedding=embedding,
                    top_k=fetch_k,
                )
                # 应用时间衰减重排序
                chunks = self._rerank_by_recency(chunks, recency_weight)[:top_k]
                results["chunks"] = [
                    {
                        "chapter_number": c.chapter_number,
                        "chapter_title": c.chapter_title,
                        "content": c.content[:500] + "..." if len(c.content) > 500 else c.content,
                        "semantic_score": round(c.score, 4),
                    }
                    for c in chunks
                ]
            except Exception as e:
                logger.warning("检索剧情片段失败: %s", e)

        if search_type in ("summaries", "both"):
            try:
                summaries = await vector_store.query_summaries(
                    project_id=project_id,
                    embedding=embedding,
                    top_k=fetch_k,
                )
                # 应用时间衰减重排序
                summaries = self._rerank_summaries_by_recency(summaries, recency_weight)[:top_k]
                results["summaries"] = [
                    {
                        "chapter_number": s.chapter_number,
                        "title": s.title,
                        "summary": s.summary[:300] + "..." if len(s.summary) > 300 else s.summary,
                        "semantic_score": round(s.score, 4),
                    }
                    for s in summaries
                ]
            except Exception as e:
                logger.warning("检索章节摘要失败: %s", e)

        total_results = len(results["chunks"]) + len(results["summaries"])

        if total_results == 0:
            return ToolResult(
                success=True,
                message=f"未找到与「{query}」相关的内容",
                data=results,
            )

        # 构建结果摘要
        summary_parts = []
        if results["chunks"]:
            summary_parts.append(f"{len(results['chunks'])} 个剧情片段")
        if results["summaries"]:
            summary_parts.append(f"{len(results['summaries'])} 个章节摘要")

        logger.info(
            "搜索内容成功: project=%s, query=%s, recency_weight=%.2f, results=%d",
            project_id,
            query[:50],
            recency_weight,
            total_results,
        )

        return ToolResult(
            success=True,
            message=f"找到 {' 和 '.join(summary_parts)}",
            data=results,
        )

    def _rerank_by_recency(
        self, chunks: List[RetrievedChunk], recency_weight: float
    ) -> List[RetrievedChunk]:
        """根据时间衰减权重重排序剧情片段。

        final_score = semantic_distance * (1 - recency_weight) + recency_penalty * recency_weight

        其中 recency_penalty 基于章节号归一化，章节越新惩罚越小。
        """
        if not chunks or recency_weight == 0:
            return chunks

        max_chapter = max(c.chapter_number for c in chunks)
        min_chapter = min(c.chapter_number for c in chunks)
        chapter_range = max_chapter - min_chapter if max_chapter > min_chapter else 1

        scored_chunks = []
        for c in chunks:
            # 归一化章节号：最新章节 = 0，最老章节 = 1
            recency_penalty = (max_chapter - c.chapter_number) / chapter_range
            # 综合得分：语义距离 + 时间惩罚
            final_score = c.score * (1 - recency_weight) + recency_penalty * recency_weight
            scored_chunks.append((final_score, c))

        scored_chunks.sort(key=lambda x: x[0])
        return [c for _, c in scored_chunks]

    def _rerank_summaries_by_recency(
        self, summaries: List[RetrievedSummary], recency_weight: float
    ) -> List[RetrievedSummary]:
        """根据时间衰减权重重排序章节摘要。"""
        if not summaries or recency_weight == 0:
            return summaries

        max_chapter = max(s.chapter_number for s in summaries)
        min_chapter = min(s.chapter_number for s in summaries)
        chapter_range = max_chapter - min_chapter if max_chapter > min_chapter else 1

        scored_summaries = []
        for s in summaries:
            recency_penalty = (max_chapter - s.chapter_number) / chapter_range
            final_score = s.score * (1 - recency_weight) + recency_penalty * recency_weight
            scored_summaries.append((final_score, s))

        scored_summaries.sort(key=lambda x: x[0])
        return [s for _, s in scored_summaries]

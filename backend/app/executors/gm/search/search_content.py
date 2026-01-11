"""搜索小说内容工具执行器。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..base import BaseToolExecutor, ToolDefinition, ToolResult
from ....services.gm.tool_registry import ToolRegistry
from ....services.vector_store_service import VectorStoreService, RetrievedChunk, RetrievedSummary

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@ToolRegistry.register
class SearchContentExecutor(BaseToolExecutor):
    """搜索小说内容（基于 RAG 向量检索）。"""

    @classmethod
    def get_name(cls) -> str:
        return "search_content"

    @classmethod
    def get_definition(cls) -> ToolDefinition:
        return ToolDefinition(
            name="search_content",
            description="搜索小说内容，基于语义相似度查找相关的剧情片段和章节摘要。用于回顾特定情节、确认设定一致性。",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询，描述要查找的内容，如：「主角与反派的第一次交锋」「女主的身世背景」",
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

        # 执行向量检索
        vector_store = VectorStoreService()
        results: Dict[str, Any] = {
            "query": query,
            "chunks": [],
            "summaries": [],
        }

        if search_type in ("chunks", "both"):
            try:
                chunks = await vector_store.query_chunks(
                    project_id=project_id,
                    embedding=embedding,
                    top_k=top_k,
                )
                results["chunks"] = [
                    {
                        "chapter_number": c.chapter_number,
                        "chapter_title": c.chapter_title,
                        "content": c.content[:500] + "..." if len(c.content) > 500 else c.content,
                        "score": round(c.score, 4),
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
                    top_k=top_k,
                )
                results["summaries"] = [
                    {
                        "chapter_number": s.chapter_number,
                        "title": s.title,
                        "summary": s.summary[:300] + "..." if len(s.summary) > 300 else s.summary,
                        "score": round(s.score, 4),
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
            "搜索内容成功: project=%s, query=%s, results=%d",
            project_id,
            query[:50],
            total_results,
        )

        return ToolResult(
            success=True,
            message=f"找到 {' 和 '.join(summary_parts)}",
            data=results,
        )

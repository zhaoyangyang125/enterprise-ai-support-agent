import math
import re
from typing import Protocol

from app.schemas.rag import IndexedChunk, RetrievedChunk


class VectorRepository(Protocol):
    """定义权限过滤后的语义检索接口。 / Defines the semantic-retrieval interface with authorization filtering."""

    def search(
        self,
        query: str,
        allowed_document_version_ids: frozenset[str],
        limit: int,
    ) -> list[RetrievedChunk]:
        """只在允许的文档版本内检索相关片段。 / Searches relevant chunks only within allowed document versions."""

        ...


class InMemoryVectorRepository:
    """提供无需外部服务的本地确定性检索实现。 / Provides deterministic local retrieval without external services."""

    def __init__(self, chunks: list[IndexedChunk]) -> None:
        """保存本地可检索的文档片段。 / Stores document chunks available for local retrieval."""

        self._chunks = list(chunks)

    def search(
        self,
        query: str,
        allowed_document_version_ids: frozenset[str],
        limit: int,
    ) -> list[RetrievedChunk]:
        """先按权限版本过滤，再计算字符 n-gram 相似度。 / Filters by authorized versions before calculating character n-gram similarity."""

        candidates = (
            chunk
            for chunk in self._chunks
            if chunk.document_version_id in allowed_document_version_ids
        )
        ranked = [
            RetrievedChunk(**chunk.model_dump(), score=self._similarity(query, chunk.content))
            for chunk in candidates
        ]
        ranked.sort(key=lambda chunk: chunk.score, reverse=True)
        return ranked[:limit]

    @staticmethod
    def _similarity(left: str, right: str) -> float:
        """计算适合本地演示的字符二元组余弦相似度。 / Calculates character-bigram cosine similarity for the local demo."""

        left_terms = InMemoryVectorRepository._bigrams(left)
        right_terms = InMemoryVectorRepository._bigrams(right)
        if not left_terms or not right_terms:
            return 0.0
        overlap = len(left_terms & right_terms)
        return overlap / math.sqrt(len(left_terms) * len(right_terms))

    @staticmethod
    def _bigrams(value: str) -> set[str]:
        """将中日英文本规范化为字符二元组集合。 / Normalizes Chinese, Japanese, and English text into character-bigram sets."""

        normalized = re.sub(r"[^\w\u3040-\u30ff\u3400-\u9fff]", "", value.lower())
        if len(normalized) < 2:
            return {normalized} if normalized else set()
        return {normalized[index : index + 2] for index in range(len(normalized) - 1)}

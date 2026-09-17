"""BM25关键词检索与RRF融合。 / BM25 keyword retrieval and RRF fusion."""
import math
import re
from collections import Counter
from typing import Protocol

from app.repositories.vector_repository import (
    ChromaVectorRepository,
    VectorRepository,
    matches_retrieval_scope,
)
from app.schemas.rag import IndexedChunk, RetrievedChunk, RetrievalFilter


class KeywordRepository(Protocol):
    """定义带授权范围的关键词检索接口。 / Defines authorized keyword retrieval."""

    def search(
        self,
        query: str,
        allowed_document_version_ids: frozenset[str],
        limit: int,
        metadata_filter: RetrievalFilter | None = None,
    ) -> list[RetrievedChunk]:
        """只检索授权且符合metadata条件的Chunk。 / Searches only authorized chunks."""
        ...


class Bm25KeywordRetriever:
    """对小型授权候选集合执行容易理解的BM25。 / Runs readable BM25 over authorized candidates."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        """保存标准BM25参数。 / Stores standard BM25 parameters."""
        self._k1 = k1
        self._b = b

    def rank(
        self,
        query: str,
        chunks: list[IndexedChunk],
        limit: int,
    ) -> list[RetrievedChunk]:
        """使用正文和可追踪metadata进行关键词排名。 / Ranks content and citation metadata."""
        query_terms = self._tokenize(query)
        if not query_terms or not chunks or limit <= 0:
            return []
        documents: list[list[str]] = []
        for chunk in chunks:
            documents.append(self._tokenize(self._searchable_text(chunk)))
        average_length = sum(len(document) for document in documents) / len(documents)
        document_frequencies: Counter[str] = Counter()
        for document in documents:
            for term in set(document):
                document_frequencies[term] += 1
        raw_results: list[tuple[IndexedChunk, float]] = []
        for index in range(len(chunks)):
            document = documents[index]
            score = self._score_document(
                query_terms,
                document,
                document_frequencies,
                len(documents),
                average_length,
            )
            if score > 0:
                raw_results.append((chunks[index], score))
        raw_results.sort(key=lambda item: (-item[1], item[0].chunk_id))
        if not raw_results:
            return []
        maximum_score = raw_results[0][1]
        results: list[RetrievedChunk] = []
        for chunk, raw_score in raw_results[:limit]:
            normalized_score = raw_score / maximum_score
            document_terms = self._tokenize(self._searchable_text(chunk))
            match_ratio = self._calculate_match_ratio(query_terms, document_terms)
            result = RetrievedChunk(
                **chunk.model_dump(),
                score=normalized_score,
                keyword_score=normalized_score,
                keyword_match_ratio=match_ratio,
            )
            results.append(result)
        return results

    @staticmethod
    def _calculate_match_ratio(
        query_terms: list[str],
        document_terms: list[str],
    ) -> float:
        """计算查询词中实际出现在证据里的比例。 / Calculates query-term coverage in evidence."""
        unique_query_terms = set(query_terms)
        if not unique_query_terms:
            return 0.0

        document_term_set = set(document_terms)
        matched_count = 0
        for term in unique_query_terms:
            if term in document_term_set:
                matched_count += 1

        return matched_count / len(unique_query_terms)

    def _score_document(
        self,
        query_terms: list[str],
        document: list[str],
        frequencies: Counter[str],
        document_count: int,
        average_length: float,
    ) -> float:
        """计算单个文档的BM25分数。 / Calculates one BM25 score."""
        term_counts = Counter(document)
        score = 0.0
        for term in set(query_terms):
            term_count = term_counts.get(term, 0)
            if term_count == 0:
                continue
            document_frequency = frequencies.get(term, 0)
            numerator = document_count - document_frequency + 0.5
            denominator_for_idf = document_frequency + 0.5
            idf = math.log(1 + numerator / denominator_for_idf)

            length_ratio = 0.0
            if average_length > 0:
                length_ratio = len(document) / average_length

            denominator = term_count + self._k1 * (1 - self._b + self._b * length_ratio)
            score += idf * (term_count * (self._k1 + 1)) / denominator
        return score

    @staticmethod
    def _searchable_text(chunk: IndexedChunk) -> str:
        """合并正文与精确定位metadata供关键词匹配。 / Combines content and searchable metadata."""
        values = [chunk.content, chunk.document_id, chunk.source_name, chunk.section,
                  chunk.sheet, chunk.cell_range, chunk.rows]
        parts: list[str] = []
        for value in values:
            if value:
                parts.append(str(value))
        return " ".join(parts)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """保留编号/范围，并为中日文补充字符bigram。 / Preserves codes and adds CJK bigrams."""
        normalized = text.casefold()
        token_pattern = (
            r"[a-z0-9]+(?:[-_.:][a-z0-9]+)*"
            r"|[\u3040-\u30ff]+"
            r"|[\u3400-\u9fff]+"
        )
        tokens = re.findall(token_pattern, normalized)
        result: list[str] = []
        for token in tokens:
            result.append(token)
            if re.fullmatch(r"[\u3040-\u30ff\u3400-\u9fff]+", token) and len(token) > 1:
                for index in range(len(token) - 1):
                    result.append(token[index:index + 2])
        return result


class ChromaKeywordRepository:
    """从同一Chroma集合读取已授权Chunk后执行BM25。 / Runs BM25 over authorized Chroma chunks."""

    def __init__(
        self,
        source: ChromaVectorRepository,
        retriever: Bm25KeywordRetriever | None = None,
    ) -> None:
        """复用Chroma存储和where过滤。 / Reuses Chroma storage and filters."""
        self._source = source
        self._retriever = retriever or Bm25KeywordRetriever()

    def search(
        self,
        query: str,
        allowed_document_version_ids: frozenset[str],
        limit: int,
        metadata_filter: RetrievalFilter | None = None,
    ) -> list[RetrievedChunk]:
        """ACL和metadata先过滤，再计算BM25。 / Filters before BM25 ranking."""
        chunks = self._source.list_authorized_chunks(
            allowed_document_version_ids,
            metadata_filter,
        )
        return self._retriever.rank(query, chunks, limit)


class InMemoryKeywordRepository:
    """为离线测试和评测提供同规则关键词检索。 / Provides offline keyword retrieval."""

    def __init__(
        self,
        chunks: list[IndexedChunk],
        retriever: Bm25KeywordRetriever | None = None,
    ) -> None:
        """保存固定Chunk集合。 / Stores a fixed chunk collection."""
        self._chunks = list(chunks)
        self._retriever = retriever or Bm25KeywordRetriever()

    def search(
        self,
        query: str,
        allowed_document_version_ids: frozenset[str],
        limit: int,
        metadata_filter: RetrievalFilter | None = None,
    ) -> list[RetrievedChunk]:
        """先做安全过滤，再执行BM25。 / Applies scope before BM25."""
        candidates: list[IndexedChunk] = []
        for chunk in self._chunks:
            is_visible = matches_retrieval_scope(
                chunk,
                allowed_document_version_ids,
                metadata_filter,
            )
            if is_visible:
                candidates.append(chunk)
        return self._retriever.rank(query, candidates, limit)


def reciprocal_rank_fusion(
    result_lists: list[list[RetrievedChunk]],
    rrf_k: int = 60,
) -> list[RetrievedChunk]:
    """按chunk_id去重并计算规范化RRF分数。 / Deduplicates and computes normalized RRF."""
    if rrf_k <= 0:
        raise ValueError("rrf_k must be positive")
    if not result_lists:
        return []
    scores: dict[str, float] = {}
    chunks: dict[str, RetrievedChunk] = {}
    vector_scores: dict[str, float] = {}
    keyword_scores: dict[str, float] = {}
    keyword_match_ratios: dict[str, float] = {}
    for results in result_lists:
        seen_in_list: set[str] = set()
        for index in range(len(results)):
            chunk = results[index]
            if chunk.chunk_id in seen_in_list:
                continue
            seen_in_list.add(chunk.chunk_id)
            rank = index + 1
            current_score = scores.get(chunk.chunk_id, 0.0)
            rank_score = 1.0 / (rrf_k + rank)
            scores[chunk.chunk_id] = current_score + rank_score
            if chunk.chunk_id not in chunks:
                chunks[chunk.chunk_id] = chunk
            _keep_highest_signal(vector_scores, chunk.chunk_id, chunk.vector_score)
            _keep_highest_signal(keyword_scores, chunk.chunk_id, chunk.keyword_score)
            _keep_highest_signal(
                keyword_match_ratios,
                chunk.chunk_id,
                chunk.keyword_match_ratio,
            )
    maximum_possible = len(result_lists) / (rrf_k + 1)
    fused: list[RetrievedChunk] = []
    for chunk_id, raw_score in scores.items():
        normalized_score = min(1.0, raw_score / maximum_possible)
        updates = {
            "score": normalized_score,
            "vector_score": vector_scores.get(chunk_id),
            "keyword_score": keyword_scores.get(chunk_id),
            "keyword_match_ratio": keyword_match_ratios.get(chunk_id),
        }
        fused_chunk = chunks[chunk_id].model_copy(update=updates)
        fused.append(fused_chunk)
    fused.sort(key=lambda chunk: (-chunk.score, chunk.chunk_id))
    return fused


def _keep_highest_signal(
    signals: dict[str, float],
    chunk_id: str,
    value: float | None,
) -> None:
    """保留同一Chunk最强的原始检索信号。 / Keeps the strongest raw retrieval signal."""
    if value is None:
        return

    current_value = signals.get(chunk_id)
    if current_value is None or value > current_value:
        signals[chunk_id] = value


class HybridVectorRepository:
    """并行概念上的Vector+Keyword检索并用RRF合并。 / Combines vector and keyword rankings."""

    def __init__(
        self,
        vector_repository: VectorRepository,
        keyword_repository: KeywordRepository,
        candidate_multiplier: int = 4,
        minimum_vector_score: float = 0.15,
    ) -> None:
        """设置候选扩大倍率和向量最低可信度。 / Configures candidate expansion."""
        if candidate_multiplier < 1:
            raise ValueError("candidate_multiplier must be positive")
        self._vector = vector_repository
        self._keyword = keyword_repository
        self._candidate_multiplier = candidate_multiplier
        self._minimum_vector_score = minimum_vector_score

    def search(
        self,
        query: str,
        allowed_document_version_ids: frozenset[str],
        limit: int,
        metadata_filter: RetrievalFilter | None = None,
    ) -> list[RetrievedChunk]:
        """两路使用相同安全范围，融合后再次防御性检查。 / Uses identical safe scopes."""
        if not allowed_document_version_ids or limit <= 0:
            return []
        candidate_limit = max(limit, limit * self._candidate_multiplier)
        vector_results = self._vector.search(
            query,
            allowed_document_version_ids,
            candidate_limit,
            metadata_filter,
        )
        reliable_vector_results: list[RetrievedChunk] = []
        for chunk in vector_results:
            if chunk.score >= self._minimum_vector_score:
                chunk_with_signal = chunk.model_copy(
                    update={"vector_score": chunk.score}
                )
                reliable_vector_results.append(chunk_with_signal)
        keyword_results = self._keyword.search(
            query,
            allowed_document_version_ids,
            candidate_limit,
            metadata_filter,
        )
        fused = reciprocal_rank_fusion([reliable_vector_results, keyword_results])
        safe_results: list[RetrievedChunk] = []
        for chunk in fused:
            is_visible = matches_retrieval_scope(
                chunk,
                allowed_document_version_ids,
                metadata_filter,
            )
            if is_visible:
                safe_results.append(chunk)
        return safe_results[:limit]

"""命中片段的上下文扩展:同节邻居 + 「→P.xx」引用页。 / Context expansion for retrieval hits: same-section neighbors and "→P.xx" referenced pages.

只在证据判定通过之后追加,不参与证据门限。追加的片段分数低于命中片段,且数量有上限。
Runs after the evidence gate, never affects it; extras score below the hit and are capped.
"""
from app.repositories.vector_repository import ChromaVectorRepository
from app.schemas.rag import IndexedChunk, RetrievedChunk

_SUPPORT_SCORE_FACTOR = 0.5  # 追加片段分数 = 命中分数 × 此系数 / support chunks score = hit score × this


class ContextExpander:
    """为前几条命中补充邻居和引用页片段。 / Adds neighbors and referenced-page chunks for the top hits."""

    def __init__(
        self,
        repository: ChromaVectorRepository,
        top_hits: int = 1,
        neighbor_window: int = 1,
        max_referenced_per_hit: int = 0,  # 引用页は関連しないものが多いため既定で無効 / off by default: referenced pages were often off-topic
        max_extra: int = 2,
    ) -> None:
        self._repository = repository
        self._top_hits = top_hits
        self._neighbor_window = neighbor_window
        self._max_referenced_per_hit = max_referenced_per_hit
        self._max_extra = max_extra

    def expand(
        self,
        evidence: list[RetrievedChunk],
        allowed_document_version_ids: frozenset[str],
    ) -> list[RetrievedChunk]:
        """返回需要追加在证据之后的支撑片段(已去重、已授权)。 / Returns deduplicated, authorized support chunks to append."""
        seen = {chunk.chunk_id for chunk in evidence}
        extras: list[RetrievedChunk] = []
        for hit in evidence[: self._top_hits]:
            for support in self._candidates(hit, allowed_document_version_ids):
                if len(extras) >= self._max_extra:
                    return extras
                if support.chunk_id in seen:
                    continue
                seen.add(support.chunk_id)
                extras.append(self._as_support(support, hit))
        return extras

    def _candidates(
        self, hit: RetrievedChunk, allowed: frozenset[str]
    ) -> list[IndexedChunk]:
        neighbors = [
            n
            for n in self._repository.get_neighbors(hit, allowed, self._neighbor_window)
            # 两块都有小标题且不同,说明主题不同。 / Both headed and different means a different topic.
            if not (n.heading and hit.heading and n.heading != hit.heading)
        ]
        referenced = (
            self._repository.get_referenced(hit, allowed)[: self._max_referenced_per_hit]
            if self._max_referenced_per_hit > 0
            else []
        )
        return [*neighbors, *referenced]

    @staticmethod
    def _as_support(support: IndexedChunk, hit: RetrievedChunk) -> RetrievedChunk:
        return RetrievedChunk(
            **support.model_dump(),
            score=max(0.0, min(1.0, hit.score * _SUPPORT_SCORE_FACTOR)),
        )

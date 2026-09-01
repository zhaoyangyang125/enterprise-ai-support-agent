import hashlib
import math
import re
from typing import Protocol


class EmbeddingProvider(Protocol):
    """定义文本转换为固定维度向量的可替换接口。 / Defines a replaceable interface for converting text into fixed-size vectors."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """为一批文本生成向量。 / Generates vectors for a batch of texts."""

        ...


class HashEmbeddingProvider:
    """提供无需模型下载的确定性字符 n-gram Embedding。 / Provides deterministic character n-gram embeddings without model downloads."""

    def __init__(self, dimensions: int = 256) -> None:
        """设置固定向量维度。 / Sets the fixed vector dimension."""

        if dimensions < 8:
            raise ValueError("dimensions must be at least 8")
        self._dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        """使用稳定哈希将中日英字符二元组映射到归一化向量。 / Maps Chinese, Japanese, and English character bigrams to normalized vectors with stable hashing."""

        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        """生成单段文本的本地向量。 / Generates a local vector for one text."""

        normalized = re.sub(r"[^\w\u3040-\u30ff\u3400-\u9fff]", "", text.casefold())
        terms = (
            [normalized]
            if len(normalized) < 2
            else [normalized[index : index + 2] for index in range(len(normalized) - 1)]
        )
        vector = [0.0] * self._dimensions
        for term in terms:
            digest = hashlib.sha256(term.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

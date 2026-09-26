class RagProviderError(Exception):
    """表示外部 RAG Provider 失败，消息只含安全错误代码。 / Safe external-provider failure."""


class EmbeddingIndexMismatchError(Exception):
    """表示现有向量索引与当前 Embedding 配置不兼容。 / Incompatible embedding index."""

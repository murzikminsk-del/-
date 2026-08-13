"""Три стратегии чанкинга для сравнительного эксперимента (Блок 5.4)."""

from llama_index.core.node_parser import SentenceSplitter, TokenTextSplitter
from llama_index.core.schema import BaseNode, Document


def fixed_size(documents: list[Document]) -> list[BaseNode]:
    splitter = TokenTextSplitter(chunk_size=512, chunk_overlap=64)
    return splitter.get_nodes_from_documents(documents)


def recursive(documents: list[Document]) -> list[BaseNode]:
    splitter = SentenceSplitter(
        chunk_size=512,
        chunk_overlap=64,
        paragraph_separator="\n\n",
    )
    return splitter.get_nodes_from_documents(documents)


def semantic(documents: list[Document], embed_model) -> list[BaseNode]:
    from llama_index.core.node_parser import SemanticSplitterNodeParser

    splitter = SemanticSplitterNodeParser(
        buffer_size=1,
        breakpoint_percentile_threshold=95,
        embed_model=embed_model,
    )
    return splitter.get_nodes_from_documents(documents)
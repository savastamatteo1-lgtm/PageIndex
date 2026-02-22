"""Data models for the ingestion pipeline.

Defines dataclasses that carry intermediate state between pipeline stages.
``DocumentPipeline`` tracks the complete lifecycle of a single document,
while ``ChunkData`` represents a single text chunk produced by the chunker
and consumed by the embedder and storage layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChunkData:
    """A single chunk of text extracted from a tree leaf node.

    Attributes
    ----------
    content : str
        The raw text content of the chunk.
    node_id : str
        The ``node_id`` from the tree structure for traceability.
    tree_path : str
        Human-readable path from root to this node
        (e.g. ``"Article 4 > Section 2 > Paragraph 3"``).
    metadata : dict
        Additional metadata: title, start_page, end_page, sub_chunk_index.
    """

    content: str
    node_id: str
    tree_path: str
    metadata: dict = field(default_factory=dict)


@dataclass
class DocumentPipeline:
    """Holds the complete state of a single document flowing through the pipeline.

    Fields are populated progressively as the document passes through each
    pipeline stage (tree indexing -> metadata extraction -> description ->
    chunking -> embedding -> storage).

    Attributes
    ----------
    pdf_path : str
        Absolute path to the source PDF file.
    doc_name : str
        Filename derived from ``os.path.basename(pdf_path)``.
    doc_id : str | None
        Populated after the document row is inserted into Supabase.
    tree_json : dict | None
        Tree structure produced by ``page_index_main()``.
    metadata : dict | None
        Structured Italian legal metadata extracted by the LLM.
    description : str | None
        LLM-generated one-sentence document description.
    needs_review : bool
        ``True`` if metadata extraction was incomplete (missing fields).
    chunks : list[ChunkData]
        Chunks produced by the tree-aware chunker.
    embeddings : list[list[float]]
        Embedding vectors aligned 1:1 with ``chunks``.
    """

    pdf_path: str
    doc_name: str
    doc_id: str | None = None
    tree_json: dict | None = None
    metadata: dict | None = None
    description: str | None = None
    needs_review: bool = False
    chunks: list[ChunkData] = field(default_factory=list)
    embeddings: list[list[float]] = field(default_factory=list)

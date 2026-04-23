"""Retrieval layer: BM25 (Postgres FTS), dense/sparse (Qdrant), hybrid fusion.

Three independent scorers, one fusion step. Dense lives in
:mod:`src.embeddings.indexer` (day-10 Qdrant upserts), BM25 lives here
(day-11), hybrid RRF lands on day-12 in :mod:`src.retrieval.hybrid`.
"""

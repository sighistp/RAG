from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    text: str
    doc_name: str
    chunk_index: int
    doc_permission_id: int | None = None

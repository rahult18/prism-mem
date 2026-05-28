from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Triple:
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0
    embedding: bytes = b""
    session_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    stale: bool = False
    id: int = 0


@dataclass
class Edge:
    from_id: int
    to_id: int
    edge_type: str
    weight: float

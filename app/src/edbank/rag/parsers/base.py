from dataclasses import dataclass, field


@dataclass
class ParsedChunk:
    record_key: str        # eindeutiger Schlüssel innerhalb des Dokuments
    content: str           # Text, der eingebettet wird
    metadata: dict = field(default_factory=dict)

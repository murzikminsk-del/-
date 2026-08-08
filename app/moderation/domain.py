from dataclasses import dataclass, field


@dataclass
class ModerationResult:
    allowed: bool
    categories: list[str] = field(default_factory=list)
    layer: str = ""
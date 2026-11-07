from dataclasses import dataclass


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    w: int
    h: int
    label: str   # "email", "card", "phone", "postcode", "ni", "bank", "name", "checking"
    text: str
    confidence: float = 1.0

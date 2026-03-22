from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PricePoint:
    timestamp: float
    price: float


@dataclass(frozen=True)
class NewsItem:
    timestamp_utc: str
    source: str
    headline: str
    url: str | None = None


JSONDict = dict[str, Any]

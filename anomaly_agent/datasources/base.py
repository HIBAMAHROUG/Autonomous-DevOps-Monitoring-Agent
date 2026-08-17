from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from abc import ABC, abstractmethod
from typing import Dict


@dataclass
class Sample:
    timestamp: datetime
    values: Dict[str, float]
    is_anomaly: bool = False

    @staticmethod
    def now(values: Dict[str, float], is_anomaly: bool = False) -> "Sample":
        return Sample(timestamp=datetime.now(timezone.utc), values=values, is_anomaly=is_anomaly)


class DataSource(ABC):
    @abstractmethod
    def fetch_latest(self) -> Sample:
        raise NotImplementedError

    @abstractmethod
    def fetch_history(self, days: int = 7):
        raise NotImplementedError

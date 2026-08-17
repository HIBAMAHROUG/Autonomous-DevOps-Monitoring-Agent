from .base import DataSource, Sample
from .mock import MockDataSource
from .metrics_api import MetricsApiDataSource
from ..config import settings


def get_data_source(name: str = None) -> DataSource:
    selected = (name or settings.data_source).lower()
    if selected in {"api", "metrics_api", "http"}:
        return MetricsApiDataSource()
    return MockDataSource()

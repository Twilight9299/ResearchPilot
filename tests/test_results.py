from decimal import Decimal

import pytest

from researchpilot.results import summarize_metric_csv


def test_metric_csv_counts_runs_and_calculates_mean() -> None:
    assert summarize_metric_csv(b"\xef\xbb\xbfvalue\r\n0.8\r\n0.9\r\n") == (Decimal("0.85"), 2)


@pytest.mark.parametrize(
    "data",
    [b"value\n", b"value,unit\n1,%\n", b"value\nNaN\n", b"value\ninvalid\n"],
)
def test_metric_csv_rejects_invalid_runs(data: bytes) -> None:
    with pytest.raises(ValueError):
        summarize_metric_csv(data)

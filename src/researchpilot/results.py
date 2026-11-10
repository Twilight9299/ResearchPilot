import csv
import io
from decimal import Decimal, DecimalException


def summarize_metric_csv(data: bytes) -> tuple[Decimal, int]:
    if len(data) > 256_000:
        raise ValueError("指标 CSV 不得超过 256 KB。")

    try:
        rows = csv.reader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
        if next(rows, None) != ["value"]:
            raise ValueError("CSV 必须只有一列，首行列名为 value。")
        values = []
        for row_number, row in enumerate(rows, start=2):
            if len(row) != 1:
                raise ValueError(f"CSV 第 {row_number} 行应有且仅有一个数值。")
            try:
                value = Decimal(row[0].strip())
            except DecimalException as exc:
                raise ValueError(f"CSV 第 {row_number} 行不是有效数值。") from exc
            if not value.is_finite():
                raise ValueError(f"CSV 第 {row_number} 行必须是有限数值。")
            values.append(value)
        if not values:
            raise ValueError("CSV 至少需要一条实测记录。")
        return sum(values, Decimal(0)) / len(values), len(values)
    except (UnicodeDecodeError, csv.Error, DecimalException) as exc:
        raise ValueError("无法计算 CSV 均值，请检查编码、格式及数值范围。") from exc

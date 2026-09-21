"""Data audit script to inspect OpenSTEF benchmark files."""

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from src.utils.logger import get_logger

logger = get_logger("data.audit")


def inspect_parquet_file(file_path: Path) -> dict[str, Any]:
    """Load and audit a parquet file."""
    if not file_path.exists():
        raise FileNotFoundError(f"File does not exist: {file_path}")

    df = pd.read_parquet(file_path)
    info = {
        "file_path": str(file_path),
        "shape": df.shape,
        "columns": list(df.columns),
        "dtypes": {str(col): str(dtype) for col, dtype in df.dtypes.items()},
        "index_type": str(type(df.index)),
    }

    # Inspect time index / column
    if isinstance(df.index, pd.DatetimeIndex):
        dt_series = df.index
        info["datetime_source"] = "index"
        info["tz"] = str(df.index.tz)
    else:
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                dt_series = pd.DatetimeIndex(df[col])
                info["datetime_source"] = col
                info["tz"] = str(dt_series.tz)
                break

    if "datetime_source" in info:
        info["min_time"] = str(dt_series.min())
        info["max_time"] = str(dt_series.max())
        info["total_records"] = len(dt_series)
        diffs = dt_series.to_series().diff().value_counts()
        info["cadence_counts"] = {str(k): int(v) for k, v in diffs.head(5).items()}

    # Nulls & duplicates
    info["null_counts"] = {col: int(df[col].isna().sum()) for col in df.columns}
    info["duplicate_rows"] = int(df.duplicated().sum())

    # Summary statistics for numeric columns
    numeric_df = df.select_dtypes(include=["number"])
    info["stats"] = numeric_df.describe().to_dict()

    return info


def run_full_audit(raw_dir: str = "data/raw") -> dict[str, Any]:
    """Run audit across all downloaded benchmark files."""
    raw_path = Path(raw_dir)
    audit_results = {}

    targets_yaml_path = raw_path / "liander2024_targets.yaml"
    if targets_yaml_path.exists():
        with open(targets_yaml_path, "r", encoding="utf-8") as f:
            targets_meta = yaml.safe_load(f)
        audit_results["targets_metadata"] = targets_meta
        logger.info("Parsed liander2024_targets.yaml metadata.")

    files_to_audit = [
        raw_path / "load_measurements/mv_feeder/OS Leiden Noord.parquet",
        raw_path / "load_measurements/mv_feeder/OS Edam.parquet",
        raw_path / "load_measurements/solar_park/Within 10 kilometers of Westwoud_normalized.parquet",
        raw_path / "EPEX.parquet",
    ]

    for fpath in files_to_audit:
        logger.info("Auditing %s...", fpath)
        audit_results[fpath.name] = inspect_parquet_file(fpath)

    return audit_results


if __name__ == "__main__":
    results = run_full_audit()
    print("\n" + "=" * 60)
    print("DATA AUDIT SUMMARY")
    print("=" * 60)
    for fname, audit in results.items():
        if fname == "targets_metadata":
            continue
        print(f"\nFile: {fname}")
        print(f"Shape: {audit['shape']}")
        print(f"Columns: {audit['columns']}")
        print(f"Time Range: {audit.get('min_time')} -> {audit.get('max_time')} (tz: {audit.get('tz')})")
        print(f"Cadence: {audit.get('cadence_counts')}")
        print(f"Nulls: {audit.get('null_counts')}")
        print(f"Duplicates: {audit['duplicate_rows']}")
        if "stats" in audit:
            for col, stats in audit["stats"].items():
                print(f"  Col '{col}': min={stats.get('min'):.2f}, mean={stats.get('mean'):.2f}, max={stats.get('max'):.2f}")

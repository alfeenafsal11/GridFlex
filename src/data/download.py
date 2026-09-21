"""Programmatic downloader for OpenSTEF / Liander 2024 Energy Forecasting Benchmark."""

from pathlib import Path

from huggingface_hub import hf_hub_download

from src.utils.config import load_yaml_config
from src.utils.logger import get_logger

logger = get_logger("data.download")

REPO_ID = "OpenSTEF/liander2024-energy-forecasting-benchmark"
REPO_TYPE = "dataset"

DEFAULT_FILES = [
    "load_measurements/mv_feeder/OS Edam.parquet",
    "load_measurements/solar_park/Within 10 kilometers of Westwoud_normalized.parquet",
    "EPEX.parquet",
    "liander2024_targets.yaml",
]


def download_benchmark_files(
    repo_id: str = REPO_ID,
    files: list[str] | None = None,
    raw_dir: str | Path = "data/raw",
) -> list[Path]:
    """Download specified files from Hugging Face dataset repository into local raw directory."""
    if files is None:
        files = DEFAULT_FILES

    raw_path = Path(raw_dir)
    raw_path.mkdir(parents=True, exist_ok=True)
    downloaded_paths = []

    for remote_filename in files:
        target_local_path = raw_path / remote_filename
        target_local_path.parent.mkdir(parents=True, exist_ok=True)

        if target_local_path.exists():
            logger.info("File already exists locally: %s", target_local_path)
            downloaded_paths.append(target_local_path)
            continue

        logger.info("Downloading '%s' from repo '%s'...", remote_filename, repo_id)
        cached_download = hf_hub_download(
            repo_id=repo_id,
            filename=remote_filename,
            repo_type=REPO_TYPE,
            local_dir=str(raw_path),
        )
        logger.info("Successfully downloaded: %s", cached_download)
        downloaded_paths.append(Path(cached_download))

    return downloaded_paths


if __name__ == "__main__":
    cfg = load_yaml_config("configs/default.yaml")
    selected_files = [
        cfg["data"]["load_feeder"],
        cfg["data"]["solar_park"],
        cfg["data"]["price_file"],
        "liander2024_targets.yaml",
    ]
    download_benchmark_files(
        repo_id=cfg["data"]["hf_repo"],
        files=selected_files,
        raw_dir=cfg["data"]["raw_dir"],
    )

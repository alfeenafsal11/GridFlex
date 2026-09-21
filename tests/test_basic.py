"""Baseline environment and configuration sanity tests."""

from pathlib import Path

from src.utils.config import load_yaml_config
from src.utils.logger import get_logger


def test_imports():
    """Verify that all core project dependencies import without errors."""
    import lightgbm
    import numpy
    import pandas
    import pyarrow
    import scipy
    import sklearn

    assert pandas.__version__ is not None
    assert numpy.__version__ is not None
    assert scipy.__version__ is not None
    assert sklearn.__version__ is not None
    assert lightgbm.__version__ is not None
    assert pyarrow.__version__ is not None


def test_logger():
    """Verify logger instantiation."""
    logger = get_logger("test_logger")
    assert logger.name == "test_logger"


def test_config_loading():
    """Verify loading default and scenario configs."""
    default_config_path = Path("configs/default.yaml")
    scenarios_config_path = Path("configs/scenarios.yaml")

    assert default_config_path.exists()
    assert scenarios_config_path.exists()

    default_cfg = load_yaml_config(default_config_path)
    assert default_cfg["project"]["name"] == "GridFlex AI"
    assert "battery" in default_cfg
    assert "forecasting" in default_cfg
    assert "optimization" in default_cfg

    scenarios_cfg = load_yaml_config(scenarios_config_path)
    assert "penetration_scenarios" in scenarios_cfg
    assert "duration_scenarios" in scenarios_cfg

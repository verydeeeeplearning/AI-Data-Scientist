import importlib
import pytest

@pytest.mark.parametrize("pkg", [
    "sklearn", "xgboost", "lightgbm", "matplotlib", "seaborn", "joblib", "optuna",
])
def test_ml_dependency_available(pkg):
    """Verify that the core ML dependencies are available in the environment."""
    try:
        importlib.import_module(pkg)
    except ImportError:
        pytest.fail(f"Required ML dependency '{pkg}' is NOT available in the current environment.")

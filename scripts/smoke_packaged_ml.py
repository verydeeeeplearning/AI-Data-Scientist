"""Smoke: verify packaged backend's embedded Python can import + run ML stack.

Run via:
    ./dist/ds-agent-backend/ds-agent-api.exe --mode exec scripts/smoke_packaged_ml.py
"""

from __future__ import annotations

import sys


def main() -> int:
    print(f"python={sys.version}", flush=True)
    print(f"frozen={getattr(sys, 'frozen', False)}", flush=True)

    import lightgbm
    import matplotlib
    import numpy  # noqa: F401
    import pandas  # noqa: F401
    import scipy  # noqa: F401
    import sklearn
    import xgboost
    matplotlib.use("Agg")
    import joblib  # noqa: F401
    import matplotlib.pyplot as plt  # noqa: F401
    import seaborn  # noqa: F401

    print(f"sklearn={sklearn.__version__}", flush=True)
    print(f"xgboost={xgboost.__version__}", flush=True)
    print(f"lightgbm={lightgbm.__version__}", flush=True)

    # Quick fit-predict loop (sklearn + numpy)
    from sklearn.datasets import load_iris
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split

    features, labels = load_iris(return_X_y=True)
    f_train, f_test, l_train, l_test = train_test_split(features, labels, random_state=0)
    model = LogisticRegression(max_iter=500).fit(f_train, l_train)
    acc = float(model.score(f_test, l_test))
    print(f"iris_accuracy={acc:.4f}", flush=True)
    if acc < 0.9:
        print("ERROR: iris accuracy below 0.9", file=sys.stderr)
        return 1

    print("SMOKE_OK", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

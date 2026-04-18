"""Code pattern extraction from project code."""

from __future__ import annotations

import re

import structlog

logger = structlog.get_logger()

# Known library patterns for detection
LIBRARY_PATTERNS = {
    "lightgbm": ["LGBMClassifier", "LGBMRegressor", "lgb.train", "lightgbm"],
    "xgboost": ["XGBClassifier", "XGBRegressor", "xgb.train", "xgboost"],
    "catboost": ["CatBoostClassifier", "CatBoostRegressor", "catboost"],
    "sklearn": ["sklearn", "train_test_split", "cross_val_score", "GridSearchCV"],
    "pandas": ["pd.read_csv", "pd.DataFrame", "pandas"],
    "optuna": ["optuna.create_study", "optuna"],
    "shap": ["shap.Explainer", "shap.TreeExplainer", "shap"],
    "matplotlib": ["plt.savefig", "matplotlib"],
    "seaborn": ["sns.", "seaborn"],
}


class PatternLearner:
    """Extract reusable patterns from project code."""

    def extract_patterns(
        self,
        code: str,
        task_type: str = "general",
    ) -> list[dict]:
        """Analyze code and extract detected patterns."""
        if not code.strip():
            return []

        patterns = []

        # Detect libraries used
        for lib_name, indicators in LIBRARY_PATTERNS.items():
            for indicator in indicators:
                if indicator in code:
                    patterns.append(
                        {
                            "type": "library_usage",
                            "name": lib_name,
                            "task_type": task_type,
                        }
                    )
                    break

        # Detect common DS patterns
        if "train_test_split" in code:
            patterns.append(
                {
                    "type": "technique",
                    "name": "train_test_split",
                    "task_type": task_type,
                }
            )

        if re.search(r"cross_val_score|KFold|StratifiedKFold", code):
            patterns.append(
                {
                    "type": "technique",
                    "name": "cross_validation",
                    "task_type": task_type,
                }
            )

        if "SMOTE" in code or "smote" in code:
            patterns.append(
                {
                    "type": "technique",
                    "name": "smote_oversampling",
                    "task_type": task_type,
                }
            )

        if re.search(r"optuna|hyperopt|GridSearchCV|RandomizedSearchCV", code):
            patterns.append(
                {
                    "type": "technique",
                    "name": "hyperparameter_tuning",
                    "task_type": task_type,
                }
            )

        if "shap" in code.lower():
            patterns.append(
                {
                    "type": "technique",
                    "name": "shap_explanation",
                    "task_type": task_type,
                }
            )

        return patterns

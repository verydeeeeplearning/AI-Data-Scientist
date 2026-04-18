"""DS domain error translator — converts raw tracebacks to actionable guidance.

Implements harness principle: "error messages = fix instructions."
"""

from __future__ import annotations

import re

_DS_ERROR_PATTERNS: list[tuple[str, dict[str, str]]] = [
    (
        r"could not convert string to float",
        {
            "diagnosis": "Categorical column included in numeric operation",
            "suggestion": "Encode with LabelEncoder (ordinal) or OneHotEncoder (nominal) before fitting",
            "example": (
                "from sklearn.preprocessing import LabelEncoder\n"
                "le = LabelEncoder()\n"
                "df['col'] = le.fit_transform(df['col'])"
            ),
        },
    ),
    (
        r"Found input variables with inconsistent numbers of samples",
        {
            "diagnosis": "X and y have different row counts",
            "suggestion": (
                "Check that train_test_split output shapes match. "
                "If you dropped NaN rows, reset index and re-align X and y"
            ),
        },
    ),
    (
        r"Target is multiclass but average='binary'",
        {
            "diagnosis": "Binary metric used for multiclass problem",
            "suggestion": "Use average='weighted' or average='macro' for multiclass",
            "example": "f1_score(y_true, y_pred, average='weighted')",
        },
    ),
    (
        r"Input contains NaN",
        {
            "diagnosis": "Missing values passed to model that cannot handle NaN",
            "suggestion": "Impute missing values before fitting. SimpleImputer(strategy='median') recommended",
            "example": (
                "from sklearn.impute import SimpleImputer\n"
                "imputer = SimpleImputer(strategy='median')\n"
                "X_train = imputer.fit_transform(X_train)\n"
                "X_test = imputer.transform(X_test)"
            ),
        },
    ),
    (
        r"CUDA out of memory",
        {
            "diagnosis": "GPU memory exhausted",
            "suggestion": "Reduce batch_size, use gradient accumulation, or enable mixed precision (fp16)",
        },
    ),
    (
        r"has no attribute '(?:predict|fit|transform|score)'",
        {
            "diagnosis": "Model object not properly initialized or wrong variable name",
            "suggestion": "Check that the model was trained (fit called) before predict/transform",
        },
    ),
    (
        r"Number of features .* does not match",
        {
            "diagnosis": "Train and test datasets have different column counts",
            "suggestion": (
                "Ensure the same feature engineering pipeline is applied to both. "
                "Fit encoders on train, transform both train and test"
            ),
        },
    ),
    (
        r"cannot reindex from a duplicate axis",
        {
            "diagnosis": "DataFrame has duplicate index values",
            "suggestion": "Reset index with df.reset_index(drop=True) before the operation",
        },
    ),
    (
        r"Columns must be same length as key",
        {
            "diagnosis": "OneHotEncoder/get_dummies output column count mismatch",
            "suggestion": (
                "Use pd.get_dummies with columns parameter, or "
                "fit OneHotEncoder on train and use the same categories for test"
            ),
        },
    ),
    (
        r"Only one class present in y_true",
        {
            "diagnosis": "Evaluation set contains only one class label",
            "suggestion": (
                "Use stratified split (StratifiedKFold, stratify=y in train_test_split) "
                "to ensure all classes appear in each split"
            ),
        },
    ),
]


def translate_error(raw_error: str) -> str:
    """Translate a raw Python traceback into DS-context actionable guidance.

    Returns the translated guidance if a known pattern matches,
    otherwise returns the last 5 lines of the original error.
    """
    for pattern, guidance in _DS_ERROR_PATTERNS:
        if re.search(pattern, raw_error, re.IGNORECASE):
            parts = [f"**Diagnosis**: {guidance['diagnosis']}"]
            parts.append(f"**Suggestion**: {guidance['suggestion']}")
            if "example" in guidance:
                parts.append(f"**Example**:\n```python\n{guidance['example']}\n```")
            return "\n".join(parts)

    # No match — return condensed traceback (last 5 lines)
    lines = raw_error.strip().split("\n")
    return "\n".join(lines[-5:])

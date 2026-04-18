"""Sampling helpers for resource-aware planning."""

from __future__ import annotations

import pandas as pd  # type: ignore[import-untyped]


def stratified_sample(
    df: pd.DataFrame,
    *,
    by: str,
    fraction: float,
    random_state: int = 42,
) -> pd.DataFrame:
    """Sample while preserving the category mix of a target column."""
    return (
        df.groupby(by, group_keys=False)
        .apply(lambda group: group.sample(frac=min(fraction, 1.0), random_state=random_state))
        .reset_index(drop=True)
    )


def random_sample(
    df: pd.DataFrame,
    *,
    fraction: float,
    random_state: int = 42,
) -> pd.DataFrame:
    """Random sample with fixed seed."""
    return df.sample(frac=min(fraction, 1.0), random_state=random_state).reset_index(drop=True)


def recent_time_window_sample(
    df: pd.DataFrame,
    *,
    time_column: str,
    days: int,
) -> pd.DataFrame:
    """Keep only the most recent N days."""
    series = pd.to_datetime(df[time_column], errors="coerce")
    cutoff = series.max() - pd.Timedelta(days=days)
    return df.loc[series >= cutoff].reset_index(drop=True)

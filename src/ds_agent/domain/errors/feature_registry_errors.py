"""Domain errors for Decision OS feature-registry workflows."""

from __future__ import annotations


class FeatureRegistryError(Exception):
    """Base class for feature-registry failures."""

    error_code = "FEATURE_REGISTRY_ERROR"


class FeatureNotFoundError(FeatureRegistryError):
    """Raised when a feature version cannot be found."""

    error_code = "FEATURE_NOT_FOUND"


class FeatureVersionConflictError(FeatureRegistryError):
    """Raised when a registration would overwrite or regress a version."""

    error_code = "FEATURE_VERSION_CONFLICT"


class UnknownSourceTableError(FeatureRegistryError):
    """Raised when a feature refers to tables missing from the schema catalog."""

    error_code = "UNKNOWN_SOURCE_TABLE"

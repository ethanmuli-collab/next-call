"""Dataset contracts: one declared spec per dataset profile."""
from __future__ import annotations

from types import ModuleType

DATASETS = ("synthetic", "kaggle")


def get_spec(dataset: str = "synthetic") -> ModuleType:
    """The versioned spec module of a dataset profile."""
    if dataset == "kaggle":
        from contract import spec_kaggle
        return spec_kaggle
    if dataset == "synthetic":
        from contract import spec
        return spec
    raise ValueError(f"unknown dataset profile '{dataset}'; expected one of {DATASETS}")

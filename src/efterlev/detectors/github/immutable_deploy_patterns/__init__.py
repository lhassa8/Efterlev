"""Immutable-deploy-patterns detector. See `detector.py` for registration."""

from __future__ import annotations

from efterlev.detectors.github.immutable_deploy_patterns.detector import detect

__all__ = ["detect"]

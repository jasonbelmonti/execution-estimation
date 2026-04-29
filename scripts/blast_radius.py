#!/usr/bin/env python3
"""Deterministic blast-radius assessment for execution estimation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

LOW_IMPACT_SUFFIXES = {".adoc", ".md", ".mdx", ".rst"}
ROOT_TEST_PREFIXES = ("__tests__/", "test/", "tests/")
NESTED_TEST_MARKERS = ("/__tests__/", "/test/", "/tests/")
TEST_SUFFIXES = (
    ".spec.c",
    ".spec.cc",
    ".spec.cpp",
    ".spec.cs",
    ".spec.go",
    ".spec.java",
    ".spec.js",
    ".spec.jsx",
    ".spec.kt",
    ".spec.m",
    ".spec.php",
    ".spec.py",
    ".spec.rb",
    ".spec.rs",
    ".spec.swift",
    ".spec.ts",
    ".spec.tsx",
    ".test.c",
    ".test.cc",
    ".test.cpp",
    ".test.cs",
    ".test.go",
    ".test.java",
    ".test.js",
    ".test.jsx",
    ".test.kt",
    ".test.m",
    ".test.php",
    ".test.py",
    ".test.rb",
    ".test.rs",
    ".test.swift",
    ".test.ts",
    ".test.tsx",
)
BUILD_DEPLOY_FILENAMES = {
    ".gitlab-ci.yml",
    "Dockerfile",
    "Makefile",
    "Procfile",
    "Vagrantfile",
    "app.json",
    "bun.lock",
    "bun.lockb",
    "compose.yaml",
    "compose.yml",
    "docker-compose.yaml",
    "docker-compose.yml",
    "justfile",
    "package-lock.json",
    "package.json",
    "pnpm-lock.yaml",
    "tsconfig.json",
    "tsup.config.ts",
    "turbo.json",
    "vite.config.js",
    "vite.config.ts",
    "webpack.config.js",
    "webpack.config.ts",
    "yarn.lock",
}
ENTRYPOINT_PATHS = {
    "app.js",
    "app.ts",
    "app.tsx",
    "index.js",
    "index.ts",
    "index.tsx",
    "main.js",
    "main.ts",
    "main.tsx",
    "server.js",
    "server.ts",
    "src/app.ts",
    "src/app.tsx",
    "src/index.ts",
    "src/index.tsx",
    "src/main.ts",
    "src/main.tsx",
    "src/server.ts",
}

LEVEL_CONTROLS = {
    "low": (
        "Run the smallest targeted verification that proves the touched path still works.",
    ),
    "medium": (
        "Run targeted automated tests around the touched boundary.",
        "Request review from the primary owner of the touched area.",
    ),
    "high": (
        "Run targeted automated tests around the touched boundary.",
        "Run integration or regression coverage across adjacent boundaries.",
        "Include a reviewer from an adjacent impacted boundary.",
    ),
    "very-high": (
        "Run targeted automated tests around the touched boundary.",
        "Run integration or regression coverage across adjacent boundaries.",
        "Include a reviewer from an adjacent impacted boundary.",
        "Verify rollback or containment steps before merge or release.",
    ),
}


@dataclass(frozen=True)
class BlastRadiusSignal:
    key: str
    weight: int
    reason: str
    matched_files: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "weight": self.weight,
            "reason": self.reason,
            "matchedFiles": list(self.matched_files),
        }


@dataclass(frozen=True)
class BlastRadiusAssessment:
    score: int
    level: str
    low_impact_only: bool
    signals: tuple[BlastRadiusSignal, ...]
    requires_heightened_controls: bool
    recommended_controls: tuple[str, ...]
    investigation_areas: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "score": self.score,
            "level": self.level,
            "lowImpactOnly": self.low_impact_only,
            "signals": [signal.to_dict() for signal in self.signals],
            "requiresHeightenedControls": self.requires_heightened_controls,
            "recommendedControls": list(self.recommended_controls),
            "investigationAreas": list(self.investigation_areas),
        }


@dataclass(frozen=True)
class PathSignalRule:
    key: str
    weight: int
    reason: str
    matcher: Callable[[str], bool]
    control: str | None = None
    investigation: str | None = None


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip().lower()


def path_tokens(path: str) -> set[str]:
    return {token for token in re.split(r"[/._-]+", normalize_path(path)) if token}


def ordered_unique(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []

    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)

    return tuple(ordered)


def is_doc_path(path: str) -> bool:
    normalized = normalize_path(path)
    suffix = Path(normalized).suffix.lower()
    return normalized.startswith(("docs/", "doc/")) or suffix in LOW_IMPACT_SUFFIXES


def is_test_path(path: str) -> bool:
    normalized = normalize_path(path)
    return (
        normalized.startswith(ROOT_TEST_PREFIXES)
        or any(marker in normalized for marker in NESTED_TEST_MARKERS)
        or normalized.endswith(TEST_SUFFIXES)
    )


def matches_auth_security(path: str) -> bool:
    tokens = path_tokens(path)
    return bool(
        tokens
        & {
            "auth",
            "authorization",
            "cookie",
            "cookies",
            "csrf",
            "crypto",
            "oauth",
            "permission",
            "permissions",
            "policy",
            "policies",
            "rbac",
            "secret",
            "secrets",
            "session",
            "token",
            "tokens",
        }
    )


def matches_data_schema(path: str) -> bool:
    normalized = normalize_path(path)
    tokens = path_tokens(path)
    return normalized.endswith(".sql") or bool(
        tokens
        & {
            "database",
            "db",
            "ddl",
            "migration",
            "migrations",
            "schema",
            "schemas",
            "seed",
            "seeds",
            "sql",
        }
    )


def matches_api_contract(path: str) -> bool:
    normalized = normalize_path(path)
    tokens = path_tokens(path)
    return normalized.endswith((".avsc", ".graphql", ".proto")) or bool(
        tokens
        & {
            "contract",
            "contracts",
            "dto",
            "graphql",
            "openapi",
            "proto",
            "protobuf",
            "swagger",
        }
    )


def matches_shared_surface(path: str) -> bool:
    normalized = normalize_path(path)
    tokens = path_tokens(path)
    return normalized.startswith("packages/") or bool(
        tokens & {"common", "core", "platform", "shared", "sdk"}
    )


def matches_runtime_entrypoint(path: str) -> bool:
    normalized = normalize_path(path)
    return normalized in ENTRYPOINT_PATHS


def matches_build_deploy(path: str) -> bool:
    normalized = normalize_path(path)
    basename = Path(path).name
    return (
        basename in BUILD_DEPLOY_FILENAMES
        or normalized.startswith((".github/workflows/", "deploy/", "deployment/", "helm/", "infra/", "k8s/", "terraform/"))
    )


def matches_runtime_config(path: str) -> bool:
    normalized = normalize_path(path)
    basename = Path(normalized).name
    tokens = path_tokens(path)
    config_markers = {
        "config",
        "configs",
        "env",
        "flag",
        "flags",
        "settings",
    }
    return basename.startswith(".env") or bool(tokens & config_markers)


PATH_SIGNAL_RULES = (
    PathSignalRule(
        key="auth-security",
        weight=3,
        reason="authentication, authorization, or secret-handling path touched",
        matcher=matches_auth_security,
        control="Exercise authorization and failure-path tests, not just happy paths.",
        investigation="Inspect authentication, authorization, token/session lifecycle, and failure paths.",
    ),
    PathSignalRule(
        key="data-schema",
        weight=3,
        reason="database, migration, or schema path touched",
        matcher=matches_data_schema,
        control="Validate backward compatibility and rollback or repair paths for data changes.",
        investigation="Inspect schema consumers, migrations, rollback path, and data compatibility assumptions.",
    ),
    PathSignalRule(
        key="api-contract",
        weight=2,
        reason="public API or contract definition path touched",
        matcher=matches_api_contract,
        control="Verify backward compatibility for contract consumers and producers.",
        investigation="Inspect client and server consumers plus serialization boundaries.",
    ),
    PathSignalRule(
        key="shared-surface",
        weight=2,
        reason="shared, core, or multi-consumer path touched",
        matcher=matches_shared_surface,
        control="Expand regression checks to the main downstream consumers of the shared path.",
        investigation="Inspect downstream callers and importers of shared modules.",
    ),
    PathSignalRule(
        key="runtime-entrypoint",
        weight=2,
        reason="application entrypoint or bootstrap path touched",
        matcher=matches_runtime_entrypoint,
        control="Smoke-test startup or bootstrap paths in addition to unit coverage.",
        investigation="Inspect startup, routing/bootstrap, and failure handling around the entrypoint.",
    ),
    PathSignalRule(
        key="build-deploy",
        weight=2,
        reason="build, CI, or deployment path touched",
        matcher=matches_build_deploy,
        control="Verify build, CI, or deployment commands on the main delivery path.",
        investigation="Inspect CI, build graph, deployment manifests, and operational automation.",
    ),
    PathSignalRule(
        key="runtime-config",
        weight=2,
        reason="runtime configuration or environment path touched",
        matcher=matches_runtime_config,
        control="Check environment-specific defaults and feature-flag interactions.",
        investigation="Inspect environment-specific configuration, defaults, and flag interactions.",
    ),
)


def structural_signals(change: dict) -> tuple[BlastRadiusSignal, ...]:
    signals: list[BlastRadiusSignal] = []
    files = tuple(change["files"])

    if change["files_touched"] >= 8:
        signals.append(
            BlastRadiusSignal(
                key="wide-file-fanout",
                weight=1,
                reason="change spans at least 8 files",
                matched_files=files,
            )
        )
    if len(change["dirs_touched"]) >= 3:
        signals.append(
            BlastRadiusSignal(
                key="cross-boundary-surface",
                weight=1,
                reason="change spans at least 3 top-level directories",
                matched_files=files,
            )
        )
    if change["max_file_churn"] >= 300:
        signals.append(
            BlastRadiusSignal(
                key="deep-single-file-churn",
                weight=1,
                reason="single-file churn is at least 300 lines",
                matched_files=files,
            )
        )
    if change["binaries_touched"] > 0:
        signals.append(
            BlastRadiusSignal(
                key="binary-artifacts",
                weight=1,
                reason="binary or generated artifacts changed",
                matched_files=files,
            )
        )

    return tuple(signals)


def blast_radius_level(score: int, low_impact_only: bool) -> str:
    if low_impact_only and score <= 1:
        return "low"
    if score <= 1:
        return "low"
    if score <= 4:
        return "medium"
    if score <= 7:
        return "high"
    return "very-high"


def assess_blast_radius(change: dict) -> BlastRadiusAssessment:
    files = tuple(change["files"])
    low_impact_only = bool(files) and all(is_doc_path(path) or is_test_path(path) for path in files)

    signals: list[BlastRadiusSignal] = []
    controls: list[str] = []
    investigation_areas: list[str] = []

    if not low_impact_only:
        for rule in PATH_SIGNAL_RULES:
            matched_files = tuple(path for path in files if rule.matcher(path))
            if not matched_files:
                continue

            signals.append(
                BlastRadiusSignal(
                    key=rule.key,
                    weight=rule.weight,
                    reason=rule.reason,
                    matched_files=matched_files,
                )
            )
            if rule.control:
                controls.append(rule.control)
            if rule.investigation:
                investigation_areas.append(rule.investigation)

    signals.extend(structural_signals(change))

    score = sum(signal.weight for signal in signals)
    level = blast_radius_level(score, low_impact_only)
    requires_heightened_controls = level in {"high", "very-high"}

    level_controls = list(LEVEL_CONTROLS[level])
    recommended_controls = ordered_unique(tuple(level_controls + controls))
    investigation = ordered_unique(investigation_areas)

    return BlastRadiusAssessment(
        score=score,
        level=level,
        low_impact_only=low_impact_only,
        signals=tuple(signals),
        requires_heightened_controls=requires_heightened_controls,
        recommended_controls=recommended_controls,
        investigation_areas=investigation,
    )

#!/usr/bin/env python3
"""Deterministic planning recommendation for execution estimation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanningSignal:
    key: str
    weight: int
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "weight": self.weight,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class PlanningRecommendation:
    score: int
    level: str
    recommended: bool
    signals: tuple[PlanningSignal, ...]
    rationale: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "score": self.score,
            "level": self.level,
            "recommended": self.recommended,
            "signals": [signal.to_dict() for signal in self.signals],
            "rationale": list(self.rationale),
        }


def planning_level(score: int) -> str:
    if score >= 5:
        return "plan-first"
    if score >= 3:
        return "plan-recommended"
    return "direct-execution"


def assess_planning_recommendation(
    change: dict,
    story_points: int,
    decomposition_recommended: bool,
    blast_radius: dict[str, object],
) -> PlanningRecommendation:
    signals: list[PlanningSignal] = []

    if decomposition_recommended:
        signals.append(
            PlanningSignal(
                key="decomposition-recommended",
                weight=3,
                reason="work item is large enough that execution should be split before implementation",
            )
        )

    blast_radius_level = str(blast_radius["level"])
    if blast_radius_level in {"high", "very-high"}:
        signals.append(
            PlanningSignal(
                key="high-blast-radius",
                weight=3,
                reason="blast radius is high enough that sequencing and controls should be decided before coding",
            )
        )
    elif blast_radius_level == "medium":
        signals.append(
            PlanningSignal(
                key="medium-blast-radius",
                weight=2,
                reason="blast radius crosses a boundary where pre-deciding checks and ownership is useful",
            )
        )

    if story_points >= 8:
        signals.append(
            PlanningSignal(
                key="large-estimate",
                weight=2,
                reason="story point estimate is 8 or higher",
            )
        )
    elif story_points >= 5:
        signals.append(
            PlanningSignal(
                key="mid-sized-estimate",
                weight=1,
                reason="story point estimate is 5, which usually benefits from explicit sequencing",
            )
        )

    if len(change["dirs_touched"]) >= 3:
        signals.append(
            PlanningSignal(
                key="cross-boundary-change",
                weight=1,
                reason="change spans at least 3 top-level directories",
            )
        )

    if change["files_touched"] >= 8:
        signals.append(
            PlanningSignal(
                key="wide-file-fanout",
                weight=1,
                reason="change touches at least 8 files",
            )
        )

    if change["max_file_churn"] >= 300:
        signals.append(
            PlanningSignal(
                key="deep-single-file-churn",
                weight=1,
                reason="single-file churn is at least 300 lines",
            )
        )

    if change["mode"] == "proposal":
        signals.append(
            PlanningSignal(
                key="proposal-uncertainty",
                weight=1,
                reason="work is still proposed, so the implementation path is not yet validated by a concrete diff",
            )
        )

    score = sum(signal.weight for signal in signals)
    level = planning_level(score)
    recommended = level in {"plan-recommended", "plan-first"}

    rationale = tuple(
        f"planning signal: {signal.key} (+{signal.weight}) - {signal.reason}"
        for signal in signals
    )

    return PlanningRecommendation(
        score=score,
        level=level,
        recommended=recommended,
        signals=tuple(signals),
        rationale=rationale,
    )

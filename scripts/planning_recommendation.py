#!/usr/bin/env python3
"""Deterministic binary planning recommendation for execution estimation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanningRecommendation:
    recommended: bool
    matched_rules: tuple[str, ...]
    rationale: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "recommended": self.recommended,
            "matchedRules": list(self.matched_rules),
            "rationale": list(self.rationale),
        }


def assess_planning_recommendation(
    change: dict,
    story_points: int,
    decomposition_recommended: bool,
    blast_radius: dict[str, object],
) -> PlanningRecommendation:
    matched_rules: list[str] = []
    rationale: list[str] = []

    def match(rule_key: str, reason: str) -> None:
        matched_rules.append(rule_key)
        rationale.append(f"planning rule matched: {rule_key} - {reason}")

    if decomposition_recommended:
        match(
            "decomposition-recommended",
            "work item should be split before implementation",
        )

    blast_radius_level = str(blast_radius["level"])
    if blast_radius_level in {"high", "very-high"}:
        match(
            "high-blast-radius",
            "blast radius is high enough that sequencing and controls should be decided before coding",
        )
    elif blast_radius_level == "medium" and (change["mode"] == "proposal" or story_points >= 5):
        match(
            "medium-blast-radius-shaping",
            "blast radius is medium and the work is still being shaped or is already mid-sized",
        )

    if story_points >= 5 and len(change["dirs_touched"]) >= 3:
        match(
            "mid-sized-cross-boundary",
            "story point estimate is at least 5 and the change spans multiple top-level boundaries",
        )

    if change["files_touched"] >= 8 and change["mode"] == "proposal":
        match(
            "wide-proposal-change",
            "proposal touches at least 8 files before implementation has started",
        )

    if change["max_file_churn"] >= 300:
        match(
            "deep-single-file-churn",
            "single-file churn is large enough to justify pre-deciding the execution approach",
        )

    recommended = bool(matched_rules)
    if not rationale:
        rationale.append(
            "planning rule not matched: no explicit planning trigger fired; proceed directly unless the user explicitly asks for a plan"
        )

    return PlanningRecommendation(
        recommended=recommended,
        matched_rules=tuple(matched_rules),
        rationale=tuple(rationale),
    )

#!/usr/bin/env python3
"""Deterministic planning recommendation for execution estimation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanningRecommendation:
    recommended: bool
    level: str
    blocks_execution: bool
    matched_rules: tuple[str, ...]
    rationale: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "recommended": self.recommended,
            "level": self.level,
            "blocksExecution": self.blocks_execution,
            "matchedRules": list(self.matched_rules),
            "rationale": list(self.rationale),
        }


def assess_planning_recommendation(
    change: dict,
    base_story_points: int,
    adjusted_story_points: int,
    decomposition_recommended: bool,
    blast_radius: dict[str, object],
) -> PlanningRecommendation:
    matched_rules: list[str] = []
    rationale: list[str] = []
    level = "none"
    level_rank = {"none": 0, "brief": 1, "required": 2}

    def match(rule_key: str, reason: str, matched_level: str) -> None:
        nonlocal level
        matched_rules.append(rule_key)
        rationale.append(f"planning rule matched: {rule_key} - {reason}")
        if level_rank[matched_level] > level_rank[level]:
            level = matched_level

    if decomposition_recommended:
        match(
            "decomposition-recommended",
            "work item should be split before implementation",
            "required",
        )

    blast_radius_level = str(blast_radius["level"])
    low_impact_only = bool(blast_radius.get("lowImpactOnly", False))

    if blast_radius_level in {"high", "very-high"}:
        match(
            "high-blast-radius",
            "blast radius is high enough that sequencing and controls should be decided before coding",
            "required",
        )
    elif blast_radius_level == "medium" and (base_story_points >= 5 or len(change["dirs_touched"]) >= 3):
        match(
            "medium-blast-radius-shaping",
            "blast radius is medium and paired with mid-sized or cross-boundary work",
            "brief",
        )

    if base_story_points >= 5 and len(change["dirs_touched"]) >= 3:
        match(
            "mid-sized-cross-boundary",
            "base story point estimate is at least 5 and the change spans multiple top-level boundaries",
            "brief",
        )

    if change["files_touched"] >= 8 and change["mode"] == "proposal" and not low_impact_only:
        match(
            "wide-proposal-change",
            "proposal touches at least 8 files before implementation has started",
            "brief",
        )

    if change["max_file_churn"] >= 300:
        match(
            "deep-single-file-churn",
            "single-file churn is large enough to justify pre-deciding the execution approach",
            "brief",
        )

    recommended = bool(matched_rules)
    if not rationale:
        rationale.append(
            "planning rule not matched: no explicit planning trigger fired; proceed directly unless the user explicitly asks for a plan"
        )

    return PlanningRecommendation(
        recommended=recommended,
        level=level,
        blocks_execution=level == "required",
        matched_rules=tuple(matched_rules),
        rationale=tuple(rationale),
    )

---
name: execution-estimation
description: Estimate implementation effort for proposed engineering work by comparing anticipated change scope against repository size and structure. Use when triaging tickets, sizing backlog items, deciding whether to decompose work, deciding whether to stop and plan before coding, or producing pre-implementation LoE. Produces deterministic story-point estimates, lines changed, files touched, decomposition recommendations, planning recommendations, and blast-radius risk guidance.
---

# Execution Estimation

## Workflow
1. Collect inputs.
- Use `repoRoot` for the target repository.
- Use `baseRef` and `headRef` when an actual diff exists.
- Use a proposed file list when work is planned but not yet implemented.

Skill-local resources:
- The estimator script and rubric live inside this skill folder, not inside the target repo.
- Resolve `scripts/estimate_execution.py` and `references/estimation-rubric.md` relative to this
  `SKILL.md`.

2. Run the estimator.
- Diff-backed estimate:
```bash
python3 <skill-dir>/scripts/estimate_execution.py \
  --repo-root /path/to/repo \
  --base-ref origin/main \
  --head-ref HEAD
```
- Proposal-backed estimate:
```bash
python3 <skill-dir>/scripts/estimate_execution.py \
  --repo-root /path/to/repo \
  --proposed-files /path/to/proposed-files.txt
```

3. Report deterministic output fields.
- `estimation.storyPoints`: recommended LoE in story points.
- `change.filesTouched`: expected/observed files touched.
- `change.linesChanged`: expected/observed line churn.
- `comparison`: relative impact versus repository baseline.
- `risk.blastRadius.score` and `risk.blastRadius.level`: deterministic blast-radius assessment.
- `risk.blastRadius.recommendedControls`: stricter review and test controls for high-risk work.
- `risk.blastRadius.investigationAreas`: adjacent areas to inspect when the touched paths imply wider impact.
- `estimation.decompositionRecommended`: whether to split the work item.
- `planning.recommended`: binary guidance on whether to stop and plan before coding.
- `planning.matchedRules` and `planning.rationale`: explicit rules that explain why the recommendation is yes or no.

4. Apply execution guidance.
- Split work when `decompositionRecommended` is `true`.
- Split by workflow boundary (resolver/integration/tests) or by risk boundary (schema/runtime/integration).
- Preserve deterministic ordering for proposed split items.
- Treat blast radius as independent from story points. Small diffs can still require stricter test depth and broader review.
- When `risk.blastRadius.requiresHeightenedControls` is `true`, explicitly add broader regression coverage, adjacent-boundary review, and the listed investigation items before execution or merge.
- When `planning.recommended` is `true`, stop after estimation and present a concrete execution plan before implementation.
- When `planning.recommended` is `false`, proceed directly unless the user explicitly asks for a plan.

## Output Contract
Return a concise summary plus the JSON artifact fields:
1. Story points and confidence.
2. Files touched and lines changed.
3. Comparison percentages against codebase.
4. Blast radius level, score, signals, recommended controls, and investigation areas.
5. Planning recommendation as a binary recommendation, matched rules, and rationale.
6. Decomposition recommendation with rationale.

## Resources
- Estimator script: `scripts/estimate_execution.py` relative to this skill directory
- Blast-radius helpers: `scripts/blast_radius.py` relative to this skill directory
- Planning helpers: `scripts/planning_recommendation.py` relative to this skill directory
- Rubric and thresholds: `references/estimation-rubric.md` relative to this skill directory

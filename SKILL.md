---
name: execution-estimation
description: Estimate scope, change footprint, blast radius, and execution gates for proposed work or an existing diff. Use when sizing a task, assessing implementation risk, deciding whether to split work, or deciding whether planning must block coding.
---

# Execution Estimation

## Workflow
1. Collect inputs.
- Use `repoRoot` for the target repository.
- Use diff mode with `baseRef` and optional `headRef` when an actual diff exists.
- Add `--include-working-tree` in diff mode when uncommitted or untracked working-tree changes are part of the estimate.
- Use proposal mode with a newline-delimited proposed file list when work is planned but not yet implemented.
- Add `--decomposition-depth 1` or higher when estimating a child task that already came from decomposition.
- Resolve skill-local resources relative to this `SKILL.md`, not relative to the target repo.

2. Run the estimator.
- Diff-backed estimate:
```bash
python3 <skill-dir>/scripts/estimate_execution.py \
  --repo-root /path/to/repo \
  --base-ref origin/main
```
- Proposal-backed estimate:
```bash
python3 <skill-dir>/scripts/estimate_execution.py \
  --repo-root /path/to/repo \
  --proposed-files /path/to/proposed-files.txt
```
- Use `--head-ref <ref>` only when the default `HEAD` is not the intended comparison target.
- Use `--proposal-lines-changed <n>` only when the proposal file list materially understates or overstates likely churn and you need to override the heuristic estimate.

3. Handle failures before interpreting results.
- If the estimator exits non-zero or returns an `error` object, report the error verbatim.
- Do not fabricate an estimate when inputs are missing, the repo is invalid, or the proposal file cannot be read.
- Fix the input problem first, then rerun the estimator.

4. Report deterministic output.
- Return a concise summary plus the raw JSON artifact when the user asked for an estimate.
- Include `schemaVersion`, `mode`, and `repoRoot`.
- Include `codebase`, `change`, and `comparison`.
- Include `risk.blastRadius.score`, `risk.blastRadius.level`, `risk.blastRadius.signals`, `risk.blastRadius.requiresHeightenedControls`, `risk.blastRadius.recommendedControls`, and `risk.blastRadius.investigationAreas`.
- Include `planning.recommended`, `planning.level`, `planning.blocksExecution`, `planning.matchedRules`, and `planning.rationale`.
- Include `execution.action` and `execution.rationale`.
- Include `estimation.baseStoryPoints`, `estimation.adjustedStoryPoints`, `estimation.confidence`, `estimation.riskSteps`, `estimation.decompositionRecommended`, and `estimation.decompositionRationale`.

5. Apply execution guidance.
- Treat `execution.action` as the authoritative gate.
- Proceed directly when `execution.action` is `proceed`.
- Proceed with the listed controls when `execution.action` is `proceed-with-controls`; do not stop solely because `planning.recommended` is `true`.
- Stop and present a concrete plan before implementation only when `execution.action` is `plan-first` or `planning.blocksExecution` is `true`.
- Stop and split the work only when `execution.action` is `decompose-first` or `estimation.decompositionRecommended` is `true`.
- Split by workflow boundary (resolver/integration/tests) or by risk boundary (schema/runtime/integration).
- Preserve deterministic ordering for proposed split items.
- Do not recursively decompose an already-split child task unless the estimator still returns `decompose-first` with `--decomposition-depth` set.
- Treat blast radius as independent from story points. Small diffs can still require stricter test depth and broader review.
- When `risk.blastRadius.requiresHeightenedControls` is `true`, explicitly add broader regression coverage, adjacent-boundary review, and the listed investigation items before execution or merge.

## Resources
- Run `scripts/estimate_execution.py` first for normal use.
- Read `references/estimation-rubric.md` when you need to explain why the estimate landed where it did or when you need the threshold table.
- Read `scripts/blast_radius.py` when debugging or changing blast-radius signals, controls, or investigation areas.
- Read `scripts/planning_recommendation.py` when debugging or changing planning trigger rules.

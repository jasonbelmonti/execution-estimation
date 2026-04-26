# Execution Estimation User Guide

`execution-estimation` is a user-facing estimation skill for sizing engineering work before or after implementation. It produces deterministic guidance for:

- Story-point-style level of effort
- Expected or observed file and line churn
- Relative footprint versus the codebase baseline
- Blast radius and required quality controls
- Planning gates
- Decomposition gates
- A single execution action for coding agents

The skill is calibrated for agentic coding workflows: risk signals can increase controls without automatically stopping execution, and decomposition is reserved for true split-worthy footprint.

## What the skill can do

The skill supports two estimation modes:

1. Diff-backed estimation
Use this when work already exists in a branch or diff. The estimator reads the changed file list and actual line churn from git.

2. Proposal-backed estimation
Use this when work is still planned. The estimator reads a newline-delimited list of proposed files and infers likely churn from file types.

In both modes, the estimator returns deterministic JSON that includes:

- `estimation.baseStoryPoints`
- `estimation.adjustedStoryPoints`
- `estimation.confidence`
- `estimation.decompositionRecommended`
- `change.filesTouched`
- `change.linesChanged`
- `comparison.trackedFilesTouchedPct`
- `comparison.sourceLinesChangedPct`
- `risk.blastRadius`
- `planning`
- `execution.action`

## Inputs

The estimator script lives in the skill folder, not in the target repository:

- `scripts/estimate_execution.py`
- `scripts/blast_radius.py`
- `scripts/planning_recommendation.py`
- `references/estimation-rubric.md`

You always provide:

- `--repo-root`: path to the target git repository

You then choose exactly one mode:

- Diff mode: `--base-ref` and optional `--head-ref`
- Proposal mode: `--proposed-files`

## Commands

### Diff-backed estimate

```bash
python3 /path/to/execution-estimation/scripts/estimate_execution.py \
  --repo-root /path/to/repo \
  --base-ref origin/main
```

Optional:

- `--head-ref <ref>` compares a non-`HEAD` ref.
- `--include-working-tree` includes uncommitted and untracked working-tree changes.
- `--decomposition-depth <n>` marks already-split child work.

### Proposal-backed estimate

Create a file containing one proposed path per line:

```text
src/auth/token.ts
db/schema.sql
tests/auth.test.ts
```

Then run:

```bash
python3 /path/to/execution-estimation/scripts/estimate_execution.py \
  --repo-root /path/to/repo \
  --proposed-files /path/to/proposed-files.txt
```

Optional:

- `--proposal-lines-changed <n>` overrides the inferred line-churn estimate in proposal mode.
- `--decomposition-depth <n>` marks already-split child work.

## Story Points

The estimator reports two story-point values:

- `estimation.baseStoryPoints`: line-churn size before risk adjustment.
- `estimation.adjustedStoryPoints`: base size plus deterministic risk steps.

Risk steps are still useful for communicating uncertainty and review load, but they do not directly force decomposition. This prevents proposal-mode uncertainty from turning ordinary agent tasks into split-required work.

Base story points by lines changed:

- `<= 60` -> `1`
- `61-180` -> `2`
- `181-450` -> `3`
- `451-900` -> `5`
- `901-1700` -> `8`
- `> 1700` -> `13`

Risk steps are added for:

- Files touched `>= 8`
- Files touched `>= 15`
- Top-level directories touched `>= 3`
- Max single-file churn `>= 300`
- Binary changes present
- Proposal mode uncertainty

## Blast Radius

Blast radius is separate from story points. A small change can still require stronger controls.

The skill adds path-based signals for areas such as:

- Auth and security
- Database and schema
- Explicit API contracts
- Shared or multi-consumer code
- Runtime entrypoints
- Build and deploy paths
- Runtime configuration

Generic `api`, `data`, and `lib` path names do not trigger blast radius by themselves. They are too common as local implementation folders in agentic coding tasks.

Blast-radius levels:

- `low`
- `medium`
- `high`
- `very-high`

Medium blast radius means targeted tests and owner review are appropriate. It does not stop coding by itself.

## Planning Gates

The `planning` object keeps a backward-compatible boolean and adds severity:

```json
{
  "recommended": true,
  "level": "brief",
  "blocksExecution": false,
  "matchedRules": [
    "mid-sized-cross-boundary"
  ],
  "rationale": [
    "planning rule matched: mid-sized-cross-boundary - base story point estimate is at least 5 and the change spans multiple top-level boundaries"
  ]
}
```

Planning levels:

- `none`: no planning trigger fired.
- `brief`: write a short execution note or checklist, then proceed.
- `required`: stop and produce a concrete plan before coding.

`planning.blocksExecution` is the operational stop flag. Do not stop solely because `planning.recommended` is `true`.

## Decomposition Gates

The skill recommends splitting work when any of these are true:

- Base story points `>= 8`
- Base story points `>= 13`, even for decomposed child tasks
- Files touched `>= 18`
- Lines changed `>= 1500`

When estimating a child task that already came from decomposition, pass `--decomposition-depth 1`. At depth greater than `0`, the estimator suppresses repeat decomposition from base story points `>= 8` unless a hard footprint threshold also matches. This prevents recursive split loops.

## Execution Action

Use `execution.action` as the authoritative gate:

- `proceed`: execute directly.
- `proceed-with-controls`: execute after applying listed controls or brief planning notes.
- `plan-first`: stop and plan before coding.
- `decompose-first`: stop and split before coding.

This lets the estimator preserve thorough risk assessment without treating every risk signal as a coding blocker.

## Confidence

- `high`: diff-backed estimate.
- `medium`: proposal-backed estimate.

Proposal mode is less certain, but that uncertainty is reflected in adjusted story points and confidence rather than automatic decomposition.

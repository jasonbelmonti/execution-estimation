# Execution Estimation User Guide

`execution-estimation` is a user-facing estimation skill for sizing engineering work before implementation. It produces deterministic guidance for:

- Story-point-style level of effort
- Expected or observed file and line churn
- Relative footprint versus the codebase baseline
- Blast radius and required quality controls
- Planning recommendation
- Decomposition recommendation

This skill is useful when you want a consistent pre-implementation answer to questions like:

- How big is this task?
- Is this risky even if the diff is small?
- Should I stop and make a plan before coding?
- Should this work be split into smaller items?

## What the skill can do

The skill supports two estimation modes:

1. Diff-backed estimation
Use this when the work already exists in a branch or diff. The estimator reads the changed file list and actual line churn from git.

2. Proposal-backed estimation
Use this when the work is still planned. The estimator reads a newline-delimited list of proposed files and infers likely churn from file types.

In both modes, the estimator returns deterministic JSON that includes:

- `estimation.storyPoints`
- `estimation.confidence`
- `estimation.decompositionRecommended`
- `change.filesTouched`
- `change.linesChanged`
- `comparison.trackedFilesTouchedPct`
- `comparison.sourceLinesChangedPct`
- `risk.blastRadius`
- `planning`

The `planning` object has this shape:

```json
{
  "recommended": true,
  "matchedRules": [
    "high-blast-radius"
  ],
  "rationale": [
    "planning rule matched: high-blast-radius - blast radius is high enough that sequencing and controls should be decided before coding"
  ]
}
```

`planning.recommended` is always a boolean.

## What it does not do

- It does not automatically switch Codex into the app's actual Planning mode.
- It does not inspect runtime behavior or business impact beyond file-path and churn signals.
- It does not replace engineering judgment for ambiguous architecture choices.

Instead, it gives a deterministic recommendation for whether you should stop and plan before implementation.

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
  --base-ref origin/main \
  --head-ref HEAD
```

### Proposal-backed estimate

Create a file containing one proposed path per line:

```text
src/api/users.ts
src/db/schema.sql
src/api/users.test.ts
```

Then run:

```bash
python3 /path/to/execution-estimation/scripts/estimate_execution.py \
  --repo-root /path/to/repo \
  --proposed-files /path/to/proposed-files.txt
```

Optional:

- `--proposal-lines-changed <n>` overrides the inferred line-churn estimate in proposal mode

## How story points are calculated

The estimator starts from line churn, then adds deterministic risk steps.

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

The total is then mapped upward to this fixed sequence:

- `1, 2, 3, 5, 8, 13`

## How blast radius works

Blast radius is separate from story points. A small change can still have a high blast radius.

The skill adds path-based signals for areas such as:

- Auth and security
- Database and schema
- Public API contracts
- Shared or multi-consumer code
- Runtime entrypoints
- Build and deploy paths
- Runtime configuration

It also adds structural signals for:

- Wide file fanout
- Cross-boundary changes
- Deep single-file churn
- Binary artifacts

Blast-radius levels:

- `low`
- `medium`
- `high`
- `very-high`

The estimator also returns recommended controls, such as:

- Targeted automated tests
- Integration or regression coverage
- Adjacent-boundary review
- Rollback or containment review

## How planning recommendation works

Planning recommendation is a separate deterministic output. It answers one yes/no question:

Should you stop after estimation and explicitly plan before coding?

The answer lives at:

- `planning.recommended`

It becomes `true` when any explicit planning rule matches:

- `decomposition-recommended`: the work item should already be split before implementation
- `high-blast-radius`: blast radius is `high` or `very-high`
- `medium-blast-radius-shaping`: blast radius is `medium` and the work is still proposal-mode or already mid-sized
- `mid-sized-cross-boundary`: story points are at least `5` and the change spans at least `3` top-level directories
- `wide-proposal-change`: proposal mode touches at least `8` files
- `deep-single-file-churn`: max single-file churn is at least `300`

If no planning rule matches:

- `planning.recommended` is `false`
- `planning.matchedRules` is empty
- `planning.rationale` explains that direct execution is appropriate unless the user explicitly asks for a plan

Important:

- This is a binary recommendation output, not an enum.
- It does not flip the product into true Planning mode.

## How decomposition recommendation works

The skill recommends splitting work when any of these are true:

- Story points `>= 8`
- Files touched `>= 18`
- Lines changed `>= 1500`

When decomposition is recommended, split by workflow boundary or risk boundary, for example:

- Resolver, integration, tests
- Schema, runtime, integration

## Understanding the output

Typical output sections:

- `codebase`: baseline repository size used for comparison
- `change`: the direct footprint of the diff or proposal
- `comparison`: percent of the repository touched
- `risk.blastRadius`: risk signals, level, controls, and investigation areas
- `planning`: boolean recommendation plus matched rules and rationale
- `estimation`: story points, confidence, rationale, and decomposition guidance

Example interpretation:

- High story points plus low blast radius means the work is large but locally contained.
- Low story points plus high blast radius means the change is small but touches sensitive boundaries.
- `planning.recommended = true` means you should stop after estimation and produce an execution plan before coding.
- `planning.recommended = false` means direct execution is appropriate unless the user explicitly asks for a plan.
- `decompositionRecommended = true` means the work should be split into smaller items.

## Confidence levels

- `high`: diff-backed estimate
- `medium`: proposal-backed estimate

Proposal mode is intentionally more conservative because the actual diff does not exist yet.

## Recommended workflow

1. Gather the target repo and either a real diff or a proposed file list.
2. Run the estimator.
3. Report the JSON fields, not just a single story-point number.
4. Use blast radius to choose test depth and review breadth.
5. Use planning recommendation to decide whether to stop and plan.
6. Use decomposition recommendation to decide whether to split the work item.

## Related files

- `SKILL.md`: agent instructions for using the skill
- `references/estimation-rubric.md`: thresholds and deterministic rules
- `scripts/estimate_execution.py`: main estimator
- `scripts/blast_radius.py`: blast-radius logic
- `scripts/planning_recommendation.py`: planning recommendation logic

# Execution Estimation Rubric

## Story point baseline by line churn
- `<= 60` lines changed: `1`
- `61-180`: `2`
- `181-450`: `3`
- `451-900`: `5`
- `901-1700`: `8`
- `> 1700`: `13`

## Risk adjustments
Add one risk step for each condition:
- Files touched `>= 8`
- Files touched `>= 15`
- Top-level directories touched `>= 3`
- Single-file churn `>= 300`
- Binary changes present
- Proposal-only mode (higher uncertainty)

Map adjusted score upward to Fibonacci-like points: `1, 2, 3, 5, 8, 13`.

The estimator reports both:
- `estimation.baseStoryPoints`: raw line-churn size.
- `estimation.adjustedStoryPoints`: raw size plus risk steps.

Use adjusted story points for level-of-effort communication. Use base story points and hard footprint thresholds for decomposition gates so uncertainty and review risk do not force artificial splits.

## Blast radius
Blast radius is a separate dimension from story points. Use it to decide test depth, review breadth, and whether to inspect adjacent code even when the diff is small.

### Path-based blast-radius signals
Add weights once per matched signal family:
- `auth-security` `+3`: auth, permissions, policies, sessions, tokens, secrets, crypto
- `data-schema` `+3`: schema, migrations, SQL, database/db paths
- `api-contract` `+2`: explicit contract, DTO, GraphQL, OpenAPI, protobuf paths or files
- `shared-surface` `+2`: shared/core/common/platform/sdk/packages paths
- `runtime-entrypoint` `+2`: app/server/main/index entrypoints and bootstrap paths
- `build-deploy` `+2`: package manifests, lockfiles, Docker, CI, infra, deploy, terraform, helm, k8s
- `runtime-config` `+2`: config, settings, flags, env files

Generic `api`, `data`, and `lib` path tokens do not signal blast radius by themselves. In many repositories those names are local implementation folders, not public system boundaries.

### Structural blast-radius signals
Add weights once per matched condition:
- `wide-file-fanout` `+1`: files touched `>= 8`
- `cross-boundary-surface` `+1`: top-level directories touched `>= 3`
- `deep-single-file-churn` `+1`: max single-file churn `>= 300`
- `binary-artifacts` `+1`: binary changes present

### Blast-radius levels
- `0-1`: `low`
- `2-4`: `medium`
- `5-7`: `high`
- `>= 8`: `very-high`
- Docs-only or tests-only work stays `low` unless structural signals push it higher.

### Quality-control guidance
- `low`: smallest targeted verification
- `medium`: targeted automated tests plus primary-owner review
- `high`: targeted tests, integration/regression coverage, adjacent-boundary review
- `very-high`: same as `high`, plus rollback or containment review before merge or release

## Decomposition recommendation
Recommend decomposition when any condition is true:
- Base story points `>= 8`
- Base story points `>= 13`, even when estimating a decomposed child task
- Files touched `>= 18`
- Lines changed `>= 1500`

When `--decomposition-depth` is greater than `0`, suppress decomposition from base story points `>= 8` unless one of the hard footprint thresholds also matches. This prevents infinite decomposition loops for already-split child work.

## Planning recommendation
Planning recommendation is a separate dimension from decomposition. Use it to decide whether a plan is useful and whether that plan must block coding.

### Planning levels
- `none`: no explicit planning trigger fired.
- `brief`: a short execution note or checklist is useful, but coding can proceed.
- `required`: stop after estimation and present a concrete plan before implementation.

`planning.blocksExecution` is `true` only for `required`.

### Planning rules
Set `planning.recommended` to `true` when any rule is true:
- `decomposition-recommended`: `decompositionRecommended` is `true`
- `high-blast-radius`: blast radius level is `high` or `very-high`
- `medium-blast-radius-shaping`: blast radius level is `medium` and the work is either `>= 5` base story points or spans at least 3 top-level directories
- `mid-sized-cross-boundary`: base story points `>= 5` and top-level directories touched `>= 3`
- `wide-proposal-change`: files touched `>= 8`, mode is `proposal`, and the work is not docs-only or tests-only
- `deep-single-file-churn`: max single-file churn `>= 300`

`decomposition-recommended` and `high-blast-radius` are `required` planning rules. The other rules are `brief` planning rules.

Medium blast radius by itself is not a planning stop. It selects stronger controls, and only becomes a planning recommendation when paired with meaningful size or boundary complexity.

### Planning output
- `planning.recommended`: binary yes/no recommendation
- `planning.level`: `none`, `brief`, or `required`
- `planning.blocksExecution`: whether the recommendation blocks coding
- `planning.matchedRules`: stable rule keys that caused `true`; empty when `false`
- `planning.rationale`: human-readable explanation of the matched rules, or a direct-execution explanation when no rule matched

## Execution action
The top-level execution action is the authoritative gate:
- `proceed`: no blocking planning or decomposition gate matched.
- `proceed-with-controls`: coding can proceed, but apply the listed planning notes or quality controls.
- `plan-first`: stop and plan before coding.
- `decompose-first`: stop and split before coding.

## Confidence
- `high`: diff-backed estimate
- `medium`: proposal-backed estimate

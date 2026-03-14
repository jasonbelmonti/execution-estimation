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

## Blast radius
Blast radius is a separate dimension from story points. Use it to decide test depth, review breadth, and whether to inspect adjacent code even when the diff is small.

### Path-based blast-radius signals
Add weights once per matched signal family:
- `auth-security` `+3`: auth, permissions, policies, sessions, tokens, secrets, crypto
- `data-schema` `+3`: schema, migrations, SQL, database paths
- `api-contract` `+2`: API contracts, GraphQL, OpenAPI, protobuf, DTO paths
- `shared-surface` `+2`: shared/core/common/lib/platform/packages paths
- `runtime-entrypoint` `+2`: app/server/main/index entrypoints and bootstrap paths
- `build-deploy` `+2`: package manifests, lockfiles, Docker, CI, infra, deploy, terraform, helm, k8s
- `runtime-config` `+2`: config, settings, flags, env files

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
- Story points `>= 8`
- Files touched `>= 18`
- Lines changed `>= 1500`

## Confidence
- `high`: diff-backed estimate
- `medium`: proposal-backed estimate

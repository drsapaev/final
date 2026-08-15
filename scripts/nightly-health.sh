#!/usr/bin/env bash
# scripts/nightly-health.sh — Reliability R3: nightly health evidence.
#
# Collects the minimal observable metric set for the reliability milestone:
#   mutation backend/frontend, api contract, release gate, security scans,
#   weekly load/chaos/DR — status, duration, artifact existence, mutation scores.
#
# Output: markdown table to stdout and to $GITHUB_STEP_SUMMARY (if set).
# Exit code: 0 always (observability, not enforcement — R1 handles alerting).
#
# Usage (from repo root, GITHUB_TOKEN + GITHUB_REPOSITORY in env):
#   bash scripts/nightly-health.sh
set -uo pipefail

REPO="${GITHUB_REPOSITORY:-drsapaev/final}"
API="https://api.github.com/repos/${REPO}"

api() { curl -sS -H "Authorization: Bearer ${GITHUB_TOKEN}" -H "Accept: application/vnd.github+json" "$1"; }

# jq is preinstalled on GitHub runners; fail early with a clear message if not.
command -v jq >/dev/null || { echo "jq is required"; exit 1; }

# workflow_file | display name | required-event filter | cadence | expected artifacts (comma-sep)
WORKFLOWS=(
  "mutation.yml|mutation (backend+frontend)|schedule|daily|mutmut-report,stryker-report"
  "ci-cd-unified.yml|unified CI (incl. api-contract gates)|schedule|daily|-"
  "security-scan.yml|security scan|schedule|daily|security-reports"
  "gitleaks.yml|gitleaks|schedule|daily|-"
  "release-gate.yml|release gate|workflow_dispatch|on-release|-"
  "ai-safety-guardrails.yml|AI safety guardrails|schedule|daily|-"
  "dr-drill.yml|DR drill|schedule|weekly|-"
  "load.yml|load testing|schedule|weekly|-"
  "chaos.yml|chaos testing|schedule|weekly|-"
  "weekly-maintenance.yml|weekly maintenance|schedule|weekly|-"
)

# Latest completed run of a workflow for a given event (empty if none).
latest_run() {
  api "${API}/actions/workflows/$1/runs?status=completed&event=$2&per_page=5" \
    | jq -r '[.workflow_runs[] | select(.head_branch == "main" or .event == "workflow_dispatch")][0] // empty'
}

# Human duration from run timestamps (n/a on any parse failure).
run_duration() {
  jq -r '
    (.updated_at | fromdateiso8601) as $end | (.created_at | fromdateiso8601) as $start
    | ($end - $start) as $s
    | if $s >= 3600 then "\($s / 3600 | floor)h \($s % 3600 / 60 | floor)m"
      elif $s >= 60 then "\($s / 60 | floor)m \($s % 60)s"
      else "\($s)s" end
  ' <<<"$1" 2>/dev/null || echo "n/a"
}

# Mutation scores, best-effort: parse steps' conclusions + log grep is heavy,
# so scores come from step names being green plus artifact presence; the exact
# percentages stay in the run artifacts (linked from the table).

{
  echo "# Nightly health — $(date -u '+%Y-%m-%d %H:%M UTC')"
  echo
  echo "| Workflow | Cadence | Last run (event) | Status | Duration | Artifacts | Link |"
  echo "|---|---|---|---|---|---|---|"

  for entry in "${WORKFLOWS[@]}"; do
    IFS='|' read -r file name event cadence artifacts <<<"$entry"
    run_json="$(latest_run "$file" "$event")"
    if [ -z "$run_json" ]; then
      echo "| ${name} | ${cadence} | — | ⚠️ NO COMPLETED RUN | — | — | — |"
      continue
    fi
    conclusion=$(jq -r .conclusion <<<"$run_json")
    run_number=$(jq -r .run_number <<<"$run_json")
    run_id=$(jq -r .id <<<"$run_json")
    created=$(jq -r .created_at <<<"$run_json")
    duration=$(run_duration <<<"$run_json")

    icon="❓ ${conclusion}"
    [ "$conclusion" = "success" ] && icon="✅ PASS"
    [ "$conclusion" = "failure" ] && icon="❌ FAIL"
    [ "$conclusion" = "cancelled" ] && icon="⛔ cancelled"

    art_cell="—"
    if [ "$artifacts" != "-" ]; then
      art_cell=""
      IFS=',' read -ra expected <<<"$artifacts"
      got=$(api "${API}/actions/runs/${run_id}/artifacts?per_page=100" | jq -r '.artifacts[].name')
      for want in "${expected[@]}"; do
        if grep -qx "$want" <<<"$got"; then art_cell+="✅ ${want}<br>"; else art_cell+="❌ ${want} MISSING<br>"; fi
      done
    fi

    echo "| ${name} | ${cadence} | #${run_number} (${created%%T*}, ${event}) | ${icon} | ${duration} | ${art_cell} | [run ${run_id}](https://github.com/${REPO}/actions/runs/${run_id}) |"
  done

  echo
  echo "## Mutation score evidence"
  echo "Exact percentages are recorded in each run's artifacts (\`mutmut-report\`, \`stryker-report\`) and in the parse-step logs of the linked run."
  echo "Baseline at enforcement start (2026-08-14): backend 34.5% (floor 30, do not raise until several green nightlies), frontend 83.15% (floor 70)."
  echo
  echo "## Alerting"
  echo "Failed scheduled runs open a \`ci-failure\` issue automatically (R1, \`.github/actions/notify-failure\`). This report is observability, not alerting."
} | tee /tmp/nightly-health.md

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  cat /tmp/nightly-health.md >> "$GITHUB_STEP_SUMMARY"
fi

#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./snapshot.sh           # from repo root
#   ./snapshot.sh /path/to/cryptopilot
#
# Env:
#   LANG_HINT=python                # tag in filename
#   INCLUDE_CONCRETE=1              # also include impl-heavy modules (coingecko, ollama, strategies)

ROOT_DIR=${1:-$(pwd)}
ROOT_DIR=$(cd "$ROOT_DIR" && pwd)
REPO_NAME=$(basename "$ROOT_DIR")
LANG_HINT=${LANG_HINT:-python}
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")

OUT_DIR="${HOME}/tmp"
mkdir -p "${OUT_DIR}"
OUT_FILE="${OUT_DIR}/${REPO_NAME}-${LANG_HINT}-${TIMESTAMP}.txt"


###############################################################################
# Header
###############################################################################
{
  echo "Snapshot generated: ${TIMESTAMP}"
  echo "Project: ${REPO_NAME}"
  echo "Language hint: ${LANG_HINT}"
  echo "Root: ${ROOT_DIR}"
  echo
  echo "==============================================="
  echo "TREE (excluding venv/.git/tests/etc)"
  echo "==============================================="
} > "${OUT_FILE}"

###############################################################################
# Tree (or find fallback)
###############################################################################
if command -v tree >/dev/null 2>&1; then
  tree -aJ --gitignore "${ROOT_DIR}" \
    -I '.git|.hg|.svn|.venv|venv|.mypy_cache|.pytest_cache|__pycache__|.idea|.vscode|dist|build|.tox|.ruff_cache|tests' \
    >> "${OUT_FILE}"
else
  find "${ROOT_DIR}" -maxdepth 6 \
    \( -name '.git' -o -name '.hg' -o -name '.svn' -o -name '.venv' -o -name 'venv' \
       -o -name '.mypy_cache' -o -name '.pytest_cache' -o -name '__pycache__' \
       -o -name '.idea' -o -name '.vscode' -o -name 'dist' -o -name 'build' \
       -o -name '.tox' -o -name '.ruff_cache' -o -name 'tests' \) \
    -prune -o -print \
    >> "${OUT_FILE}"
fi

###############################################################################
# Top-level docs
###############################################################################
{
  echo
  echo "==============================================="
  echo "DOCS"
  echo "==============================================="
} >> "${OUT_FILE}"

DOC_FILES=(
  "README.md"
  "ROADMAP.md"
  "config.toml.example"
)

for rel in "${DOC_FILES[@]}"; do
  abs="${ROOT_DIR}/${rel}"
  if [ -f "${abs}" ]; then
    {
      echo
      echo "----- BEGIN DOC: ${rel} -----"
      cat "${abs}"
      echo
      echo "----- END DOC: ${rel} -----"
    } >> "${OUT_FILE}"
  fi
done

###############################################################################
# Manifests
###############################################################################
{
  echo
  echo "==============================================="
  echo "MANIFESTS"
  echo "==============================================="
} >> "${OUT_FILE}"

MANIFESTS=(
  "pyproject.toml"
)

for rel in "${MANIFESTS[@]}"; do
  abs="${ROOT_DIR}/${rel}"
  if [ -f "${abs}" ]; then
    {
      echo
      echo "===== ${rel} ====="
      cat "${abs}"
    } >> "${OUT_FILE}"
  fi
done

###############################################################################
# Core architecture files, tuned for cryptopilot layout
###############################################################################
{
  echo
  echo "==============================================="
  echo "CORE ARCHITECTURE"
  echo "==============================================="
  echo "# Focus: bases, schemas, registries, settings, utils, wiring."
  echo "# Skips heavy concrete impls like strategies/*, providers/coingecko.py, reporting/llm/ollama.py."
} >> "${OUT_FILE}"

# Base/architectural modules only
CORE_FILES=(
  # package root
  "cryptopilot/__init__.py"
  "cryptopilot/main.py"

  # config
  "cryptopilot/config/__init__.py"
  "cryptopilot/config/schema.py"
  "cryptopilot/config/settings.py"

  # database
  "cryptopilot/database/__init__.py"
  "cryptopilot/database/connection.py"
  "cryptopilot/database/models.py"
  "cryptopilot/database/repository.py"
  "cryptopilot/database/migrations.py"
  "cryptopilot/database/schema.sql"

  # analysis core
  "cryptopilot/analysis/__init__.py"
  "cryptopilot/analysis/engine.py"
  "cryptopilot/analysis/indicators.py"
  "cryptopilot/analysis/models.py"
  "cryptopilot/analysis/registry.py"
  "cryptopilot/analysis/strategies/__init__.py"
  "cryptopilot/analysis/strategies/base.py"

  # providers (interfaces + registry, skip impls)
  "cryptopilot/providers/__init__.py"
  "cryptopilot/providers/base.py"
  "cryptopilot/providers/models.py"
  "cryptopilot/providers/registry.py"

  # portfolio
  "cryptopilot/portfolio/__init__.py"
  "cryptopilot/portfolio/models.py"
  "cryptopilot/portfolio/manager.py"
  "cryptopilot/portfolio/trades.py"

  # reporting + LLM abstractions
  "cryptopilot/reporting/__init__.py"
  "cryptopilot/reporting/formatters.py"
  "cryptopilot/reporting/generator.py"
  "cryptopilot/reporting/llm/__init__.py"
  "cryptopilot/reporting/llm/base.py"
  "cryptopilot/reporting/llm/registry.py"

  # cli (wiring + commands define public surface, low volume)
  "cryptopilot/cli/__init__.py"
  "cryptopilot/cli/formatters.py"
  "cryptopilot/cli/commands/__init__.py"
  "cryptopilot/cli/commands/analyze.py"
  "cryptopilot/cli/commands/collect.py"
  "cryptopilot/cli/commands/config.py"
  "cryptopilot/cli/commands/portfolio.py"
  "cryptopilot/cli/commands/report.py"
  "cryptopilot/cli/commands/system.py"

  # collectors (data pipeline architecture)
  "cryptopilot/collectors/__init__.py"
  "cryptopilot/collectors/gap_filler.py"
  "cryptopilot/collectors/market_data.py"

  # utils
  "cryptopilot/utils/__init__.py"
  "cryptopilot/utils/datetime_utils.py"
  "cryptopilot/utils/decimal_math.py"
  "cryptopilot/utils/retry.py"
  "cryptopilot/utils/validation.py"
)

# Optional heavy concrete implementations if explicitly requested
CONCRETE_FILES=(
  "cryptopilot/analysis/strategies/mean_reversion.py"
  "cryptopilot/analysis/strategies/momentum.py"
  "cryptopilot/analysis/strategies/trend_following.py"
  "cryptopilot/providers/coingecko.py"
  "cryptopilot/reporting/llm/ollama.py"
)

if [ "${INCLUDE_CONCRETE:-0}" = "1" ]; then
  CORE_FILES+=("${CONCRETE_FILES[@]}")
fi

found_any=0
for rel in "${CORE_FILES[@]}"; do
  abs="${ROOT_DIR}/${rel}"
  if [ -f "${abs}" ]; then
    found_any=1
    {
      echo
      echo "----- BEGIN PY: ${rel} -----"
      cat "${abs}"
      echo
      echo "----- END PY: ${rel} -----"
    } >> "${OUT_FILE}"
  fi
done

if [ "${found_any}" -eq 0 ]; then
  echo "No core files found; check CORE_FILES list in script." >> "${OUT_FILE}"
fi

###############################################################################
# Final marker
###############################################################################
{
  echo
  echo "==============================================="
  echo "END OF SNAPSHOT"
  echo "==============================================="
} >> "${OUT_FILE}"

echo "${OUT_FILE}"


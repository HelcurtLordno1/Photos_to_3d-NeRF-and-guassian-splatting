#!/usr/bin/env bash

set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

config_arg="${1:-}"
[[ -f "${config_arg}" ]] || die "Usage: $0 PATH/TO/config.yml"
require_command ns-eval

config_path="$(realpath "${config_arg}")"
case "${config_path}" in
  "${ARTIFACT_ROOT}/runs/"*) ;;
  *) die "Config must be inside ${ARTIFACT_ROOT}/runs: ${config_path}" ;;
esac
relative="${config_path#${ARTIFACT_ROOT}/runs/}"
run_slug="${relative%/config.yml}"
metrics_path="${ARTIFACT_ROOT}/metrics/${run_slug}/metrics.json"
renders_path="${ARTIFACT_ROOT}/renders/${run_slug}"
ensure_dir "$(dirname "${metrics_path}")"
ensure_dir "${renders_path}"

ns-eval \
  --load-config "${config_path}" \
  --output-path "${metrics_path}" \
  --render-output-path "${renders_path}"

du -sb "$(dirname "${config_path}")" | awk '{print $1}' > "$(dirname "${metrics_path}")/run-bytes.txt"

info "Metrics: ${metrics_path}"
info "Held-out renders: ${renders_path}"

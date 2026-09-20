#!/usr/bin/env bash

set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

output="${1:-}"
interval="${2:-${GPU_SAMPLE_SECONDS}}"
[[ -n "${output}" ]] || die "Usage: $0 OUTPUT.csv [INTERVAL_SECONDS]"
require_command nvidia-smi
ensure_dir "$(dirname "${output}")"

nvidia-smi \
  --query-gpu=timestamp,index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw \
  --format=csv \
  --loop="${interval}" > "${output}"

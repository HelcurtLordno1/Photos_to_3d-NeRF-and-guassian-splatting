#!/usr/bin/env bash

set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

failures=0

check_command() {
  local command_name="$1"
  if command -v "${command_name}" >/dev/null 2>&1; then
    printf '[ok]      %-18s %s\n' "${command_name}" "$(command -v "${command_name}")"
  else
    printf '[missing] %-18s\n' "${command_name}"
    failures=$((failures + 1))
  fi
}

printf 'Project: %s\n' "${PROJECT_ROOT}"
printf 'Kernel:  %s\n' "$(uname -srmo)"
for tool in bash git curl unzip ffmpeg make rg nvidia-smi; do
  check_command "${tool}"
done

if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap --format=csv,noheader
fi

if command -v python >/dev/null 2>&1; then
  printf '[info]    python             %s\n' "$(python --version 2>&1)"
fi
if command -v pixi >/dev/null 2>&1; then
  printf '[info]    pixi               %s\n' "$(pixi --version 2>&1)"
fi
if command -v ns-train >/dev/null 2>&1; then
  printf '[ok]      ns-train           available\n'
else
  printf '[pending] ns-train           activate the pinned Nerfstudio environment first\n'
fi

available_kb="$(df -Pk "${PROJECT_ROOT}" | awk 'NR==2 {print $4}')"
printf '[info]    free workspace     %s GiB\n' "$((available_kb / 1024 / 1024))"

if (( failures > 0 )); then
  die "${failures} required host command(s) are missing. See Construction_architect.md section 9."
fi

info "Host-level checks passed. CUDA/PyTorch import checks run after environment activation."

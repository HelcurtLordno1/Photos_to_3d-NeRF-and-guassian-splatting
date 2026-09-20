#!/usr/bin/env bash

set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

require_command ns-process-data

scene="${1:-}"
train_images="${2:-}"
eval_images="${3:-}"
[[ -n "${scene}" && -n "${train_images}" ]] \
  || die "Usage: $0 SCENE_NAME TRAIN_IMAGE_DIR [EVAL_IMAGE_DIR]"
[[ "${scene}" =~ ^[a-z0-9][a-z0-9_-]*$ ]] \
  || die "SCENE_NAME may contain only lowercase letters, digits, '_' and '-'."
[[ -d "${train_images}" ]] || die "Train image directory does not exist: ${train_images}"
if [[ -n "${eval_images}" ]]; then
  [[ -d "${eval_images}" ]] || die "Eval image directory does not exist: ${eval_images}"
fi

output_dir="${PROCESSED_DATA_ROOT}/custom/${scene}"
if [[ -e "${output_dir}/transforms.json" ]]; then
  die "Processed scene already exists at ${output_dir}; use a new scene name to preserve provenance."
fi
ensure_dir "${output_dir}"

command=(ns-process-data images --data "${train_images}" --output-dir "${output_dir}")
if [[ -n "${eval_images}" ]]; then
  command+=(--eval-data "${eval_images}")
fi

info "Running COLMAP-backed preprocessing for ${scene}."
"${command[@]}"
[[ -f "${output_dir}/transforms.json" ]] || die "Preprocessing did not produce transforms.json."
info "Processed capture ready: ${output_dir}"

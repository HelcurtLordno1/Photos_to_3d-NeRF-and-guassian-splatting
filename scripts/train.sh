#!/usr/bin/env bash

set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

method="${1:-}"
dataset_key="${2:-}"
shift "$(( $# >= 2 ? 2 : $# ))"
[[ "${method}" == "nerfacto" || "${method}" == "splatfacto" ]] \
  || die "METHOD must be nerfacto or splatfacto."
[[ -n "${dataset_key}" ]] || die "Usage: $0 {nerfacto|splatfacto} DATASET_KEY [extra ns-train args]"
require_command ns-train
require_command rg

parser=""
eval_mode="interval"
data_dir=""
case "${dataset_key}" in
  poster)
    data_dir="${RAW_DATA_ROOT}/nerfstudio/poster"
    parser="nerfstudio-data"
    ;;
  garden|bonsai|room)
    data_dir="${RAW_DATA_ROOT}/mipnerf360/${dataset_key}"
    parser="colmap"
    ;;
  custom:*)
    scene="${dataset_key#custom:}"
    [[ -n "${scene}" ]] || die "Custom key must be custom:SCENE_NAME."
    data_dir="${PROCESSED_DATA_ROOT}/custom/${scene}"
    parser="nerfstudio-data"
    if rg -q 'eval_' "${data_dir}/transforms.json" 2>/dev/null; then
      eval_mode="filename"
    fi
    ;;
  *) die "Unknown dataset key: ${dataset_key}. Use poster, garden, bonsai, room, or custom:NAME." ;;
esac

[[ -d "${data_dir}" ]] || die "Dataset is missing: ${data_dir}"
if [[ "${parser}" == "nerfstudio-data" ]]; then
  [[ -f "${data_dir}/transforms.json" ]] || die "Missing transforms.json in ${data_dir}"
else
  [[ -d "${data_dir}/sparse/0" ]] || die "Missing COLMAP sparse/0 in ${data_dir}"
fi
if [[ "${DOWNSCALE_FACTOR}" == "1" ]]; then
  [[ -d "${data_dir}/images" ]] || die "Missing images directory in ${data_dir}"
else
  [[ -d "${data_dir}/images_${DOWNSCALE_FACTOR}" ]] \
    || die "Missing images_${DOWNSCALE_FACTOR} in ${data_dir}"
fi
run_id="$(date -u +%Y%m%dT%H%M%SZ)"
run_name="${dataset_key//:/-}"
run_dir="${ARTIFACT_ROOT}/runs/${run_name}/${method}/${run_id}"
log_dir="${ARTIFACT_ROOT}/logs/${run_name}/${method}/${run_id}"
ensure_dir "${run_dir}"
ensure_dir "${log_dir}"

monitor_pid=""
stop_monitor() {
  if [[ -n "${monitor_pid}" ]]; then
    kill "${monitor_pid}" >/dev/null 2>&1 || true
    wait "${monitor_pid}" >/dev/null 2>&1 || true
  fi
}
trap stop_monitor EXIT INT TERM

if command -v nvidia-smi >/dev/null 2>&1; then
  "${SCRIPT_DIR}/monitor_gpu.sh" "${log_dir}/gpu.csv" "${GPU_SAMPLE_SECONDS}" &
  monitor_pid=$!
fi

printf 'method=%s\ndataset=%s\ndata_dir=%s\niterations=%s\ndownscale=%s\neval_mode=%s\n' \
  "${method}" "${dataset_key}" "${data_dir}" "${TRAIN_ITERATIONS}" \
  "${DOWNSCALE_FACTOR}" "${eval_mode}" > "${log_dir}/run.env"
printf 'seed=%s\n' "${RANDOM_SEED}" >> "${log_dir}/run.env"
git -C "${PROJECT_ROOT}" status --short -- . > "${log_dir}/git-status.txt" 2>/dev/null || true
nvidia-smi -q > "${log_dir}/nvidia-smi.txt" 2>/dev/null || true
python --version > "${log_dir}/python-version.txt" 2>&1 || true

command=(
  ns-train "${method}"
  --output-dir "${ARTIFACT_ROOT}/runs"
  --experiment-name "${run_name}"
  --timestamp "${run_id}"
  --max-num-iterations "${TRAIN_ITERATIONS}"
  --machine.seed "${RANDOM_SEED}"
  --vis tensorboard
  "${parser}"
  --data "${data_dir}"
  --downscale-factor "${DOWNSCALE_FACTOR}"
  --eval-mode "${eval_mode}"
)
if [[ "${eval_mode}" == "interval" ]]; then
  command+=(--eval-interval "${EVAL_INTERVAL}")
fi
command+=("$@")

info "Run directory: ${run_dir}"
printf '%q ' "${command[@]}" | tee "${log_dir}/command.txt"
printf '\n' | tee -a "${log_dir}/command.txt"
start_epoch="$(date +%s)"
start_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
set +e
"${command[@]}" 2>&1 | tee "${log_dir}/train.log"
train_status="${PIPESTATUS[0]}"
set -e
end_epoch="$(date +%s)"
end_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'start_utc=%s\nend_utc=%s\nelapsed_seconds=%s\nexit_code=%s\n' \
  "${start_utc}" "${end_utc}" "$((end_epoch - start_epoch))" "${train_status}" \
  > "${log_dir}/timing.env"
(( train_status == 0 )) || die "Training failed with exit code ${train_status}; see ${log_dir}/train.log"

info "Training complete. Evaluate ${run_dir}/config.yml with scripts/evaluate.sh."

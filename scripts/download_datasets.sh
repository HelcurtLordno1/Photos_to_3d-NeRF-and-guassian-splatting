#!/usr/bin/env bash

set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

mode="${1:-smoke}"

download_smoke() {
  require_command ns-download-data
  ensure_dir "${RAW_DATA_ROOT}"
  if [[ -f "${RAW_DATA_ROOT}/nerfstudio/poster/transforms.json" ]]; then
    info "Smoke dataset already present; skipping."
    return
  fi
  ns-download-data nerfstudio --save-dir "${RAW_DATA_ROOT}" --capture-name poster
  [[ -f "${RAW_DATA_ROOT}/nerfstudio/poster/transforms.json" ]] \
    || die "Poster download finished but transforms.json was not found."
}

download_benchmark() {
  require_command curl
  require_command unzip
  local cache_dir="${DATA_ROOT}/.cache"
  local archive="${cache_dir}/360_v2.zip"
  local target="${RAW_DATA_ROOT}/mipnerf360"
  local required_free_kb=$((20 * 1024 * 1024))
  local available_kb
  available_kb="$(df -Pk "${PROJECT_ROOT}" | awk 'NR==2 {print $4}')"
  (( available_kb >= required_free_kb )) \
    || die "Benchmark download needs at least 20 GiB free in the workspace filesystem."

  ensure_dir "${cache_dir}"
  ensure_dir "${target}"
  if [[ -f "${archive}" ]] && [[ "$(wc -c < "${archive}")" == "${MIPNERF360_ARCHIVE_BYTES}" ]]; then
    info "Validated-size archive already present; skipping network download."
  else
    info "Downloading the official 12.5 GB Mip-NeRF 360 archive (resume enabled)."
    curl --fail --location --retry 5 --retry-delay 3 --continue-at - \
      --output "${archive}" "${MIPNERF360_URL}"
  fi

  local actual_bytes
  actual_bytes="$(wc -c < "${archive}")"
  [[ "${actual_bytes}" == "${MIPNERF360_ARCHIVE_BYTES}" ]] \
    || die "Archive size mismatch: expected ${MIPNERF360_ARCHIVE_BYTES}, got ${actual_bytes}."
  unzip -tq "${archive}" >/dev/null

  local scene
  for scene in ${MIPNERF360_SCENES}; do
    if [[ -d "${target}/${scene}/images" && -d "${target}/${scene}/sparse" ]]; then
      info "${scene} already extracted; skipping."
      continue
    fi
    info "Extracting selected scene: ${scene}"
    unzip -q -o "${archive}" "${scene}/*" -d "${target}"
    [[ -d "${target}/${scene}/images" && -d "${target}/${scene}/sparse" ]] \
      || die "Unexpected archive layout for scene ${scene}."
  done

  info "Archive retained at ${archive} so interrupted/repeated setup is cheap."
}

case "${mode}" in
  smoke) download_smoke ;;
  benchmark) download_benchmark ;;
  all)
    download_smoke
    download_benchmark
    ;;
  *) die "Usage: $0 {smoke|benchmark|all}" ;;
esac

info "Dataset profile '${mode}' is ready."

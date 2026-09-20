#!/usr/bin/env bash

set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

require_command git
mode="${1:-runtime}"

clone_at_commit() {
  local name="$1"
  local url="$2"
  local commit="$3"
  local recursive="${4:-false}"
  local destination="${THIRD_PARTY_ROOT}/${name}"

  if [[ -e "${destination}" && ! -d "${destination}/.git" ]]; then
    die "${destination} exists but is not a Git repository; refusing to overwrite it."
  fi

  if [[ ! -d "${destination}/.git" ]]; then
    info "Initializing ${name}"
    mkdir -p "${destination}"
    git -C "${destination}" init
    git -C "${destination}" remote add origin "${url}"
  fi

  info "Fetching ${name} at ${commit}"
  git -C "${destination}" fetch --depth 1 origin "${commit}"
  git -C "${destination}" checkout --detach FETCH_HEAD
  if [[ "${recursive}" == "true" ]]; then
    git -C "${destination}" submodule update --init --recursive --depth 1
  fi

  local actual
  actual="$(git -C "${destination}" rev-parse HEAD)"
  [[ "${actual}" == "${commit}" ]] || die "Commit mismatch for ${name}: ${actual}"
}

ensure_dir "${THIRD_PARTY_ROOT}"

case "${mode}" in
  runtime)
    clone_at_commit nerfstudio https://github.com/nerfstudio-project/nerfstudio.git "${NERFSTUDIO_COMMIT}"
    ;;
  research)
    clone_at_commit nerf https://github.com/bmild/nerf.git "${NERF_REFERENCE_COMMIT}"
    clone_at_commit multinerf https://github.com/google-research/multinerf.git "${MULTINERF_REFERENCE_COMMIT}"
    clone_at_commit instant-ngp https://github.com/NVlabs/instant-ngp.git "${INSTANT_NGP_REFERENCE_COMMIT}" true
    clone_at_commit gaussian-splatting https://github.com/graphdeco-inria/gaussian-splatting.git "${GAUSSIAN_SPLATTING_REFERENCE_COMMIT}" true
    clone_at_commit gsplat https://github.com/nerfstudio-project/gsplat.git "${GSPLAT_COMMIT}"
    clone_at_commit colmap https://github.com/colmap/colmap.git "${COLMAP_REFERENCE_COMMIT}"
    ;;
  all)
    "${BASH_SOURCE[0]}" runtime
    "${BASH_SOURCE[0]}" research
    ;;
  *)
    die "Usage: $0 {runtime|research|all}"
    ;;
esac

info "Repository snapshot(s) ready under ${THIRD_PARTY_ROOT}."

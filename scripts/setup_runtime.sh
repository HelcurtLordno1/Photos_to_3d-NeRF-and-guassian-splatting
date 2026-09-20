#!/usr/bin/env bash

set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

require_command pixi
require_command git
require_command nvidia-smi

if [[ ! -d "${THIRD_PARTY_ROOT}/nerfstudio/.git" ]]; then
  "${SCRIPT_DIR}/download_repos.sh" runtime
fi

actual_commit="$(git -C "${THIRD_PARTY_ROOT}/nerfstudio" rev-parse HEAD)"
[[ "${actual_commit}" == "${NERFSTUDIO_COMMIT}" ]] \
  || die "Nerfstudio is at ${actual_commit}; expected ${NERFSTUDIO_COMMIT}."

info "Building the upstream pinned Pixi environment."
(
  cd "${THIRD_PARTY_ROOT}/nerfstudio"
  pixi run post-install
  pixi run python -c 'import torch, gsplat, nerfstudio; assert torch.cuda.is_available(); print("torch", torch.__version__, "cuda", torch.version.cuda); print("gpu", torch.cuda.get_device_name(0)); print("gsplat", getattr(gsplat, "__version__", "unknown")); print("nerfstudio", getattr(nerfstudio, "__version__", "unknown"))'
)

info "Runtime is valid. Activate it with: cd '${THIRD_PARTY_ROOT}/nerfstudio' && pixi shell"

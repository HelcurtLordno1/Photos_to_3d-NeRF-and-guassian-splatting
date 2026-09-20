#!/usr/bin/env bash

set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

require_command curl
paper_dir="${PROJECT_ROOT}/docs/research/papers"
ensure_dir "${paper_dir}"

download_pdf() {
  local filename="$1"
  local url="$2"
  local destination="${paper_dir}/${filename}"
  if [[ -s "${destination}" ]] && head -c 4 "${destination}" | grep -q '%PDF'; then
    info "${filename} already present; skipping."
    return
  fi
  info "Downloading ${filename}"
  curl --fail --location --retry 4 --output "${destination}.part" "${url}"
  head -c 4 "${destination}.part" | grep -q '%PDF' || die "Not a PDF: ${url}"
  mv "${destination}.part" "${destination}"
}

download_pdf 01_nerf_eccv2020.pdf https://arxiv.org/pdf/2003.08934
download_pdf 02_mipnerf360_cvpr2022.pdf https://arxiv.org/pdf/2111.12077
download_pdf 03_instant_ngp_siggraph2022.pdf https://arxiv.org/pdf/2201.05989
download_pdf 04_nerfstudio_siggraph2023.pdf https://arxiv.org/pdf/2302.04264
download_pdf 05_3d_gaussian_splatting_siggraph2023.pdf https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/3d_gaussian_splatting_low.pdf
download_pdf 06_gsplat_jmlr2025.pdf https://jmlr.org/papers/volume26/24-1476/24-1476.pdf
download_pdf 07_colmap_cvpr2016.pdf https://openaccess.thecvf.com/content_cvpr_2016/papers/Schonberger_Structure-From-Motion_Revisited_CVPR_2016_paper.pdf

info "Core papers ready under ${paper_dir}."

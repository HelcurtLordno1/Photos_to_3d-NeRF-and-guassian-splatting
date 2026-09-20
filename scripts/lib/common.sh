#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_LIB_DIR}/../.." && pwd)"

# shellcheck disable=SC1091
source "${PROJECT_ROOT}/configs/project.env"

DATA_ROOT="${PROJECT_ROOT}/data"
RAW_DATA_ROOT="${DATA_ROOT}/raw"
PROCESSED_DATA_ROOT="${DATA_ROOT}/processed"
ARTIFACT_ROOT="${PROJECT_ROOT}/artifacts"
THIRD_PARTY_ROOT="${PROJECT_ROOT}/third_party"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

info() {
  printf '[topic16] %s\n' "$*"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"
}

ensure_dir() {
  mkdir -p "$1"
}

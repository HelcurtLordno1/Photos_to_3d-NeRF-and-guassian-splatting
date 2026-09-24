# Local setup audit — 2026-09-23 (updated 2026-09-24)

This is the observed state of the target laptop. Both dataset profiles, the
MSVC v142 host toolchain and the pinned native Windows runtime now pass setup
validation. No training/evaluation run has been completed yet.
Reproducible commands are in `setup_full_command.md`.

| Check | Observed result |
|---|---|
| Windows PowerShell | 5.1.26100.9444 |
| GPU | NVIDIA RTX A4500 Laptop GPU, 16,384 MiB, compute capability 8.6 |
| NVIDIA driver | 597.06 |
| Workspace free space | About 236 GiB at preflight; dataset downloads completed on D: |
| Git/Conda | Available; `topic16-ns115` Conda environment created |
| Nerfstudio source | Exact v1.1.5 commit `6b60855003011b2ca23c2fe3f8e2ca6314c69924` checked out under ignored `third_party/` |
| Visual Studio | C++ toolset 14.44 and v142/14.29.30133 present. The corrected installer completed, `vswhere` found the v142 component, `Check-Environment.ps1` passed, and `Import-VisualStudioEnvironment` selected `cl.exe` from 14.29.30133. |
| CUDA/Python runtime | `tinycudann` built and installed; PyTorch `2.1.2+cu118`, gsplat `1.4.0+pt21cu118`, Nerfstudio imports and a CUDA tensor pass `Test-Runtime.ps1`. |
| Native CLIs | `colmap 3.9.1`, `ffmpeg 6.1.1`, `ns-train`, `ns-eval` and `ns-process-data` help commands exit 0. |
| Setup snapshot | `Setup-Project.ps1 -FinalizeOnly` completed on 2026-09-24; `artifacts/logs/runtime/requirements.txt` contains 238 resolved Python packages. |
| Poster smoke data | Official pinned Hugging Face source downloaded under `data/raw/nerfstudio/poster`; its 226-frame metadata was filtered to the 100 available image pairs under `data/processed/nerfstudio/poster`. All processed frame paths validated. |
| Mip-NeRF 360 | Official 12,535,427,936-byte archive downloaded to `data/.cache/360_v2.zip`; `garden` (185 images), `bonsai` (292), and `room` (311) extracted under `data/raw/mipnerf360`, each with `sparse/0/cameras.bin` |
| Dataset command | `scripts/Download-Datasets.ps1 -Mode all` rerun succeeded without re-download |
| Training/inference | Not run; `G-Core` remains blocked |

Recheck 2026-09-24: PowerShell parser over `scripts/*.ps1` and
`Check-Environment.ps1 -RequireRuntime` both passed again. A separate
`python -m pip check` reports `mkl-fft 1.3.10 requires mkl, which is not
installed`, while `conda list -n topic16-ns115 mkl` confirms Conda MKL
`2023.2.0` is installed. This is a pip/Conda metadata mismatch to record, not
evidence of a failing CUDA or native CLI check; do not mark training PASS from
this observation. The `requirements.txt` snapshot is Git ignored and is not a
cross-machine installer/lockfile.

The previous wrong Visual Studio component ID in `Install-HostTools.ps1` was fixed.
The installer log also showed canceled channel-feed requests, but a later
read-only `curl.exe --head --location` check reached the manifest with HTTP 200.
The corrected install then succeeded. The first runtime setup stopped only at
its final multiline `python -c` validation: Conda on Windows cannot wrap a
newline-containing argument. Validation is now a single-line command in
`Test-Runtime.ps1` and is reused by `Check-Environment.ps1 -RequireRuntime`.

A deeper CLI check found two mixed-channel Windows package defects: COLMAP's
Conda GPU build omitted its `mpir.dll` dependency; FFmpeg loaded an overlapping
`intl-8.dll` from defaults `libglib` instead of conda-forge `libintl`.
`configs/project.psd1` now pins the tested MPIR, FFmpeg, conda-forge libglib and
libintl builds; `Setup-Runtime.ps1` installs them without downgrading PyTorch or
NumPy. Open a **normal** Windows PowerShell at the project root and verify:

```powershell
.\scripts\Setup-Runtime.ps1 -RepairNativeTools
.\scripts\Test-Runtime.ps1
.\scripts\Check-Environment.ps1 -RequireRuntime
.\scripts\Setup-Project.ps1 -FinalizeOnly
```

`Setup-Project.ps1 -FinalizeOnly` reuses the completed datasets and refreshes
`artifacts/logs/runtime/requirements.txt` without rebuilding `tinycudann`.
Training, inference, paired benchmarks and `G-Core` remain unverified.
Do not delete `data\.cache\360_v2.zip`. Dataset and generated artifacts remain
Git ignored.

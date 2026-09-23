# Local setup audit — 2026-09-23

This is the observed state of the target laptop. Both dataset profiles are ready;
the training runtime is not. Reproducible commands are in `setup_full_command.md`.

| Check | Observed result |
|---|---|
| Windows PowerShell | 5.1.26100.9444 |
| GPU | NVIDIA RTX A4500 Laptop GPU, 16,384 MiB, compute capability 8.6 |
| NVIDIA driver | 597.06 |
| Workspace free space | About 236 GiB at preflight; dataset downloads completed on D: |
| Git/Conda | Available; `topic16-ns115` Conda environment created |
| Nerfstudio source | Exact v1.1.5 commit `6b60855003011b2ca23c2fe3f8e2ca6314c69924` checked out under ignored `third_party/` |
| Visual Studio | C++ toolset 14.44 present; required v142/14.29 component absent |
| CUDA/COLMAP/Nerfstudio Python packages | Not validated; MSVC v142 gate prevents finishing runtime |
| Poster smoke data | Official pinned Hugging Face source downloaded under `data/raw/nerfstudio/poster`; its 226-frame metadata was filtered to the 100 available image pairs under `data/processed/nerfstudio/poster`. All processed frame paths validated. |
| Mip-NeRF 360 | Official 12,535,427,936-byte archive downloaded to `data/.cache/360_v2.zip`; `garden` (185 images), `bonsai` (292), and `room` (311) extracted under `data/raw/mipnerf360`, each with `sparse/0/cameras.bin` |
| Dataset command | `scripts/Download-Datasets.ps1 -Mode all` rerun succeeded without re-download |
| Training/inference | Not run; `G-Core` remains blocked |

The non-elevated PowerShell session cannot add the missing Visual Studio component.
Open Windows PowerShell as administrator, run `scripts\Install-HostTools.ps1
-InstallBuildTools`, then reopen a normal PowerShell at the project root:

```powershell
.\scripts\Check-Environment.ps1
.\scripts\Setup-Project.ps1
.\scripts\Check-Environment.ps1 -RequireRuntime
```

`Setup-Project.ps1` will reuse the completed datasets, finish the isolated
environment, and export `artifacts/logs/runtime/requirements.txt` when its GPU
validation passes. Until then, training, inference, and `G-Core` remain unverified.
Do not delete `data\.cache\360_v2.zip`. Dataset and generated artifacts remain
Git ignored.

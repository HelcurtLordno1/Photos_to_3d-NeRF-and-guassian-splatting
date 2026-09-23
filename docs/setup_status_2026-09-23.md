# Local setup audit — 2026-09-23

This is the observed state of the target laptop, not a claim that the runtime or
datasets are ready. The reproducible commands are in `setup_full_command.md`.

| Check | Observed result |
|---|---|
| Windows PowerShell | 5.1.26100.9444 |
| GPU | NVIDIA RTX A4500 Laptop GPU, 16,384 MiB, compute capability 8.6 |
| NVIDIA driver | 597.06 |
| Workspace free space | About 236 GiB at preflight |
| Git/Conda | Available; `topic16-ns115` Conda environment created |
| Nerfstudio source | Exact v1.1.5 commit `6b60855003011b2ca23c2fe3f8e2ca6314c69924` checked out under ignored `third_party/` |
| Visual Studio | C++ toolset 14.44 present; required v142/14.29 component absent |
| CUDA/COLMAP/Nerfstudio Python packages | Not validated; large Conda download was interrupted after network throughput stalled |
| Poster smoke data | Not downloaded; requires finished runtime for `ns-download-data` |
| Mip-NeRF 360 | Official 12.5 GB archive download attempted; partial cache retained for resume |
| Training/inference | Not run; `G-Core` remains blocked |

The non-elevated PowerShell session cannot add the missing Visual Studio component.
Open Windows PowerShell as administrator, run `scripts\Install-HostTools.ps1
-InstallBuildTools`, then reopen a normal PowerShell at the project root:

```powershell
.\scripts\Check-Environment.ps1
.\scripts\Setup-Runtime.ps1
.\scripts\Check-Environment.ps1 -RequireRuntime
.\scripts\Download-Datasets.ps1 -Mode smoke
.\scripts\Download-Datasets.ps1 -Mode benchmark
```

The benchmark command resumes the existing archive. Do not delete
`data\.cache\360_v2.zip`. Dataset and generated artifacts remain Git ignored.

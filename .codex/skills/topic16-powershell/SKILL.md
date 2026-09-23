---
name: topic16-powershell
description: Build, debug, or operate the Topic 16 Nerfacto-vs-Splatfacto repository using its native Windows PowerShell pipeline, dataset contracts, laptop GPU guardrails, and core-before-production gates. Use for implementation, setup, data, training, inference, benchmark, or production work in this repository.
---

# Topic 16 PowerShell Pipeline

Read `Construction_architect.md` and `Modular_construct.md` at the repository root
before changing architecture or execution flow. Use `setup_full_command.md` for the
current commands.

## Invariants

- Use native Windows PowerShell entrypoints (`.ps1`) and PowerShell data files
  (`.psd1`) only. Do not add Bash scripts, Make targets, WSL commands or `/mnt/*`
  runtime paths.
- Derive paths from `$PSScriptRoot`; pass native commands argument arrays so spaces
  and Unicode paths remain safe.
- Keep dependency/dataset/protocol pins only in `configs/project.psd1`. Run tools
  through the project wrappers or `conda run -n topic16-ns115`; do not require
  users to manage an activated shell.
- Preserve raw data, processed pose/split, run and artifact contracts. Both methods
  must consume the same frozen cameras, split and downscale.
- Keep training (`Train.ps1`) separate from inference/evaluation
  (`Evaluate-Run.ps1`). Evaluate the exact generated `config.yml`.
- Target one RTX A4500 Laptop GPU with 16 GB: default downscale 2, sequential jobs,
  no viewer during timed runs. A low-memory change is a separately named paired
  protocol, never a hidden one-method override.
- Do not build production code until `G-Core` in `Modular_construct.md` passes.

## Validation

Parse every changed PowerShell file, run `scripts\Check-Environment.ps1` for host
changes, and use `-RequireRuntime` only when the runtime is expected to exist.
Dataset and setup operations must remain resumable/idempotent and must not delete
user data or prior artifacts.

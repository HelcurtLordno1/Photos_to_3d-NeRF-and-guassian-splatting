# Measured results — diagnostic

| Scene | Method | Steps | PSNR ↑ | SSIM ↑ | LPIPS ↓ | Train s | VRAM MiB | Checkpoint bytes | FPS ↑ | Run |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| bonsai | nerfacto | 100 | 18.1974 | 0.5894 | 0.7201 | 20.66 | 2828 | 176063414 |  | `bonsai/nerfacto/20260930T131202856Z` |
| bonsai | splatfacto | 100 | 18.0743 | 0.6449 | 0.5900 | 21.11 | 3951 | 156183438 |  | `bonsai/splatfacto/20260930T131621149Z` |
| poster | nerfacto | 100 | 18.7516 | 0.7456 | 0.6172 | 13.28 | 2772 | 175986806 | 0.8850536563779254 | `poster/nerfacto/20260930T125546831Z` |
| poster | splatfacto | 100 | 16.6175 | 0.7662 | 0.7134 | 10.55 | 2343 | 19088910 | 272.8068254870285 | `poster/splatfacto/20260930T125630450Z` |

Poster is a gate only. Custom results form a separate scene group. Empty FPS means no paired synchronized measurement.

Limitations: one laptop, one primary seed, Windows runtime, 10-second VRAM sampling, different batch semantics. No cross-hardware/general-method claim follows from these observations. Figures use identical held-out camera/crop; manual failure interpretation is required.

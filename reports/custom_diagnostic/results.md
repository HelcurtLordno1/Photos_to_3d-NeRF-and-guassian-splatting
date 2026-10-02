# Measured results — diagnostic

| Scene | Method | Steps | PSNR ↑ | SSIM ↑ | LPIPS ↓ | Train s | VRAM MiB | Checkpoint bytes | FPS ↑ | Run |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| custom:tea_sets_2 | nerfacto | 100 | 18.9146 | 0.6124 | 0.6687 | 15.66 | 2924 | 176008702 |  | `custom-tea_sets_2/nerfacto/20260930T163635661Z` |
| custom:tea_sets_2 | splatfacto | 100 | 18.2013 | 0.6428 | 0.6950 | 10.35 | 2286 | 22082722 |  | `custom-tea_sets_2/splatfacto/20260930T164151196Z` |

Poster is a gate only. Custom results form a separate scene group. Empty FPS means no paired synchronized measurement.

Limitations: one laptop, one primary seed, Windows runtime, 10-second VRAM sampling, different batch semantics. No cross-hardware/general-method claim follows from these observations. Figures use identical held-out camera/crop; manual failure interpretation is required.

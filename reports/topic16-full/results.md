# Measured results — primary

| Scene | Method | Steps | PSNR ↑ | SSIM ↑ | LPIPS ↓ | Train s | VRAM MiB | Checkpoint bytes | FPS ↑ | Run |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| bonsai | nerfacto | 30000 | 20.5936 | 0.6183 | 0.2103 | 2884.53 | 6022 | 176077054 | 0.17996086649790757 | `bonsai/nerfacto/20261001T014957052Z` |
| bonsai | splatfacto | 30000 | 31.5059 | 0.9381 | 0.1324 | 3311.24 | 5572 | 321490662 | 47.3592200253078 | `bonsai/splatfacto/20261001T022329468Z` |
| custom:tea_sets_2 | nerfacto | 30000 | 21.7555 | 0.6255 | 0.1268 | 2919.51 | 5904 | 176008702 | 1.6071736746980196 | `custom-tea_sets_2/nerfacto/20261001T151914364Z` |
| custom:tea_sets_2 | splatfacto | 30000 | 30.4557 | 0.9013 | 0.0737 | 1377.50 | 3410 | 187827942 | 120.15520848666603 | `custom-tea_sets_2/splatfacto/20261001T153020900Z` |
| garden | nerfacto | 30000 | 21.4435 | 0.4994 | 0.4255 | 4459.16 | 6975 | 176034238 | 0.06677696994146719 | `garden/nerfacto/20261001T032052797Z` |
| garden | splatfacto | 30000 | 26.2415 | 0.7937 | 0.1848 | 8631.01 | 10520 | 1205666150 | 20.598258096835345 | `garden/splatfacto/20261001T044422289Z` |
| room | nerfacto | 30000 | 22.9068 | 0.7385 | 0.2821 | 3417.23 | 7826 | 176084926 | 0.18816274425470092 | `room/nerfacto/20261001T071118206Z` |
| room | splatfacto | 30000 | 31.6652 | 0.9224 | 0.1627 | 3631.30 | 6123 | 398871270 | 44.063275767875076 | `room/splatfacto/20261001T081439786Z` |

Poster is a gate only. Custom results form a separate scene group. Empty FPS means no paired synchronized measurement.

Limitations: one laptop, one primary seed, Windows runtime, 10-second VRAM sampling, different batch semantics. No cross-hardware/general-method claim follows from these observations. Figures use identical held-out camera/crop; manual failure interpretation is required.

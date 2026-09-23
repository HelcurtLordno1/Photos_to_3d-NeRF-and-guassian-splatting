# Third-party source snapshots

Không commit source của upstream vào repository này. Chạy:

```powershell
.\scripts\Download-Repositories.ps1 -Mode runtime   # Nerfstudio runtime
.\scripts\Download-Repositories.ps1 -Mode research  # paper code để đối chiếu
```

Mọi commit được pin trong `configs/project.psd1`. `nerfstudio` là runtime duy nhất;
các repo còn lại không được trộn dependency vào cùng environment.

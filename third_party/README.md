# Third-party source snapshots

Không commit source của upstream vào repository này. Chạy:

```bash
bash scripts/download_repos.sh runtime   # Nerfstudio dùng để chạy project
bash scripts/download_repos.sh research  # code paper chỉ để đọc/đối chiếu
```

Mọi commit được pin trong `configs/project.env`. `nerfstudio` là runtime duy nhất;
các repo còn lại không được trộn dependency vào cùng environment.

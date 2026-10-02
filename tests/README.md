# Tests

Chạy `scripts/Test-Project.ps1`: parse mọi PowerShell entrypoint; host/schema/data
negative fixtures; Python run/pair/eval/analysis/resume/path/hash và safety/video/
throughput tests. `-PythonExecutable python` dành cho CPU/Windows CI, không cần CUDA.

Safety tests dùng mock telemetry, không làm nóng máy. Test CPU không chứng minh
full GPU training, static-scene pose, demo quality hoặc independent replay.
`-RequireAnalyzer` enforce PSScriptAnalyzer; `-RequireRuntime` cần Administrator
và safety gate trước GPU smoke. Giữ test failure-mode có ý nghĩa; không copy upstream tests.

Managed-session acceptance thật nằm trong `artifacts/logs/sessions/` và
[implementation_status](../docs/implementation_status.md): training pause/resume
cả hai methods sau refinement, total budget; custom eval stop giữa cameras và
paired GT validation. `test_sessions.py` kiểm tra budget/stop/readonly loader/
tamper; ancestry cycles bị reject. Tmux interactive attach/detach kiểm chứng riêng.

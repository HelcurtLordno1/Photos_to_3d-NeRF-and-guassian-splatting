# tests\Test-ManifestContract.ps1
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== BẮT ĐẦU TEST JSON SCHEMA V2 (STRICT MODE) ===" -ForegroundColor Cyan

# 1. Run thành công chuẩn chỉ
$validSucceeded = @"
{
  "schema_version": "1.0",
  "run_key": "garden/nerfacto/20260927T145759000Z",
  "scene": "garden",
  "method": "nerfacto",
  "status": "succeeded",
  "started_at": "2026-09-27T14:00:00Z",
  "finished_at": "2026-09-27T15:00:00Z",
  "provenance": { "git_commit_sha": "a1b2c3d", "dataset_split_hash": "hash123" },
  "protocol": { "iterations": 30000, "downscale_factor": 2, "seed": 42 }
}
"@

# 2. Run thất bại nhưng khai báo đàng hoàng (chuẩn if/then)
$validFailed = @"
{
  "schema_version": "1.0",
  "run_key": "bonsai/splatfacto/20260927T145759000Z",
  "scene": "bonsai",
  "method": "splatfacto",
  "status": "failed",
  "failure_reason": "CUDA Out of Memory",
  "started_at": "2026-09-27T14:00:00Z",
  "finished_at": "2026-09-27T14:15:00Z",
  "provenance": { "git_commit_sha": "a1b2c3d", "dataset_split_hash": "hash123" },
  "protocol": { "iterations": 30000, "downscale_factor": 2, "seed": 42 }
}
"@

# 3. Kẻ lách luật: Thất bại nhưng giấu lỗi, nhét thêm key rác
$invalidRun = @"
{
  "schema_version": "1.0",
  "run_key": "room/nerfacto/20260927T145759000Z",
  "scene": "room",
  "method": "nerfacto",
  "status": "failed",
  "started_at": "2026-09-27T14:00:00Z",
  "rac_thai_cong_nghiep": "hack_he_thong",
  "provenance": { "git_commit_sha": "a1b2c3d", "dataset_split_hash": "hash123" },
  "protocol": { "iterations": 30000, "downscale_factor": 2, "seed": 42 }
}
"@

# Danh sách các trường được phép (để test additionalProperties: false)
$allowedKeys = @("schema_version", "run_key", "scene", "method", "status", "failure_reason", "started_at", "finished_at", "provenance", "hardware", "protocol", "execution_metrics", "artifacts")

function Validate-ManifestV2 ($jsonString, $testName) {
    Write-Host "`nĐang test: $testName" -ForegroundColor Yellow
    $obj = $jsonString | ConvertFrom-Json
    $errors = @()

    # 1. Test cấm thuộc tính lạ (additionalProperties: false)
    $obj.psobject.properties.name | ForEach-Object {
        if ($_ -notin $allowedKeys) { $errors += "LỖI: Phát hiện trường dữ liệu lạ không có trong hợp đồng ('$_')" }
    }

    # 2. Test điều kiện chéo if/then (allOf)
    if ($obj.status -eq 'failed') {
        if ([string]::IsNullOrWhiteSpace($obj.failure_reason)) { $errors += "LỖI CHÉO: Status là 'failed' nhưng giấu 'failure_reason'." }
        if ([string]::IsNullOrWhiteSpace($obj.finished_at)) { $errors += "LỖI CHÉO: Status là 'failed' nhưng không ghi nhận giờ kết thúc 'finished_at'." }
    }
    if ($obj.status -eq 'succeeded') {
        if ([string]::IsNullOrWhiteSpace($obj.finished_at)) { $errors += "LỖI CHÉO: Status là 'succeeded' nhưng không ghi nhận giờ hoàn thành 'finished_at'." }
    }

    # 3. Test Provenance bọc thép
    if ($null -eq $obj.provenance.dataset_split_hash) { $errors += "LỖI BẮT BUỘC: Không tìm thấy dataset_split_hash. Nghi ngờ rò rỉ dữ liệu (Data Leakage)!" }

    if ($errors.Count -eq 0) {
        Write-Host " => PASS: Hồ sơ hợp lệ, qua ải!" -ForegroundColor Green
    } else {
        Write-Host " => FAIL: Hồ sơ bị bác bỏ vì vi phạm:" -ForegroundColor Red
        $errors | ForEach-Object { Write-Host "    - $_" -ForegroundColor Red }
    }
}

# Chạy Test Fixtures
Validate-ManifestV2 $validSucceeded "Case 1: Run Succeeded (Hoàn hảo)"
Validate-ManifestV2 $validFailed "Case 2: Run Failed (Khai báo lỗi đàng hoàng)"
Validate-ManifestV2 $invalidRun "Case 3: Kẻ lách luật (Giấu lỗi + Nhét rác)"
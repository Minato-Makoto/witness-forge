<# 
  Kiểm tra nhanh môi trường Windows 11 + CUDA + WSL cho Witness Forge.
  Chạy: powershell -ExecutionPolicy Bypass -File scripts/setup_win_deps.ps1
#>

Write-Host "=== Witness Forge Windows setup ==="

Write-Host "`n[1] Kiểm tra phiên bản Windows & GPU"
Get-ComputerInfo -Property OsName, OsVersion | Format-Table
try {
    & nvidia-smi | Select-String "Driver Version"
} catch {
    Write-Warning "Không tìm thấy nvidia-smi. Cài driver NVIDIA mới nhất trước."
}

Write-Host "`n[2] Kiểm tra WSL"
if ((wsl --status) -match "Default Distribution") {
    Write-Host "WSL sẵn sàng."
} else {
    Write-Warning "Chưa bật WSL2. Chạy 'wsl --install' rồi reboot."
}

Write-Host "`n[3] Chuẩn bị Python môi trường ảo"
if (-not (Test-Path .venv)) {
    Write-Host "Tạo .venv ..."
    python -m venv .venv
}
Write-Host "Cài đặt phụ thuộc cốt lõi..."
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Write-Host "Nếu cần LoRA/bitsandbytes: .\.venv\Scripts\python.exe -m pip install .[lora]"

Write-Host "`nHoàn tất. Sử dụng 'run_witness.bat' hoặc 'python -m witness_forge chat' để chạy."

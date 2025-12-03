#!/usr/bin/env bash
set -euo pipefail

echo "=== Witness Forge WSL2 Setup ==="
if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "[warn] nvidia-smi không khả dụng trong WSL. Đảm bảo bật GPU passthrough (driver >= 535)."
fi

sudo apt update
sudo apt install -y python3 python3-venv python3-pip build-essential

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "Nếu cần LoRA/QLoRA: pip install .[lora]"

cat <<'EOF'
Gợi ý:
- Xuất CUDA: export LD_LIBRARY_PATH=/usr/lib/wsl/lib:$LD_LIBRARY_PATH
- Nếu bitsandbytes báo lỗi, thử `pip install bitsandbytes` và chạy lại Witness Forge.
- Chạy smoke test: python scripts/smoke_test.py
EOF

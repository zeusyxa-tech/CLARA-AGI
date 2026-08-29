#!/usr/bin/env bash
# Chạy CLARA-AGI ở chế độ tự học + tự nâng cấp tự động
# Linux/macOS
cd "$(dirname "$0")"
echo "🧬 Khởi động CLARA-AGI ở chế độ autopilot..."
echo "   Tự học + tự nghiên cứu web đã bật."
echo "   Nhấn Ctrl+C để dừng."
python3 main.py --auto-learn --self-improve "$@"

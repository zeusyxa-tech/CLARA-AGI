#!/usr/bin/env bash
# Chạy giao diện web + tự học khi rảnh
cd "$(dirname "$0")"
pip install flask -q 2>/dev/null
python3 main.py --web --auto-learn "$@"

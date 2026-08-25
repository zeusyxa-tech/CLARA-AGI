#!/usr/bin/env bash
# Chạy CLARA với giao diện web đẹp
cd "$(dirname "$0")"
pip install flask -q 2>/dev/null
python3 main.py --web "$@"

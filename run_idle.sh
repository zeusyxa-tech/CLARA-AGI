#!/usr/bin/env bash
# Chạy CLARA với chế độ TỰ HỌC KHI RẢNH — để mở treo cả ngày là nó tự học
cd "$(dirname "$0")"
echo "🧬 Khởi động CLARA-AGI với tự học nền..."
echo "   (bạn có thể để mở cửa sổ này cả ngày, CLARA sẽ tự suy nghĩ khi bạn không nói)"
echo ""
python3 main.py --auto-learn "$@"

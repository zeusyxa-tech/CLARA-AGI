#!/usr/bin/env bash
# Script tự cài Ollama + model phù hợp cho CLARA-AGI (Linux/macOS)
set -e
echo "🧬 CLARA-AGI — Trình cài đặt tự động Ollama"
echo "============================================="

if command -v ollama >/dev/null 2>&1; then
    echo "✅ Ollama đã có: $(ollama --version)"
else
    echo "📥 Đang cài Ollama..."
    if [ "$(uname -s)" = "Darwin" ]; then
        echo "⚠️  macOS: hãy tải Ollama thủ công từ https://ollama.com/download"
        echo "   Sau khi cài, chạy lại script này để pull model."
        open https://ollama.com/download 2>/dev/null || true
        exit 0
    else
        curl -fsSL https://ollama.com/install.sh | sh
    fi
fi

echo ""
echo "ℹ️  Các model phù hợp theo cấu hình máy:"
echo "   • qwen2.5:0.5b   ~350MB  — máy RẤT YẾU (4GB RAM, CPU cũ)"
echo "   • qwen2.5:1.5b   ~900MB  — máy vừa (6-8GB RAM) — khuyến nghị"
echo "   • qwen2.5:3b     ~1.9GB  — máy khá (8GB+ RAM)"
echo ""
read -p "Bạn muốn cài model nào? [1.5b] " MODEL
MODEL=${MODEL:-1.5b}
case "$MODEL" in
    0.5b|nho|tiny)  MODEL_NAME="qwen2.5:0.5b" ;;
    3b|lon|large)   MODEL_NAME="qwen2.5:3b" ;;
    *)              MODEL_NAME="qwen2.5:1.5b" ;;
esac

echo "📥 Đang pull model $MODEL_NAME (có thể mất vài phút)..."
ollama pull "$MODEL_NAME"

echo ""
echo "✅ Xong! Bạn có thể chạy CLARA:"
echo "   ./run.sh              # tự nhận Ollama"
echo "   ./run.sh --web        # mở giao diện web"
echo "   ./run.sh --model $MODEL_NAME   # chỉ định model"

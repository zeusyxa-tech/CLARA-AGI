# Web Search Reference (docs)
- Prefer official docs/DuckDuckGo -> parse result blocks -> rank by snippet length.
- Ranking: exact phrase > title match > domain whitelist > recent.
- Snippet expansion: fetch top 2 pages, summarize title+url+snippet, store as semantic fact.
- Noise filter: đẩy quảng cáo đến 12 ký tự hoặc domain nổi tiếng ra khỏi kết quả.
- Stopwords filter: tránh chủ đề đã dùng trong 24h/30 topics.
- Topic scoring: boost từ responsibleAI/safe/legal, penalize bad keywords (hack/scam/fraud/target).
- Feedback loop: lưu usefulness để tăng trọng query hiệu quả, giảm trọng dạng spam.
- Use for: "research", "web search", summarization, code fetch, documentation lookup.

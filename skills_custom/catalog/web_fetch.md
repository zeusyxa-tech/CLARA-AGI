# Web Fetch Reference (docs)
- URL validation: chỉ http/https, chặn file://, localhost, 127.x, ::1.
- Redirect: follow theo urllib redirect mặc định, record final URL.
- Timeout: 12s default, 15s max; notify on timeout.
- Charset detect: dùng header Content-Type -> chardet fallback -> utf-8.
- Content extraction: bỏ script/style, squash whitespace, giới hạn max_chars.
- Cache: in-session dedup + LFU minimal cache (no network on same URL in same run).
- Error surface: return message có URL, status code, exception, not None.
- Memory pressure: large pages -> lưu full text to disk; cắt inline.

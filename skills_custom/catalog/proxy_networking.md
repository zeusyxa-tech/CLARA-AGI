# Proxy Networking Reference (docs)
Kerruyệt HTTP proxy, retry, caching nâng cao.
- Proxy env: HTTPS_PROXY, HTTP_PROXY, NO_PROXY cho home/internal/CAPTCHA sites.
- Session reuse: dùng session nhận gọn nhẹ cho multi-request.
- Retries: exponential backoff 1..30s, cap retry theo 403/429/500.
- Rate-limit: 1 req/s đối với public web; giảm 2x khi bị 429.
- Headers: native browser UA, accept-language vi/en.
- Chunked: giới hạn body, đọc nếu cần decode utf-8 with replace.
- Termination: timeout per-request 20s; nếu proxy chậm -> fail fast.
- Privacy: không log secret header values; không cache credentials.

# Web Scraping Reference Skill (docs)
- Polite crawling: respect robots.txt, add delays >=1s between requests.
- Header rotation: chọn UA phổ biến, không gửi nhiều request cùng UA liên tiếp.
- Rate limit: max 1 req/s, backoff on 429, exponential backoff 2..30s.
- Dedup: content hash + URL dedup ngay trong phiên.
- HTML -> text: strip script/style/noscript, collapse whitespace.
- Link normalization: resolve relative -> absolute, lowercase host/path.
- Parser strategy: use minimal regex/HTMLParser if BeautifulSoup unavailable.
- Data shape: rows -> list[dict], schema validation after extraction.
- Respect privacy: do not collect email/phone unless explicitly instructed.
- Error tolerance: skip bad pages, continue harvest, record failure count.

CLARA màu xanh: chỉ scrape trang KHÔNG CẤM, không tự host reproduction.

"""
CLARA-AGI - Web tools: tự tìm kiếm internet, đọc trang web.
Không cần API key — dùng DuckDuckGo HTML search + urllib, hoàn toàn miễn phí.
"""
import re, json, urllib.request, urllib.parse, html as html_mod
from html.parser import HTMLParser

_NETWORK_ALLOWED = False


def allow_network(enabled: bool):
    global _NETWORK_ALLOWED
    _NETWORK_ALLOWED = bool(enabled)


def _check_network():
    if not _NETWORK_ALLOWED:
        return {"error": "Mạng đã tắt: bật --allow-network để sử dụng web research."}
    return None


USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


class _TextExtractor(HTMLParser):
    """Trích text thô từ HTML, bỏ script/style."""
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip > 0:
            self.skip -= 1
    def handle_data(self, data):
        if self.skip == 0:
            t = data.strip()
            if t: self.parts.append(t)
    def get_text(self):
        return " ".join(self.parts)


def _request(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "vi,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace"), r.headers.get_content_charset() or "utf-8"


def web_search(query, max_results=5):
    """Tìm kiếm DuckDuckGo, trả về list {title, url, snippet}."""
    err = _check_network()
    if err:
        return [err]
    try:
        q = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={q}"
        html, _ = _request(url, timeout=12)
    except Exception as e:
        return [{"error": f"Không tìm được: {e}"}]

    results = []
    # Phân tích kết quả từ HTML DDG
    blocks = re.findall(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        html, re.S
    )
    for href, title, snippet in blocks[:max_results]:
        # giải mã uddg redirect
        m = re.search(r"uddg=([^&]+)", href)
        real_url = urllib.parse.unquote(m.group(1)) if m else href
        title = re.sub(r"<.*?>", "", title).strip()
        snippet = re.sub(r"<.*?>", "", snippet).strip()
        title = html_mod.unescape(title)
        snippet = html_mod.unescape(snippet)
        bad_domains = ["udemy.com", "ebay.com", "amazon.com", "courses.", "shop."]
        if any(b in (real_url + title + snippet).lower() for b in bad_domains):
            continue
        if len(snippet) < 12 or any(k in title.lower() for k in ["official site", "sold direct", "bootcamp"]):
            continue
        results.append({"title": title, "url": real_url, "snippet": snippet})
    if not results:
        return [{"error": "Không có kết quả."}]
    return results


def web_fetch(url, max_chars=4000):
    """Đọc nội dung 1 trang web, trả về text thô (bỏ HTML)."""
    err = _check_network()
    if err:
        return err["error"]
    # chặn file:// và nội bộ
    if url.startswith("file:") or url.startswith("localhost") or url.startswith("127."):
        return "❌ Không cho phép truy cập nội bộ."
    try:
        if not url.startswith("http"):
            url = "https://" + url
        html, _ = _request(url, timeout=12)
        parser = _TextExtractor()
        parser.feed(html)
        text = parser.get_text()
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > max_chars:
            text = text[:max_chars] + f"...(còn {len(text)-max_chars} ký tự)"
        return text
    except Exception as e:
        return f"❌ Không đọc được {url}: {e}"


def search_and_summarize(agi, query, max_pages=2):
    """Tìm kiếm, đọc trang đầu, tóm tắt và học."""
    results = web_search(query, max_results=max_pages + 1)
    if results and "error" in results[0]:
        return results[0]["error"]
    bits = []
    for r in results[:max_pages]:
        content = web_fetch(r["url"], max_chars=2000)
        bits.append(f"[{r['title']}] ({r['url']})\n{r['snippet']}\n{content[:500]}")
        # học fact từ snippet
        if len(r["snippet"]) > 15:
            agi.mem.learn(f"web::{query[:30]}",
                          f"{r['title']}: {r['snippet']} (nguồn: {r['url']})",
                          confidence=0.55, source="web_search")
    return "\n\n---\n\n".join(bits)

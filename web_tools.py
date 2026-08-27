"""
CLARA-AGI - Web tools: tự tìm kiếm internet, đọc trang web.
Không cần API key — dùng DuckDuckGo HTML search + urllib, hoàn toàn miễn phí.
Nâng cấp: BeautifulSoup parser, retry/backoff, rate limiting, structured logging.
"""
import re
import json
import time
import urllib.request
import urllib.parse
import urllib.error
import html as html_mod
from html.parser import HTMLParser
from typing import List, Dict, Optional, Tuple
from config import get_config

# Try import BeautifulSoup, fallback to built-in HTMLParser
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    from html.parser import HTMLParser


# Load config
_web_cfg = get_config("web")
USER_AGENT = _web_cfg.get("user_agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")
FETCH_TIMEOUT = _web_cfg.get("fetch_timeout", 15)
MAX_RESULTS = _web_cfg.get("max_results", 5)
RETRY_ATTEMPTS = _web_cfg.get("retry_attempts", 3)
RETRY_BACKOFF_BASE = _web_cfg.get("retry_backoff_base", 2.0)
RETRY_MAX_BACKOFF = _web_cfg.get("retry_max_backoff", 30.0)
RATE_LIMIT_DELAY = _web_cfg.get("rate_limit_delay", 1.0)

_last_request_time = 0.0


class _TextExtractor(HTMLParser):
    """Trích text thô từ HTML, bỏ script/style (fallback khi không có BeautifulSoup)."""
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


def _rate_limit():
    """Enforce minimum delay between requests."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < RATE_LIMIT_DELAY:
        time.sleep(RATE_LIMIT_DELAY - elapsed)
    _last_request_time = time.time()


def _request_with_retry(url: str, timeout: int = FETCH_TIMEOUT) -> Tuple[str, str]:
    """
    HTTP request with exponential backoff retry.
    Returns (content, charset).
    """
    last_error = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            _rate_limit()
            req = urllib.request.Request(
                url,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "vi,en;q=0.9"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                content = r.read().decode("utf-8", errors="replace")
                charset = r.headers.get_content_charset() or "utf-8"
                return content, charset
        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code}: {e.reason}"
            if e.code in (429, 500, 502, 503, 504):
                # Retryable status codes
                pass
            else:
                # Non-retryable
                break
        except urllib.error.URLError as e:
            last_error = f"URL Error: {e.reason}"
        except Exception as e:
            last_error = f"Error: {type(e).__name__}: {e}"
        
        # Calculate backoff
        if attempt < RETRY_ATTEMPTS - 1:
            backoff = min(RETRY_BACKOFF_BASE ** attempt, RETRY_MAX_BACKOFF)
            time.sleep(backoff)
    
    raise Exception(f"Request failed after {RETRY_ATTEMPTS} attempts: {last_error}")


def _parse_ddg_results(html: str) -> List[Dict]:
    """Parse DuckDuckGo HTML results - works with or without BeautifulSoup."""
    results = []
    
    if HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        # Multiple selector strategies for resilience
        selectors = [
            "a.result__a",
            "a.result__snippet",
            ".result__title",
            ".result__snippet",
            "[class*='result'] a",
        ]
        
        # Primary: find result containers
        for link in soup.select("a.result__a"):
            try:
                title = link.get_text(strip=True)
                href = link.get("href", "")
                
                # Find associated snippet
                container = link.find_parent(class_=re.compile(r"result"))
                snippet = ""
                if container:
                    snip_elem = container.select_one("a.result__snippet, .result__snippet, [class*='snippet']")
                    if snip_elem:
                        snippet = snip_elem.get_text(strip=True)
                
                # Decode DDG redirect
                m = re.search(r"uddg=([^&]+)", href)
                real_url = urllib.parse.unquote(m.group(1)) if m else href
                
                # Clean
                title = html_mod.unescape(title)
                snippet = html_mod.unescape(snippet)
                
                # Filter
                bad_domains = ["udemy.com", "ebay.com", "amazon.com", "courses.", "shop."]
                if any(b in (real_url + title + snippet).lower() for b in bad_domains):
                    continue
                if len(snippet) < 12 or any(k in title.lower() for k in ["official site", "sold direct", "bootcamp"]):
                    continue
                    
                results.append({"title": title, "url": real_url, "snippet": snippet})
            except Exception:
                continue
    else:
        # Fallback: regex (original implementation)
        blocks = re.findall(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
            html, re.S
        )
        for href, title, snippet in blocks:
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
    
    return results[:MAX_RESULTS]


def web_search(query: str, max_results: int = MAX_RESULTS) -> List[Dict]:
    """Tìm kiếm DuckDuckGo, trả về list {title, url, snippet}."""
    try:
        q = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={q}"
        html, _ = _request_with_retry(url, timeout=FETCH_TIMEOUT)
    except Exception as e:
        return [{"error": f"Không tìm được: {e}"}]
    
    results = _parse_ddg_results(html)
    
    if not results:
        return [{"error": "Không có kết quả."}]
    return results


def _extract_text_from_html(html: str) -> str:
    """Extract clean text from HTML."""
    if HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        # Remove script/style
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
    else:
        parser = _TextExtractor()
        parser.feed(html)
        text = parser.get_text()
    
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def web_fetch(url: str, max_chars: int = 4000) -> str:
    """Đọc nội dung 1 trang web, trả về text thô (bỏ HTML)."""
    # chặn file:// và nội bộ
    if url.startswith("file:") or url.startswith("localhost") or url.startswith("127."):
        return "❌ Không cho phép truy cập nội bộ."
    try:
        if not url.startswith("http"):
            url = "https://" + url
        html, _ = _request_with_retry(url, timeout=FETCH_TIMEOUT)
        text = _extract_text_from_html(html)
        if len(text) > max_chars:
            text = text[:max_chars] + f"...(còn {len(text)-max_chars} ký tự)"
        return text
    except Exception as e:
        return f"❌ Không đọc được {url}: {e}"


def search_and_summarize(agi, query: str, max_pages: int = 2) -> str:
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
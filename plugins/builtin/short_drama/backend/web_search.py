"""Auditable, dependency-free web search for the local assistant."""

from __future__ import annotations

import html
import ipaddress
import json
import os
import re
import socket
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


class WebSearchError(RuntimeError):
    pass


_CACHE_LOCK = threading.Lock()
_CACHE_FILE = os.path.abspath(os.environ.get("SHORT_DRAMA_WEB_SEARCH_CACHE", os.path.join(os.path.dirname(__file__), "../../../../output/narrative-cache/web-search-cache.json")))
_CACHE_TTL_SECONDS = max(60, int(os.environ.get("SHORT_DRAMA_WEB_SEARCH_CACHE_TTL_SECONDS", "21600")))


def _cache_key(query: str, count: int) -> str:
    return f"{query.strip().lower()}::{count}"


def _load_cache() -> dict:
    try:
        with open(_CACHE_FILE, "r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_cache(cache: dict) -> None:
    directory = os.path.dirname(_CACHE_FILE)
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".web-search-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(cache, handle, ensure_ascii=False, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, _CACHE_FILE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _remember_success(query: str, count: int, payload: dict) -> None:
    with _CACHE_LOCK:
        cache = _load_cache()
        cache[_cache_key(query, count)] = {"cached_at":time.time(),"payload":payload}
        _write_cache(cache)


def _cached_success(query: str, count: int, attempts: list[dict]) -> dict | None:
    with _CACHE_LOCK:
        entry = _load_cache().get(_cache_key(query, count), {})
    if time.time() - float(entry.get("cached_at", 0)) > _CACHE_TTL_SECONDS:
        return None
    payload = dict(entry.get("payload") or {})
    results = []
    for item in list(payload.get("results") or []):
        try: _public_http_url(str(item.get("url", "")))
        except WebSearchError: continue
        if _result_is_relevant(query, item): results.append(item)
    if not results:
        return None
    payload.update({"provider_id":f"cache:{payload.get('provider_id', 'unknown')}","cache_hit":True,"cache_recovered_at":datetime.now(UTC).isoformat(),"live_attempts":attempts,"results":results[:count]})
    return payload


WEB_SEARCH_PROVIDERS = (
    {"id":"brave", "description":"Brave Search API（配置Key时优先）", "hosts":("api.search.brave.com",), "handler":"_brave", "required_env":"BRAVE_SEARCH_API_KEY"},
    {"id":"github-api", "description":"GitHub Repository Search API（开源项目后备）", "hosts":("api.github.com",), "handler":"_github", "required_env":""},
    {"id":"duckduckgo-html", "description":"DuckDuckGo HTML（免Key第一后备）", "hosts":("html.duckduckgo.com","duckduckgo.com"), "handler":"_duck", "required_env":""},
    {"id":"bing-html", "description":"Bing HTML（免Key第二后备）", "hosts":("www.bing.com","bing.com"), "handler":"_bing", "required_env":""},
    {"id":"google-news-rss", "description":"Google News RSS（时效信息后备）", "hosts":("news.google.com",), "handler":"_google_news", "required_env":""},
    {"id":"google-html", "description":"Google HTML（免Key第四后备）", "hosts":("www.google.com","google.com"), "handler":"_google", "required_env":""},
)
WEB_SEARCH_PROVIDER_DESCRIPTIONS = tuple(item["description"] for item in WEB_SEARCH_PROVIDERS)


class _DuckParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._link = False
        self._snippet = False
        self._current: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = values.get("class", "") or ""
        if tag == "a" and "result__a" in classes:
            self._link = True
            self._current = {"title": "", "url": _decode_duck_url(values.get("href", "") or ""), "snippet": ""}
        elif "result__snippet" in classes and self._current:
            self._snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._link:
            self._link = False
            if self._current and self._current["title"] and self._current["url"]:
                self.results.append(self._current)
        if self._snippet and tag in {"a", "div", "span"}:
            self._snippet = False

    def handle_data(self, data: str) -> None:
        if self._link and self._current:
            self._current["title"] += data.strip()
        elif self._snippet and self.results:
            self.results[-1]["snippet"] += data.strip() + " "


def _decode_duck_url(value: str) -> str:
    parsed = urlparse(html.unescape(value))
    redirected = parse_qs(parsed.query).get("uddg", [""])[0]
    return unquote(redirected) if redirected else html.unescape(value)


def _public_http_url(value: str, *, allow_managed_proxy: bool = False) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise WebSearchError("search_result_url_invalid")
    if allow_managed_proxy and parsed.hostname not in _SEARCH_PROVIDER_HOSTS:
        raise WebSearchError("managed_proxy_only_allowed_for_registered_provider")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))}
    except OSError as error:
        raise WebSearchError("search_result_host_unresolvable") from error
    for address in addresses:
        ip = ipaddress.ip_address(address)
        managed_proxy = allow_managed_proxy and ip in ipaddress.ip_network("198.18.0.0/15")
        if not allow_managed_proxy and ip in ipaddress.ip_network("198.18.0.0/15"):
            authoritative = _dns_over_https_addresses(parsed.hostname)
            if not authoritative or any(not ipaddress.ip_address(value).is_global for value in authoritative):
                raise WebSearchError("search_result_private_network_blocked")
            continue
        if not ip.is_global and not managed_proxy:
            raise WebSearchError("search_result_private_network_blocked")
    return value


_SEARCH_PROVIDER_HOSTS = {host for spec in WEB_SEARCH_PROVIDERS for host in spec["hosts"]}


def _validate_transport_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in _SEARCH_PROVIDER_HOSTS:
        raise WebSearchError("search_provider_url_rejected")
    _public_http_url(url, allow_managed_proxy=True)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _dns_over_https_addresses(hostname: str) -> set[str]:
    opener = build_opener(_NoRedirect)
    request = Request(f"https://dns.google/resolve?name={quote_plus(hostname)}&type=A", headers={"User-Agent":"AI-Agent-WebSearch/1.0","Accept":"application/json"})
    try:
        with opener.open(request, timeout=8) as response:
            if urlparse(response.geturl()).hostname != "dns.google":
                return set()
            payload = response.read(200_001)
            if len(payload) > 200_000:
                return set()
        return {str(item.get("data", "")) for item in json.loads(payload).get("Answer", []) if int(item.get("type", 0)) in {1, 28}}
    except Exception:
        return set()


def _request(url: str, *, headers: dict[str, str] | None = None, timeout: int = 12) -> bytes:
    # Some managed runtimes map public provider hosts into an RFC 2544 proxy range.
    # Pinning the exact provider host is safer and remains functional in that setup.
    _validate_transport_url(url)
    request_headers = {"User-Agent": "AI-Agent-WebSearch/1.0", "Accept": "application/json,text/html;q=0.9"}
    request_headers.update(headers or {})
    current = url
    opener = build_opener(_NoRedirect)
    try:
        for _ in range(4):
            _validate_transport_url(current)
            try:
                response = opener.open(Request(current, headers=request_headers), timeout=timeout)
            except HTTPError as redirect:
                if redirect.code not in {301, 302, 303, 307, 308}:
                    raise
                location = redirect.headers.get("Location", "")
                if not location:
                    raise WebSearchError("search_redirect_without_location")
                from urllib.parse import urljoin
                current = urljoin(current, location)
                _validate_transport_url(current)
                continue
            with response:
                _validate_transport_url(response.geturl())
                content_type = response.headers.get_content_type()
                if content_type not in {"application/json", "text/html", "text/plain", "application/rss+xml", "application/xml", "text/xml"}:
                    raise WebSearchError("search_response_content_type_rejected")
                payload = response.read(1_000_001)
                if len(payload) > 1_000_000:
                    raise WebSearchError("search_response_too_large")
                return payload
        raise WebSearchError("search_redirect_limit_exceeded")
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise WebSearchError(f"search_transport_failed:{type(error).__name__}") from error


def _brave(query: str, count: int, api_key: str) -> list[dict[str, str]]:
    payload = json.loads(_request(
        f"https://api.search.brave.com/res/v1/web/search?q={quote_plus(query)}&count={count}",
        headers={"X-Subscription-Token": api_key},
    ).decode("utf-8"))
    return [{"title": str(item.get("title", "")).strip(), "url": str(item.get("url", "")).strip(), "snippet": str(item.get("description", "")).strip()} for item in payload.get("web", {}).get("results", [])]


def _duck(query: str, count: int) -> list[dict[str, str]]:
    parser = _DuckParser()
    parser.feed(_request(f"https://html.duckduckgo.com/html/?q={quote_plus(query)}").decode("utf-8", "replace"))
    return parser.results[:count]


def _github(query: str, count: int) -> list[dict[str, str]]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9._+-]{2,}", query)
    github_generic = _GENERIC_QUERY_TERMS | {"text","image","generation","generative","model","models","weights","checkpoint","open-source","text-to-image","image-to-image","apple","silicon","local","inference","deployment","downloadable"}
    entities = [token for token in tokens if token.lower() not in github_generic]
    if not entities:
        return []
    compact = " ".join(entities)
    payload = json.loads(_request(f"https://api.github.com/search/repositories?q={quote_plus(compact or query)}&per_page={count}", headers={"Accept":"application/vnd.github+json"}).decode("utf-8"))
    return [{"title":str(item.get("full_name", "")),"url":str(item.get("html_url", "")),"snippet":str(item.get("description", "")),"repository_updated_at":str(item.get("updated_at", ""))} for item in payload.get("items", [])]


def _bing(query: str, count: int) -> list[dict[str, str]]:
    payload = _request(f"https://www.bing.com/search?format=rss&q={quote_plus(query)}&count={count}")
    root = ET.fromstring(payload)
    return [{"url":str(item.findtext("link") or ""),"title":str(item.findtext("title") or ""),"snippet":str(item.findtext("description") or "")} for item in root.findall("./channel/item")][:count]


def _google(query: str, count: int) -> list[dict[str, str]]:
    page = _request(f"https://www.google.com/search?q={quote_plus(query)}&num={count}").decode("utf-8", "replace")
    results = []
    for match in re.finditer(r'<a[^>]+href="(?:/url\?q=)?(https?://[^"&]+)[^"]*"[^>]*>.*?<h3[^>]*>(.*?)</h3>', page, re.I | re.S):
        url = html.unescape(match.group(1))
        title = html.unescape(re.sub(r'<[^>]+>', ' ', match.group(2)))
        results.append({"url":url,"title":title,"snippet":""})
    return results[:count]


def _google_news(query: str, count: int) -> list[dict[str, str]]:
    payload = _request(f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en")
    root = ET.fromstring(payload)
    clean = lambda value: html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    return [{"url":str(item.findtext("link") or ""),"title":str(item.findtext("title") or ""),"snippet":clean(item.findtext("description")),"published_at":str(item.findtext("pubDate") or "")} for item in root.findall("./channel/item")][:max(count * 3, count)]


_GENERIC_QUERY_TERMS = {"latest","recent","current","official","github","documentation","docs","source","open","which","what","release","commercial","license","today","2026"}


def _relevance_terms(query: str) -> set[str]:
    terms = {token for token in re.findall(r"[a-z0-9][a-z0-9.+_]{2,}", query.lower()) if token not in _GENERIC_QUERY_TERMS}
    return {"generat" if token.startswith("generat") else token for token in terms}


def _result_is_relevant(query: str, item: dict[str, str]) -> bool:
    terms = _relevance_terms(query)
    if not terms:
        return True
    haystack = " ".join((item.get("title", ""), item.get("url", ""), item.get("snippet", ""))).lower()
    if "image" in terms and "image" not in haystack:
        return False
    normalized_query = query.lower().replace("-", " ")
    requires_open_source = "open source" in normalized_query
    if requires_open_source and "open source" not in haystack.replace("-", " "):
        return False
    matches = sum(1 for term in terms if term in haystack)
    if "model" in terms or "models" in terms:
        model_evidence = bool(re.search(r"(?:\bmodels?\b|\bweights?\b|\bcheckpoint\b|\b[A-Z][A-Za-z0-9]*[-_.][A-Za-z0-9][A-Za-z0-9_.-]*\b)", " ".join((item.get("title", ""), item.get("snippet", "")))))
        if not model_evidence:
            return False
    return matches >= min(1 if requires_open_source else 2, len(terms))


def search_web(body: dict) -> dict:
    query = re.sub(r"\s+", " ", str(body.get("query", "")).strip())
    if not query:
        raise ValueError("search_query_required")
    count = max(1, min(8, int(body.get("count", 5))))
    attempts: list[dict[str, str]] = []
    for spec in WEB_SEARCH_PROVIDERS:
        required_env = str(spec["required_env"])
        secret = os.environ.get(required_env, "").strip() if required_env else ""
        if required_env and not secret:
            continue
        provider_id = str(spec["id"])
        for provider_attempt in range(2):
          try:
            handler = globals()[str(spec["handler"])]
            raw = handler(query, count, secret) if required_env else handler(query, count)
            results = []
            for item in raw:
                try:
                    url = _public_http_url(item["url"])
                except (KeyError, WebSearchError):
                    continue
                title = re.sub(r"\s+", " ", item.get("title", "")).strip()
                snippet = re.sub(r"\s+", " ", html.unescape(item.get("snippet", ""))).strip()
                if title and url and _result_is_relevant(query, {"title":title,"url":url,"snippet":snippet}):
                    results.append({"title":title[:300],"url":url,"snippet":snippet[:1200],**({"published_at":str(item.get("published_at"))} if item.get("published_at") else {}),**({"repository_updated_at":str(item.get("repository_updated_at"))} if item.get("repository_updated_at") else {})})
            if results:
                if any(item.get("published_at") for item in results):
                    def published_timestamp(item: dict[str, str]) -> float:
                        try: return parsedate_to_datetime(item.get("published_at", "")).timestamp()
                        except (TypeError, ValueError, OverflowError): return 0.0
                    results.sort(key=published_timestamp, reverse=True)
                payload = {"query":query,"provider_id":provider_id,"searched_at":datetime.now(UTC).isoformat(),"cache_hit":False,"results":results[:count],"attempts":attempts}
                _remember_success(query, count, payload)
                return payload
            attempts.append({"provider_id": provider_id, "attempt":provider_attempt + 1, "error": "no_results"})
          except Exception as error:
            attempts.append({"provider_id": provider_id, "attempt":provider_attempt + 1, "error": str(error)[:300]})
    cached = _cached_success(query, count, attempts)
    if cached:
        return cached
    raise WebSearchError("all_search_providers_failed:" + json.dumps(attempts, ensure_ascii=False))

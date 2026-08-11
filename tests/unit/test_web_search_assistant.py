import json
from io import BytesIO

import pytest

from plugins.builtin.short_drama.backend import web_search


@pytest.fixture(autouse=True)
def isolated_search_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(web_search, "_CACHE_FILE", str(tmp_path / "web-search-cache.json"))


def test_search_provider_falls_back_and_returns_auditable_sources(monkeypatch):
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "configured")
    monkeypatch.setattr(web_search, "_brave", lambda *_: (_ for _ in ()).throw(web_search.WebSearchError("brave_down")))
    monkeypatch.setattr(web_search, "_duck", lambda *_: [])
    monkeypatch.setattr(web_search, "_github", lambda *_: [])
    monkeypatch.setattr(web_search, "_bing", lambda *_: [
        {"title": "Official documentation", "url": "https://example.com/docs", "snippet": "verified"}
    ])
    monkeypatch.setattr(web_search, "_public_http_url", lambda value, **_: value)
    result = web_search.search_web({"query": "latest official docs", "count": 5})
    assert result["provider_id"] == "bing-html"
    assert result["results"][0]["url"] == "https://example.com/docs"
    assert result["searched_at"]
    assert [(item["provider_id"], item["attempt"]) for item in result["attempts"]] == [
        ("brave", 1), ("brave", 2), ("github-api", 1), ("github-api", 2), ("duckduckgo-html", 1), ("duckduckgo-html", 2)
    ]


@pytest.mark.parametrize("url", ["http://127.0.0.1:8787", "http://localhost:8194", "file:///etc/passwd"])
def test_search_blocks_local_and_non_http_urls(url):
    with pytest.raises(web_search.WebSearchError):
        web_search._public_http_url(url)


def test_duck_parser_extracts_results():
    parser = web_search._DuckParser()
    parser.feed('<a class="result__a" href="https://example.com/a">Title</a><div class="result__snippet">Summary</div>')
    assert parser.results == [{"title": "Title", "url": "https://example.com/a", "snippet": "Summary "}]


def test_no_provider_result_is_a_hard_failure(monkeypatch):
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    monkeypatch.setattr(web_search, "_github", lambda *_: [])
    monkeypatch.setattr(web_search, "_duck", lambda *_: [])
    monkeypatch.setattr(web_search, "_bing", lambda *_: [])
    monkeypatch.setattr(web_search, "_google_news", lambda *_: [])
    monkeypatch.setattr(web_search, "_google", lambda *_: [])
    with pytest.raises(web_search.WebSearchError, match="all_search_providers_failed"):
        web_search.search_web({"query": "current facts"})


def test_managed_proxy_exception_is_provider_transport_only(monkeypatch):
    monkeypatch.setattr(web_search.socket, "getaddrinfo", lambda *args: [(2, 1, 6, "", ("198.18.0.9", 443))])
    with pytest.raises(web_search.WebSearchError, match="private_network"):
        web_search._public_http_url("https://attacker.example/result")
    with pytest.raises(web_search.WebSearchError, match="registered_provider"):
        web_search._public_http_url("https://attacker.example/result", allow_managed_proxy=True)


def test_provider_registry_is_the_only_route_and_capability_fact_source():
    assert [item["id"] for item in web_search.WEB_SEARCH_PROVIDERS] == ["brave", "github-api", "duckduckgo-html", "bing-html", "google-news-rss", "google-html"]
    assert web_search.WEB_SEARCH_PROVIDER_DESCRIPTIONS == tuple(item["description"] for item in web_search.WEB_SEARCH_PROVIDERS)
    assert web_search._SEARCH_PROVIDER_HOSTS == {host for item in web_search.WEB_SEARCH_PROVIDERS for host in item["hosts"]}


def test_irrelevant_sources_are_rejected_before_llm_grounding():
    query = "latest open source text-to-image model 2026 official release"
    assert not web_search._result_is_relevant(query, {"title":"Google Translate", "url":"https://translate.google.example", "snippet":"Translate words online"})
    assert web_search._result_is_relevant(query, {"title":"New open source image model released", "url":"https://example.com/model", "snippet":"text-to-image weights"})


def test_validated_same_query_cache_recovers_provider_outage(monkeypatch):
    source = {"title":"LangGraph official docs","url":"https://example.com/langgraph","snippet":"LangGraph documentation"}
    monkeypatch.setattr(web_search, "_duck", lambda *_: [source])
    monkeypatch.setattr(web_search, "_public_http_url", lambda value, **_: value)
    live = web_search.search_web({"query":"LangGraph documentation","count":3})
    assert live["cache_hit"] is False
    monkeypatch.setattr(web_search, "_duck", lambda *_: [])
    monkeypatch.setattr(web_search, "_github", lambda *_: [])
    monkeypatch.setattr(web_search, "_bing", lambda *_: [])
    monkeypatch.setattr(web_search, "_google_news", lambda *_: [])
    monkeypatch.setattr(web_search, "_google", lambda *_: [])
    cached = web_search.search_web({"query":"LangGraph documentation","count":3})
    assert cached["cache_hit"] is True
    assert cached["provider_id"].startswith("cache:")
    assert cached["results"] == live["results"]


def test_generic_model_query_does_not_get_hijacked_by_github_tools(monkeypatch):
    monkeypatch.setattr(web_search, "_request", lambda *_args, **_kwargs: pytest.fail("generic model query must not call GitHub"))
    assert web_search._github('"image generation" "open-source" latest 2026 model "Apple Silicon" local inference', 8) == []


def test_model_relevance_rejects_apps_and_accepts_named_weights():
    query = '"image generation" "open-source" latest 2026 model'
    assert not web_search._result_is_relevant(query, {"title":"Open source image prompt application", "url":"https://example.com/app", "snippet":"client and skills"})
    assert web_search._result_is_relevant(query, {"title":"Open-source GLM-Image model released", "url":"https://example.com/glm", "snippet":"image generation weights"})

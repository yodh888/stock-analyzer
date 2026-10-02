import logging

import requests

import ai_analyzer


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.response = self

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")

    def json(self):
        return self.payload


def signal_result():
    return {
        "latest_price": 10.0,
        "pct_change": 1.2,
        "turnover": 2.0,
        "indicator_values": {},
        "support_resistance": {"support": 9.0, "resistance": 11.0},
        "details": [],
        "patterns": [],
        "suggestion": "中性震荡",
        "total_score": 0,
        "action": "建议观望",
    }


def test_connection_test_success(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return FakeResponse({"choices": [{"message": {"content": "OK"}}]})

    monkeypatch.setattr(ai_analyzer.requests, "post", fake_post)
    result = ai_analyzer.test_ai_connection("secret-key", "deepseek", "deepseek-chat")
    assert result["ok"] is True
    assert result["model"] == "deepseek-chat"
    assert captured["url"].endswith("/chat/completions")
    assert captured["json"]["model"] == "deepseek-chat"


def test_missing_api_key_is_reported_without_request(monkeypatch):
    def fail_post(*args, **kwargs):
        raise AssertionError("request should not be sent")

    monkeypatch.setattr(ai_analyzer.requests, "post", fail_post)
    result = ai_analyzer.test_ai_connection("", "deepseek", "deepseek-chat")
    assert result["ok"] is False
    assert result["error"] == "missing_api_key"


def test_connection_test_rejects_unknown_provider():
    result = ai_analyzer.test_ai_connection("secret-key", "unknown", "model")
    assert result["ok"] is False
    assert result["error"] == "ValueError"


def test_ai_failure_does_not_log_api_key(monkeypatch, caplog):
    secret = "sk-super-secret-value"
    monkeypatch.setattr(ai_analyzer.time, "sleep", lambda _: None)

    def fake_post(url, **kwargs):
        raise requests.ConnectionError(f"Authorization Bearer {secret}")

    monkeypatch.setattr(ai_analyzer.requests, "post", fake_post)
    with caplog.at_level(logging.WARNING):
        result = ai_analyzer.ai_analyze(
            "测试股票",
            "600519",
            signal_result(),
            {},
            secret,
            "deepseek",
            "deepseek-chat",
        )
    assert result["error"] == "ConnectionError"
    assert secret not in caplog.text
    assert "AI请求失败" in caplog.text

def test_http_401_is_not_retried(monkeypatch):
    calls = {"count": 0}

    def fake_post(url, **kwargs):
        calls["count"] += 1
        return FakeResponse({"error": {"message": "unauthorized"}}, status_code=401)

    monkeypatch.setattr(ai_analyzer.requests, "post", fake_post)
    result = ai_analyzer.ai_analyze(
        "测试股票",
        "600519",
        signal_result(),
        {},
        "secret-key",
        "deepseek",
        "deepseek-chat",
    )
    assert result["error"] == "HTTPError"
    assert calls["count"] == 1

def test_ai_analyze_success(monkeypatch):
    def fake_post(url, **kwargs):
        return FakeResponse({
            "choices": [{"message": {"content": "测试分析"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        })

    monkeypatch.setattr(ai_analyzer.requests, "post", fake_post)
    result = ai_analyzer.ai_analyze(
        "测试股票",
        "600519",
        signal_result(),
        {"pe": 10, "pb": 1.2, "roe": 15},
        "secret-key",
        "deepseek",
        "deepseek-chat",
    )
    assert result["text"] == "测试分析"
    assert result["provider"] == "deepseek"
    assert result["model"] == "deepseek-chat"
    assert result["input_tokens"] == 100
    assert result["output_tokens"] == 20
    assert result["cost"] > 0

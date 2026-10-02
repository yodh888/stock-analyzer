import logging

import requests

import pusher


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")

    def json(self):
        return self.payload


def test_pushplus_uses_https(monkeypatch):
    captured = {}

    def fake_post(url, data, timeout):
        captured["url"] = url
        captured["data"] = data
        captured["timeout"] = timeout
        return FakeResponse({"code": 200})

    monkeypatch.setattr(pusher.requests, "post", fake_post)
    assert pusher.push_to_pushplus("token", "title", "content") is True
    assert captured["url"].startswith("https://")
    assert captured["data"]["token"] == "token"


def test_serverchan_failure_does_not_log_secret(monkeypatch, caplog):
    monkeypatch.setattr(pusher.time, "sleep", lambda _: None)

    def fake_post(url, data, timeout):
        raise requests.ConnectionError(f"failed url: {url}")

    monkeypatch.setattr(pusher.requests, "post", fake_post)
    secret = "SCT_SECRET_VALUE"
    with caplog.at_level(logging.WARNING):
        assert pusher.push_to_serverchan(secret, "title", "content") is False
    assert secret not in caplog.text
    assert "ConnectionError" in caplog.text

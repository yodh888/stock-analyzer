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

def test_feishu_payload_and_signature(monkeypatch):
    captured = {}
    monkeypatch.setattr(pusher.time, "time", lambda: 1700000000)

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return FakeResponse({"code": 0})

    monkeypatch.setattr(pusher.requests, "post", fake_post)
    assert pusher.push_to_feishu(
        "https://open.feishu.cn/webhook/test",
        "每日日报",
        "测试内容",
        "feishu-secret",
    ) is True
    assert captured["json"]["msg_type"] == "text"
    assert "测试内容" in captured["json"]["content"]["text"]
    assert captured["json"]["timestamp"] == "1700000000"
    assert captured["json"]["sign"] == pusher._feishu_signature(
        "feishu-secret",
        "1700000000",
    )


def test_feishu_failure_does_not_log_webhook(monkeypatch, caplog):
    monkeypatch.setattr(pusher.time, "sleep", lambda _: None)
    webhook = "https://open.feishu.cn/webhook/secret-token"

    def fake_post(url, json, timeout):
        raise requests.ConnectionError(f"failed url: {url}")

    monkeypatch.setattr(pusher.requests, "post", fake_post)
    with caplog.at_level(logging.WARNING):
        assert pusher.push_to_feishu(webhook, "title", "content") is False
    assert webhook not in caplog.text
    assert "ConnectionError" in caplog.text

def test_pushdeer_payload(monkeypatch):
    captured = {}

    def fake_post(url, data, timeout):
        captured["url"] = url
        captured["data"] = data
        return FakeResponse({"code": 0})

    monkeypatch.setattr(pusher.requests, "post", fake_post)
    assert pusher.push_to_pushdeer("push-key", "日报标题", "日报内容") is True
    assert captured["url"] == "https://api2.pushdeer.com/message/push"
    assert captured["data"] == {
        "pushkey": "push-key",
        "text": "日报标题",
        "desp": "日报内容",
        "type": "markdown",
    }


def test_pushdeer_business_error_logs_code_and_error_without_key(monkeypatch, caplog):
    def fake_post(url, data, timeout):
        return FakeResponse({"code": 80501, "error": "bad pushkey push-key"})

    monkeypatch.setattr(pusher.requests, "post", fake_post)
    with caplog.at_level(logging.WARNING):
        assert pusher.push_to_pushdeer("push-key", "title", "content") is False
    assert "code=80501" in caplog.text
    assert "bad pushkey" in caplog.text
    assert "push-key" not in caplog.text


def test_pushdeer_supports_self_hosted_url(monkeypatch):
    captured = {}

    def fake_post(url, data, timeout):
        captured["url"] = url
        return FakeResponse({"code": 0})

    monkeypatch.setattr(pusher.requests, "post", fake_post)
    assert pusher.push_to_pushdeer(
        "push-key",
        "title",
        "content",
        "https://push.example.com/message/push",
    ) is True
    assert captured["url"] == "https://push.example.com/message/push"

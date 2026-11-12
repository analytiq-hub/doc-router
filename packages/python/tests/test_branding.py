import os

from analytiq_data.common.branding import DEFAULT_APP_NAME, app_name


def test_app_name_default(monkeypatch):
    monkeypatch.delenv("APP_NAME", raising=False)
    assert app_name() == DEFAULT_APP_NAME


def test_app_name_from_env(monkeypatch):
    monkeypatch.setenv("APP_NAME", "Smart Document Router")
    assert app_name() == "Smart Document Router"


def test_app_name_empty_falls_back(monkeypatch):
    monkeypatch.setenv("APP_NAME", "   ")
    assert app_name() == DEFAULT_APP_NAME

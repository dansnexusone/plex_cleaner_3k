from services.config import _env_flag


def test_env_flag_unset_uses_default(monkeypatch):
    monkeypatch.delenv("NTFY_ENABLED", raising=False)
    assert _env_flag("NTFY_ENABLED", True) is True
    assert _env_flag("NTFY_ENABLED", False) is False


def test_env_flag_truthy(monkeypatch):
    for value in ("true", "1", "yes", "on", "TRUE"):
        monkeypatch.setenv("NTFY_ENABLED", value)
        assert _env_flag("NTFY_ENABLED", False) is True


def test_env_flag_falsy(monkeypatch):
    for value in ("false", "0", "no", "off", ""):
        monkeypatch.setenv("NTFY_ENABLED", value)
        assert _env_flag("NTFY_ENABLED", True) is False

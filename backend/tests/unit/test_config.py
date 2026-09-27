from app.core.config import Settings


def test_cors_origins_are_loaded_from_comma_separated_env(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://one.test,http://two.test")
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ["http://one.test", "http://two.test"]

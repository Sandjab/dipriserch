import sys
import pytest

def test_load_config_valid(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "LLM_BASE_URL=http://localhost:11434/v1\nLLM_MODEL=qwen2.5:32b\nLLM_API_KEY=ollama\n"
    )
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("dipriserch", None)
    import dipriserch
    cfg = dipriserch.load_config()
    assert cfg["base_url"] == "http://localhost:11434/v1"
    assert cfg["model"] == "qwen2.5:32b"
    assert cfg["api_key"] == "ollama"

def test_load_config_missing_key(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("LLM_BASE_URL=http://localhost:11434/v1\n")
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("dipriserch", None)
    import dipriserch
    with pytest.raises(SystemExit):
        dipriserch.load_config()

def test_env_int_helper():
    import dipriserch
    assert dipriserch._env_int({"K": "5"}, "K", 8) == 5
    assert dipriserch._env_int({}, "K", 8) == 8           # absent → défaut
    assert dipriserch._env_int({"K": ""}, "K", 8) == 8    # vide → défaut
    assert dipriserch._env_int({"K": "abc"}, "K", 8) == 8 # invalide → défaut

def test_load_config_extract_defaults(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "LLM_BASE_URL=http://x/v1\nLLM_MODEL=m\nLLM_API_KEY=k\n"
    )
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("dipriserch", None)
    import dipriserch
    cfg = dipriserch.load_config()
    assert cfg["map_k"] == 8
    assert cfg["map_page_cap"] == 60000
    assert cfg["reduce_max_chars"] == 32000

def test_load_config_extract_overrides(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "LLM_BASE_URL=http://x/v1\nLLM_MODEL=m\nLLM_API_KEY=k\n"
        "EXTRACT_MAP_K=5\nEXTRACT_MAP_PAGE_CAP=40000\nEXTRACT_REDUCE_MAX_CHARS=20000\n"
    )
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("dipriserch", None)
    import dipriserch
    cfg = dipriserch.load_config()
    assert cfg["map_k"] == 5
    assert cfg["map_page_cap"] == 40000
    assert cfg["reduce_max_chars"] == 20000

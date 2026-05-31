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

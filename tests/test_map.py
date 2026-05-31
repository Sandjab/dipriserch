import json
from unittest.mock import patch, MagicMock
import pytest

MAP_RESPONSE = {"passages": [
    "Gradient descent minimise une fonction de perte.",
    "Il ajuste les paramètres itérativement.",
]}

def test_map_writes_passages(run_dir, fixtures_dir):
    import shutil, dipriserch
    shutil.copy(fixtures_dir / "sweep_results.json", run_dir / "sweep_results.json")
    with patch("dipriserch.chat_structured", return_value=MAP_RESPONSE):
        dipriserch.run_map("gradient-descent", run_dir, MagicMock(), "test-model")
    passages = json.loads((run_dir / "passages.json").read_text())
    assert len(passages) == 2
    assert passages[0]["url"] == "https://example.com/gradient"
    assert passages[0]["passages"] == MAP_RESPONSE["passages"]

def test_map_skipped_if_passages_exist(run_dir, fixtures_dir):
    import shutil, dipriserch
    shutil.copy(fixtures_dir / "sweep_results.json", run_dir / "sweep_results.json")
    (run_dir / "passages.json").write_text("[]")
    with patch("dipriserch.chat_structured") as mock_chat:
        dipriserch.run_map("gradient-descent", run_dir, MagicMock(), "test-model")
        mock_chat.assert_not_called()

def test_map_fails_if_fewer_than_two_sources(run_dir, fixtures_dir):
    import shutil, dipriserch
    shutil.copy(fixtures_dir / "sweep_results.json", run_dir / "sweep_results.json")
    with patch("dipriserch.chat_structured", return_value={"passages": []}):
        with pytest.raises(SystemExit):
            dipriserch.run_map("gradient-descent", run_dir, MagicMock(), "test-model")

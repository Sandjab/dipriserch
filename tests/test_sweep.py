import json
from unittest.mock import patch, MagicMock


def test_sweep_writes_results(run_dir):
    mock_hits = [
        {"href": "https://example.com/1", "title": "Page 1"},
        {"href": "https://other.org/2",   "title": "Page 2"},
    ]
    mock_markdown = "# Title\n\nSome content about gradient descent."

    with patch("dipriserch.DDGS") as mock_ddgs_cls, \
         patch("dipriserch.requests.get") as mock_get:

        instance = MagicMock()
        instance.text.return_value = mock_hits
        mock_ddgs_cls.return_value.__enter__.return_value = instance
        mock_get.return_value.text = mock_markdown

        import dipriserch
        dipriserch.run_sweep("gradient-descent", run_dir,
                             queries=["gradient descent neural network"])

    results = json.loads((run_dir / "sweep_results.json").read_text())
    assert len(results) == 2
    assert results[0]["url"] == "https://example.com/1"
    assert results[0]["markdown"] == mock_markdown
    assert results[0]["query"] == "gradient descent neural network"


def test_sweep_skipped_if_results_exist(run_dir, fixtures_dir):
    import shutil, dipriserch
    shutil.copy(fixtures_dir / "sweep_results.json", run_dir / "sweep_results.json")

    with patch("dipriserch.DDGS") as mock_ddgs_cls:
        dipriserch.run_sweep("gradient-descent", run_dir, queries=["test"])
        mock_ddgs_cls.assert_not_called()

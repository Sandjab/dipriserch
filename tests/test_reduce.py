import json
from unittest.mock import patch, MagicMock

LLM_RESPONSE = {
    "facts": [
        {"id": "fact_001", "fact": "Gradient descent minimizes a loss function.",
         "sources": ["https://example.com/gradient", "https://other.org/ml-basics"]}
    ],
    "sections": [
        {"id": "section_introduction",     "title": "Introduction",     "level": 1, "content": "Gradient descent is fundamental."},
        {"id": "section_gradient_descent", "title": "Gradient Descent", "level": 2, "content": "It adjusts parameters iteratively."}
    ]
}

def test_reduce_writes_files(run_dir, fixtures_dir):
    import shutil, dipriserch
    shutil.copy(fixtures_dir / "passages.json", run_dir / "passages.json")
    with patch("dipriserch.chat_structured", return_value=LLM_RESPONSE):
        dipriserch.run_reduce("gradient-descent", run_dir, MagicMock(), "test-model")
    knowledge = json.loads((run_dir / "knowledge.json").read_text())
    sections  = json.loads((run_dir / "sections_draft.json").read_text())
    assert len(knowledge) == 1
    assert knowledge[0]["id"] == "fact_001"
    assert knowledge[0]["confirmed"] is False
    assert len(sections) == 2
    assert sections[0]["id"] == "section_introduction"

def test_reduce_skipped_if_files_exist(run_dir, fixtures_dir):
    import shutil, dipriserch
    shutil.copy(fixtures_dir / "knowledge.json",      run_dir / "knowledge.json")
    shutil.copy(fixtures_dir / "sections_draft.json", run_dir / "sections_draft.json")
    with patch("dipriserch.chat_structured") as mock_chat:
        dipriserch.run_reduce("gradient-descent", run_dir, MagicMock(), "test-model")
        mock_chat.assert_not_called()

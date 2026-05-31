import json
from unittest.mock import patch, MagicMock


def test_verify_marks_confirmed_facts(run_dir, fixtures_dir):
    import shutil, dipriserch
    shutil.copy(fixtures_dir / "sweep_results.json", run_dir / "sweep_results.json")

    knowledge = [
        {"id": "fact_001", "fact": "Gradient descent minimizes loss.",
         "sources": ["https://example.com/gradient", "https://other.org/ml-basics"], "confirmed": False},
        {"id": "fact_002", "fact": "Learning rate must be tuned.",
         "sources": ["https://example.com/gradient"], "confirmed": False},
    ]
    (run_dir / "knowledge.json").write_text(json.dumps(knowledge))

    def mock_verify(client, model, prompt):
        if "fact_001" in prompt:
            return {"confirmed": True,  "reason": "Two independent sources confirm this."}
        return     {"confirmed": False, "reason": "Only one source found."}

    with patch("dipriserch.chat_structured", side_effect=mock_verify):
        dipriserch.run_verify(run_dir, MagicMock(), "test-model")

    updated   = json.loads((run_dir / "knowledge.json").read_text())
    confirmed = [f for f in updated if f["confirmed"]]
    assert len(confirmed) == 1
    assert confirmed[0]["id"] == "fact_001"


def test_verify_skipped_if_done_flag_exists(run_dir, fixtures_dir):
    import shutil, dipriserch
    shutil.copy(fixtures_dir / "knowledge.json", run_dir / "knowledge.json")
    shutil.copy(fixtures_dir / "sweep_results.json", run_dir / "sweep_results.json")
    (run_dir / ".verify_done").write_text("done")

    with patch("dipriserch.chat_structured") as mock_chat:
        dipriserch.run_verify(run_dir, MagicMock(), "test-model")
        mock_chat.assert_not_called()


def test_verify_rejette_faits_source_unique(run_dir, fixtures_dir):
    import shutil, dipriserch
    shutil.copy(fixtures_dir / "sweep_results.json", run_dir / "sweep_results.json")

    knowledge = [
        {"id": "fact_001", "fact": "Well-sourced fact.",
         "sources": ["https://example.com/gradient", "https://other.org/ml-basics"], "confirmed": False},
        {"id": "fact_002", "fact": "Poorly sourced fact.",
         "sources": ["https://example.com/gradient"], "confirmed": False},
    ]
    (run_dir / "knowledge.json").write_text(json.dumps(knowledge))

    with patch("dipriserch.chat_structured", return_value={"confirmed": True, "reason": "ok"}):
        dipriserch.run_verify(run_dir, MagicMock(), "test-model")

    updated = json.loads((run_dir / "knowledge.json").read_text())
    assert updated[0]["confirmed"] is True   # 2 sources → confirmé par LLM
    assert updated[1]["confirmed"] is False  # 1 source → rejeté sans appel LLM


def test_verify_exit2_et_pas_done_flag_si_ratio_insuffisant(run_dir, fixtures_dir):
    import shutil, dipriserch, pytest
    shutil.copy(fixtures_dir / "sweep_results.json", run_dir / "sweep_results.json")

    knowledge = [
        {"id": "fact_001", "fact": "Fact A.", "sources": ["https://example.com/gradient", "https://other.org/ml-basics"], "confirmed": False},
        {"id": "fact_002", "fact": "Fact B.", "sources": ["https://example.com/gradient", "https://other.org/ml-basics"], "confirmed": False},
        {"id": "fact_003", "fact": "Fact C.", "sources": ["https://example.com/gradient", "https://other.org/ml-basics"], "confirmed": False},
    ]
    (run_dir / "knowledge.json").write_text(json.dumps(knowledge))

    # 0 confirmés / 3 total = 0% < 50%
    with patch("dipriserch.chat_structured", return_value={"confirmed": False, "reason": "no"}):
        with pytest.raises(SystemExit) as exc:
            dipriserch.run_verify(run_dir, MagicMock(), "test-model")

    assert exc.value.code == 2
    assert not (run_dir / ".verify_done").exists()  # --from verify peut relancer

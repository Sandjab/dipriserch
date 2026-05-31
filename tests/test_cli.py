import sys
from unittest.mock import patch, MagicMock


def test_cli_orchestre_toutes_les_phases(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "LLM_BASE_URL=http://x\nLLM_MODEL=test\nLLM_API_KEY=x\n"
    )
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("dipriserch", None)

    with patch("dipriserch.run_sweep")   as ms, \
         patch("dipriserch.run_extract") as me, \
         patch("dipriserch.run_verify")  as mv, \
         patch("dipriserch.make_llm_client", return_value=MagicMock()):
        import dipriserch
        dipriserch.main(["gradient-descent"])

    run_dir = tmp_path / "run" / "gradient-descent"
    assert run_dir.exists()
    ms.assert_called_once()
    me.assert_called_once()
    mv.assert_called_once()


def test_cli_from_extract_saute_sweep(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "LLM_BASE_URL=http://x\nLLM_MODEL=test\nLLM_API_KEY=x\n"
    )
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("dipriserch", None)

    with patch("dipriserch.run_sweep")   as ms, \
         patch("dipriserch.run_extract") as me, \
         patch("dipriserch.run_verify")  as mv, \
         patch("dipriserch.make_llm_client", return_value=MagicMock()):
        import dipriserch
        dipriserch.main(["gradient-descent", "--from", "extract"])

    ms.assert_not_called()
    me.assert_called_once()
    mv.assert_called_once()


def test_cli_from_verify_saute_sweep_et_extract(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "LLM_BASE_URL=http://x\nLLM_MODEL=test\nLLM_API_KEY=x\n"
    )
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("dipriserch", None)

    with patch("dipriserch.run_sweep")   as ms, \
         patch("dipriserch.run_extract") as me, \
         patch("dipriserch.run_verify")  as mv, \
         patch("dipriserch.make_llm_client", return_value=MagicMock()):
        import dipriserch
        dipriserch.main(["gradient-descent", "--from", "verify"])

    ms.assert_not_called()
    me.assert_not_called()
    mv.assert_called_once()

from unittest.mock import patch, MagicMock

def test_extract_orchestrates_map_then_reduce(run_dir):
    import dipriserch
    with patch("dipriserch.run_map") as m_map, patch("dipriserch.run_reduce") as m_reduce:
        dipriserch.run_extract("gradient-descent", run_dir, MagicMock(), "test-model")
        m_map.assert_called_once()
        m_reduce.assert_called_once()

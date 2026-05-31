import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

FIXTURES = Path(__file__).parent / "fixtures"

@pytest.fixture
def fixtures_dir():
    return FIXTURES

@pytest.fixture
def run_dir(tmp_path):
    d = tmp_path / "test-slug"
    d.mkdir()
    return d

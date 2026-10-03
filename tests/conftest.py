from pathlib import Path

import pytest

from kitbuilder.config import load_config

FIXTURES_SOURCE = Path(__file__).parent / "fixtures" / "packs"


@pytest.fixture
def source_dir() -> Path:
    return FIXTURES_SOURCE


@pytest.fixture
def config() -> dict:
    return load_config(None)


@pytest.fixture
def adg_template(tmp_path) -> Path:
    from ableton_fixture import write_template

    return write_template(tmp_path / "templates" / "pad_template.adg")

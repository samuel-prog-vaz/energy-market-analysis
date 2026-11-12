from omie.config import DATA_RAW, ROOT


def test_paths_exist():
    assert (ROOT / "pyproject.toml").exists()
    assert DATA_RAW.is_dir()

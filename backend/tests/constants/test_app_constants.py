import sys
from pathlib import Path

from minutes_app.constants import app_constants


def test_get_app_root_resolves_to_repo_root_in_dev_mode() -> None:
    root = app_constants.get_app_root()

    assert (root / "CLAUDE.md").exists()


def test_get_app_root_resolves_to_executable_dir_when_frozen(monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(Path("C:/dist/minutes-app/minutes-app.exe")))

    root = app_constants.get_app_root()

    assert root == Path("C:/dist/minutes-app").resolve()


def test_get_data_dir_is_app_root_slash_data() -> None:
    assert app_constants.get_data_dir() == app_constants.get_app_root() / "data"


def test_get_models_dir_is_app_root_slash_models() -> None:
    assert app_constants.get_models_dir() == app_constants.get_app_root() / "models"


def test_get_db_path_is_data_dir_slash_app_db() -> None:
    assert app_constants.get_db_path() == app_constants.get_data_dir() / "app.db"


def test_get_audio_dir_is_data_dir_slash_audio() -> None:
    assert app_constants.get_audio_dir() == app_constants.get_data_dir() / "audio"

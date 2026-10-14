import pytest


@pytest.fixture(autouse=True)
def isolated_user_state(tmp_path, monkeypatch):
    """Never touch the real user's settings, library or autostart entries, and let test runs overlap."""
    from PySide6.QtCore import QSettings

    for var in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
        monkeypatch.setenv(var, str(tmp_path / var.lower()))
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path / "qsettings"))
    yield

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from screencapture import diagnostics


def test_painter_calls_do_not_corrupt_none_refcount():
    """PySide6 6.12.0 on Python < 3.12 leaks None refs and kills the app (none_dealloc). CI runs this on 3.10."""
    assert diagnostics.check_runtime() is None

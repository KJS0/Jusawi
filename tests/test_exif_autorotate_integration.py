import os
import tempfile
import pytest

PIL = pytest.importorskip("PIL", reason="Pillow is required for EXIF autorotate tests")
from PIL import Image  # type: ignore  # noqa: E402


def make_with_orientation(path: str, orientation: int):
    img = Image.new("RGB", (3, 2), (0, 0, 0))
    exif = Image.Exif()
    exif[274] = orientation
    img.save(path, format="JPEG", exif=exif)


def test_viewer_load_respects_exif_orientation(qtbot):
    from src.main_window import JusawiViewer

    w = JusawiViewer()
    qtbot.addWidget(w)
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "o6.jpg")
        make_with_orientation(path, 6)
        assert w.load_image(path)
        pix = w.image_display_area.originalPixmap()
        assert pix and not pix.isNull()
        assert (pix.width(), pix.height()) == (2, 3)



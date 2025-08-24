import os
import tempfile
import pytest
from PyQt6.QtGui import QColor


PIL = pytest.importorskip("PIL", reason="Pillow is required for EXIF autorotate tests")
from PIL import Image  # type: ignore  # noqa: E402


ORIENTATION_TAG = 274  # TIFF Orientation tag id


def make_oriented_jpeg(path: str, orientation: int, size=(3, 2)) -> None:
    w, h = size
    img = Image.new("RGB", (w, h))
    px = img.load()
    # Corner pattern
    px[0, 0] = (255, 0, 0)        # top-left red
    px[w - 1, 0] = (0, 255, 0)    # top-right green
    px[0, h - 1] = (0, 0, 255)    # bottom-left blue
    px[w - 1, h - 1] = (255, 255, 0)  # bottom-right yellow

    exif = Image.Exif()
    exif[ORIENTATION_TAG] = orientation
    # JPEG 압축 아티팩트를 최소화
    img.save(path, format="JPEG", exif=exif, quality=100, subsampling=0, optimize=True)


def qcolor_at(qimage, x, y):
    c = QColor(qimage.pixel(x, y))
    return (c.red(), c.green(), c.blue())


def color_close(actual, expected, tol=32):
    ar, ag, ab = actual
    er, eg, eb = expected
    return abs(ar - er) <= tol and abs(ag - eg) <= tol and abs(ab - eb) <= tol


@pytest.mark.parametrize(
    "orientation, expected_size, expected_corners",
    [
        # (tl, tr, bl, br)
        (1, (3, 2), ((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0))),  # Normal
        (6, (2, 3), ((0, 0, 255), (255, 0, 0), (255, 255, 0), (0, 255, 0))),  # 90 CW
        (8, (2, 3), ((0, 255, 0), (255, 255, 0), (255, 0, 0), (0, 0, 255))),  # 270 CW
        (3, (3, 2), ((255, 255, 0), (0, 0, 255), (0, 255, 0), (255, 0, 0))),  # 180
    ],
)
def test_image_service_exif_autorotate(orientation, expected_size, expected_corners, qtbot):
    from src.image_service import ImageService

    svc = ImageService()
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, f"o{orientation}.jpg")
        make_oriented_jpeg(path, orientation)
        p, img, ok, err = svc.load(path)
        assert ok, err
        assert (img.width(), img.height()) == expected_size
        w, h = expected_size
        tl = qcolor_at(img, 0, 0)
        tr = qcolor_at(img, w - 1, 0)
        bl = qcolor_at(img, 0, h - 1)
        br = qcolor_at(img, w - 1, h - 1)
        exp_tl, exp_tr, exp_bl, exp_br = expected_corners
        assert color_close(tl, exp_tl)
        assert color_close(tr, exp_tr)
        assert color_close(bl, exp_bl)
        assert color_close(br, exp_br)



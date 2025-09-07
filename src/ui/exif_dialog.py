from __future__ import annotations

import os
from typing import Dict, Any, Tuple
from datetime import datetime
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, QTabWidget, QWidget  # type: ignore[import]
from PyQt6.QtCore import Qt  # type: ignore[import]

try:
    from ..utils.status_utils import human_readable_size  # type: ignore
except Exception:
    def human_readable_size(size_bytes: int) -> str:
        try:
            b = float(size_bytes)
        except Exception:
            return "-"
        units = ["B", "KiB", "MiB", "GiB", "TiB"]
        i = 0
        while b >= 1024.0 and i < len(units) - 1:
            b /= 1024.0
            i += 1
        return (f"{int(b)} {units[i]}" if i == 0 else f"{b:.2f} {units[i]}")


# --- EXIF value mapping helpers ---

def _to_int(v: Any) -> int | None:
    try:
        s = str(v).strip()
        if s.endswith(")") and "(" in s:
            s = s.split("(")[-1].rstrip(")")
        return int(s)
    except Exception:
        try:
            return int(v)
        except Exception:
            return None


def _label_with_code(name: str, v: Any) -> str:
    code = _to_int(v)
    if name == "Orientation":
        m = {1: "좌상단", 2: "우상단", 3: "우하단", 4: "좌하단", 5: "좌상-대각", 6: "우상-대각", 7: "우하-대각", 8: "좌하-대각"}
        if code is not None:
            return f"{m.get(code, str(v))} ({code})"
    if name == "ExposureProgram":
        m = {0: "정의되지 않음", 1: "수동", 2: "프로그램 AE", 3: "조리개 우선", 4: "셔터 우선", 5: "크리에이티브", 6: "액션", 7: "인물", 8: "풍경"}
        if code is not None:
            return f"{m.get(code, str(v))} ({code})"
    if name == "MeteringMode":
        m = {0: "알 수 없음", 1: "평균", 2: "중앙중점", 3: "스팟", 4: "멀티 스팟", 5: "다분할", 6: "부분"}
        if code is not None:
            return f"{m.get(code, str(v))} ({code})"
    if name == "LightSource":
        m = {0: "알 수 없음", 1: "주광", 2: "형광등", 3: "백열등", 4: "플래시", 9: "맑음", 10: "흐림", 11: "그늘"}
        if code is not None:
            return f"{m.get(code, str(v))} ({code})"
    if name == "Flash":
        try:
            ival = _to_int(v)
            if ival is None:
                return str(v)
            return "발광" if (ival & 0x1) else "발광 안 함"
        except Exception:
            return str(v)
    if name == "WhiteBalance":
        m = {0: "자동", 1: "수동"}
        if code is not None:
            return f"{m.get(code, str(v))} ({code})"
    if name == "SceneCaptureType":
        m = {0: "표준", 1: "풍경", 2: "인물", 3: "야경"}
        if code is not None:
            return f"{m.get(code, str(v))} ({code})"
    if name == "ColorSpace":
        m = {1: "sRGB", 65535: "보정 안 됨"}
        if code is not None:
            return m.get(code, str(v))
    return str(v)


def _format_fraction(v: Any) -> str:
    try:
        if isinstance(v, tuple) and len(v) == 2 and float(v[1]) != 0:
            num, den = float(v[0]), float(v[1])
            if num > den:
                return f"{num/den:.4f}"
            return f"{int(num)}/{int(den)}"
        s = str(v)
        if "/" in s:
            a, b = s.split("/", 1)
            fa = float(a.strip())
            fb = float(b.strip())
            if fb != 0:
                return f"{fa/fb:.4f}"
        return str(v)
    except Exception:
        return str(v)


def _format_bytes(tag: str, b: bytes) -> str:
    try:
        if tag in ("ExifVersion", "FlashPixVersion"):
            s = ''.join(chr(x) for x in b if 48 <= x <= 57)
            if len(s) >= 4:
                return f"{s[0]}.{s[1:]}"
        if tag == "UserComment":
            if len(b) >= 8:
                prefix = b[:8]
                rest = b[8:]
                try:
                    if prefix.startswith(b"ASCII"):
                        return rest.decode('ascii', errors='ignore').strip('\x00 ')
                    if prefix.startswith(b"UNICODE"):
                        return rest.decode('utf-16', errors='ignore').strip('\x00 ')
                except Exception:
                    pass
        try:
            return b.decode('utf-8', errors='ignore')
        except Exception:
            return f"<bytes {len(b)}>"
    except Exception:
        return f"<bytes {len(b)}>"


def _format_exif(name: str, v: Any) -> str:
    try:
        if isinstance(v, bytes):
            return _format_bytes(name, v)
        if name == "FNumber":
            try:
                if isinstance(v, tuple) and len(v) == 2 and float(v[1]) != 0:
                    return f"{float(v[0]) / float(v[1]):.1f}"
                s = str(v)
                if "/" in s:
                    a, b = s.split("/", 1)
                    fa = float(a.strip())
                    fb = float(b.strip())
                    if fb != 0:
                        return f"{fa/fb:.1f}"
                return f"{float(s):.1f}"
            except Exception:
                return str(v)
        enum_tags = {"Orientation", "ExposureProgram", "MeteringMode", "LightSource", "Flash", "WhiteBalance", "SceneCaptureType", "ColorSpace"}
        if name in enum_tags:
            return _label_with_code(name, v)
        if name in {"FocalLength", "FocalLengthIn35mmFilm", "ExposureBiasValue", "XResolution", "YResolution", "CompressedBitsPerPixel"}:
            return _format_fraction(v)
        return str(v)
    except Exception:
        return str(v)


def _merge_exifread_into(image_path: str, exif_dict: Dict[str, Any], gps_dict: Dict[str, Any]) -> None:
    try:
        import exifread  # type: ignore
    except Exception:
        return
    try:
        with open(image_path, 'rb') as fh:
            tags = exifread.process_file(fh, details=False)
        mapping = {
            'Image Make': 'Make',
            'Image Model': 'Model',
            'Image Orientation': 'Orientation',
            'Image XResolution': 'XResolution',
            'Image YResolution': 'YResolution',
            'Image ResolutionUnit': 'ResolutionUnit',
            'Image Software': 'Software',
            'Image DateTime': 'DateTime',
            'Image YCbCrPositioning': 'YCbCrPositioning',
            'EXIF ExposureTime': 'ExposureTime',
            'EXIF FNumber': 'FNumber',
            'EXIF ExposureProgram': 'ExposureProgram',
            'EXIF ISOSpeedRatings': 'ISOSpeedRatings',
            'EXIF ExifVersion': 'ExifVersion',
            'EXIF DateTimeOriginal': 'DateTimeOriginal',
            'EXIF DateTimeDigitized': 'DateTimeDigitized',
            'EXIF ComponentsConfiguration': 'ComponentsConfiguration',
            'EXIF CompressedBitsPerPixel': 'CompressedBitsPerPixel',
            'EXIF ExposureBiasValue': 'ExposureBiasValue',
            'EXIF MeteringMode': 'MeteringMode',
            'EXIF LightSource': 'LightSource',
            'EXIF Flash': 'Flash',
            'EXIF FocalLength': 'FocalLength',
            'EXIF UserComment': 'UserComment',
            'EXIF FlashPixVersion': 'FlashPixVersion',
            'EXIF ColorSpace': 'ColorSpace',
            'EXIF ExifImageWidth': 'ExifImageWidth',
            'EXIF ExifImageLength': 'ExifImageLength',
            'EXIF InteroperabilityOffset': 'InteroperabilityOffset',
            'EXIF SensingMethod': 'SensingMethod',
            'EXIF FileSource': 'FileSource',
            'EXIF SceneType': 'SceneType',
            'EXIF CFAPattern': 'CFAPattern',
            'EXIF CustomRendered': 'CustomRendered',
            'EXIF ExposureMode': 'ExposureMode',
            'EXIF WhiteBalance': 'WhiteBalance',
            'EXIF FocalLengthIn35mmFilm': 'FocalLengthIn35mmFilm',
            'EXIF SceneCaptureType': 'SceneCaptureType',
            'EXIF GainControl': 'GainControl',
            'EXIF Contrast': 'Contrast',
            'EXIF Saturation': 'Saturation',
            'EXIF Sharpness': 'Sharpness',
            'EXIF SubjectDistanceRange': 'SubjectDistanceRange',
            'EXIF LensMake': 'LensMake',
            'EXIF LensModel': 'LensModel',
        }
        for ek, ourk in mapping.items():
            if ourk not in exif_dict and ek in tags:
                exif_dict[ourk] = tags[ek]
        gps_map = {
            'GPS GPSLatitude': 'GPSLatitude',
            'GPS GPSLatitudeRef': 'GPSLatitudeRef',
            'GPS GPSLongitude': 'GPSLongitude',
            'GPS GPSLongitudeRef': 'GPSLongitudeRef',
            'GPS GPSAltitude': 'GPSAltitude',
        }
        for ek, ourk in gps_map.items():
            if ek in tags and ourk not in gps_dict:
                gps_dict[ourk] = tags[ek]
    except Exception:
        return


class ExifDialog(QDialog):
    def __init__(self, parent=None, image_path: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("사진 정보 (EXIF)")
        self._image_path = image_path or ""

        root = QVBoxLayout(self)
        try:
            root.setContentsMargins(8, 8, 8, 8)
            root.setSpacing(6)
        except Exception:
            pass

        title = QLabel(os.path.basename(self._image_path) if self._image_path else "-")
        try:
            title.setStyleSheet("font-weight: bold; font-size: 14px; color: #EAEAEA;")
        except Exception:
            pass
        sub = QLabel(self._image_path)
        try:
            sub.setStyleSheet("color: #BEBEBE;")
        except Exception:
            pass
        root.addWidget(title)
        root.addWidget(sub)

        self.tabs = QTabWidget(self)
        root.addWidget(self.tabs, 1)

        self.summary_table = self._make_table()
        self.props_table = self._make_table()
        self.details_table = self._make_table()
        self.gps_table = self._make_table()

        self.tabs.addTab(self._wrap(self.summary_table), "요약")
        self.tabs.addTab(self._wrap(self.props_table), "속성")
        self.tabs.addTab(self._wrap(self.details_table), "EXIF")
        self.tabs.addTab(self._wrap(self.gps_table), "GPS")

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

        self._populate()

    def _wrap(self, w: QTableWidget) -> QWidget:
        holder = QWidget(self)
        lay = QVBoxLayout(holder)
        try:
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)
        except Exception:
            pass
        lay.addWidget(w)
        return holder

    def _make_table(self) -> QTableWidget:
        t = QTableWidget(0, 2, self)
        t.setHorizontalHeaderLabels(["항목", "값"])
        try:
            header = t.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        except Exception:
            pass
        try:
            t.setEditTriggers(t.EditTrigger.NoEditTriggers)
            t.setSelectionMode(t.SelectionMode.NoSelection)
        except Exception:
            pass
        return t

    def _add_category(self, table: QTableWidget, name: str) -> None:
        r = table.rowCount()
        table.insertRow(r)
        it = QTableWidgetItem(str(name))
        try:
            it.setFlags(Qt.ItemFlag.ItemIsEnabled)
            it.setForeground(Qt.gray)
            it.setBackground(Qt.transparent)
        except Exception:
            pass
        table.setItem(r, 0, it)
        table.setItem(r, 1, QTableWidgetItem(""))

    def _populate(self) -> None:
        if not self._image_path or not os.path.exists(self._image_path):
            QMessageBox.warning(self, "사진 정보", "유효한 파일이 없습니다.")
            return
        try:
            from PIL import Image, ExifTags  # type: ignore
        except Exception:
            self._set_rows(self.props_table, {"오류": "Pillow가 설치되어 있지 않습니다."})
            return
        try:
            st = None
            try:
                st = os.stat(self._image_path)
            except Exception:
                st = None
            self.props_table.setRowCount(0)
            self._add_category(self.props_table, "파일")
            def add_prop(label: str, value: Any):
                r = self.props_table.rowCount()
                self.props_table.insertRow(r)
                it0 = QTableWidgetItem(label)
                it1 = QTableWidgetItem(str(value))
                try:
                    it0.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    it1.setFlags(Qt.ItemFlag.ItemIsEnabled)
                except Exception:
                    pass
                self.props_table.setItem(r, 0, it0)
                self.props_table.setItem(r, 1, it1)

            base = os.path.basename(self._image_path)
            add_prop("파일명", base)
            add_prop("파일 경로", os.path.dirname(self._image_path))
            ext = os.path.splitext(base)[1].lower()
            add_prop("확장자", ext or "-")
            type_name = {
                ".jpg": "JPG 파일", ".jpeg": "JPG 파일", ".png": "PNG 파일", ".bmp": "BMP 파일",
                ".gif": "GIF 파일", ".tif": "TIFF 파일", ".tiff": "TIFF 파일", ".webp": "WebP 파일",
            }.get(ext, (ext.upper().lstrip('.') + " 파일") if ext else "-")
            add_prop("파일 형식", type_name)
            if st:
                size_b = int(st.st_size)
                add_prop("파일 크기", f"{human_readable_size(size_b)} ({size_b} bytes)")
                try:
                    add_prop("생성 시간", datetime.fromtimestamp(st.st_ctime).strftime("%Y-%m-%d %H:%M:%S"))
                    add_prop("수정 시간", datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"))
                    add_prop("접근 시간", datetime.fromtimestamp(st.st_atime).strftime("%Y-%m-%d %H:%M:%S"))
                except Exception:
                    pass
            try:
                ro = not os.access(self._image_path, os.W_OK)
                add_prop("읽기 전용", "예" if ro else "아니오")
            except Exception:
                pass
            try:
                hidden = False
                if os.name == 'nt':
                    import ctypes  # type: ignore
                    attrs = ctypes.windll.kernel32.GetFileAttributesW(self._image_path)
                    if attrs != -1:
                        hidden = bool(attrs & 0x2)
                add_prop("숨김", "예" if hidden else "아니오")
            except Exception:
                pass

            with Image.open(self._image_path) as im:
                exif_map_name: Dict[str, Any] = {}
                gps_exif: Dict[str, Any] = {}
                try:
                    exif = im.getexif()
                    if exif:
                        for tag_id, value in exif.items():
                            name = getattr(ExifTags, 'TAGS', {}).get(tag_id, f"Tag {int(tag_id)}")
                            if name == 'GPSInfo' and isinstance(value, dict):
                                try:
                                    from PIL.ExifTags import GPSTAGS  # type: ignore
                                    gps_exif = {GPSTAGS.get(k, str(k)): value[k] for k in value.keys()}
                                except Exception:
                                    gps_exif = {str(k): value[k] for k in value.keys()}
                                continue
                            exif_map_name[name] = value
                except Exception:
                    pass
                # backfill with exifread for summary also
                try:
                    _merge_exifread_into(self._image_path, exif_map_name, gps_exif)
                except Exception:
                    pass
                try:
                    if exif_map_name.get("ImageDescription"):
                        add_prop("설명", exif_map_name.get("ImageDescription"))
                except Exception:
                    pass

                self._add_category(self.props_table, "이미지")
                add_prop("형식", str(im.format or ""))
                w, h = int(im.width), int(im.height)
                add_prop("크기", f"{w} x {h} px")
                try:
                    mp = (w * h) / 1_000_000.0
                    add_prop("픽셀 수", f"{mp:.4f} Mpixels")
                except Exception:
                    pass
                add_prop("색 모델", str(im.mode or ""))
                bits_by_mode = {"1": 1, "L": 8, "P": 8, "RGB": 24, "RGBA": 32, "CMYK": 32, "I;16": 16, "I;16B": 16, "I;16L": 16, "I": 32, "F": 32}
                add_prop("비트 수", bits_by_mode.get(str(im.mode), "-"))
                try:
                    icc = im.info.get("icc_profile")
                    add_prop("ICC 프로파일", "있음" if icc else "없음")
                except Exception:
                    pass
                try:
                    dpi = im.info.get("dpi")
                    if isinstance(dpi, tuple) and len(dpi) >= 2:
                        xd, yd = float(dpi[0]), float(dpi[1])
                        add_prop("해상도(DPI)", f"{xd:.0f} x {yd:.0f} dpi")
                        if xd > 0 and yd > 0:
                            inch_w, inch_h = w / xd, h / yd
                            add_prop("인쇄 크기", f"{inch_w:.2f} x {inch_h:.2f} in, {inch_w*2.54:.1f} x {inch_h*2.54:.1f} cm")
                except Exception:
                    pass
                try:
                    if str(im.format).upper() == 'JPEG':
                        prog = bool(im.info.get('progression')) if 'progression' in im.info else False
                        add_prop("프로그레시브 모드", "예" if prog else "아니오")
                        subs = im.info.get('subsampling')
                        subs_map = {0: "4:4:4 (1x1,1x1,1x1)", 1: "4:2:2 (2x1,1x1,1x1)", 2: "4:2:0 (2x2,1x1,1x1)", 3: "4:1:1 (4x1,1x1,1x1)"}
                        if subs is not None:
                            add_prop("서브 샘플링", subs_map.get(subs, str(subs)))
                        add_prop("압축", "JPEG")
                except Exception:
                    pass
                try:
                    frames = int(getattr(im, 'n_frames', 1)) if hasattr(im, 'n_frames') else 1
                    add_prop("이미지/프레임 수", frames)
                except Exception:
                    pass
                try:
                    ori = exif_map_name.get("Orientation")
                    if ori:
                        add_prop("원점", _label_with_code("Orientation", ori))
                except Exception:
                    pass

                # Summary tab populate
                try:
                    summary_rows: Dict[str, Any] = {}
                    make = str(exif_map_name.get("Make", "")).strip()
                    model = str(exif_map_name.get("Model", "")).strip()
                    camera = (make + " " + model).strip()
                    lens = str(exif_map_name.get("LensModel", exif_map_name.get("LensMake", "")))
                    fnum = _format_exif("FNumber", exif_map_name.get("FNumber", ""))
                    etime = _format_exif("ExposureTime", exif_map_name.get("ExposureTime", ""))
                    if etime and "/" not in etime and not etime.endswith("s"):
                        etime = etime + "s"
                    iso = str(exif_map_name.get("ISOSpeedRatings", exif_map_name.get("PhotographicSensitivity", "")))
                    fl = exif_map_name.get("FocalLength", "")
                    fls = _format_fraction(fl)
                    try:
                        if "/" in fls:
                            flv = float(fls)
                            fls = f"{flv:.1f} mm"
                        elif fls.replace('.', '', 1).isdigit():
                            fls = f"{float(fls):.1f} mm"
                    except Exception:
                        pass
                    dt = str(exif_map_name.get("DateTimeOriginal", exif_map_name.get("DateTime", "")))
                    lat = lon = None
                    if gps_exif:
                        lat, lon, _alt = self._parse_gps(gps_exif)
                    summary_rows["파일명"] = base
                    if dt:
                        summary_rows["촬영 시간"] = dt
                    if camera:
                        summary_rows["촬영 기기"] = camera
                    if lens:
                        summary_rows["촬영 렌즈"] = lens
                    if fnum:
                        summary_rows["조리개"] = f"f/{fnum}" if fnum else ""
                    if etime:
                        summary_rows["노출 시간"] = etime
                    if iso:
                        summary_rows["ISO"] = iso
                    if fls:
                        summary_rows["화각"] = fls
                    if lat is not None and lon is not None:
                        summary_rows["GPS"] = f"{lat:.6f}, {lon:.6f}"
                    self._set_rows(self.summary_table, summary_rows)
                except Exception:
                    pass

            # EXIF/GPS tabs populate
            from PIL import Image as _PILImage, ExifTags as _ExifTags  # type: ignore
            with _PILImage.open(self._image_path) as im2:
                exif_map_name2: Dict[str, Any] = {}
                gps_exif2: Dict[str, Any] = {}
                try:
                    exif2 = im2.getexif()
                    if exif2:
                        for tag_id, value in exif2.items():
                            name = getattr(_ExifTags, 'TAGS', {}).get(tag_id, f"Tag {int(tag_id)}")
                            if name == 'GPSInfo' and isinstance(value, dict):
                                try:
                                    from PIL.ExifTags import GPSTAGS  # type: ignore
                                    gps_exif2 = {GPSTAGS.get(k, str(k)): value[k] for k in value.keys()}
                                except Exception:
                                    gps_exif2 = {str(k): value[k] for k in value.keys()}
                                continue
                            exif_map_name2[name] = value
                except Exception:
                    pass
                try:
                    _merge_exifread_into(self._image_path, exif_map_name2, gps_exif2)
                except Exception:
                    pass

                self.details_table.setRowCount(0)
                def add_detail(label: str, value: Any, keyname: str | None = None):
                    text = _format_exif(keyname or label, value) if keyname else _format_exif(label, value)
                    r = self.details_table.rowCount()
                    self.details_table.insertRow(r)
                    it0 = QTableWidgetItem(label)
                    it1 = QTableWidgetItem(text)
                    try:
                        it0.setFlags(Qt.ItemFlag.ItemIsEnabled)
                        it1.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    except Exception:
                        pass
                    self.details_table.setItem(r, 0, it0)
                    self.details_table.setItem(r, 1, it1)

                self._add_category(self.details_table, "카메라")
                for (label, key, mapkey) in [
                    ("카메라 제조사", "Make", None),
                    ("카메라 모델", "Model", None),
                    ("원점", "Orientation", "Orientation"),
                    ("X 해상도", "XResolution", None),
                    ("Y 해상도", "YResolution", None),
                    ("해상도 단위", "ResolutionUnit", None),
                    ("소프트웨어", "Software", None),
                    ("수정 시각", "DateTime", None),
                    ("YCbCr 위치", "YCbCrPositioning", None),
                ]:
                    if key in exif_map_name2:
                        add_detail(label, exif_map_name2[key], mapkey)

                self._add_category(self.details_table, "이미지")
                for (label, key, mapkey) in [
                    ("노출 시간 [s]", "ExposureTime", None),
                    ("조리개 값", "FNumber", "FNumber"),
                    ("노출 프로그램", "ExposureProgram", "ExposureProgram"),
                    ("ISO 감도", "ISOSpeedRatings", None),
                    ("EXIF 버전", "ExifVersion", None),
                    ("촬영 시각", "DateTimeOriginal", None),
                    ("디지털화 시각", "DateTimeDigitized", None),
                    ("구성 요소", "ComponentsConfiguration", None),
                    ("픽셀당 압축 비트", "CompressedBitsPerPixel", None),
                    ("노출 보정", "ExposureBiasValue", None),
                    ("측광 모드", "MeteringMode", "MeteringMode"),
                    ("광원", "LightSource", "LightSource"),
                    ("플래시", "Flash", "Flash"),
                    ("초점거리 [mm]", "FocalLength", None),
                    ("사용자 주석", "UserComment", None),
                    ("하위초(촬영)", "SubSecTime", None),
                    ("하위초(원본)", "SubSecTimeOriginal", None),
                    ("하위초(디지털화)", "SubSecTimeDigitized", None),
                    ("FlashPix 버전", "FlashPixVersion", None),
                    ("색 공간", "ColorSpace", "ColorSpace"),
                    ("EXIF 이미지 가로", "ExifImageWidth", None),
                    ("EXIF 이미지 세로", "ExifImageLength", None),
                    ("상호운용성 오프셋", "InteroperabilityOffset", None),
                    ("센싱 방식", "SensingMethod", None),
                    ("파일 소스", "FileSource", None),
                    ("장면 유형", "SceneType", None),
                    ("CFA 패턴", "CFAPattern", None),
                    ("커스텀 렌더링", "CustomRendered", None),
                    ("노출 모드", "ExposureMode", None),
                    ("화이트 밸런스", "WhiteBalance", "WhiteBalance"),
                    ("환산 초점거리(35mm)", "FocalLengthIn35mmFilm", None),
                    ("장면 캡처 유형", "SceneCaptureType", "SceneCaptureType"),
                    ("게인 제어", "GainControl", None),
                    ("명암", "Contrast", None),
                    ("채도", "Saturation", None),
                    ("선명도", "Sharpness", None),
                    ("피사체 거리 범위", "SubjectDistanceRange", None),
                    ("시리얼 번호", "SerialNumber", None),
                    ("바디 시리얼", "BodySerialNumber", None),
                    ("렌즈 제조사", "LensMake", None),
                    ("렌즈 모델", "LensModel", None),
                    ("렌즈 시리얼", "LensSerialNumber", None),
                ]:
                    if key in exif_map_name2:
                        add_detail(label, exif_map_name2[key], mapkey)

                # GPS tab content
                gps_rows: Dict[str, Any] = {}
                if gps_exif2:
                    lat, lon, alt = self._parse_gps(gps_exif2)
                    if lat is not None and lon is not None:
                        gps_rows["위도"] = f"{lat:.6f}"
                        gps_rows["경도"] = f"{lon:.6f}"
                    if alt is not None:
                        gps_rows["고도"] = f"{alt:.2f} m"
                if gps_rows:
                    self._set_rows(self.gps_table, gps_rows)
                else:
                    self._set_rows(self.gps_table, {})
        except Exception as e:
            self._set_rows(self.props_table, {"오류": str(e)})

    def _set_rows(self, table: QTableWidget, rows: Dict[str, Any]) -> None:
        try:
            table.setRowCount(0)
            for k, v in rows.items():
                r = table.rowCount()
                table.insertRow(r)
                it0 = QTableWidgetItem(str(k))
                it1 = QTableWidgetItem(str(v))
                try:
                    it0.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    it1.setFlags(Qt.ItemFlag.ItemIsEnabled)
                except Exception:
                    pass
                table.setItem(r, 0, it0)
                table.setItem(r, 1, it1)
            try:
                table.resizeRowsToContents()
            except Exception:
                pass
        except Exception:
            pass

    def _parse_gps(self, gps: Dict[str, Any]) -> Tuple[float | None, float | None, float | None]:
        try:
            def _to_deg(x):
                try:
                    num, den = float(x[0]), float(x[1])
                    return num / den if den != 0 else 0.0
                except Exception:
                    return float(x)
            def _dms_to_deg(dms):
                d = _to_deg(dms[0]) if len(dms) > 0 else 0.0
                m = _to_deg(dms[1]) if len(dms) > 1 else 0.0
                s = _to_deg(dms[2]) if len(dms) > 2 else 0.0
                return d + (m / 60.0) + (s / 3600.0)
            lat = lon = None
            if 'GPSLatitude' in gps and 'GPSLatitudeRef' in gps:
                lat = _dms_to_deg(gps['GPSLatitude'])
                if str(gps['GPSLatitudeRef']).upper().startswith('S'):
                    lat = -lat
            if 'GPSLongitude' in gps and 'GPSLongitudeRef' in gps:
                lon = _dms_to_deg(gps['GPSLongitude'])
                if str(gps['GPSLongitudeRef']).upper().startswith('W'):
                    lon = -lon
            alt = None
            if 'GPSAltitude' in gps:
                try:
                    alt = _to_deg(gps['GPSAltitude'])
                except Exception:
                    alt = None
            return lat, lon, alt
        except Exception:
            return None, None, None

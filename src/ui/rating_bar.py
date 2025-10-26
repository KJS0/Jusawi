from __future__ import annotations

import os
from typing import Optional

from PyQt6.QtCore import Qt  # type: ignore[import]
from PyQt6.QtWidgets import QLabel, QPushButton  # type: ignore[import]

from ..services.ratings_store import get_image as ratings_get_image, upsert_image as ratings_upsert_image  # type: ignore


def create(owner) -> None:
    try:
        from PyQt6.QtWidgets import QWidget, QHBoxLayout  # type: ignore[import]
        owner._rating_flag_bar = QWidget(owner)
        bar_layout = QHBoxLayout(owner._rating_flag_bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(8)
        bar_layout.addStretch(1)
        try:
            # 상단 경계선만 유지, 배경색은 부모를 따름
            owner._rating_flag_bar.setStyleSheet("border-top: 1px solid #444;")
        except Exception:
            pass
        owner._stars = []
        for i in range(1, 6):
            lb = QLabel("☆", owner._rating_flag_bar)
            lb.setStyleSheet("color:#EAEAEA; font-size:16px;")
            lb.setCursor(Qt.CursorShape.PointingHandCursor)
            lb.mousePressEvent = (lambda e, n=i: owner._on_set_rating(n))  # type: ignore[assignment]
            owner._stars.append(lb)
            bar_layout.addWidget(lb)
        bar_layout.addSpacing(16)
        owner._flag_pick = QPushButton("✔", owner._rating_flag_bar)
        owner._flag_rej = QPushButton("✖", owner._rating_flag_bar)
        for b in (owner._flag_pick, owner._flag_rej):
            b.setStyleSheet("color:#EAEAEA; background:transparent; border:1px solid #555; padding:2px 6px;")
            bar_layout.addWidget(b)
        owner._flag_pick.clicked.connect(lambda: owner._on_set_flag('pick'))
        owner._flag_rej.clicked.connect(lambda: owner._on_set_flag('rejected'))
        bar_layout.addStretch(1)
        owner.main_layout.addWidget(owner._rating_flag_bar, 0)
    except Exception:
        pass


def register_shortcuts(owner) -> None:
    try:
        from PyQt6.QtGui import QKeySequence, QShortcut  # type: ignore[import]
        owner._rating_shortcuts = []
        # 숫자(0~5) 단축키를 다시 등록하여 별점 직접 설정
        for n in range(0, 6):
            sc = QShortcut(QKeySequence(str(n)), owner)
            sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
            sc.activated.connect(lambda n=n: owner._on_set_rating(n))
            owner._rating_shortcuts.append(sc)
        # 숫자 키패드(NumPad)도 동일하게 매핑
        try:
            for n in range(0, 6):
                key_name = f"Keypad{n}"
                kp_key = getattr(Qt.Key, key_name, None)
                if kp_key is None:
                    continue
                sc_kp = QShortcut(QKeySequence(kp_key), owner)
                sc_kp.setContext(Qt.ShortcutContext.ApplicationShortcut)
                sc_kp.activated.connect(lambda n=n: owner._on_set_rating(n))
                owner._rating_shortcuts.append(sc_kp)
        except Exception:
            pass
        owner._flag_sc_z = QShortcut(QKeySequence("Z"), owner)
        owner._flag_sc_z.setContext(Qt.ShortcutContext.ApplicationShortcut)
        owner._flag_sc_z.activated.connect(lambda: owner._on_set_flag('pick'))
        owner._flag_sc_x = QShortcut(QKeySequence("X"), owner)
        owner._flag_sc_x.setContext(Qt.ShortcutContext.ApplicationShortcut)
        owner._flag_sc_x.activated.connect(lambda: owner._on_set_flag('rejected'))
        owner._flag_sc_c = QShortcut(QKeySequence("C"), owner)
        owner._flag_sc_c.setContext(Qt.ShortcutContext.ApplicationShortcut)
        owner._flag_sc_c.activated.connect(lambda: owner._on_set_flag('unflagged'))
    except Exception:
        pass


def apply_theme(owner, is_light: bool) -> None:
    try:
        # 항상 다크 테마 스타일 유지
        try:
            if getattr(owner, "_rating_flag_bar", None):
                owner._rating_flag_bar.setStyleSheet("border-top: 1px solid #444;")
        except Exception:
            pass
        for lb in getattr(owner, "_stars", []):
            lb.setStyleSheet("color:#EAEAEA; font-size:16px;")
        if getattr(owner, '_flag_pick', None):
            owner._flag_pick.setStyleSheet("color:#EAEAEA; background:transparent; border:1px solid #555; padding:2px 6px;")
        if getattr(owner, '_flag_rej', None):
            owner._flag_rej.setStyleSheet("color:#EAEAEA; background:transparent; border:1px solid #555; padding:2px 6px;")
    except Exception:
        pass


def refresh(owner) -> None:
    try:
        if not hasattr(owner, "_rating_flag_bar") or owner._rating_flag_bar is None:
            return
        path = None
        try:
            if 0 <= owner.current_image_index < len(owner.image_files_in_dir):
                path = owner.image_files_in_dir[owner.current_image_index]
        except Exception:
            path = None
        # 세션 복원 등으로 디렉터리 목록이 아직 비어있는 경우 현재 파일 경로로 폴백
        if not path:
            try:
                cur = getattr(owner, "current_image_path", "")
                if cur:
                    path = cur
            except Exception:
                path = None
        rating = 0
        flag = "unflagged"
        if path:
            row = ratings_get_image(path) or {}
            if not row:
                # 기존 항목이 없으면 디폴트 표시만 하고 DB는 생성하지 않음
                rating = 0
                flag = "unflagged"
            else:
                try:
                    rating = int(row.get("rating", 0))
                except Exception:
                    rating = 0
                raw_flag = row.get("flag", "unflagged")
                try:
                    flag = str(raw_flag).strip().lower() if raw_flag is not None else "unflagged"
                except Exception:
                    flag = "unflagged"
        # 별 상태 반영
        try:
            for i, lb in enumerate(getattr(owner, "_stars", []), start=1):
                lb.setText("★" if i <= max(0, rating) else "☆")
        except Exception:
            pass
        # 플래그 버튼 상태(일관성 유지: 항상 다크 스타일)
        def _style(btn, active_color_bg: str, active_text: str = "#FFFFFF"):
            if not btn:
                return
            btn.setStyleSheet(f"color:#EAEAEA; background:{active_color_bg}; border:1px solid #555; padding:2px 6px;")
        def _style_inactive(btn):
            if not btn:
                return
            btn.setStyleSheet("color:#EAEAEA; background:transparent; border:1px solid #555; padding:2px 6px;")
        if flag == "pick":
            _style(owner._flag_pick, "#2E7D32")
            _style_inactive(owner._flag_rej)
        elif flag == "rejected":
            _style_inactive(owner._flag_pick)
            _style(owner._flag_rej, "#D32F2F", active_text="#FFFFFF")
        else:
            _style_inactive(owner._flag_pick)
            _style_inactive(owner._flag_rej)
    except Exception:
        pass


def set_rating(owner, n: int) -> None:
    try:
        if not (0 <= owner.current_image_index < len(owner.image_files_in_dir)):
            return
        path = owner.image_files_in_dir[owner.current_image_index]
        # 토글 동작: 현재 평점과 동일한 별을 누르면 0점으로 해제
        try:
            row_cur = ratings_get_image(path) or {}
            cur_rating = int(row_cur.get("rating", 0))
        except Exception:
            cur_rating = 0
        req = int(n)
        new_rating = 0 if req == cur_rating else req
        try:
            st = os.stat(path)
            mt = int(st.st_mtime)
        except Exception:
            mt = 0
        row = ratings_get_image(path) or {}
        if not row:
            ratings_upsert_image(path, mt, rating=new_rating, label=None, flag='unflagged')
        else:
            ratings_upsert_image(path, mt, rating=new_rating, label=row.get("label"), flag=row.get("flag", "unflagged"))
        try:
            owner.filmstrip.update_item_meta_by_path(path, rating=new_rating)
        except Exception:
            pass
        refresh(owner)
        # 이벤트 루프 다음 틱에도 한 번 더 반영(스타일/페인트 타이밍 보강)
        try:
            from PyQt6.QtCore import QTimer  # type: ignore[import]
            QTimer.singleShot(0, lambda: refresh(owner))
        except Exception:
            pass
    except Exception:
        pass


def set_flag(owner, f: str) -> None:
    try:
        if not (0 <= owner.current_image_index < len(owner.image_files_in_dir)):
            # 디렉터리 목록이 없더라도 현재 파일이 있으면 처리
            path = getattr(owner, "current_image_path", "")
            if not path:
                return
        else:
            path = owner.image_files_in_dir[owner.current_image_index]
        try:
            st = os.stat(path)
            mt = int(st.st_mtime)
        except Exception:
            mt = 0
        row = ratings_get_image(path) or {}
        # 동일 플래그를 누르면 unflagged로 토글
        cur_flag = (row.get("flag") if row else None) or 'unflagged'
        target = f
        if str(cur_flag).strip().lower() == str(f).strip().lower():
            target = 'unflagged'

        if target == 'rejected':
            cur_rating = int(row.get("rating", 0)) if row else 0
            if not row:
                ratings_upsert_image(path, mt, rating=cur_rating, label=None, flag='rejected')
            else:
                ratings_upsert_image(path, mt, rating=cur_rating, label=row.get("label"), flag='rejected')
            try:
                owner.filmstrip.update_item_meta_by_path(path, rating=cur_rating, flag='rejected')
            except Exception:
                pass
            refresh(owner)
            try:
                from PyQt6.QtCore import QTimer  # type: ignore[import]
                QTimer.singleShot(0, lambda: refresh(owner))
            except Exception:
                pass
        elif target == 'pick':
            cur_rating = int(row.get("rating", 0)) if row else 0
            ratings_upsert_image(path, mt, rating=cur_rating, label='Green', flag='pick')
            try:
                owner.filmstrip.update_item_meta_by_path(path, label='Green', flag='pick')
            except Exception:
                pass
            refresh(owner)
            try:
                from PyQt6.QtCore import QTimer  # type: ignore[import]
                QTimer.singleShot(0, lambda: refresh(owner))
            except Exception:
                pass
        elif target == 'unflagged':
            cur_rating = int(row.get("rating", 0)) if row else 0
            if cur_rating < 0:
                cur_rating = 0
            ratings_upsert_image(path, mt, rating=cur_rating, label=None, flag='unflagged')
            try:
                owner.filmstrip.update_item_meta_by_path(path, rating=cur_rating, label=None, flag='unflagged')
            except Exception:
                pass
            refresh(owner)
            try:
                from PyQt6.QtCore import QTimer  # type: ignore[import]
                QTimer.singleShot(0, lambda: refresh(owner))
            except Exception:
                pass
    except Exception:
        pass



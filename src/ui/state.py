from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TransformState:
    rotation_degrees: int = 0  # 0/90/180/270
    flip_horizontal: bool = False
    flip_vertical: bool = False

    def normalized(self) -> "TransformState":
        rot = int(self.rotation_degrees) % 360
        # 90도 배수로 정규화
        rot = (round(rot / 90.0) * 90) % 360
        return TransformState(rot, bool(self.flip_horizontal), bool(self.flip_vertical))


@dataclass(frozen=True)
class ViewerState:
    current_image_path: str | None
    image_files_in_dir: tuple[str, ...]
    current_image_index: int
    is_fullscreen: bool
    is_slideshow_active: bool
    transform: TransformState

    @staticmethod
    def snapshot_from(viewer) -> "ViewerState":
        return ViewerState(
            current_image_path=getattr(viewer, "current_image_path", None),
            image_files_in_dir=tuple(getattr(viewer, "image_files_in_dir", []) or ()),
            current_image_index=int(getattr(viewer, "current_image_index", -1)),
            is_fullscreen=bool(getattr(viewer, "is_fullscreen", False)),
            is_slideshow_active=bool(getattr(viewer, "is_slideshow_active", False)),
            transform=TransformState(
                int(getattr(viewer, "_tf_rotation", 0)) % 360,
                bool(getattr(viewer, "_tf_flip_h", False)),
                bool(getattr(viewer, "_tf_flip_v", False)),
            ).normalized(),
        )

    def restore_into(self, viewer) -> None:
        viewer.current_image_path = self.current_image_path
        viewer.image_files_in_dir = list(self.image_files_in_dir)
        viewer.current_image_index = int(self.current_image_index)
        viewer.is_fullscreen = bool(self.is_fullscreen)
        viewer.is_slideshow_active = bool(self.is_slideshow_active)
        ts = self.transform.normalized()
        viewer._tf_rotation = int(ts.rotation_degrees) % 360
        viewer._tf_flip_h = bool(ts.flip_horizontal)
        viewer._tf_flip_v = bool(ts.flip_vertical)



from __future__ import annotations


def apply_transform_to_view(owner) -> None:
    try:
        owner.image_display_area.set_transform_state(owner._tf_rotation, owner._tf_flip_h, owner._tf_flip_v)
    except Exception:
        pass
    owner.update_status_right()


def get_transform_status_text(owner) -> str:
    parts = []
    parts.append(f"{int(owner._tf_rotation)}°")
    if owner._tf_flip_h:
        parts.append("H")
    if owner._tf_flip_v:
        parts.append("V")
    return " ".join(parts)



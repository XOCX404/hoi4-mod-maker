"""Country 模式渲染: 国家颜色块 + 已分配国家间白边 + 选中国家红边 (覆盖白).

性能: 白边 mask 缓存到 canvas, country_rgb 不变就不重算 (只重算红边).
正确性:
  - 白边只在两侧都是"已分配国家"的 land 之间画 (跳过海洋/未分配 state).
  - 选中国家边界两侧都涂红 (完全覆盖白边, 不会出现红白夹杂).
"""

import numpy as np


def _compute_white_borders(country_rgb, assigned_mask):
    """算所有已分配国家间的白色边界 mask (H, W bool).

    边界 = 颜色变化处, 且边界两侧都属于"已分配国家".
    海洋 / 未分配 state 不参与 → 这些区域和邻居之间不画白边.
    """
    h, w = country_rgb.shape[:2]
    borders = np.zeros((h, w), dtype=bool)
    if assigned_mask is None:
        # 没传 mask, 退回到"所有颜色变化都画白" (兼容旧调用方)
        diff_v = (country_rgb[:-1] != country_rgb[1:]).any(axis=2)
        diff_h = (country_rgb[:, :-1] != country_rgb[:, 1:]).any(axis=2)
        borders[:-1, :] |= diff_v
        borders[1:, :]  |= diff_v
        borders[:, :-1] |= diff_h
        borders[:, 1:]  |= diff_h
        return borders

    # 上下方向: 像素 (y, x) 与 (y+1, x) 颜色不同, 且两个像素都 assigned
    diff_v = (country_rgb[:-1] != country_rgb[1:]).any(axis=2)
    a_v = assigned_mask[:-1] & assigned_mask[1:]
    border_v = diff_v & a_v
    borders[:-1, :] |= border_v
    borders[1:, :]  |= border_v

    # 左右方向
    diff_h = (country_rgb[:, :-1] != country_rgb[:, 1:]).any(axis=2)
    a_h = assigned_mask[:, :-1] & assigned_mask[:, 1:]
    border_h = diff_h & a_h
    borders[:, :-1] |= border_h
    borders[:, 1:]  |= border_h

    return borders


def _compute_red_borders(country_rgb, highlight_rgb):
    """算选中国家边界的 mask (H, W bool, 边界两侧都涂红, 自动覆盖白边)."""
    if highlight_rgb is None:
        return None
    h, w = country_rgb.shape[:2]
    hr, hg, hb = highlight_rgb
    is_hl = (
        (country_rgb[:, :, 0] == hr)
        & (country_rgb[:, :, 1] == hg)
        & (country_rgb[:, :, 2] == hb)
    )
    if not is_hl.any():
        return None

    borders = np.zeros((h, w), dtype=bool)
    # 上下: 一侧是高亮 + 另一侧不是高亮 → 这两个像素都涂红
    edge_v = is_hl[:-1] != is_hl[1:]
    borders[:-1, :] |= edge_v
    borders[1:, :]  |= edge_v
    # 左右
    edge_h = is_hl[:, :-1] != is_hl[:, 1:]
    borders[:, :-1] |= edge_h
    borders[:, 1:]  |= edge_h

    # 加宽 1 像素 (2 像素厚的红边)
    borders = (
        borders
        | np.roll(borders, 1, axis=0)
        | np.roll(borders, -1, axis=0)
        | np.roll(borders, 1, axis=1)
        | np.roll(borders, -1, axis=1)
    )
    return borders


def _get_white_borders_cached(canvas):
    """从 canvas cache 拿白边, 没有就算一次并缓存."""
    rgb = canvas._country_color_rgb
    mask = getattr(canvas, "_country_assigned_mask", None)
    cache = getattr(canvas, "_country_borders_cache", None)
    rgb_id = id(rgb)
    mask_id = id(mask) if mask is not None else 0
    if cache and cache[0] == (rgb_id, mask_id):
        return cache[1]
    white = _compute_white_borders(rgb, mask)
    canvas._country_borders_cache = ((rgb_id, mask_id), white)
    return white


def render(canvas) -> None:
    if canvas._country_color_rgb is not None:
        rgb = canvas._country_color_rgb
        canvas._display_buffer[:, :, 0] = rgb[:, :, 2]
        canvas._display_buffer[:, :, 1] = rgb[:, :, 1]
        canvas._display_buffer[:, :, 2] = rgb[:, :, 0]
        canvas._display_buffer[:, :, 3] = 255

        # 1. 白边 (从 cache 拿)
        white = _get_white_borders_cached(canvas)
        canvas._display_buffer[white, 0] = 255
        canvas._display_buffer[white, 1] = 255
        canvas._display_buffer[white, 2] = 255
        canvas._display_buffer[white, 3] = 255

        # 2. 红边 (覆盖白)
        red = _compute_red_borders(rgb, getattr(canvas, "_highlight_country_rgb", None))
        if red is not None:
            canvas._display_buffer[red, 0] = 0    # B
            canvas._display_buffer[red, 1] = 0    # G
            canvas._display_buffer[red, 2] = 255  # R
            canvas._display_buffer[red, 3] = 255
    else:
        canvas._display_buffer[:, :, 0] = 60
        canvas._display_buffer[:, :, 1] = 60
        canvas._display_buffer[:, :, 2] = 60
        canvas._display_buffer[:, :, 3] = 255


def partial_render(canvas, x0: int, y0: int, x1: int, y1: int) -> None:
    """局部重绘: 仍然用 cache 里的全图白边切片, 红边只算选区."""
    buf = canvas._display_buffer[y0:y1, x0:x1]
    if canvas._country_color_rgb is not None:
        rgb_full = canvas._country_color_rgb
        region = rgb_full[y0:y1, x0:x1]
        buf[:, :, 0] = region[:, :, 2]
        buf[:, :, 1] = region[:, :, 1]
        buf[:, :, 2] = region[:, :, 0]
        buf[:, :, 3] = 255

        white_full = _get_white_borders_cached(canvas)
        white = white_full[y0:y1, x0:x1]
        buf[white, 0] = 255
        buf[white, 1] = 255
        buf[white, 2] = 255
        buf[white, 3] = 255

        red = _compute_red_borders(region, getattr(canvas, "_highlight_country_rgb", None))
        if red is not None:
            buf[red, 0] = 0
            buf[red, 1] = 0
            buf[red, 2] = 255
            buf[red, 3] = 255
    else:
        buf[:, :, :] = [60, 60, 60, 255]

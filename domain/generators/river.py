"""
河流自动生成器 — 基于高度图的汇流模拟

算法参考：
- mapgen4 (redblobgames): downslope BFS + flow accumulation + mini-erosion
- Azgaar Fantasy Map Generator: flux 累积 + 阈值成河

流程：
1. 计算每个省份的平均高度
2. 建省份邻接图
3. BFS 从海洋向内陆建下坡树（每个省份指向最低邻居方向的海洋）
4. 从叶到根累积流量（降水 → 汇入低处）
5. 流量超阈值的省份边界画为河流
6. 根据流量大小分配河流宽度类型
7. 在源头加绿色标记，入海口加黄色标记
"""
import numpy as np
from collections import defaultdict
import heapq


# 河流类型常量（与 domain/managers/river.py 一致）
RIVER_SOURCE = 0       # 源头 (0,255,0)
RIVER_MARKER = 1       # 汇入点 (255,0,0)
RIVER_MOUTH = 2        # 入海口 (255,252,0)
RIVER_BG_SEA = 254     # 海洋背景
RIVER_BG_LAND = 255    # 陆地背景

# 宽度类型：流量越大越宽
# vanilla 只使用 [3,4,6,7,9,10,11]，索引 5 和 8 虽然 wiki 声明合法但 vanilla 不用
# 实测用 5/8 会触发 EXCEPTION_INT_DIVIDE_BY_ZERO 崩溃
RIVER_WIDTHS = [3, 4, 6, 7, 9, 10, 11]  # 7 档宽度，跳过 5 和 8


def generate_rivers(
    province_map: np.ndarray,
    height_map: np.ndarray,
    tile_map: np.ndarray,
    flow_threshold: float = 3.0,
    rain_per_province: float = 1.0,
) -> np.ndarray:
    """
    从高度图自动生成河流。

    参数:
        province_map: (H, W) int32, 省份 ID
        height_map: (H, W) uint8, 高度图（0=最低, 255=最高）
        tile_map: (H, W) uint8, 地块类型（LAND/SEA/LAKE）
        flow_threshold: 流量超过此值才画河流
        rain_per_province: 每个陆地省份的降水量

    返回:
        river_map: (H, W) uint8, 河流图（与现有格式兼容）
    """
    from data.constants import TILE_LAND, TILE_SEA, TILE_LAKE

    H, W = province_map.shape
    river_map = np.full((H, W), RIVER_BG_LAND, dtype=np.uint8)

    # 海洋区域填充海洋背景色
    sea_mask = (tile_map == TILE_SEA) | (tile_map == TILE_LAKE)
    river_map[sea_mask] = RIVER_BG_SEA

    # ── 1. 计算每个省份的平均高度和类型 ──
    max_pid = int(province_map.max())
    if max_pid <= 0:
        return river_map

    prov_height = np.zeros(max_pid + 1, dtype=np.float64)
    prov_count = np.zeros(max_pid + 1, dtype=np.int64)
    prov_is_land = np.zeros(max_pid + 1, dtype=bool)
    prov_is_water = np.zeros(max_pid + 1, dtype=bool)

    flat_pid = province_map.ravel()
    flat_height = height_map.ravel().astype(np.float64)
    flat_tile = tile_map.ravel()

    np.add.at(prov_height, flat_pid, flat_height)
    np.add.at(prov_count, flat_pid, 1)

    valid = prov_count > 0
    prov_height[valid] /= prov_count[valid]

    # 高度归一化：如果范围太窄（< 50），拉伸到 0-255 确保有足够的高度差
    land_heights = prov_height[valid & (prov_height > 0)]
    if len(land_heights) > 0:
        h_min, h_max = float(land_heights.min()), float(land_heights.max())
        if h_max - h_min < 50:
            # 拉伸到 0-255
            if h_max > h_min:
                prov_height[valid] = (prov_height[valid] - h_min) / (h_max - h_min) * 255.0
            # 水域高度强制为 0
            prov_height[~valid] = 0

    # 判断每个省份是陆地还是水域（多数像素决定）
    land_count = np.zeros(max_pid + 1, dtype=np.int64)
    water_count = np.zeros(max_pid + 1, dtype=np.int64)
    land_pixels = flat_tile == TILE_LAND
    water_pixels = (flat_tile == TILE_SEA) | (flat_tile == TILE_LAKE)
    np.add.at(land_count, flat_pid, land_pixels.astype(np.int64))
    np.add.at(water_count, flat_pid, water_pixels.astype(np.int64))
    prov_is_land = land_count > water_count
    prov_is_water = ~prov_is_land
    prov_is_water[0] = True  # ID 0 视为水

    # ── 2. 建省份邻接图 ──
    neighbors = _build_adjacency(province_map)

    # ── 3. BFS 建下坡树（从海洋向内陆） ──
    # 参考 mapgen4 assignDownslope: 优先队列 BFS
    downslope = np.full(max_pid + 1, -1, dtype=np.int32)  # 每个省份的下坡方向
    visited = np.zeros(max_pid + 1, dtype=bool)
    heap = []  # (height, pid)

    # 种子：所有水域省份
    for pid in range(1, max_pid + 1):
        if prov_is_water[pid] and prov_count[pid] > 0:
            visited[pid] = True
            downslope[pid] = -1  # 水域没有下坡
            heapq.heappush(heap, (prov_height[pid], pid))

    # BFS：从低处向高处扩展
    topo_order = []  # 拓扑排序（根在前，叶在后）
    while heap:
        _, current = heapq.heappop(heap)
        topo_order.append(current)
        for nb in neighbors.get(current, []):
            if not visited[nb] and prov_is_land[nb]:
                visited[nb] = True
                downslope[nb] = current  # nb 的水往 current 流
                heapq.heappush(heap, (prov_height[nb], nb))

    # ── 4. 从叶到根累积流量 ──
    flow = np.zeros(max_pid + 1, dtype=np.float64)
    for pid in range(1, max_pid + 1):
        if prov_is_land[pid] and visited[pid]:
            flow[pid] = rain_per_province

    # 反向遍历拓扑序（叶→根）
    for pid in reversed(topo_order):
        ds = downslope[pid]
        if ds > 0 and prov_is_land[pid]:
            flow[ds] += flow[pid]

    # ── 5. 画河流：在流量超阈值的省份边界上画线 ──
    # 找所有需要画河流的省份边界
    river_edges = []  # [(pid_from, pid_to, flow_value)]
    for pid in range(1, max_pid + 1):
        if flow[pid] >= flow_threshold and prov_is_land[pid]:
            ds = downslope[pid]
            if ds > 0:
                river_edges.append((pid, ds, flow[pid]))

    # 在像素级别画河流边界线
    _draw_river_boundaries(
        river_map, province_map, river_edges,
        flow, downslope, prov_is_water, flow_threshold,
    )

    return river_map


def _build_adjacency(province_map: np.ndarray) -> dict[int, set[int]]:
    """建省份邻接图（4-连通），用编码key + set去重，避免 np.unique(axis=0) 慢。"""
    max_pid = int(province_map.max())
    stride = max_pid + 1
    pair_set: set[int] = set()

    # 水平相邻
    left = province_map[:, :-1].ravel()
    right = province_map[:, 1:].ravel()
    diff_h = left != right
    a_h, b_h = left[diff_h], right[diff_h]
    valid = (a_h > 0) & (b_h > 0)
    lo = np.minimum(a_h[valid], b_h[valid]).astype(np.int64)
    hi = np.maximum(a_h[valid], b_h[valid]).astype(np.int64)
    pair_set.update((lo * stride + hi).tolist())

    # 垂直相邻
    top = province_map[:-1, :].ravel()
    bot = province_map[1:, :].ravel()
    diff_v = top != bot
    a_v, b_v = top[diff_v], bot[diff_v]
    valid = (a_v > 0) & (b_v > 0)
    lo = np.minimum(a_v[valid], b_v[valid]).astype(np.int64)
    hi = np.maximum(a_v[valid], b_v[valid]).astype(np.int64)
    pair_set.update((lo * stride + hi).tolist())

    # 解码
    neighbors: dict[int, set[int]] = defaultdict(set)
    for k in pair_set:
        a = int(k // stride)
        b = int(k % stride)
        neighbors[a].add(b)
        neighbors[b].add(a)

    return dict(neighbors)


def _draw_river_boundaries(
    river_map: np.ndarray,
    province_map: np.ndarray,
    river_edges: list[tuple[int, int, float]],
    flow: np.ndarray,
    downslope: np.ndarray,
    prov_is_water: np.ndarray,
    flow_threshold: float,
) -> None:
    """画 1px 宽的河流细线：每对省份取边界中点，用直线连接。"""
    H, W = province_map.shape
    if not river_edges:
        return

    max_pid = int(province_map.max())
    stride = max_pid + 1

    # ── 1. 预计算每对相邻省份的边界中点 ──
    # 收集所有边界像素，按省份对分组取中位数
    boundary_mid: dict[int, tuple[int, int]] = {}  # key → (mid_y, mid_x)
    boundary_all: dict[int, list[tuple[int, int]]] = {}

    # 水平边界
    diff_h = province_map[:, :-1] != province_map[:, 1:]
    ys_h, xs_h = np.where(diff_h)
    if len(ys_h) > 0:
        ah = province_map[ys_h, xs_h].astype(np.int64)
        bh = province_map[ys_h, xs_h + 1].astype(np.int64)
        kh = np.minimum(ah, bh) * stride + np.maximum(ah, bh)
        for i in range(len(kh)):
            k = int(kh[i])
            if k not in boundary_all:
                boundary_all[k] = []
            boundary_all[k].append((int(ys_h[i]), int(xs_h[i])))

    # 垂直边界
    diff_v = province_map[:-1, :] != province_map[1:, :]
    ys_v, xs_v = np.where(diff_v)
    if len(ys_v) > 0:
        av = province_map[ys_v, xs_v].astype(np.int64)
        bv = province_map[ys_v + 1, xs_v].astype(np.int64)
        kv = np.minimum(av, bv) * stride + np.maximum(av, bv)
        for i in range(len(kv)):
            k = int(kv[i])
            if k not in boundary_all:
                boundary_all[k] = []
            boundary_all[k].append((int(ys_v[i]), int(xs_v[i])))

    # 取每对的中点
    for k, pixels in boundary_all.items():
        mid_idx = len(pixels) // 2
        boundary_mid[k] = pixels[mid_idx]

    # ── 2. 预计算每个省份的质心 ──
    prov_cy = np.zeros(max_pid + 1, dtype=np.float64)
    prov_cx = np.zeros(max_pid + 1, dtype=np.float64)
    prov_count = np.zeros(max_pid + 1, dtype=np.int64)
    flat_pid = province_map.ravel()
    ys_all = np.repeat(np.arange(H), W)
    xs_all = np.tile(np.arange(W), H)
    np.add.at(prov_cy, flat_pid, ys_all.astype(np.float64))
    np.add.at(prov_cx, flat_pid, xs_all.astype(np.float64))
    np.add.at(prov_count, flat_pid, 1)
    valid = prov_count > 0
    prov_cy[valid] /= prov_count[valid]
    prov_cx[valid] /= prov_count[valid]

    # ── 3. 沿流向画 1px 细线 ──
    max_flow = max((f for _, _, f in river_edges), default=1.0)
    flow_scale = max(max_flow * 0.8, 1.0)

    edge_set = set()
    for pid_from, pid_to, f in river_edges:
        lo, hi = min(pid_from, pid_to), max(pid_from, pid_to)
        edge_set.add(lo * stride + hi)

    def _draw_orthogonal(y0, x0, y1, x1, val):
        """画严格正交的折线（先水平后垂直），所有像素只在上/下/左/右连接，
        永远不会有对角线像素相邻。HOI4 要求河流像素必须正交连接。"""
        # 水平段：从 (y0, x0) 到 (y0, x1)
        if x0 != x1:
            step = 1 if x1 > x0 else -1
            for x in range(x0, x1 + step, step):
                if 0 <= y0 < H and 0 <= x < W:
                    river_map[y0, x] = val
        # 垂直段：从 (y0, x1) 到 (y1, x1)
        if y0 != y1:
            step = 1 if y1 > y0 else -1
            for y in range(y0, y1 + step, step):
                if 0 <= y < H and 0 <= x1 < W:
                    river_map[y, x1] = val

    # 沿着省份边界画河流（只画边界中点附近一小段，不穿过 province 内部）
    # vanilla 河流就是沿省份边界细线
    for pid_from, pid_to, f in river_edges:
        ratio = min(f / flow_scale, 1.0)
        width_idx = int(ratio * (len(RIVER_WIDTHS) - 1))
        river_type = RIVER_WIDTHS[width_idx]

        lo, hi = min(pid_from, pid_to), max(pid_from, pid_to)
        # 取边界上所有像素，画其中一段（不穿过 province 内部）
        boundary_pixels = boundary_all.get(lo * stride + hi, [])
        if not boundary_pixels:
            continue

        # 只画边界中点附近的几个像素（保持 1 像素宽 + 正交）
        # 取边界像素列表的中间一段（10% ~ 50% 长度）
        n = len(boundary_pixels)
        if n == 0:
            continue
        seg_len = max(2, min(n, int(n * 0.3)))
        start_idx = (n - seg_len) // 2
        segment = boundary_pixels[start_idx:start_idx + seg_len]

        # 把段内的相邻像素用正交方式连起来
        prev = segment[0]
        if 0 <= prev[0] < H and 0 <= prev[1] < W:
            river_map[prev[0], prev[1]] = river_type
        for cur in segment[1:]:
            _draw_orthogonal(prev[0], prev[1], cur[0], cur[1], river_type)
            prev = cur

    # ── 4. 标记源头和入海口 ──
    has_upstream = np.zeros(len(flow), dtype=bool)
    for pid in range(1, len(downslope)):
        ds = downslope[pid]
        if ds > 0 and flow[pid] >= flow_threshold:
            has_upstream[ds] = True

    for pid in range(1, len(flow)):
        if flow[pid] >= flow_threshold and not has_upstream[pid] and not prov_is_water[pid]:
            ds = downslope[pid]
            if ds > 0:
                lo, hi = min(pid, ds), max(pid, ds)
                pixel = boundary_mid.get(lo * stride + hi)
                if pixel:
                    river_map[pixel[0], pixel[1]] = RIVER_SOURCE

    marked_mouths = set()
    for pid_from, pid_to, f in river_edges:
        if prov_is_water[pid_from] or prov_is_water[pid_to]:
            land_pid = pid_to if prov_is_water[pid_from] else pid_from
            water_pid = pid_from if prov_is_water[pid_from] else pid_to
            if land_pid not in marked_mouths:
                lo, hi = min(land_pid, water_pid), max(land_pid, water_pid)
                pixel = boundary_mid.get(lo * stride + hi)
                if pixel:
                    river_map[pixel[0], pixel[1]] = RIVER_MOUTH
                    marked_mouths.add(land_pid)


def _mark_single_pixel(
    river_map: np.ndarray,
    province_map: np.ndarray,
    pid_a: int, pid_b: int,
    marker_type: int,
) -> None:
    """在 pid_a 和 pid_b 的边界上标记一个像素。"""
    H, W = province_map.shape
    # 快速扫描找一个边界像素
    # 优化：只在 pid_a 的 bounding box 里找
    ys, xs = np.where(province_map == pid_a)
    if len(ys) == 0:
        return
    y_min, y_max = ys.min(), ys.max()
    x_min, x_max = xs.min(), xs.max()

    for y in range(max(0, y_min), min(H - 1, y_max + 1)):
        for x in range(max(0, x_min), min(W - 1, x_max + 1)):
            if province_map[y, x] != pid_a:
                continue
            # 检查 4 邻居是否有 pid_b
            for dy, dx in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                ny, nx = y + dy, x + dx
                if 0 <= ny < H and 0 <= nx < W and province_map[ny, nx] == pid_b:
                    river_map[y, x] = marker_type
                    return

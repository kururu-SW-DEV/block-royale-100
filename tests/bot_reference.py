"""
테스트 전용 기준 구현 (봇 두뇌의 최적화 전/단순한 버전). 게임 코드에서는 쓰지 않고, 빠른 구현과 결과가 같은지 대조하는 테스트가 씀.
 - _collide / _drop / SHAPE_SPAN: 예전 단순 구현 (하드 드롭 위치 계산 대조용)
 - t_placements_ref: 최적화 전 T-스핀 탐색 (스폰 위치에서 전체 BFS)
 - board_eval_ref: 최적화 전 보드 평가
"""
from collections import deque

from block_engine import JLSTZ_KICKS
from bot_brain import BITS, FULL, H, PARAMS, ROW_TRANS, SHAPES, TSD_ROW, W, _top, _tspin_kind
from config import SPAWN_Y

SHAPE_SPAN = {p: [(min(dx for dx, _ in s), max(dx for dx, _ in s)) for s in rots] for p, rots in SHAPES.items()}


def _collide(rows, cells, px, py):
    for dx, dy in cells:
        x = px + dx
        y = py + dy
        if x < 0 or x >= W or y >= H:
            return True
        if y >= 0 and (rows[y] >> x) & 1:
            return True
    return False


def _drop(rows, cells, px, py):
    """py에서 한 칸씩 내려 막히기 직전 y를 돌려줌 (_collide를 반복 호출하던 것과 같은 결과를 호출 단계 없이 계산: 봇 계산에서 가장 많이 불리는 함수)"""
    while True:
        ny = py + 1
        for dx, dy in cells:
            x = px + dx
            y = ny + dy
            if x < 0 or x >= W or y >= H or (y >= 0 and (rows[y] >> x) & 1):
                return py
        py = ny


def t_placements_ref(rows):
    """(기준 구현) T 블록의 도달 가능한 모든 고정 자리와 입력 경로: [(rot, px, py, kind, path)]
    path는 'L','R','D','cw','ccw' 입력 목록(마지막 하드 드롭은 따로)."""
    cells_by_rot = SHAPES["T"]
    sx, sy, sr = 3, SPAWN_Y, 0
    if _collide(rows, cells_by_rot[sr], sx, sy):
        return []
    start = (sx, sy, sr, 0)
    parent = {start: None}
    q = deque([start])
    locks = []
    while q:
        st = q.popleft()
        x, y, r, f = st
        cells = cells_by_rot[r]
        resting = _collide(rows, cells, x, y + 1)
        if resting:
            locks.append(st)
        for dx, name in ((-1, "L"), (1, "R")):
            if not _collide(rows, cells, x + dx, y):
                ns = (x + dx, y, r, 0)
                if ns not in parent:
                    parent[ns] = (st, name)
                    q.append(ns)
        if not resting:
            ns = (x, y + 1, r, 0)
            if ns not in parent:
                parent[ns] = (st, "D")
                q.append(ns)
        for cw, name in ((True, "cw"), (False, "ccw")):
            nr = (r + 1) % 4 if cw else (r - 1) % 4
            for ki, (kx, ky) in enumerate(JLSTZ_KICKS.get((r, nr), [(0, 0)])):
                tx, ty = x + kx, y - ky
                if not _collide(rows, cells_by_rot[nr], tx, ty):
                    ns = (tx, ty, nr, 2 if ki == 4 else 1)
                    if ns not in parent:
                        parent[ns] = (st, name)
                        q.append(ns)
                    break
    best = {}
    for st in locks:
        x, y, r, f = st
        if y < 0:
            continue
        kind = _tspin_kind(rows, x, y, r, f)
        key = tuple(sorted((x + dx, y + dy) for dx, dy in cells_by_rot[r]))
        rank = 2 if kind == "full" else (1 if kind == "mini" else 0)
        if key not in best or rank > best[key][0]:
            path = []
            cur = st
            while parent[cur] is not None:
                cur, act = parent[cur][0], parent[cur][1]
                path.append(act)
            path.reverse()
            best[key] = (rank, r, x, y, kind, path)
    return [(r, x, y, kind, path) for _rank, r, x, y, kind, path in best.values() if y >= 0]        # 숨김 구역에 걸치는 자리는 쓰지 않음 (_apply가 보이는 줄만 다룸)


def board_eval_ref(rows, incoming, attack_style, i_soon=True, t_soon=False, top=None):
    """놓은 뒤 보드의 좋고 나쁨 (클수록 좋음). top: 가장 위 블록이 있는 행(모르면 None)"""
    if top is None:
        top = _top(rows)
    seen = 0
    holes = 0
    heights = [0] * W
    row_tr = 0
    for y in range(top, H):
        r = rows[y]
        new = r & ~seen
        if new:
            hgt = H - y
            for x in BITS[new]:
                heights[x] = hgt
        holes += (seen & ~r & FULL).bit_count()
        seen |= r
        row_tr += ROW_TRANS[r]
    col_tr = (rows[H - 1] ^ FULL).bit_count()
    for y in range(top - 1 if top > 0 else 0, H - 1):
        d = rows[y] ^ rows[y + 1]
        if d:
            col_tr += d.bit_count()
    wells = 0.0
    for c in range(W):
        left = heights[c - 1] if c > 0 else 99
        right = heights[c + 1] if c < W - 1 else 99
        d = (left if left < right else right) - heights[c]
        if d > 0:
            w = d * (d + 1) / 2.0
            if attack_style and c == W - 1:
                w *= PARAMS["edge_well"]      # 오른쪽 끝 우물은 쿼드용으로 남겨 둠
            wells += w
    max_h = H - top
    score = 0.0
    if attack_style and incoming == 0 and max_h <= 12:       # 위협이 없을 때만 쿼드/T-스핀을 준비 (쓰레기가 오거나 높이 쌓이면 안전 운영)
        ready = 0                                            # 오른쪽 끝 한 칸만 비고 나머지가 찬 줄: I 블록 하나로 쿼드를 만들 수 있는 준비된 줄
        target = FULL ^ (1 << (W - 1))
        for y in range(top, H):
            if rows[y] == target:
                ready += 1
        score += PARAMS["ready"] * min(ready, 4) * (1.0 if i_soon else PARAMS["no_i"])   # 곧 나올 I 블록이 안 보이면 우물 준비를 덜 밀어붙임
        for y in range(top if top > 1 else 1, H - 1):            # T-스핀 더블 자리: 3칸 빈 줄 + 그 아래 한 칸 우물 + 위쪽 처마
            c = TSD_ROW.get(rows[y])
            if c is not None and rows[y + 1] == FULL ^ (1 << (c + 1)):
                if rows[y - 1] & ((1 << c) | (1 << (c + 2))):
                    score += PARAMS["tslot"] * (1.0 if t_soon else 0.4)
                else:
                    score += PARAMS["tslot_partial"] * (1.0 if t_soon else 0.4)   # 처마만 아직 없는 절반 완성 자리
                break
    P = PARAMS
    score = score - P["w_row"] * row_tr - P["w_col"] * col_tr - P["w_hole"] * holes - P["w_well"] * wells
    eff = max_h + incoming
    dh = P["danger_h"]
    if eff > dh:
        score -= (eff - dh) ** 2 * P["w_danger"]       # 쌓인 높이 + 곧 올라올 쓰레기가 위험선을 넘으면 크게 감점
    return score

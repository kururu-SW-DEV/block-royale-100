"""
Block Royale 100 - AI 두뇌 (탐색형 배치 계획기)
보드를 행 비트마스크(정수 20개)로 다뤄 빠르게 평가하고, 다음 블록/홀드까지 미리 내다보며 최선의 배치를 고릅니다.
 - 평가: El-Tetris 계열 특징(랜딩 높이, 지운 칸, 행/열 전환, 구멍, 우물) + 공격 보상(줄 수, T-스핀, B2B, 콤보, 퍼펙트 클리어) + 위험(쌓인 높이 + 들어올 쓰레기)
 - 탐색: 홀드 유무 x 모든 배치 -> 상위 후보만 다음 블록으로 확장 (깊이 1~3)
 - T-스핀: T 블록은 실제 SRS 회전/킥을 따라 도달 가능한 자리를 너비 우선 탐색으로 찾아 T-스핀 클리어를 계획
"""

from collections import deque

from config import (
    BOARD_WIDTH, BOARD_HEIGHT, SPAWN_Y, TETROMINOES,
    GARBAGE_ATTACK_TABLE, COMBO_BONUS, TSPIN_ATTACK_TABLE, TSPIN_MINI_ATTACK_TABLE, PERFECT_CLEAR_ATTACK,
)
from block_engine import JLSTZ_KICKS

W = BOARD_WIDTH
H = BOARD_HEIGHT
FULL = (1 << W) - 1

SHAPES = {p: [list(shape) for shape in rots] for p, rots in TETROMINOES.items()}
_MIN_DY = {p: [min(dy for _, dy in sh) for sh in rots] for p, rots in SHAPES.items()}

# 행 전환 수 표: 양쪽 벽을 채워진 것으로 보고 이웃한 칸이 다른 횟수
ROW_TRANS = []
for _r in range(1 << W):
    _ext = (1 << (W + 1)) | (_r << 1) | 1
    ROW_TRANS.append(((_ext ^ (_ext >> 1)) & FULL).bit_count() if _r else 0)      # 빈 줄은 세지 않음

# 조정 가능한 가중치 (공격 성향)
PARAMS = {
    # 기본 평가(El-Tetris 계열)  [tools/tune_bot.py 자체 대전으로 튜닝한 값]
    "w_row": 2.635, "w_col": 23.66, "w_hole": 7.356, "w_well": 2.747, "w_danger": 0.91, "danger_h": 11, "land": 1.325,
    # 공격 성향
    "b2b_chain": 0, "safe_h": 6, "ready": 22.34, "hold_i": 6.346, "land_atk": 0.661, "atk": 9.968, "single_pen": 5.678, "edge_well": 0.071, "combo": 5.694, "b2b": 6.36, "defend": 7.462, "tslot": 134.312, "no_i": 0.42, "low": 7,
    "tslot_partial": 0.0, "hold_t": 0.0,
}

# 비트마스크 -> 켜진 비트 위치 목록
BITS = [tuple(i for i in range(W) if (m >> i) & 1) for m in range(1 << W)]

# 블록 모양별 미리 계산: 서로 다른 방향만(같은 모양은 한 번), 열마다 가장 아래 칸, 가장 위 칸
ORIENTS = {}
for _p, _rots in SHAPES.items():
    _seen = set()
    _lst = []
    for _rot, _cells in enumerate(_rots):
        _mx = min(dx for dx, _ in _cells)
        _my = min(dy for _, dy in _cells)
        _norm = tuple(sorted((dx - _mx, dy - _my) for dx, dy in _cells))
        if _norm in _seen:
            continue
        _seen.add(_norm)
        _bottom = {}
        for dx, dy in _cells:
            _bottom[dx] = max(_bottom.get(dx, -1), dy)
        _lo, _hi = min(dx for dx, _ in _cells), max(dx for dx, _ in _cells)
        _lst.append((_rot, _lo, _hi, tuple(_bottom.items()), _cells, _my))
    ORIENTS[_p] = _lst

# T-스핀 더블 자리(가로 3칸이 빈 줄): 줄 값 -> 빈 3칸의 시작 열
TSD_ROW = {}
for _c in range(W - 2):
    TSD_ROW[FULL ^ (7 << _c)] = _c

# 프레임 하나에서 탐색에 쓸 수 있는 시간(초). 100명이 한꺼번에 생각해도 화면이 끊기지 않도록 공유
_budget = [0.0]


def begin_frame(seconds):
    _budget[0] = seconds


def budget_left():
    return _budget[0]


def spend(seconds):
    _budget[0] -= seconds


def rows_from_grid(grid):
    return [sum(1 << x for x, c in enumerate(row) if c is not None) for row in grid]


def _top(rows):
    t = 0
    while t < H and not rows[t]:
        t += 1
    return t


def _tops(rows, top):
    """열마다 가장 위에 있는 블록의 행 번호(없으면 H)"""
    tops = [H] * W
    seen = 0
    for y in range(top, H):
        r = rows[y]
        new = r & ~seen
        if new:
            for x in BITS[new]:
                tops[x] = y
            seen |= r
            if seen == FULL:
                break
    return tops


def simple_placements(rows, piece, tops=None, top=None):
    """하드 드롭으로 놓을 수 있는 자리들: [(rot, px, py)] (같은 모양은 한 번만)"""
    if tops is None:
        tops = _tops(rows, _top(rows) if top is None else top)
    out = []
    for rot, lo, hi, cols, _cells, _my in ORIENTS[piece]:
        for px in range(-lo, W - hi):
            py = 99
            for dx, dyb in cols:
                v = tops[px + dx] - 1 - dyb
                if v < py:
                    py = v
            if py >= 0:
                out.append((rot, px, py))
    return out


def _tspin_kind(rows, x, y, rot, flag):
    """엔진의 T-스핀 판정(3-코너 + 앞쪽 코너)과 동일. flag: 0 회전 아님 / 1 회전 / 2 5번째 킥 회전"""
    if flag == 0:
        return None
    cx, cy = x + 1, y + 1

    def occ(px, py):
        if px < 0 or px >= W or py >= H:
            return True
        if py < 0:
            return False                                         # 위쪽 숨김 구역은 비어 있음 (엔진의 T-스핀 판정과 같은 규칙)
        return (rows[py] >> px) & 1 == 1

    tl, tr = occ(cx - 1, cy - 1), occ(cx + 1, cy - 1)
    bl, br = occ(cx - 1, cy + 1), occ(cx + 1, cy + 1)
    if tl + tr + bl + br < 3:
        return None
    front = {0: (tl, tr), 1: (tr, br), 2: (bl, br), 3: (tl, bl)}[rot % 4]
    if all(front) or flag == 2:
        return "full"
    return "mini"


# T 블록: 회전(r)과 왼쪽 위 x마다 줄별 비트마스크를 미리 계산 (칸마다 파이썬 루프를 도는 충돌 검사 대신 줄 단위 AND 한 번). 벽 밖이면 None
_T_ROT_CELLS = SHAPES["T"]
_T_MASKS = [[None] * (W + 8) for _ in range(4)]            # _T_MASKS[r][x + 4] = ((dy, mask), ...)
for _r in range(4):
    for _x in range(-4, W + 4):
        if all(0 <= _x + _dx < W for _dx, _dy in _T_ROT_CELLS[_r]):
            _rowm = {}
            for _dx, _dy in _T_ROT_CELLS[_r]:
                _rowm[_dy] = _rowm.get(_dy, 0) | (1 << (_x + _dx))
            _T_MASKS[_r][_x + 4] = tuple(sorted(_rowm.items()))
_T_MAXDY = max(dy for r in range(4) for _dx, dy in _T_ROT_CELLS[r])
_KICK_CW = [[(r + 1) % 4, JLSTZ_KICKS.get((r, (r + 1) % 4), [(0, 0)])] for r in range(4)]
_KICK_CCW = [[(r - 1) % 4, JLSTZ_KICKS.get((r, (r - 1) % 4), [(0, 0)])] for r in range(4)]


def t_placements(rows):
    """T 블록의 도달 가능한 모든 고정 자리와 입력 경로: [(rot, px, py, kind, path)] (최적화 전 기준 구현은 tests/bot_reference.py의 t_placements_ref)
    - 충돌 검사를 줄 비트마스크로 함
    - 스택 위가 충분히 비어 있으면 그 허공(어디서나 똑같이 움직일 수 있는 구간)은 건너뛰고 스택 가까이에서 탐색을 시작함 (경로 앞에 'D'를 붙임)"""
    masks = _T_MASKS
    top0 = _top(rows)
    y0 = SPAWN_Y
    air = top0 - (_T_MAXDY + 4) - SPAWN_Y                # 스택 위쪽 여유: 모양 높이 + 킥 이동폭(±2) + 여유
    if air > 0:
        y0 = SPAWN_Y + air
    sx, sy, sr = 3, y0, 0
    m0 = masks[sr][sx + 4]

    def hit(r, x, y):
        m = masks[r][x + 4] if -4 <= x < W + 4 else None
        if m is None:
            return True
        for dy, mk in m:
            yy = y + dy
            if yy >= H or (yy >= 0 and rows[yy] & mk):
                return True
        return False

    if hit(sr, sx, sy):
        return []
    start = (sx, sy, sr, 0)
    parent = {start: None}
    q = deque([start])
    locks = []
    while q:
        st = q.popleft()
        x, y, r, f = st
        resting = hit(r, x, y + 1)
        if resting:
            locks.append(st)
        if not hit(r, x - 1, y):
            ns = (x - 1, y, r, 0)
            if ns not in parent:
                parent[ns] = (st, "L")
                q.append(ns)
        if not hit(r, x + 1, y):
            ns = (x + 1, y, r, 0)
            if ns not in parent:
                parent[ns] = (st, "R")
                q.append(ns)
        if not resting:
            ns = (x, y + 1, r, 0)
            if ns not in parent:
                parent[ns] = (st, "D")
                q.append(ns)
        for nr, kicks in (_KICK_CW[r], _KICK_CCW[r]):
            name = "cw" if nr == (r + 1) % 4 else "ccw"
            for ki, (kx, ky) in enumerate(kicks):
                tx, ty = x + kx, y - ky
                if not hit(nr, tx, ty):
                    ns = (tx, ty, nr, 2 if ki == 4 else 1)
                    if ns not in parent:
                        parent[ns] = (st, name)
                        q.append(ns)
                    break
    prefix = ["D"] * (y0 - SPAWN_Y)
    best = {}
    for st in locks:
        x, y, r, f = st
        if y < 0:
            continue
        kind = _tspin_kind(rows, x, y, r, f)
        key = tuple(sorted((x + dx, y + dy) for dx, dy in _T_ROT_CELLS[r]))
        rank = 2 if kind == "full" else (1 if kind == "mini" else 0)
        if key not in best or rank > best[key][0]:
            path = []
            cur = st
            while parent[cur] is not None:
                cur, act = parent[cur][0], parent[cur][1]
                path.append(act)
            path.reverse()
            best[key] = (rank, r, x, y, kind, prefix + path)
    return [(r, x, y, kind, path) for _rank, r, x, y, kind, path in best.values() if y >= 0]


def _apply(rows, piece, rot, px, py, top=None):
    """블록을 놓고 줄을 지운 결과: (새 행들, 지운 줄 수, 지워진 줄에 속한 블록 칸 수, 랜딩 높이, 새 최상단 행)"""
    if top is None:
        top = _top(rows)
    cells = SHAPES[piece][rot]
    new = rows[:]
    ysum = 0
    ymin = H
    for dx, dy in cells:
        y = py + dy
        new[y] |= 1 << (px + dx)
        ysum += y
        if y < ymin:
            ymin = y
    landing = H - ysum / 4.0
    if ymin < top:
        top = ymin
    if FULL in new:
        fullset = {i for i, r in enumerate(new) if r == FULL}
        eroded = sum(1 for dx, dy in cells if (py + dy) in fullset)
        n = len(fullset)
        new = [0] * n + [r for r in new if r != FULL]
        t = top
        while t < H and not new[t]:
            t += 1
        return new, n, eroded, landing, t
    return new, 0, 0, landing, top


def _attack(cleared, kind, combo_after, b2b_before, is_pc):
    if kind == "full":
        base = TSPIN_ATTACK_TABLE.get(cleared, 2)
    elif kind == "mini":
        base = TSPIN_MINI_ATTACK_TABLE.get(cleared, 0)
    else:
        base = GARBAGE_ATTACK_TABLE.get(cleared, 0)
    difficult = (cleared == 4) or kind is not None
    if difficult and b2b_before:
        v = int(b2b_before)                                  # B2B 상태: 0 = 없음, 그 뒤 값 = 지금까지 이어진 연쇄 + 1 (b2b_chain 가중치가 꺼져 있으면 True = 1)
        base += 1 + (v >= 4) + (v >= 8)                      # 엔진과 같은 단계 보너스: 연쇄 1~3 = +1, 4~7 = +2, 8 이상 = +3
    if is_pc:
        base += PERFECT_CLEAR_ATTACK
    return base + COMBO_BONUS[min(combo_after, len(COMBO_BONUS) - 1)], difficult


WELL_VAL = [d * (d + 1) / 2.0 for d in range(H + 2)]       # 우물 깊이 d의 감점 d*(d+1)/2 (식과 같은 값을 미리 계산)
_READY_TARGET = FULL ^ (1 << (W - 1))


def board_eval(rows, incoming, attack_style, i_soon=True, t_soon=False, top=None):
    """놓은 뒤 보드의 좋고 나쁨 (클수록 좋음). top: 가장 위 블록이 있는 행(모르면 None).
    tests/bot_reference.py의 board_eval_ref와 같은 값을 내되 줄 훑기를 한 번으로 합치고 우물 계산을 표로 함"""
    if top is None:
        top = _top(rows)
    seen = 0
    holes = 0
    heights = [0] * W
    row_tr = 0
    col_tr = 0
    prev = 0
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
        if y > top or top > 0:                                   # 세로 전환: 이웃한 두 줄의 XOR (맨 위 블록 줄은 위의 빈 줄과 비교, 보드가 꽉 찬 경우만 제외)
            col_tr += (prev ^ r).bit_count()
        prev = r
    col_tr += (prev ^ FULL).bit_count() if top < H else (FULL ^ 0).bit_count()
    wells = 0.0
    hp = heights
    for c in range(W):
        left = hp[c - 1] if c > 0 else 99
        right = hp[c + 1] if c < W - 1 else 99
        d = (left if left < right else right) - hp[c]
        if d > 0:
            w = WELL_VAL[d]
            if attack_style and c == W - 1:
                w *= PARAMS["edge_well"]      # 오른쪽 끝 우물은 쿼드용으로 남겨 둠
            wells += w
    max_h = H - top
    score = 0.0
    if attack_style and incoming == 0 and max_h <= 12:       # 위협이 없을 때만 쿼드/T-스핀을 준비 (쓰레기가 오거나 높이 쌓이면 안전 운영)
        ready = rows[top:].count(_READY_TARGET)       # 오른쪽 끝 한 칸만 비고 나머지가 찬 줄: I 블록 하나로 쿼드를 만들 수 있는 준비된 줄
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


# ---- 증분 평가: 줄이 지워지지 않는 하드 드롭 배치는 부모 보드의 특징(구멍/전환/높이)을 한 번만 구해 두고, 놓인 몇 줄/몇 열만 고쳐서 board_eval과 같은 값을 냄
# 블록 모양(piece, rot)과 왼쪽 위 x(px)마다 미리 계산: 건드리는 줄별 비트마스크, 건드리는 열별 (x, 가장 위 dy, 칸 수), dy 합, 가장 위 dy
_PLACE = {}
for _p, _rots in SHAPES.items():
    _tab = {}
    for _rot, _lo, _hi, _c, _cells, _my in ORIENTS[_p]:
        for _px in range(-_lo, W - _hi):
            _rm, _cm = {}, {}
            for _dx, _dy in _cells:
                _rm[_dy] = _rm.get(_dy, 0) | (1 << (_px + _dx))
                _t = _cm.get(_px + _dx)
                _cm[_px + _dx] = (min(_t[0], _dy), _t[1] + 1) if _t else (_dy, 1)
            _tab[(_rot, _px)] = (tuple(sorted(_rm.items())), tuple((x, v[0], v[1]) for x, v in sorted(_cm.items())),
                                 sum(dy for _, dy in _cells), min(dy for _, dy in _cells))
    _PLACE[_p] = _tab


class _Ctx:
    """부모 보드 하나의 특징 (후보 수십 개가 함께 씀)"""
    __slots__ = ("rows", "top", "tops", "heights", "holes", "row_tr", "col_tr", "ready", "tsd")

    def __init__(self, rows, top, tops):
        self.rows, self.top, self.tops = rows, top, tops
        self.heights = [H - t for t in tops]
        seen = 0
        holes = row_tr = col_tr = 0
        prev = 0
        for y in range(top, H):
            r = rows[y]
            holes += (seen & ~r & FULL).bit_count()
            seen |= r
            row_tr += ROW_TRANS[r]
            if y > top or top > 0:
                col_tr += (prev ^ r).bit_count()
            prev = r
        col_tr += (prev ^ FULL).bit_count() if top < H else FULL.bit_count()
        self.holes, self.row_tr, self.col_tr = holes, row_tr, col_tr
        self.ready = rows[top:].count(_READY_TARGET)
        self.tsd = any(rows[y] in TSD_ROW for y in range(top if top > 1 else 1, H - 1))      # T-스핀 더블 자리 후보 줄이 있는가 (없으면 자리 검사를 건너뜀)


def _quick_delta(ctx, piece, rot, px, py, incoming, attack_style, i_soon, t_soon):
    """줄이 지워지지 않는 하드 드롭 배치의 (board_eval 값, dy 합). 줄이 지워지면 None (호출한 쪽이 기존 방식으로 계산).
    정수 특징(구멍, 행/열 전환, 높이)은 정확히 같고 부동소수점 식도 board_eval과 같은 순서로 계산해 값이 완전히 같음"""
    rowdefs, cols, ysum_base, mindy = _PLACE[piece][(rot, px)]
    rows = ctx.rows
    row_tr = ctx.row_tr
    ready = ctx.ready
    new_vals = []
    for dy, mk in rowdefs:
        old = rows[py + dy]
        nv = old | mk
        if nv == FULL:
            return None
        row_tr += ROW_TRANS[nv] - ROW_TRANS[old]
        ready += (nv == _READY_TARGET) - (old == _READY_TARGET)
        new_vals.append((py + dy, nv))
    holes = ctx.holes
    col_tr = ctx.col_tr
    tops = ctx.tops
    hp = ctx.heights[:]
    for x, md, cnt in cols:
        yt = py + md
        gap = tops[x] - yt - cnt                       # 놓인 칸 아래에 새로 생기는 빈칸 수
        holes += gap
        col_tr += (2 if gap else 0) - (1 if yt == 0 else 0)
        hp[x] = H - yt
    top = py + mindy
    if ctx.top < top:
        top = ctx.top
    wells = 0.0
    for c in range(W):
        left = hp[c - 1] if c > 0 else 99
        right = hp[c + 1] if c < W - 1 else 99
        d = (left if left < right else right) - hp[c]
        if d > 0:
            w = WELL_VAL[d]
            if attack_style and c == W - 1:
                w *= PARAMS["edge_well"]
            wells += w
    max_h = H - top
    score = 0.0
    if attack_style and incoming == 0 and max_h <= 12:
        score += PARAMS["ready"] * min(ready, 4) * (1.0 if i_soon else PARAMS["no_i"])
        if ctx.tsd or any(nv in TSD_ROW for _y, nv in new_vals):        # T-스핀 더블 자리가 있을 수 있을 때만 줄을 훑음 (보통은 건너뜀)
            new = rows[:]
            for y, nv in new_vals:
                new[y] = nv
            for y in range(top if top > 1 else 1, H - 1):
                c = TSD_ROW.get(new[y])
                if c is not None and new[y + 1] == FULL ^ (1 << (c + 1)):
                    if new[y - 1] & ((1 << c) | (1 << (c + 2))):
                        score += PARAMS["tslot"] * (1.0 if t_soon else 0.4)
                    else:
                        score += PARAMS["tslot_partial"] * (1.0 if t_soon else 0.4)
                    break
    P = PARAMS
    score = score - P["w_row"] * row_tr - P["w_col"] * col_tr - P["w_hole"] * holes - P["w_well"] * wells
    eff = max_h + incoming
    dh = P["danger_h"]
    if eff > dh:
        score -= (eff - dh) ** 2 * P["w_danger"]
    return score, ysum_base


def _mat(x):
    """_expand가 돌려준 보드가 아직 만들어지지 않은 표식 (rows, piece, rot, px, py)이면 실제 보드(줄 지움 없음)로 만듦"""
    if type(x) is tuple:
        rows, piece, rot, px, py = x
        new = rows[:]
        for dx, dy in SHAPES[piece][rot]:
            new[py + dy] |= 1 << (px + dx)
        return new
    return x


def _step_reward(landing, eroded, cleared, kind, combo_before, b2b_before, incoming, is_pc, max_h_after, attack_style):
    """이번 한 수의 보상과 다음 상태(combo, b2b)"""
    reward = -(PARAMS["land_atk"] if attack_style else PARAMS["land"]) * landing + 3.42 * eroded * cleared      # El-Tetris: (지운 줄 수) x (그 줄에 속한 이번 블록 칸 수) -> 큰 클리어일수록 훨씬 크게 보상
    if cleared > 0:
        combo_after = combo_before + 1
        attack, difficult = _attack(cleared, kind, combo_after, b2b_before, is_pc)
        if attack_style:
            scale = 1.0 if max_h_after + incoming <= 10 else 0.6
            reward += attack * PARAMS["atk"] * scale + min(combo_after, 8) * PARAMS["combo"]
            if not difficult and cleared <= 2 and max_h_after + incoming <= PARAMS["low"]:
                reward -= PARAMS["single_pen"]     # 낮게 쌓였을 땐 1~2줄 잔클리어보다 모아서 큰 공격을 노림
            if b2b_before and not difficult:
                reward -= 4.0 + (min(int(b2b_before) - 1, 7) if PARAMS["b2b_chain"] else 0)      # 연속 보너스를 끊는 수는 손해 (연쇄가 길수록 더)
            if difficult and b2b_before:
                reward += PARAMS["b2b"]
        else:
            reward += attack * 0.8
        if is_pc:
            reward += 60.0
        if incoming > 0:
            reward += min(attack, incoming) * PARAMS["defend"]      # 들어올 쓰레기를 공격으로 상쇄하면 그만큼 보너스(방어)
        if PARAMS["b2b_chain"]:
            nb2b = (int(b2b_before) + 1 if b2b_before else 1) if difficult else 0           # 연쇄 길이를 이어 감 (어려운 클리어 = +1, 아닌 클리어 = 끊김)
        else:
            nb2b = difficult
        return reward, combo_after, nb2b
    return reward, -1, b2b_before


def _expand(rows, piece, combo, b2b, incoming, attack_style, use_tspin, soon=(True, False)):
    """한 블록의 모든 배치 -> [(quick, reward, new_rows, combo, b2b, meta)]"""
    out = []
    top0 = _top(rows)
    tops = _tops(rows, top0)
    if piece == "T" and use_tspin:
        cands = t_placements(rows)
    else:
        cands = [(rot, px, py, None, None) for rot, px, py in simple_placements(rows, piece, tops)]
    i_soon, t_soon = soon
    ctx = None
    lp = PARAMS["land_atk"] if attack_style else PARAMS["land"]
    for rot, px, py, kind, path in cands:
        if py + _MIN_DY[piece][rot] < 0:
            continue
        if path is None:                                         # 하드 드롭 배치: 줄이 안 지워지면 증분 평가 (새 보드는 뽑힐 때만 만듦)
            if ctx is None:
                ctx = _Ctx(rows, top0, tops)
            fast = _quick_delta(ctx, piece, rot, px, py, incoming, attack_style, i_soon, t_soon)
            if fast is not None:
                landing = H - (4 * py + fast[1]) / 4.0
                reward = -lp * landing + 3.42 * 0 * 0
                out.append((reward + fast[0], reward, (rows, piece, rot, px, py), -1, b2b, (rot, px, py, path)))
                continue
        new, cleared, eroded, landing, top = _apply(rows, piece, rot, px, py, top0)
        is_pc = cleared > 0 and top >= H
        reward, c2, b2 = _step_reward(landing, eroded, cleared, kind if cleared > 0 else None, combo, b2b, incoming,
                                      is_pc, H - top, attack_style)
        quick = reward + board_eval(new, incoming, attack_style, i_soon, t_soon, top)
        out.append((quick, reward, new, c2, b2, (rot, px, py, path)))
    return out


def _options(cur, hold, queue, can_hold):
    """이번 차례에 쓸 수 있는 선택지: [(사용할 블록, 홀드를 쓰는가, 새 홀드, 남은 큐)]"""
    opts = [(cur, False, hold, queue)]
    if can_hold:
        if hold is None:
            if queue:
                opts.append((queue[0], True, cur, queue[1:]))
        elif hold != cur:
            opts.append((hold, True, cur, queue))
    return opts


def _leaf_best(rows, hold, cur, rest, combo, b2b, incoming, attack_style):
    """_future의 마지막 층: 이 층에서는 최고 점수 하나만 필요하므로 후보 목록/정렬을 만들지 않고 바로 최댓값만 구함 (결과는 목록을 정렬해 첫 항목을 꺼내던 것과 같음)"""
    best = None
    top0 = _top(rows)
    tops = _tops(rows, top0)
    ctx = _Ctx(rows, top0, tops)
    lp = PARAMS["land_atk"] if attack_style else PARAMS["land"]
    min_dy = _MIN_DY
    for piece, _used_hold, new_hold, rem in _options(cur, hold, rest, True):
        i_soon, t_soon = 'I' in rem[:5] or new_hold == 'I', 'T' in rem[:5] or new_hold == 'T'
        md = min_dy[piece]
        for rot, px, py in simple_placements(rows, piece, tops):
            if py + md[rot] < 0:
                continue
            fast = _quick_delta(ctx, piece, rot, px, py, incoming, attack_style, i_soon, t_soon)
            if fast is not None:
                landing = H - (4 * py + fast[1]) / 4.0
                quick = -lp * landing + 3.42 * 0 * 0 + fast[0]
                if best is None or quick > best:
                    best = quick
                continue
            new, cleared, eroded, landing, top = _apply(rows, piece, rot, px, py, top0)
            reward, _c2, _b2 = _step_reward(landing, eroded, cleared, None, combo, b2b, incoming,
                                            cleared > 0 and top >= H, H - top, attack_style)
            quick = reward + board_eval(new, incoming, attack_style, i_soon, t_soon, top)
            if best is None or quick > best:
                best = quick
    return -1e6 if best is None else best


def _future(rows, hold, queue, combo, b2b, incoming, depth, beam, attack_style):
    """이미 한 수를 둔 뒤, 남은 블록으로 depth수 더 내다본 최고 점수 (보상 + 마지막 보드 평가)"""
    if not queue or depth <= 0:
        return board_eval(rows, incoming, attack_style, 'I' in queue[:5] or hold == 'I', 'T' in queue[:5] or hold == 'T')
    cur, rest = queue[0], queue[1:]
    if depth == 1:
        return _leaf_best(rows, hold, cur, rest, combo, b2b, incoming, attack_style)
    best = -1e18
    scored = []
    for piece, used_hold, new_hold, rem in _options(cur, hold, rest, True):
        soon = ('I' in rem[:5] or new_hold == 'I', 'T' in rem[:5] or new_hold == 'T')
        for quick, reward, new_rows, c2, b2, meta in _expand(rows, piece, combo, b2b, incoming, attack_style, False, soon):
            scored.append((quick, reward, new_rows, c2, b2, new_hold, rem))
    if not scored:
        return -1e6
    scored.sort(key=lambda t: t[0], reverse=True)
    for quick, reward, new_rows, c2, b2, new_hold, rem in scored[:beam]:
        v = reward + _future(_mat(new_rows), new_hold, rem, c2, b2, incoming, depth - 1, max(2, beam - 1), attack_style)
        if v > best:
            best = v
    return best


def plan(grid, cur, hold, queue, can_hold, combo, b2b, incoming, depth=1, beam=4, attack_style=True, use_tspin=True, params=None):
    """가장 좋은 배치 후보들을 점수 순으로 반환: [(score, use_hold, rot, px, path)]
    queue: 지금 블록 뒤에 나올 블록들(보이는 것만). 첫 원소가 '다음' 블록."""
    return plan_rows(rows_from_grid(grid), cur, hold, queue, can_hold, combo, b2b, incoming, depth, beam, attack_style, use_tspin, params)


def plan_rows(rows, cur, hold, queue, can_hold, combo, b2b, incoming, depth=1, beam=4, attack_style=True, use_tspin=True, params=None):
    """plan()과 같지만 이미 행 비트마스크로 바꾼 보드를 받음 (작업 프로세스로 보낼 때 사용).
    params: 이 계산에만 쓸 가중치(자체 대전 튜닝용). 없으면 전역 PARAMS"""
    if params:
        saved = dict(PARAMS)
        PARAMS.update(params)
        try:
            return plan_rows(rows, cur, hold, queue, can_hold, combo, b2b, incoming, depth, beam, attack_style, use_tspin)
        finally:
            PARAMS.clear()
            PARAMS.update(saved)
    if attack_style:
        top = next((i for i, r in enumerate(rows) if r), H)
        if incoming > 0 or (H - top) > PARAMS["safe_h"]:
            attack_style = False             # 쓰레기가 오고 있거나 높이 쌓였으면 공격 준비보다 줄 정리(생존)에 집중
    results = []
    for piece, used_hold, new_hold, rem in _options(cur, hold, queue, can_hold):
        soon = ('I' in rem[:5] or new_hold == 'I', 'T' in rem[:5] or new_hold == 'T')     # 화면에 보이는 다음 블록 5개를 모두 활용
        cands = _expand(rows, piece, combo, b2b, incoming, attack_style, use_tspin, soon)
        if not cands:
            continue
        cands.sort(key=lambda t: t[0], reverse=True)
        look = depth > 1 and bool(rem)
        for i, (quick, reward, new_rows, c2, b2, meta) in enumerate(cands):
            rot, px, py, path = meta
            if look:
                if i >= beam:
                    break                    # 내다본 점수와 안 내다본 점수는 척도가 달라 섞지 않음: 상위 후보만 남김
                total = reward + _future(_mat(new_rows), new_hold, rem, c2, b2, incoming, depth - 1, max(2, beam - 1), attack_style)
            else:
                total = quick
            if attack_style and new_hold == "I":
                total += PARAMS["hold_i"]                # I 블록을 쿼드용으로 홀드에 보관
            elif attack_style and new_hold == "T":
                total += PARAMS["hold_t"]                # T 블록을 T-스핀용으로 홀드에 보관
            results.append((total, used_hold, rot, px, path))
    results.sort(key=lambda t: t[0], reverse=True)
    return results


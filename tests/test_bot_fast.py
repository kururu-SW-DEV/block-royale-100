"""
봇 두뇌 속도 개선(t_placements, board_eval)이 기준 구현과 같은 결과를 내는지 확인
- t_placements: 같은 자리 집합(회전, 위치, T-스핀 종류) + 입력 경로가 실제로 그 자리에 도달
- board_eval: 점수가 부동소수점까지 정확히 같음
기준 구현(t_placements_ref, board_eval_ref)은 bot_brain에 그대로 남겨 둠
실행: python tests/test_bot_fast.py
"""
import os
import random
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bot_brain as B
from block_engine import JLSTZ_KICKS
from config import SPAWN_Y

W, H = B.W, B.H
T = B.SHAPES["T"]


def _boards(n, seed):
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        rows = [0] * H
        h = rnd.randint(0, 19)
        for y in range(H - h, H):
            rows[y] = rnd.getrandbits(W) if rnd.random() < 0.9 else 0
            if rows[y] == B.FULL:
                rows[y] ^= 1 << rnd.randrange(W)
        if i % 5 == 0:                                           # 준비된 줄 / T 슬롯이 나오는 보드도 섞음
            for y in range(H - rnd.randint(1, 8), H):
                rows[y] = B.FULL ^ (1 << (W - 1)) if rnd.random() < 0.5 else (B.FULL ^ (7 << rnd.randrange(W - 2)))
        out.append(rows)
    return out


def _replay(rows, path):
    x, y, r = 3, SPAWN_Y, 0
    for a in path:
        if a == "L" and not B._collide(rows, T[r], x - 1, y):
            x -= 1
        elif a == "R" and not B._collide(rows, T[r], x + 1, y):
            x += 1
        elif a == "D" and not B._collide(rows, T[r], x, y + 1):
            y += 1
        elif a in ("cw", "ccw"):
            nr = (r + 1) % 4 if a == "cw" else (r - 1) % 4
            for kx, ky in JLSTZ_KICKS.get((r, nr), [(0, 0)]):
                if not B._collide(rows, T[nr], x + kx, y - ky):
                    x, y, r = x + kx, y - ky, nr
                    break
    return x, y, r


def test_t_placements_matches_reference_and_paths_are_valid():
    boards = _boards(600, 7) + [[0] * H]
    paths = 0
    for rows in boards:
        ref = {(r, x, y, k) for r, x, y, k, _p in B.t_placements_ref(rows)}
        new = B.t_placements(rows)
        assert {(r, x, y, k) for r, x, y, k, _p in new} == ref, [format(v, "010b") for v in rows]
        for r, x, y, k, p in new:
            paths += 1
            assert _replay(rows, p) == (x, y, r), f"입력 경로가 자리에 도달하지 못함: {(r, x, y, k)} {p[:10]}"
    assert paths > 1000


def test_board_eval_matches_reference_exactly():
    n = 0
    for rows in _boards(1500, 11):
        top = B._top(rows)
        for inc in (0, 4):
            for atk in (True, False):
                for i_soon, t_soon in ((True, False), (False, True)):
                    for tp in (None, top):
                        assert B.board_eval(rows, inc, atk, i_soon, t_soon, tp) == B.board_eval_ref(rows, inc, atk, i_soon, t_soon, tp), (rows, inc, atk, i_soon, t_soon, tp)
                        n += 1
    assert n > 20000


def test_plan_best_move_unchanged_on_sample_positions():
    """t_placements를 기준 구현으로 바꿔도 계획기가 고르는 1순위 수가 같음 (깊이 2)"""
    rnd = random.Random(5)
    orig = B.t_placements
    same = 0
    cases = 0
    for rows in _boards(120, 21):
        if rows[0] or rows[1]:
            continue
        cur, nxt = rnd.choice("IJLOSTZ"), [rnd.choice("IJLOSTZ") for _ in range(4)]
        hold = rnd.choice([None, "T", "I"])
        a = B.plan_rows(rows, cur, hold, nxt, True, 0, False, 0, depth=2, beam=3, attack_style=True, use_tspin=True)
        B.t_placements = B.t_placements_ref
        try:
            b = B.plan_rows(rows, cur, hold, nxt, True, 0, False, 0, depth=2, beam=3, attack_style=True, use_tspin=True)
        finally:
            B.t_placements = orig
        cases += 1
        same += int(bool(a) and bool(b) and a[0][:4] == b[0][:4] or (not a and not b))
    assert cases > 50 and same == cases, f"{same}/{cases}"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print("[ALL BOT FAST TESTS PASSED]")

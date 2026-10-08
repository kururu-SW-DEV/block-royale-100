"""
입력 처리 순서: 같은 프레임에서 하드드롭/회전이 들어오면, 그 시점까지의 DAS/ARR 좌우 이동을 먼저 반영한 뒤 실행해야 함
(방향키를 꾹 눌러 벽으로 보내면서 하드드롭을 눌렀을 때 벽 앞 칸에서 먼저 떨어지는 미스드롭 방지)
실행: python tests/test_input_order.py (SDL dummy 드라이버)
"""
import os
import sys
import tempfile
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame


def _app():
    import main as M
    from gfx import CANVAS
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app = M.BlockRoyaleApp()
    app.screen = CANVAS
    app.stats_mgr.filepath = os.path.join(tempfile.mkdtemp(), "s.json")
    return app


def _key(app, key):
    app._handle_game_event(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=""))


def _start(app):
    app.start_game(mode="SOLO", total_players=10)
    m = app.match
    m.countdown_until = 0.0
    m.coach_until = 0.0
    app.state = "GAME"
    app.match.local_engine.current_piece = "O"
    app.match.local_engine.current_rot = 0
    app.match.local_engine.current_x = 4
    app.match.local_engine.current_y = 0
    return m


def test_das_moves_before_hard_drop_in_same_frame():
    app = _app()
    m = _start(app)
    app.ARR_INSTANT = True                                       # ARR 0: DAS가 끝나면 벽까지 한 번에 이동
    app.DAS_DELAY = 0.1
    app.DCD_DELAY = 0.0
    app.key_right_down, app.h_dir = True, 1
    app.das_timer = app.DAS_DELAY - 0.004                        # 이번 프레임(16ms) 안에 DAS가 끝나는 상태
    app.das_fired = False
    app._frame_dt = 1 / 60
    app._frame_t0 = time.perf_counter() - 1 / 60                 # 직전 업데이트가 한 프레임 전에 있었음
    app._das_credit = 0.0
    hd = app.settings.get_action_keys("hard_drop")[0]
    _key(app, hd)                                                # 이벤트가 먼저 처리됨 (실제 메인 루프의 순서)
    app._update_game(1 / 60)
    cells = m.local_engine.last_lock_cells
    assert cells, "하드드롭으로 고정되어야 함"
    assert max(x for x, _y in cells) == 9, f"DAS 이동이 반영되기 전에 떨어짐: 고정 칸 x={sorted(set(x for x, _ in cells))}"


def test_no_double_movement_when_credit_is_used():
    """하드드롭 직전에 이동을 먼저 반영한 만큼은 그 프레임 업데이트에서 다시 세지 않음"""
    app = _app()
    m = _start(app)
    app.ARR_INSTANT = False
    app.ARR_INTERVAL = 0.05
    app.DAS_DELAY = 0.1
    app.DCD_DELAY = 0.0
    app.key_right_down, app.h_dir = True, 1
    app.das_timer = app.DAS_DELAY
    app.das_fired = True
    app.arr_timer = 0.0
    app._frame_dt = 1 / 60
    app._frame_t0 = time.perf_counter() - 1 / 60
    app._das_credit = 0.0
    x0 = m.local_engine.current_x
    rk = app.settings.get_action_keys("rotate_cw")[0]
    _key(app, rk)                                                # 회전도 같은 규칙
    app._update_game(1 / 60)
    moved = m.local_engine.current_x - x0
    assert moved <= 1, f"한 프레임(16ms)에 ARR 50ms 간격으로 {moved}칸이나 움직임 (이중 계산)"


def test_rise_line_only_when_garbage_is_ready():
    app = _app()
    m = _start(app)
    for _ in range(30):
        app._tick_game(1 / 60)
    calls = []
    orig = app.renderer._draw_rise_line
    app.renderer._draw_rise_line = lambda *a, **k: (calls.append(a), orig(*a, **k))[1]
    e = m.local_engine
    app.renderer.render(m, app.sound_mgr)
    assert not calls, "받을 공격이 없는데 상승선이 그려짐"
    e.queue_garbage(3, source="X", instant=True)
    app.renderer.render(m, app.sound_mgr)
    assert len(calls) == 1 and calls[0][-1] == 3, calls               # 마지막 인자 = 올라올 줄 수
    calls.clear()
    e.incoming_garbage = 0
    e.queue_garbage(2, source="X")                                  # 아직 충전 중(0.8초): 준비되지 않았으니 그리지 않음
    app.renderer.render(m, app.sound_mgr)
    assert not calls, "충전 중인 공격에 상승선이 그려짐"


def test_big_clears_flash_a_little():
    app = _app()
    m = _start(app)
    info = {"cleared": 4, "is_tspin": False, "is_mini": False, "is_b2b": False, "b2b_chain": 0, "is_pc": False, "attack": 4,
            "canceled": 0, "combo": 0, "cleared_rows": [16, 17, 18, 19]}
    m.local_engine.last_clear_info = info
    m.impact_t, m.impact_power = 0.0, 0.0
    m.on_lines_cleared(4)
    assert m.impact_t > 0 and abs(m.impact_power - 0.45) < 1e-9, (m.impact_t, m.impact_power)
    info2 = dict(info, cleared=1, is_tspin=False)
    m.local_engine.last_clear_info = info2
    m.impact_t, m.impact_power = 0.0, 0.0
    m.on_lines_cleared(1)
    assert m.impact_t == 0.0, "싱글 클리어는 번쩍이지 않음"


def test_one_attack_rises_with_a_straight_hole():
    from block_engine import BlockEngine
    e = BlockEngine(seed=4)
    e.queue_garbage(4, source="A", instant=True)
    e.hard_drop()                                                # 줄을 못 지우고 고정 -> 쓰레기 4줄이 올라옴
    rows = e.grid[-4:]
    holes = {[x for x, c in enumerate(r) if c is None][0] for r in rows}
    assert all(c == "G" or c is None for r in rows for c in r) and len(holes) == 1, f"한 번의 공격인데 구멍이 {holes}로 어긋남"
    for _ in range(40):                                          # 여러 번 해도 항상 일직선 (이전에는 줄마다 25% 확률로 옮겨졌음)
        f = BlockEngine(seed=_)
        f.queue_garbage(4, instant=True)
        f.hard_drop()
        hs = {[x for x, c in enumerate(r) if c is None][0] for r in f.grid[-4:]}
        assert len(hs) == 1, hs


def test_big_attack_split_across_locks_keeps_one_hole():
    from block_engine import BlockEngine
    e = BlockEngine(seed=5)
    e.queue_garbage(12, source="A", instant=True)
    g1 = e._take_garbage(8, ready_only=True)
    h1 = list(e._take_holes)
    g2 = e._take_garbage(8, ready_only=True)
    h2 = list(e._take_holes)
    assert g1 == [8] and g2 == [4], (g1, g2)
    assert h1 == h2, f"한 묶음이 두 번에 나뉘어 올라올 때 구멍이 달라짐: {h1} {h2}"


def test_separate_attacks_get_their_own_hole_choice():
    from block_engine import BlockEngine
    seen = set()
    for seed in range(60):
        e = BlockEngine(seed=seed)
        e.garbage_rng.seed(seed)
        e.queue_garbage(2, source="A", instant=True)
        e.queue_garbage(2, source="B", instant=True)
        e._take_garbage(8, ready_only=True)
        h = e._take_holes
        assert len(h) == 2
        seen.add(h[0] == h[1])
    assert seen == {True, False}, "서로 다른 공격은 구멍이 독립적으로 정해져야 함 (같을 때도 다를 때도 있음)"


def test_closing_the_rules_card_resumes_a_game_it_paused():
    app = _app()
    m = _start(app)
    assert not app.is_paused
    app._open_rules()
    assert app.rules_open and app.is_paused and m.is_paused, "규칙 카드를 열면 솔로 경기는 멈춤"
    app._close_rules()
    assert not app.rules_open and not app.is_paused and not m.is_paused, "규칙 카드를 닫았는데 일시정지 창에 갇힘"
    app.is_paused = m.is_paused = True                           # 사용자가 직접 일시정지한 경기는 규칙 카드를 닫아도 계속 멈춰 있음
    app._open_rules()
    app._close_rules()
    assert app.is_paused and m.is_paused, "직접 건 일시정지가 규칙 카드를 닫으며 풀림"


if __name__ == "__main__":
    pygame.init()
    from settings_manager import SETTINGS_FILE
    from stats_manager import STATS_FILE
    keep = {p: (open(p, "rb").read() if os.path.exists(p) else None) for p in (SETTINGS_FILE, STATS_FILE)}
    try:
        for name, fn in list(globals().items()):
            if name.startswith("test_") and callable(fn):
                print(name)
                fn()
        print("[ALL INPUT ORDER TESTS PASSED]")
    finally:
        for p, data in keep.items():
            if data is not None:
                open(p, "wb").write(data)

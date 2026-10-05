"""
조작감(핸들링) 테스트 (v1.1.7): DAS 시작 오차, DAS 끝나는 순간 첫 자동 이동, 방향 전환 시 DAS 취소, DCD, 소프트드롭 즉시,
카운트다운 DAS 충전 + 회전/홀드 선입력(IRS/IHS), 포커스 복귀 때 키 상태 재동기화, 설정 범위/프리셋.
실행: python test_handling.py
"""
import os
import sys
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from gfx import CANVAS

DT = 1 / 60.0


def _app(das=135, arr=33, sdf=35, dcd=0, cancel=False, n=6):
    import main as M
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app = M.BlockRoyaleApp()
    app.screen = CANVAS
    for k, v in (("das_ms", das), ("arr_ms", arr), ("sdf_ms", sdf), ("dcd_ms", dcd), ("das_cancel", cancel)):
        app.settings.set(k, v, autosave=False)
    app.apply_handling()
    app.start_game(mode="SOLO", total_players=n)
    app.match.countdown_until = 0.0
    e = app.match.local_engine
    e.grid = [[None] * 10 for _ in range(20)]
    e.current_piece, e.current_rot, e.current_x, e.current_y = "T", 0, 4, 0
    app.das_timer = app.arr_timer = 0.0
    app.das_fired = False
    return app, e


def _key(app, kind, key):
    app._handle_game_event(pygame.event.Event(kind, key=key, mod=0, unicode=""))


def _step(app, n=1):
    for _ in range(n):
        app._frame_dt = DT
        app._update_game(DT)


def test_das_first_auto_move_timing():
    app, e = _app()
    _key(app, pygame.KEYDOWN, pygame.K_LEFT)
    assert e.current_x == 3, "누른 순간 한 칸"
    moves = []
    for i in range(14):
        before = e.current_x
        _step(app)
        if e.current_x != before:
            moves.append(i)
    assert moves[0] == 8, f"DAS 135ms는 누른 뒤 8.5프레임 만에(9번째 갱신) 첫 자동 이동: {moves}"
    assert len(moves) >= 2 and moves[1] - moves[0] <= 3, "그다음은 ARR 간격으로 이어짐"
    print("  OK DAS 시작 타이밍")


def test_dcd_blocks_overshoot_into_next_piece():
    for dcd, expect_move in ((0, True), (100, False)):
        app, e = _app(das=60, arr=0, dcd=dcd)
        _key(app, pygame.KEYDOWN, pygame.K_LEFT)
        _step(app, 8)                                               # 벽까지 이동, DAS 충전 끝
        assert min(x for x, _ in e._get_blocks("T", 0, e.current_x, e.current_y)) == 0
        e.hard_drop()                                               # 새 블록
        e.current_x = 5
        _step(app, 4)
        moved = e.current_x != 5
        assert moved == expect_move, (dcd, e.current_x)
        if not expect_move:
            _step(app, 20)
            assert e.current_x != 5, "DCD가 끝나고 DAS를 다시 충전하면 움직임"
    print("  OK DCD")


def test_das_cancel_on_direction_change():
    results = {}
    for cancel in (False, True):
        app, e = _app(das=60, arr=33, cancel=cancel)
        _key(app, pygame.KEYDOWN, pygame.K_RIGHT)
        _key(app, pygame.KEYDOWN, pygame.K_LEFT)                    # 방향 전환 (나중에 누른 키 우선)
        _step(app, 14)
        e.current_x = 5
        _key(app, pygame.KEYUP, pygame.K_LEFT)                      # 왼쪽을 떼면 눌려 있던 오른쪽으로 이어짐
        _step(app, 2)
        results[cancel] = e.current_x
    assert results[False] > 5, "기본: 충전된 DAS로 바로 오른쪽 연사"
    assert results[True] == 5, "DAS 취소: 새로 충전하느라 바로는 안 움직임"
    print("  OK DAS 취소")


def test_instant_soft_drop():
    app, e = _app(sdf=0)
    assert app.SOFT_DROP_INSTANT
    _key(app, pygame.KEYDOWN, pygame.K_DOWN)
    _step(app, 1)
    assert e.current_y == e.get_ghost_y(), "소프트드롭 0 = 바닥까지 즉시"
    app2, e2 = _app(sdf=35)
    _key(app2, pygame.KEYDOWN, pygame.K_DOWN)
    _step(app2, 1)
    assert e2.current_y < e2.get_ghost_y()
    print("  OK 소프트드롭 즉시")


def test_countdown_precharge_and_irs_ihs():
    app, e = _app(das=100, arr=33)
    app.match.countdown_until = time.time() + 5.0                  # 카운트다운 중
    e.current_piece, e.current_rot, e.current_x, e.current_y = "T", 0, 4, 0
    start_x, start_hold = e.current_x, e.hold_piece
    _key(app, pygame.KEYDOWN, pygame.K_LEFT)
    _key(app, pygame.KEYDOWN, pygame.K_UP)                         # 회전 선입력
    _key(app, pygame.KEYDOWN, pygame.K_c)                          # 홀드 선입력
    _step(app, 12)                                                 # 카운트다운 동안 충전
    assert e.current_x == start_x and e.current_rot == 0, "카운트다운 중에는 아직 움직이지 않음"
    assert app.das_timer >= app.DAS_DELAY - 1e-9, "DAS 충전됨"
    app.match.countdown_until = 0.0
    _step(app, 1)
    assert e.hold_piece is not None and e.hold_piece != start_hold, "IHS: GO와 함께 홀드"
    assert e.current_x < start_x, "GO와 함께 바로 이동"
    print("  OK 카운트다운 충전/IRS/IHS")


def test_focus_regain_resync():
    app, e = _app()

    class Keys:
        def __getitem__(self, k):
            return k == pygame.K_LEFT

    orig = pygame.key.get_pressed
    pygame.key.get_pressed = lambda: Keys()
    try:
        app.key_left_down = app.key_right_down = False
        app._handle_game_event(pygame.event.Event(pygame.WINDOWFOCUSGAINED))
    finally:
        pygame.key.get_pressed = orig
    assert app.key_left_down and app.h_dir == -1 and not app.key_right_down
    print("  OK 포커스 복귀 재동기화")


def test_handling_settings_ranges_and_presets():
    import settings_manager as S
    assert S.HANDLING_LIMITS["das_ms"][0] == 17 and S.HANDLING_LIMITS["sdf_ms"][0] == 0
    ok, v = S._valid_setting("dcd_ms", 9999)
    assert ok and v == 200
    ok, v = S._valid_setting("sdf_ms", -5)
    assert ok and v == 0
    ok, v = S._valid_setting("das_cancel", 1)
    assert not ok, "bool이 아니면 거부"
    app, e = _app()
    st = app.settings
    st.set("sdf_ms", 6, autosave=False)
    assert st.adjust_handling("sdf_ms", -1) == 5
    assert st.adjust_handling("sdf_ms", -1) == 0, "5ms 아래는 즉시"
    assert st.adjust_handling("sdf_ms", 1) == 5
    st.set("das_ms", 20, autosave=False)
    assert st.adjust_handling("das_ms", -1) == 17
    names = [p[0] for p in S.HANDLING_PRESETS]
    st.apply_handling_preset(names.index("프로"))
    assert (st.get("arr_ms"), st.get("sdf_ms"), st.get("das_cancel")) == (0, 0, True)
    assert S.handling_preset_name(st.get("das_ms"), st.get("arr_ms"), st.get("sdf_ms"), st.get("dcd_ms"), st.get("das_cancel")) == "프로"
    st.cycle_handling_preset(1)
    assert st.get("das_ms") == S.HANDLING_PRESETS[0][1], "프리셋 순환"
    assert S.handling_preset_name(111, st.get("arr_ms"), st.get("sdf_ms"), 0, st.get("das_cancel")) == "사용자 지정"
    print("  OK 설정 범위/프리셋")


def test_settings_screen_react_tab_renders_and_navigates():
    app, e = _app()
    app.state, app.settings_tab, app.previous_state = "SETTINGS", "react", "MENU"
    import screens.settings as SS
    for f in range(len(SS.TAB_NAV["react"])):
        app.settings_focus["react"] = f
        app._kb_nav = True
        app._render_settings()
    app.settings_focus["react"] = 4                                # DAS 취소 행에서 → 로 토글
    before = app.settings.get("das_cancel")
    app._settings_key_nav(pygame.K_RIGHT)
    assert app.settings.get("das_cancel") != before and app.DAS_CANCEL == (not before)
    app.settings_focus["react"] = 5                                # 프리셋 행
    app._settings_key_nav(pygame.K_RIGHT)
    app.settings_tab = "keys"
    app.settings_focus["keys"] = SS.PRESET_FOCUS
    app._settings_key_nav(pygame.K_UP)
    assert app.settings_focus["keys"] == SS.PAD_FOCUS                  # 프리셋 줄 위 = 게임패드 줄 (v1.4.8), 그 위 = 마지막 키 카드
    app._settings_key_nav(pygame.K_UP)
    assert app.settings_focus["keys"] == SS.KEY_CARDS - 1
    print("  OK 설정 화면")


if __name__ == "__main__":
    pygame.init()
    from settings_manager import SETTINGS_FILE
    keep = open(SETTINGS_FILE, "rb").read() if os.path.exists(SETTINGS_FILE) else None
    try:
        for name, fn in list(globals().items()):
            if name.startswith("test_") and callable(fn):
                print(name)
                fn()
        print("[ALL HANDLING TESTS PASSED]")
    finally:
        if keep is not None:
            open(SETTINGS_FILE, "wb").write(keep)

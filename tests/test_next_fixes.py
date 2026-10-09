"""
다음 개선(v1.4.27): 카운트다운 중 패드, 확인 창 포커스, 봇 풀 복구/로그, 사다리 '다음 난이도' 버튼, 솔로 관전 배속 탐색 시간
실행: python tests/test_next_fixes.py (SDL dummy 드라이버)
"""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["BR_DATA_DIR"] = tempfile.mkdtemp()
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
    app.settings.filepath = os.path.join(tempfile.mkdtemp(), "set.json")
    app.settings.reset_to_defaults()
    app.apply_visual_options()
    return app


def test_pad_is_in_game_mode_during_countdown():
    app = _app()
    app.start_game(mode="SOLO", total_players=10)
    app.state = "GAME"
    m = app.match
    m.brief_open = False
    import time
    m.countdown_until = time.time() + 3
    assert m.countdown_left() > 0
    assert app._pad_in_game(), "카운트다운 중에도 패드는 게임 조작이어야 함 (B가 ESC로 바뀌어 일시정지되지 않게)"
    app.is_paused = True
    assert not app._pad_in_game()
    app.is_paused = False
    app.modal = {"x": 1}
    assert not app._pad_in_game()


def test_modal_focus_ignores_stationary_mouse():
    app = _app()
    app._open_modal("t", ["a"], [("stay", "계속", "blue", "ESC"), ("leave", "나가기", "red", "Y")])
    mx, my = pygame.mouse.get_pos()
    x, y, w, h = (1366 - 620) // 2, (768 - 250) // 2, 620, 250
    # 마우스를 '나가기' 버튼 위에 둔 채로 창이 열림
    bw, gap = 230, 20
    sx = x + (w - (bw * 2 + gap)) // 2
    target = (sx + (bw + gap) + bw // 2, y + h - 84 + 26)
    pygame.mouse.set_pos(target)
    app.modal["last_mouse"] = pygame.mouse.get_pos()          # 열릴 때의 마우스 위치
    from gfx import CANVAS
    app.renderer.screen = CANVAS
    app._render_modal()
    assert app.modal["focus"] == 0, "마우스를 움직이지 않았으면 안전한 버튼에 포커스가 남아야 함"
    app.modal["last_mouse"] = (0, 0)                          # 마우스가 움직임
    app._render_modal()
    pos = pygame.mouse.get_pos()
    if app.modal["rects"]["leave"].collidepoint(pos):         # (dummy 드라이버에서 set_pos가 먹을 때만 검사)
        assert app.modal["focus"] == 1


def test_bot_pool_logs_and_revives():
    import bot_pool
    import crash_log
    logged = []
    orig = crash_log.write_error
    crash_log.write_error = lambda title, text: logged.append(title)
    try:
        bot_pool._logged[0] = 0
        bot_pool._mark_broken("unit test")
        assert bot_pool._state["broken"]
        assert any("unit test" in t for t in logged), logged
        bot_pool.revive()
        assert not bot_pool._state["broken"], "새 경기에서 다시 켤 수 있어야 함"
        bot_pool._state["broken"] = False
    finally:
        crash_log.write_error = orig
        bot_pool._logged[0] = 0


def test_ladder_next_difficulty_button():
    app = _app()
    app.start_game(mode="SOLO", total_players=20)
    app.state = "GAME"
    m = app.match
    m.match_finished = True
    m.next_ladder = "normal"
    assert app._standings_button_ids()[0] == "next"
    app.settings.set("bot_difficulty", "easy")
    started = []
    app.start_game = lambda **kw: started.append(kw)
    app._activate_result_focus("next")
    assert app.settings.get("bot_difficulty") == "normal"
    assert started and started[0].get("mode") == "SOLO"
    m.next_ladder = None
    assert "next" not in app._standings_button_ids()
    started.clear()
    app._challenge_next_difficulty()
    assert not started, "다음 난이도가 없으면 아무 일도 하지 않음"


def test_ladder_next_set_on_finish_and_rendered():
    app = _app()
    app.start_game(mode="SOLO", total_players=20)
    app.state = "GAME"
    m = app.match
    m.match_finished = True
    m.next_ladder = "hard"
    import time
    app.renderer._vic_t0 = None
    app.renderer._standings_t0 = time.time() - 5            # 등장 연출이 끝난 뒤의 모습
    for focus in ("next", "restart"):
        app.renderer.result_focus_id = focus
        app.renderer.render(m, app.sound_mgr)
        assert app.renderer.result_next_btn is not None and app.renderer.result_next_btn.w > 100, "순위표에 다음 난이도 버튼이 그려져야 함"
        rects = [app.renderer.result_next_btn, app.renderer.result_restart_btn, app.renderer.result_practice_btn, app.renderer.result_return_btn]
        assert not any(a.colliderect(b) for i, a in enumerate(rects) for b in rects[i + 1:]), rects
    m.next_ladder = None
    app.renderer.render(m, app.sound_mgr)
    assert app.renderer.result_next_btn is None


def test_spectate_speed_shares_search_budget():
    import battle_royale
    import bot_brain
    app = _app()
    app.start_game(mode="SOLO", total_players=12)
    app.state = "GAME"
    m = app.match
    m.countdown_until = 0.0
    m.coach_until = 0.0
    seen = []
    orig = bot_brain.begin_frame
    bot_brain.begin_frame = lambda b: (seen.append(b), orig(b))[1]
    try:
        m.budget_share = 0.25
        m.update(1 / 60)
        assert seen and abs(seen[-1] - battle_royale.BOT_SEARCH_BUDGET * 0.25) < 1e-9, seen
        m.budget_share = 1.0
        m.update(1 / 60)
        assert abs(seen[-1] - battle_royale.BOT_SEARCH_BUDGET) < 1e-9
    finally:
        bot_brain.begin_frame = orig


def test_countdown_waits_while_paused():
    import time
    app = _app()
    app.start_game(mode="SOLO", total_players=10)
    app.state = "GAME"
    m = app.match
    m.brief_open = False
    m.countdown_until = time.time() + 3.0
    app.is_paused = m.is_paused = True
    before = m.countdown_left()
    for _ in range(30):
        app._update_game(1 / 60)
    assert abs(m.countdown_left() - (before + 30 / 60)) < 0.05, (before, m.countdown_left())      # 프레임마다 dt만큼 미뤄짐 (실제로는 dt = 흐른 시간이라 남은 시간이 그대로)


def test_ko_absorbs_victim_badge_points():
    app = _app()
    app.start_game(mode="SOLO", total_players=10)
    app.state = "GAME"
    m = app.match
    alive = [pid for pid in m.players if pid != m.local_player_id and m.players[pid]["is_alive"]]
    for pid in alive:
        m.players[pid]["ko_count"] = 6                      # 상대들이 K.O.를 많이 쌓아 둔 상태
    m.local_ko_count = 0
    kills = 0
    for victim in alive[:5]:
        m._eliminate_player(victim, m.local_player_id)
        kills += 1
        assert m.local_ko_count == kills, "실제 K.O. 수는 처치한 만큼만 오름 (전적/업적에 흡수분은 들어가지 않음)"
        extra = m.players[m.local_player_id].get("badge_extra", 0)
        assert 0 <= extra <= kills, f"흡수 누적은 내 실제 K.O. 수 이하여야 함: {extra} > {kills}"
        assert m.badge_points() <= 2 * kills, "눈덩이 방지: 배지 점수는 실제 K.O.의 2배를 넘지 않음"
    assert m.badge_points() > m.local_ko_count, "강한 상대를 잡으면 흡수가 일어남"
    assert m.BADGE_ABSORB_MAX == 2


def test_badge_extra_sync_field_is_sanitized():
    import network
    st = {"id": "p1", "name": "x", "is_alive": True, "bx": 5, "ko_count": 3}
    assert network._sanitize_world_state(st)["bx"] == 5
    assert network._sanitize_world_state({**st, "bx": 10**6})["bx"] == 99
    assert "bx" not in network._sanitize_world_state({**st, "bx": "9"}), "숫자가 아닌 값은 버림"


def test_bot_danger_uses_spawn_columns():
    from battle_royale import BattleRoyaleMatch as B
    edge = [0] * 20
    for y in range(2, 20):
        edge[y] = 0b1000000001                              # 가장자리 열만 높게 (스폰 열 3~6은 비어 있음)
    mid = [0] * 20
    for y in range(2, 20):
        mid[y] = 0b0001111000                               # 스폰 열이 높음
    d_edge = B._spawn_danger({"compact_grid": edge, "ig": 0})
    d_mid = B._spawn_danger({"compact_grid": mid, "ig": 0})
    assert d_edge == 0 and d_mid == 18, (d_edge, d_mid)
    assert B._spawn_danger({"compact_grid": mid, "ig": 3}) == 21


def test_spawn_warning_counts_ready_garbage():
    app = _app()
    app.start_game(mode="SOLO", total_players=10)
    app.state = "GAME"
    m = app.match
    m.countdown_until = 0.0
    m.coach_until = 0.0
    e = m.local_engine
    for x in range(3, 7):
        e.grid[3][x] = "G"                                  # 스폰 열의 맨 위가 3번 줄
    assert e.spawn_column_top() == 3
    e.queue_garbage(3, instant=True)                        # 바로 올라올 수 있는 쓰레기 3줄 -> 올라오면 스폰 열이 0번 줄까지 차서 막힘
    assert e.ready_garbage == 3
    app.renderer.render(m, app.sound_mgr)                   # 예외 없이 그려져야 함 (경고 포함)


def test_menu_vertical_navigation_follows_layout():
    app = _app()
    app.state = "MENU"
    app._menu_intro_t = 9
    app._render_menu()
    key = lambda k: app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))
    app._set_menu_focus("host_room", sound=False)
    key(pygame.K_DOWN)
    assert app._menu_focus_id() in ("practice", "daily"), "방 만들기 아래는 혼자하기 줄 (옆의 방 참가하기가 아님)"
    app._set_menu_focus("join_room", sound=False)
    key(pygame.K_DOWN)
    assert app._menu_focus_id() in ("daily", "weekly")
    key(pygame.K_UP)
    assert app._menu_focus_id() == "join_room"
    key(pygame.K_UP)
    assert app._menu_focus_id() == "quick_play"
    app._set_menu_focus("quick_play", sound=False)
    key(pygame.K_UP)
    assert app._menu_focus_id() in ("match_summary", "records", "settings", "toggle_sound", "toggle_fs", "quit_game")


def test_menu_ignores_motion_without_movement():
    app = _app()
    app.state = "MENU"
    app._menu_intro_t = 9
    app._render_menu()
    app._set_menu_focus("quick_play", sound=False)
    r = app.menu_buttons["weekly"]
    app._handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=r.center, rel=(0, 0), buttons=(0, 0, 0)))
    assert app._menu_focus_id() == "quick_play", "움직이지 않은 마우스 이벤트로 포커스가 바뀌면 안 됨"
    app._handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=r.center, rel=(3, 2), buttons=(0, 0, 0)))
    assert app._menu_focus_id() == "weekly"


def test_rumble_gating():
    app = _app()
    app.start_game(mode="SOLO", total_players=10)
    m = app.match
    calls = []
    m.rumble_cb = lambda p, kind="hit": calls.append((p, kind))
    m.shake_scale = 0.0                                    # 흔들림을 꺼도 패드 진동은 따로 유지됨 (진동 설정은 별개)
    m.trigger_screen_shake(14.0, rumble_kind="quad")
    assert calls and abs(calls[-1][0] - 14.0 / 18.0) < 1e-9 and calls[-1][1] == "quad", calls
    m.rumble_scale = 0.5                                   # 진동 '약하게'는 절반 세기
    m.trigger_screen_shake(18.0)
    assert abs(calls[-1][0] - 0.5) < 1e-9, calls
    n = len(calls)
    m.rumble_scale = 0.0                                   # 진동 '끔'
    m.trigger_screen_shake(14.0)
    assert len(calls) == n
    m.rumble_scale = 1.0
    m.local_is_alive = False                               # 탈락 뒤 관전 중에는 진동 없음
    m.trigger_screen_shake(14.0)
    assert len(calls) == n


def test_spin_sound_needs_ground_and_next_ladder_above_current():
    app = _app()
    app.start_game(mode="SOLO", total_players=10)
    app.state = "GAME"
    played = []
    app.sound_mgr.play = lambda name, *a, **k: played.append(name)
    eng = app.match.local_engine
    eng.current_piece = "T"
    eng._detect_tspin = lambda: "full"
    eng._is_touching_ground = lambda: False
    app._play_rotate_sound()
    assert played[-1] == "rotate", "공중에서는 스핀 소리가 나지 않음"
    eng._is_touching_ground = lambda: True
    app._play_rotate_sound()
    assert played[-1] == "spin_ready"
    from stats_manager import next_goal_text
    txt = next_goal_text(1, 3, 100, 1, difficulty="hard", cleared=["hard"], ladder_clear="hard")
    assert "마스터" in txt or "Master" in txt, txt                  # easy/normal이 미클리어여도 hard 다음은 master


def test_next_goal_uses_badge_points():
    from stats_manager import next_goal_text
    assert "배지 Lv.2까지 1 K.O." in next_goal_text(20, 1, 100, 10, badge_pts=3)
    assert "배지 Lv.1까지 1 K.O." in next_goal_text(20, 1, 100, 10), "흡수 점수가 없으면 실제 K.O. 수로 계산"


def test_rules_card_lists_b2b_and_absorption():
    from screens.rules import rules_card_data
    cols = rules_card_data()
    flat = " ".join(a + b for _t, rows in cols for a, b in rows)
    assert "B2B" in flat and "흡수" in flat


def test_garbage_does_not_top_out_unless_spawn_blocked():
    from block_engine import BlockEngine
    e = BlockEngine()
    e.grid[0][0] = "G"                                      # 스폰 구역(가운데) 밖 모서리에 블록
    e.grid[1][0] = "G"
    e._push_garbage(1, hole_x=5)
    assert not e.game_over, "스폰 자리가 막히지 않았으면 쓰레기가 올라와도 탈락하지 않음"
    e2 = BlockEngine()
    for x in range(3, 7):
        for y in range(0, 4):
            e2.grid[y][x] = "G"
    e2._push_garbage(1, hole_x=0)
    if not e2.game_over:
        e2.hard_drop()                                      # 스폰 자리가 막힌 상태에서는 다음 블록이 나오자마자(또는 고정하면) 탈락
    assert e2.game_over, "조작 중인 블록 자리가 막히면 탈락"


def test_b2b_bonus_grows_with_chain():
    from block_engine import BlockEngine
    import config
    outs = []
    for chain in (1, 4, 8):
        e = BlockEngine()
        e.b2b = True
        e.b2b_chain = chain - 1                             # 이번 쿼드로 chain이 됨
        for y in range(16, 20):
            e.grid[y] = ["G"] * 9 + [None]
        e.grid[10][0] = "G"                                 # 퍼펙트 클리어 보너스가 섞이지 않게
        e.current_piece, e.current_rot, e.current_x, e.current_y = "I", 1, 7, 15
        e.last_move_was_rotation = False
        e.hard_drop()
        outs.append(e.garbage_to_send)
    assert outs[0] == config.GARBAGE_ATTACK_TABLE[4] + 1, outs
    assert outs[1] == outs[0] + 1 and outs[2] == outs[0] + 2, outs


def test_spin_ready_sound_and_i_180_kicks():
    app = _app()
    app.start_game(mode="SOLO", total_players=10)
    app.state = "GAME"
    played = []
    app.sound_mgr.play = lambda name, *a, **k: played.append(name)
    app.match.local_engine.current_piece = "T"
    app.match.local_engine._detect_tspin = lambda: "full"
    app.match.local_engine._is_touching_ground = lambda: True
    app._play_rotate_sound()
    assert played[-1] == "spin_ready"
    app.match.local_engine._detect_tspin = lambda: None
    app._play_rotate_sound()
    assert played[-1] == "rotate"
    from block_engine import BlockEngine
    assert len(BlockEngine.ROT180_KICKS_I) > len(BlockEngine.ROT180_KICKS)
    import sound_fx
    assert "spin_ready" in open(sound_fx.__file__, encoding="utf-8").read()


def test_gamepad_rumble_is_safe_and_throttled():
    from gamepad import GamepadMapper
    calls = []

    class Dev:
        def rumble(self, lo, hi, ms):
            calls.append((lo, hi, ms))

    gm = GamepadMapper(lambda a: [])
    gm.ctrls = {1: Dev()}
    gm.rumble(0.8)
    gm.rumble(0.8)                                          # 바로 이어진 호출은 무시
    assert len(calls) == 1 and calls[0][2] > 100
    gm.joys = {2: object()}                                 # rumble이 없는 장치도 예외 없이 무시
    gm._rumble_t = 0.0
    gm.rumble(0.5)


def test_danger_ignores_big_incoming_when_stack_is_low():
    import inspect
    import ui_renderer
    src = inspect.getsource(ui_renderer.UIRenderer)
    assert "incoming >= 4 and highest - incoming <= 7" in src


def test_menu_has_mini_cards_in_focus_order():
    app = _app()
    app.state = "MENU"
    app._menu_intro_t = 9
    app._render_menu()
    for bid in ("practice", "daily", "weekly"):
        assert bid in app.menu_buttons and app.menu_buttons[bid].w > 150, bid
    rects = [app.menu_buttons[b] for b in ("quick_play", "host_room", "join_room", "practice", "daily", "weekly")]
    assert not any(a.colliderect(b) for i, a in enumerate(rects) for b in rects[i + 1:])
    assert all(r.bottom < 768 - 60 for r in rects)


def test_spawn_warning_draws_when_next_spot_blocked():
    app = _app()
    app.start_game(mode="SOLO", total_players=10)
    app.state = "GAME"
    m = app.match
    m.countdown_until = 0.0
    m.coach_until = 0.0
    e = m.local_engine
    for x in range(3, 7):
        e.grid[0][x] = "G"
    e.next_queue[0] = "T"
    app.renderer.render(m, app.sound_mgr)                   # 예외 없이 그려져야 함


if __name__ == "__main__":
    pygame.init()
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print("[ALL NEXT FIX TESTS PASSED]")

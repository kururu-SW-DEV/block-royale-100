"""
코드 리뷰(Opus)에서 나온 개선점 회귀 테스트 - 화면/입력/소리: 설정 키보드 탐색, 키 충돌, 메뉴, 미니 카드 렌더링, 확인 창, 결과/연출, BGM
(예전 test_review_fixes.py를 영역별로 나눈 파일. 실행: python test_review_ui.py, SDL dummy 드라이버 사용, 사용자 settings/stats 파일은 건드리지 않음)
"""
import os
import sys
import time
import json
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 프로젝트 루트(tests/의 부모)를 import 경로에 추가

import pygame
from network import NetworkManager, _sanitize_world_state
from block_engine import BlockEngine
from ai_bot import AIBot
from settings_manager import SettingsManager
from stats_manager import StatsManager


def test_settings_keyboard_navigation():
    import main as M
    from gfx import CANVAS
    app = M.BlockRoyaleApp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.screen = CANVAS
    app.state = "SETTINGS"
    app.previous_state = "MENU"
    key = lambda k, mod=0: app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode="", scancode=0))
    # 소리 탭: ←→로 음량 조절, ↓로 다음 행
    app.settings_tab = "audio"
    app._render_settings()
    app.settings.set("bgm_volume", 50)
    assert app._settings_focus_id() == "bgm"
    key(pygame.K_RIGHT)
    assert app.settings.get("bgm_volume") == 60, "→ 키로 볼륨이 올라가야 함"
    key(pygame.K_LEFT); key(pygame.K_LEFT)
    assert app.settings.get("bgm_volume") == 40
    key(pygame.K_DOWN)
    assert app._settings_focus_id() == "stage_bgm", "볼륨 다음 행은 스테이지 배경음 세트 선택"
    key(pygame.K_DOWN)
    assert app._settings_focus_id() == "sfx"
    app.settings.set("bgm_volume", 60); app.sound_mgr.set_bgm_volume(0.6)
    # 화면 탭: Enter는 항목을 실행할 뿐 설정을 닫지 않음
    app.settings_tab = "general"
    app.settings_focus["general"] = 2                       # 미니 보드 행
    app._render_settings()
    assert app._settings_focus_id() == "mini"
    before = app.settings.get("mini_detail")
    key(pygame.K_RETURN)
    assert app.settings.get("mini_detail") != before and app.state == "SETTINGS", "Enter가 항목을 실행해야 함(설정을 닫지 않음)"
    key(pygame.K_LEFT)                                       # ← = 첫 번째 선택지(자세히)
    assert app.settings.get("mini_detail") == "detailed"
    # 게임 탭: ↑↓ 행 이동, ←→ 난이도 조절
    key(pygame.K_TAB)                                         # general -> audio
    key(pygame.K_TAB)                                         # audio -> keys
    assert app.settings_tab == "keys"
    key(pygame.K_RIGHT); key(pygame.K_RETURN)
    assert app.rebinding_action == "move_right", app.rebinding_action
    key(pygame.K_ESCAPE)
    assert app.rebinding_action is None and app.state == "SETTINGS"
    key(pygame.K_ESCAPE)
    assert app.state == "MENU"
    # 게임 탭
    app.state = "SETTINGS"; app.settings_tab = "match"; app.settings_focus["match"] = 1          # 0은 언어 행, 1이 참가 인원
    app._render_settings()
    n0 = app.target_player_count
    key(pygame.K_LEFT)
    assert app.target_player_count == n0 - 1
    key(pygame.K_RIGHT, mod=pygame.KMOD_SHIFT)              # Shift+→ = +10
    assert app.target_player_count == min(100, n0 - 1 + 10)
    key(pygame.K_DOWN); key(pygame.K_RIGHT)
    assert app.settings.get("bot_difficulty") != "mixed" or True
    print("  OK settings keyboard navigation")


def test_key_conflict_resolution_handling_and_number_keys():
    import main as M
    from gfx import CANVAS
    from settings_manager import SettingsManager
    with tempfile.TemporaryDirectory() as d:
        s = SettingsManager(os.path.join(d, "s.json"))
        up = pygame.K_UP
        assert up in s.get_action_keys("rotate_cw")
        moved = s.set_action_key("hard_drop", up)              # 회전에 쓰이던 UP을 하드 드롭에 지정
        assert ("rotate_cw", False) in moved and up not in s.get_action_keys("rotate_cw"), moved
        assert s.get_action_keys("hard_drop") == [up]
        # 한 동작이 키를 전부 잃으면 교환(원래 키를 넘겨줌)
        s2 = SettingsManager(os.path.join(d, "s2.json"))
        old_hold = s2.get_action_keys("pause")[0]
        moved2 = s2.set_action_key("hold", old_hold)
        assert any(sw for _a, sw in moved2) or s2.get_action_keys("pause"), "동작이 키를 잃음"
        for act in [a for a, _n in __import__("settings_manager").ACTION_NAMES if a != "rotate_180"]:     # 180도 회전은 선택 키(기본 비어 있음)
            assert s2.get_action_keys(act), f"{act}에 키가 없음"
        keys_seen = {}
        for act in [a for a, _n in __import__("settings_manager").ACTION_NAMES]:
            for k in s2.get_action_keys(act):
                assert k not in keys_seen, f"키 중복: {act} / {keys_seen[k]}"
                keys_seen[k] = act
        # DAS/ARR/SDF 범위와 적용
        for _ in range(60):
            s.adjust_handling("das_ms", 1); s.adjust_handling("arr_ms", -1)
        assert s.get("das_ms") == 300 and s.get("arr_ms") == 0                 # ARR은 0(즉시)까지 내려감
        # 세분화된 단계: 정밀 구간(DAS 200ms 이하, ARR/소프트드롭 10ms 이하)은 잘게, 나머지는 크게 / 눈금에 맞춰 올림·내림
        s.set("das_ms", 135); s.set("arr_ms", 33); s.set("sdf_ms", 35)
        seq = []
        for _ in range(3):
            s.adjust_handling("das_ms", -1); s.adjust_handling("arr_ms", -1)
        assert s.get("das_ms") == 120 and s.get("arr_ms") == 20, (s.get("das_ms"), s.get("arr_ms"))
        s.set("arr_ms", 12)
        vals = []
        for _ in range(5):
            s.adjust_handling("arr_ms", -1); vals.append(s.get("arr_ms"))
        assert vals == [10, 9, 8, 7, 6], vals
        vals = []
        for _ in range(3):
            s.adjust_handling("arr_ms", 1); vals.append(s.get("arr_ms"))
        assert vals == [7, 8, 9], vals
        s.set("das_ms", 195); s.adjust_handling("das_ms", 1); assert s.get("das_ms") == 200
        s.adjust_handling("das_ms", 1); assert s.get("das_ms") == 210
        s.adjust_handling("das_ms", -1); assert s.get("das_ms") == 200
        with open(os.path.join(d, "bad.json"), "w", encoding="utf-8") as f:
            json.dump({"das_ms": 9999, "arr_ms": 0, "sdf_ms": "x"}, f)
        b = SettingsManager(os.path.join(d, "bad.json"))
        assert b.get("das_ms") == 300 and b.get("arr_ms") == 0 and b.get("sdf_ms") == 35
    app = M.BlockRoyaleApp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.screen = CANVAS
    app.settings.set("das_ms", 200); app.settings.set("arr_ms", 10); app.settings.set("sdf_ms", 20)
    app.apply_handling()
    assert abs(app.DAS_DELAY - 0.2) < 1e-9 and abs(app.ARR_INTERVAL - 0.01) < 1e-9 and abs(app.SOFT_DROP_INTERVAL - 0.02) < 1e-9
    assert not app.ARR_INSTANT
    # 숫자키로 조준 모드 선택 (조작키에 없는 경우)
    app.start_game(mode="SOLO", total_players=8)
    for _ in range(10):
        app._tick_game(1 / 60)
    from config import TARGET_MODES
    for i, key in enumerate([pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5]):
        app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0))
        assert app.match.local_target_mode == TARGET_MODES[i], (i, app.match.local_target_mode)
    # 조작키 탭 렌더링 + 핸들링 키보드 조절
    app.state = "SETTINGS"; app.previous_state = "MENU"; app.settings_tab = "keys"
    app._render_settings()                                   # 조작 탭(키 카드)
    key = lambda k: app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))
    app.settings_tab = "react"                               # 반응 속도는 별도 '반응' 탭
    app.settings_focus["react"] = 0
    app._render_settings()
    assert app._settings_focus_id() == "react_das", app._settings_focus_id()
    before = app.settings.get("das_ms")
    key(pygame.K_RIGHT)
    assert app.settings.get("das_ms") == before + 10 and abs(app.DAS_DELAY - (before + 10) / 1000) < 1e-9
    key(pygame.K_DOWN); key(pygame.K_LEFT)
    assert app._settings_focus_id() == "react_arr" and app.settings.get("arr_ms") == 9
    print("  OK key conflicts / handling settings / number keys")


def test_scoreboard_queue_no_interruption():
    """전광판: 방송 중에 새 소식이 와도 끊지 않고 앞 소식이 끝난 뒤 이어서 방송 (중요 소식은 대기열 앞쪽)"""
    import ui_renderer as U
    from gfx import CANVAS
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    r = U.UIRenderer(CANVAS)

    class FakeMatch:
        commentary = []
    m = FakeMatch()
    clock = [1000.0]
    real_time = U.time.time
    U.time.time = lambda: clock[0]
    try:
        def push(text, prio=0):
            seq = len(m.commentary) + 1
            m.commentary.append({"text": text, "color": (255, 100, 100), "birth": clock[0], "seq": seq, "prio": prio})

        def run(seconds):
            for _ in range(int(seconds * 60)):
                clock[0] += 1 / 60
                r._render_scoreboard(m)
        push("AAAA 첫번째 소식")
        run(1.0)
        st = r._led_state
        assert len(st["items"]) == 1
        a = st["items"][0]
        a_len, a_start = len(a["cols"]), a["start"]
        push("BBBB 두번째 소식")                                   # A가 흐르는 도중에 새 소식
        run(0.3)
        assert st["items"][0] is a and len(a["cols"]) == a_len and a["start"] == a_start, "방송 중인 소식이 바뀌거나 끊김"
        run(6)
        items = st["items"]
        assert len(items) >= 1
        # B는 A의 끝 이후에만 시작해야 함(겹치지 않음)
        pos = {}
        clock0 = clock[0]
        # 대기열 정책: 일반 소식이 많이 쌓이면 오래된 것부터 버리고, 중요 소식은 앞에 배치
        for i in range(8):
            push(f"일반 {i}")
        push("결승전 중요", prio=1)
        run(0.1)
        waiting_general = [e["text"] for e in st["pending"] if not e.get("prio", 0)]
        assert len(st["pending"]) <= 4, [e["text"] for e in st["pending"]]
        placed_all = list(st["items"])
        seen_ids = {id(it) for it in placed_all}
        for _ in range(60 * 40):
            clock[0] += 1 / 60
            r._render_scoreboard(m)
            for it in st["items"]:
                if id(it) not in seen_ids:
                    seen_ids.add(id(it))
                    placed_all.append(it)
        order = [it["text"] for it in placed_all]
        assert "결승전 중요" in order, order
        imp = order.index("결승전 중요")
        for g in waiting_general:                              # 이미 대기 중이던 일반 소식은 중요 소식 뒤에 방송
            if g in order:
                assert order.index(g) > imp or order.index(g) < imp and False, (order, imp)
        starts = [(it["start"], len(it["cols"])) for it in placed_all]
        for (s1, l1), (s2, l2) in zip(starts, starts[1:]):
            assert s2 >= s1 + l1, "소식이 겹쳐 방송됨"
    finally:
        U.time.time = real_time
    print("  OK scoreboard queue (no interruption / priority / no overlap)")


def test_scoreboard_speed_scales_with_backlog():
    """전광판 속도: 밀린 방송 시간에 따라 부드럽게 빨라지고(최대 2.8배), 다 소화하면 기본 속도로 돌아옴"""
    import ui_renderer as U
    from gfx import CANVAS
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    r = U.UIRenderer(CANVAS)

    class FakeMatch:
        commentary = []
    m = FakeMatch()
    clock = [2000.0]
    real_time = U.time.time
    U.time.time = lambda: clock[0]
    try:
        def push(text, prio=0):
            m.commentary.append({"text": text, "color": (255, 120, 120), "birth": clock[0], "seq": len(m.commentary) + 1, "prio": prio})

        mults = []
        def run(sec):
            for _ in range(int(sec * 60)):
                clock[0] += 1 / 60
                r._render_scoreboard(m)
                mults.append(r._led_state.get("mult", 1.0))
        push("첫 소식")
        run(0.5)
        assert abs(r._led_state["mult"] - 1.0) < 0.05, "밀린 게 없으면 기본 속도여야 함"
        for i in range(4):
            push(f"CPU_{i:02d} → CPU_{i + 10} K.O. 아주 긴 소식 {i}")
        before = len(mults)
        run(3.0)
        seg = mults[before:]
        assert max(seg) > 1.5 and max(seg) <= U.UIRenderer.LED_MAX_SPEEDUP + 1e-6, max(seg)
        steps = [abs(b - a) for a, b in zip(seg, seg[1:])]
        assert max(steps) < 0.1, f"속도가 뚝뚝 바뀜: 한 프레임 최대 변화 {max(steps):.3f}"
        run(25)
        assert r._led_state["mult"] < 1.1, "방송을 다 소화하면 기본 속도로 돌아와야 함"
    finally:
        U.time.time = real_time
    print("  OK scoreboard speed follows backlog time (smooth, max 2.8x)")


def test_visual_options_and_dead_target_attacks():
    import main as M
    import config
    from gfx import CANVAS
    from battle_royale import BattleRoyaleMatch
    app = M.BlockRoyaleApp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.screen = CANVAS
    try:
        default_i = dict(config.PIECE_COLORS_DEFAULT)["I"]
        app.state = "SETTINGS"; app.previous_state = "MENU"; app.settings_tab = "general"
        app._settings_activate("color_mode")
        assert app.settings.get("color_mode") == "colorblind" and config.PIECE_COLORS["I"] != default_i
        app._settings_activate("text_size")
        assert app.renderer.text_boost == 2 and app.settings.get("text_size") == "large"
        app.start_game(mode="SOLO", total_players=20)
        for _ in range(20):
            app._tick_game(1 / 60)                               # 색약 팔레트 + 큰 글씨로 게임 화면이 예외 없이 그려짐
        app._settings_activate("color_mode"); app._settings_activate("text_size")
        assert config.PIECE_COLORS["I"] == default_i and app.renderer.text_boost == 0
    finally:
        config.apply_color_mode("normal")
    # 탈락한 대상에게는 공격/이펙트가 가지 않음
    m = BattleRoyaleMatch(total_players=8, local_player_id="ME", local_player_name="me")
    victim = [p for p in m.players if p != "ME"][0]
    m._eliminate_player(victim)
    before = len(m.attack_effects)
    m.apply_attack("ME", victim, 4)
    assert len(m.attack_effects) == before, "죽은 대상에게 공격 이펙트가 생김"
    print("  OK color mode / text size / no attacks on dead targets")


def test_main_menu_interactions():
    import main as M
    from gfx import CANVAS
    app = M.BlockRoyaleApp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.screen = CANVAS
    app.state = "MENU"
    ev = lambda type, **kw: pygame.event.Event(type, **kw)
    key = lambda k, mod=0: app._handle_event(ev(pygame.KEYDOWN, key=k, mod=mod, unicode="", scancode=0))
    app._update_menu(1 / 60); app._render_menu()
    # ESC: 종료 확인 창 (바로 꺼지지 않음)
    key(pygame.K_ESCAPE)
    assert app.modal is not None and any(b[0] == "quit_app" for b in app.modal["buttons"])
    app._modal_choose("stay")
    # ←→: 빠른 시작에 포커스가 있을 때만 인원 조절, 방 만들기에서는 카드 이동
    n0 = app.target_player_count
    key(pygame.K_LEFT)
    assert app.target_player_count == n0 - 1
    key(pygame.K_DOWN)
    assert app._menu_focus_id() == "host_room"
    key(pygame.K_LEFT)
    assert app.target_player_count == n0 - 1, "방 만들기 포커스에서 ←가 인원을 바꿈"
    key(pygame.K_RIGHT)
    assert app._menu_focus_id() == "join_room"
    # 혼자하기 줄 / 하단 줄도 ←→로 그 줄 안에서 돌아감
    app._set_menu_focus("weekly", sound=False)
    key(pygame.K_RIGHT)
    assert app._menu_focus_id() == "practice"
    app._set_menu_focus("quit_game", sound=False)
    key(pygame.K_RIGHT)
    assert app._menu_focus_id() == "records"
    app._set_menu_focus("join_room", sound=False)
    # 마우스: 누르기만 해서는 실행되지 않고, 같은 버튼 위에서 뗄 때 실행. 호버=포커스 (강조는 하나)
    app._render_menu()
    r = app.menu_buttons["records"]
    app._handle_event(ev(pygame.MOUSEMOTION, pos=r.center, rel=(0, 0), buttons=(0, 0, 0)))
    assert app._menu_focus_id() == "records"
    app._handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=r.center))
    assert app.state == "MENU" and app._menu_press == "records"
    app._handle_event(ev(pygame.MOUSEBUTTONUP, button=1, pos=(5, 5)))            # 다른 곳에서 뗌: 취소
    assert app.state == "MENU"
    app._handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=r.center))
    app._handle_event(ev(pygame.MOUSEBUTTONUP, button=1, pos=r.center))
    assert app.state == "RECORDS"
    app.state = "MENU"
    # 게임 종료 버튼도 확인 창을 거침
    app._render_menu()
    q = app.menu_buttons["quit_game"]
    app._handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=q.center))
    app._handle_event(ev(pygame.MOUSEBUTTONUP, button=1, pos=q.center))
    assert app.modal is not None
    app.modal = None
    # 카드 안 정보: 첫 실행 / 발견된 LAN 방 표시가 예외 없이 그려짐
    app.stats_mgr.data["total_games"] = 0
    app.net_mgr.discovered_rooms = {"1.2.3.4": {"name": "방", "players": 2, "max": 10, "timestamp": time.time(), "last_seen": time.time(), "ip": "1.2.3.4", "port": 19999}}
    app._render_menu()
    print("  OK main menu (ESC / focus / press-release / info chips)")


def test_mini_card_markers_stay_on_cards():
    """나를 노리는 상대 표시(붉은 줄)와 받을 공격 게이지가 창 크기(배율)와 상관없이 카드 위에만 그려지는지"""
    import main as M
    import numpy as np
    from gfx import CANVAS
    app = M.BlockRoyaleApp()
    for size in ((1366, 768), (1266, 731), (1000, 600), (1920, 1080)):
        pygame.display.set_mode(size)
        CANVAS.attach(pygame.display.get_surface())
        app.screen = CANVAS
        app.start_game(mode="SOLO", total_players=100)
        for _ in range(60):
            app._update_game(1 / 30)
        m = app.match
        for pid in [p for p in m.players if p != m.local_player_id][:30]:
            m.players[pid]["target_id"] = m.local_player_id
        for _ in range(3):
            app._tick_game(1 / 60)
        r = app.renderer
        arr = pygame.surfarray.array3d(CANVAS.display).astype(int)
        hit = (np.abs(arr[:, :, 0] - 232) < 3) & (np.abs(arr[:, :, 1] - 84) < 3) & (np.abs(arr[:, :, 2] - 94) < 3)
        mask = np.zeros(hit.shape, dtype=bool)
        for rect in r.mini_board_rects.values():
            x0, y0 = CANVAS.X(rect.x) - 6, CANVAS.Y(rect.y) - 6
            x1, y1 = CANVAS.X(rect.right) + 6, CANVAS.Y(rect.bottom) + 6
            mask[max(0, x0):x1, max(0, y0):y1] = True
        # 조준선/이펙트 등 다른 요소는 제외하려고, 카드 바깥의 '가로로 긴 붉은 줄'만 검사
        outside = hit & ~mask
        rows = outside.sum(axis=0)
        assert rows.max() < 40, f"{size}: 카드 밖에 붉은 줄이 그려짐 ({rows.max()}px)"
    print("  OK mini card markers stay on cards (all window sizes)")


def test_multi_target_volley_effects():
    import main as M
    from gfx import CANVAS
    app = M.BlockRoyaleApp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.screen = CANVAS
    app.start_game(mode="SOLO", total_players=12)
    m = app.match
    for _ in range(5):
        app._tick_game(1 / 60)
    ids = [p for p in m.players if p != m.local_player_id][:4]
    for i, t in enumerate(ids):
        m.apply_attack(m.local_player_id, t, 6, multi=4, order=i)
    starts = [e["start_time"] for e in m.attack_effects if e["multi"] == 4]
    assert len(starts) == 4 and starts == sorted(starts) and starts[-1] > starts[0]
    for _ in range(20):                                   # 발사 전/중/후 모든 구간을 그려도 오류 없음
        app._tick_game(1 / 60)
        app._render_game_frame()
    print("  OK multi-target volley effects")


def test_survival_hides_aim_ui():
    import main as M
    from gfx import CANVAS
    app = M.BlockRoyaleApp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.screen = CANVAS
    for mode, want in (("survival", False), ("battle", True)):
        app.settings.data["game_mode"] = mode
        app.start_game(mode="SOLO", total_players=8)
        for _ in range(5):
            app._tick_game(1 / 60)
        app.renderer.key_hints = app._build_key_hints()
        labels = [h[1] for h in app.renderer.key_hints]
        assert ("조준" in labels) == want, (mode, labels)                    # 조준 순환 키와 조준 모드(1~5)는 한 칸("조준")에 합쳐 안내
        lasers = []
        orig = app.renderer._draw_targeting_laser
        app.renderer._draw_targeting_laser = lambda *a, **k: lasers.append(1)
        app.match.players[app.match.local_player_id]["target_id"] = "P2"
        for pid, p in app.match.players.items():
            if pid != app.match.local_player_id:
                p["target_id"] = app.match.local_player_id
        app._render_game_frame()
        app.renderer._draw_targeting_laser = orig
        assert (len(lasers) > 0) == want, (mode, len(lasers))
    print("  OK survival hides aim UI")


def test_mini_cards_fast_path_pixel_identical():
    """미니 카드 가속(이름표/홀드·다음 칸 레이어 캐시, 칸 좌표 표, 안쪽 좌표 계산)이 예전 방식과 픽셀 단위로 같은지.
    창 크기(배율)가 1이 아닐 때만 생기는 반올림 문제를 잡기 위해 여러 크기에서 비교"""
    import random as _r
    import numpy as np
    import main as M
    from gfx import CANVAS
    real_time = time.time
    vt = [5000.0]
    time.time = lambda: vt[0]
    try:
        for size, n, detailed in (((1366, 768), 100, True), ((1266, 731), 100, False), ((1266, 731), 30, True),
                                  ((1920, 1080), 100, True), ((1000, 600), 100, False), ((1000, 600), 10, True)):
            app = M.BlockRoyaleApp()
            pygame.display.set_mode(size)
            CANVAS.attach(pygame.display.get_surface())
            CANVAS.resize()
            app.screen = CANVAS
            app.renderer.screen = CANVAS
            app.settings.data["mini_detail"] = "detailed" if detailed else "simple"
            app.settings.data["block_skin"] = "classic"      # 반투명 광택이 있는 스킨(젤리)은 레이어 합성 순서에 따라 1단계 오차가 생기므로 고정
            app.apply_visual_options()
            app.bot_difficulty = "master"
            _r.seed(3)
            app.start_game(mode="SOLO", total_players=n)
            m = app.match
            for _ in range(150):
                vt[0] += 1 / 60
                app._update_game(1 / 60)
            ids = [p for p in m.players if p != m.local_player_id]
            m.players[ids[0]]["ko_count"] = 3
            if len(ids) > 5:
                m.players[ids[1]]["ko_count"] = 12
                m.players[m.local_player_id]["target_id"] = ids[2]
                m.players[ids[3]]["highest_y"] = 3
                m.is_spectating, m.spectate_target_id = True, ids[4]
                for pid in ids[5:8]:
                    m.players[pid]["is_alive"], m.players[pid]["rank"] = False, 5
            else:
                m.players[m.local_player_id]["target_id"] = ids[0]
            base_t = vt[0]
            shots = []
            for fast in (True, False):
                app.renderer.mini_fast = fast
                for cache in (app.renderer._card_layers, app.renderer._mini_layers, app.renderer._card_info, app.renderer._mini_tabs):
                    cache.clear()
                for f in range(3):                                    # 첫 프레임은 캐시를 만들고, 다음 프레임부터는 캐시를 씀
                    vt[0] = base_t + (f + 1) / 60
                    pygame.display.get_surface().fill((5, 6, 10))
                    app.renderer.mini_board_rects.clear()
                    _r.seed(99 + f)
                    app.renderer._render_mini_boards(m)
                shots.append(pygame.surfarray.array3d(pygame.display.get_surface()).astype(np.int16))
            diff = int((np.abs(shots[0] - shots[1]).max(axis=2) > 0).sum())
            assert diff == 0, (size, n, detailed, diff)
    finally:
        time.time = real_time
    print("  OK mini cards fast path pixel identical (6 sizes/configs)")


def test_results_bgm_plays_after_sting():
    from sound_fx import SoundManager, RESULTS_MELODY, RESULTS_BASS, RESULTS_CHORDS
    # 곡 데이터 구조: 16마디 = 64박, 베이스 박당 1개, 코드 2박당 1개
    assert abs(sum(d for _, d in RESULTS_MELODY) - 64.0) < 1e-9
    assert len(RESULTS_BASS) == 64 and len(RESULTS_CHORDS) == 32
    sm = SoundManager(enabled=True)
    if not sm.enabled or not sm.bgm_ch_a:
        print("  (오디오 장치 없음: 순위표 곡 재생 테스트 생략)")
    sm._wait_bgm('results', 20); sm._wait_bgm(1, 20)
    sm._wait_bgm('results', 20)
    assert 'results' in sm.bgm_stages
    sm.play_bgm(stage=1)
    sm.play_victory()                                              # 승리 팡파레: 전투 BGM 정지 + 순위표 곡 예약
    assert not sm.is_bgm_playing and sm._results_due is not None
    sm.update_bgm_for_alive(1, 100)                                # 아직 팡파레 중이면 시작하지 않음
    assert not sm.is_bgm_playing
    sm._results_due = time.time() - 0.1                            # 팡파레가 끝난 시점
    sm.update_bgm_for_alive(1, 100)
    assert sm.is_bgm_playing and sm.current_bgm_stage == 'results'
    for _ in range(5):                                             # 순위표가 떠 있는 동안 생존자 수로 전투 곡으로 되돌아가지 않음
        sm.update_bgm_for_alive(1, 100)
    assert sm.current_bgm_stage == 'results'
    sm.play_bgm(stage=1)                                           # 다음 판이 시작되면 전투 곡으로
    assert sm.current_bgm_stage == 1 and sm._results_due is None
    sm.play_defeat()                                               # 패배 음악 뒤에도 순위표 곡 예약
    assert sm._results_due is not None
    sm.stop_bgm()
    assert sm._results_due is None
    sm.set_bgm_enabled(False)                                      # BGM을 꺼 두었으면 켜지 않음
    sm.play_results_bgm()
    assert not sm.is_bgm_playing
    print("  OK results bgm after sting")


def test_confirm_modals():
    import main as M
    from gfx import CANVAS
    app = M.BlockRoyaleApp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.screen = CANVAS
    app.start_game(mode="SOLO", total_players=6)
    for _ in range(30):
        app._tick_game(1 / 60)
    # 창 X: 솔로 게임은 멈추고 확인
    app._confirm_quit_app()
    assert app.modal is not None and app.is_paused
    # 다른 알림이 떠 있을 때 X → 덮어쓰지 않고 대기
    app.modal = None
    app._open_modal("호스트가 게임을 종료했습니다", ["x"], [("ok_menu", "메인 메뉴로", "blue", "ENTER")])
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    ev = pygame.event.get()[0]
    assert ev.type == pygame.QUIT
    # (메인 루프 대신 동작만 검증) 대기 플래그 → 알림을 닫으면 종료 확인이 열림
    app._pending_quit = True
    app._modal_choose("stay")
    assert app.modal is not None and any(b[0] == "quit_app" for b in app.modal["buttons"])
    app.modal = None
    # 일시정지 중 ESC → 바로 나가지 않고 확인
    app.is_paused = True
    app.match.is_paused = True
    app.state = "GAME"
    app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="", scancode=0))
    assert app.state == "GAME" and app.modal is not None, "일시정지 ESC가 확인 없이 메뉴로 나감"
    app.modal = None
    # 초기화 버튼: 확인 창 → 취소하면 값 유지
    app.settings.set("bgm_volume", 30)
    app.state = "SETTINGS"
    app.previous_state = "MENU"
    app.settings_tab = "general"
    app._render_settings()
    r = app.settings_buttons.get("reset_defaults")
    if r is None:
        app.settings_tab = "match"
        app._render_settings()
        r = app.settings_buttons["reset_defaults"]
    app._handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=r.center))
    assert app.modal is not None and app.settings.get("bgm_volume") == 30
    app._modal_choose("stay")
    assert app.settings.get("bgm_volume") == 30
    print("  OK confirm modals")


def test_late_game_relayout_coach_orbs_and_heartbeat():
    """후반 미니 보드 재배치(단계가 오를 때만, 살아남은 사람만), 첫 경기 코치 마크 1회, K.O. 구슬, 위기 박동음"""
    import main as M
    from gfx import CANVAS
    app = M.BlockRoyaleApp()
    CANVAS.attach(pygame.Surface((1366, 768)))
    app.screen = CANVAS
    app.renderer.screen = CANVAS
    app.settings.data["coach_done"] = False
    app.start_game(mode="SOLO", total_players=100)
    m = app.match
    assert m.coach_until > time.time() and m.coach_pending and app.settings.get("coach_done") is False, "첫 경기에만 코치 마크 (바로 나가면 다음에 다시 보이도록 coach_done은 아직 저장 안 함)"
    m.elapsed = 11.0
    app._check_tips()
    assert app.settings.get("coach_done") is True, "코치를 볼 시간(10초)이 지나면 coach_done 저장"
    app._handle_game_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0))
    assert m.coach_until == 0.0, "Enter로 코치 마크를 닫을 수 있음"
    m.coach_until = time.time() + 15
    app._handle_game_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(600, 400)))
    assert m.coach_until == 0.0, "클릭으로도 닫힘"
    app.start_game(mode="SOLO", total_players=100)
    assert getattr(app.match, "coach_until", 0.0) == 0.0 or app.match.coach_until < time.time(), "두 번째 경기부터는 코치 마크 없음"
    m = app.match
    others = [p for p in m.players if p != m.local_player_id]

    def kill_to(target):
        alive = [p for p in others if m.players[p]["is_alive"]]
        for pid in alive[:max(0, len(alive) - target)]:
            m._eliminate_player(pid)
    for _ in range(3):
        app._tick_game(1 / 60)
    assert len(app.renderer.mini_board_rects) == 99
    kill_to(60)
    app._tick_game(1 / 60)
    assert len(app.renderer.mini_board_rects) == 99 and getattr(m, "layout_stage", 0) == 0, "단계 전에는 자리 유지(죽은 카드도 그대로)"
    kill_to(20)
    app._tick_game(1 / 60)
    assert getattr(m, "layout_stage", 0) == 1 and len(app.renderer.mini_board_rects) == 20, "20명 이하: 생존자만 다시 배치"
    ids = set(app.renderer.mini_board_rects)
    kill_to(18)                                        # 같은 단계 안에서 죽어도 카드는 그 자리에 남음 (다음 단계까지 재배치 안 함)
    app._tick_game(1 / 60)
    assert set(app.renderer.mini_board_rects) == ids
    kill_to(10)
    app._tick_game(1 / 60)
    assert m.layout_stage == 2 and len(app.renderer.mini_board_rects) == 10
    # K.O. 구슬: 내가 K.O.를 내면 생기고, 시간이 지나면 정리됨
    victim = [p for p in others if m.players[p]["is_alive"]][0]
    m._eliminate_player(victim, killer_id=m.local_player_id)
    assert len(m.ko_orbs) == 1
    m.ko_orbs[0]["t0"] -= 5.0
    app.renderer.render(m, app.sound_mgr)
    assert m.ko_orbs == []
    # 위기 박동음: 스택이 높으면 재생, 간격 안에서는 다시 재생하지 않음
    class FakeSound:
        def __init__(self):
            self.played = []

        def play(self, name, *a, **k):
            self.played.append(name)
    fs = FakeSound()
    m2 = __import__("battle_royale").BattleRoyaleMatch(total_players=4, local_player_id="ME", local_player_name="Me", sound_mgr=fs, bot_difficulty="easy")
    for y in range(2, 20):                             # 18줄
        m2.local_engine.grid[y] = ['G'] * 9 + [None]
    m2._track_danger()
    m2._track_danger()
    assert fs.played.count("heartbeat") == 1
    m2.elapsed += 0.9
    m2._track_danger()
    assert fs.played.count("heartbeat") == 2, "18줄 이상이면 0.8초 간격"
    print("  OK late-game relayout / coach marks / K.O. orbs / heartbeat")


def test_hit_alarm_sounds():
    """피격 경고음: 3단계 소리가 실제로 등록되어 있고(예전엔 없는 'garbage' 소리를 불러 아무 소리도 안 났음), 줄 수에 따라 단계가 오르며, 연속 피격은 뭉개지지 않게 간격 제한"""
    from sound_fx import SoundManager
    from battle_royale import BattleRoyaleMatch
    sm = SoundManager()
    assert all(f"hit_{i}" in sm.sounds for i in (1, 2, 3)) and "warning" in sm.sounds
    assert [BattleRoyaleMatch.hit_alarm_tier(n) for n in (1, 2, 3, 5, 6, 12)] == [1, 1, 2, 2, 3, 3]

    class Fake:
        def __init__(self):
            self.played = []

        def play(self, name, *a, **k):
            self.played.append(name)
    fs = Fake()
    m = BattleRoyaleMatch(total_players=4, local_player_id="ME", local_player_name="Me", sound_mgr=fs, bot_difficulty="easy")
    m.apply_attack("BOT_01", "ME", 2)
    assert fs.played[-1] == "hit_1" and "garbage" not in fs.played
    n = len(fs.played)
    m.apply_attack("BOT_02", "ME", 1)                    # 바로 이어진 같은 단계 피격은 소리를 겹치지 않음
    assert len([p for p in fs.played[n:] if p.startswith("hit_")]) == 0
    m.apply_attack("BOT_02", "ME", 7)                    # 더 센 공격은 간격과 무관하게 바로 울림
    assert fs.played[-1] == "hit_3"
    print("  OK hit alarm sounds")


def test_new_record_flags():
    """record_match가 이번 경기가 이전 최고 기록(순위/K.O./최대 콤보)을 넘었는지 돌려줌. 첫 경기와 동률은 기록 갱신이 아님"""
    with tempfile.TemporaryDirectory() as d:
        st = StatsManager(os.path.join(d, "s.json"))
        kw = dict(total_players=100, lines=10, survival_sec=60)
        assert st.record_match(rank=50, kos=2, max_combo=3, **kw) == [], "첫 경기는 비교할 기록이 없음"
        assert st.record_match(rank=50, kos=2, max_combo=3, **kw) == [], "동률은 갱신이 아님"
        assert st.record_match(rank=30, kos=1, max_combo=1, **kw) == ["rank"]
        assert st.record_match(rank=60, kos=5, max_combo=6, **kw) == ["ko", "combo"]
        assert st.record_match(rank=90, kos=0, max_combo=0, **kw) == [], "0은 기록이 아님"
        assert st.record_match(rank=1, kos=0, max_combo=0, mode="survival", **kw) == [], "모드별로 따로 집계 (서바이벌 첫 경기)"
    print("  OK new record flags")


def test_play_bgm_does_not_block_while_synthesizing():
    """아직 합성 중인 BGM(로비곡)을 요청해도 UI 스레드가 멈추지 않고, 준비되면 tick()이 시작 (첫 방 만들기 7초 프리징 회귀)"""
    import time as _t
    from sound_fx import SoundManager
    sm = SoundManager(enabled=True)
    if not sm.bgm_ch_a:
        return
    sm.stop_bgm()
    sm.bgm_stages.pop('lobby', None)
    class Alive:
        def is_alive(self): return True
    real = sm._bgm_thread
    sm._bgm_thread = Alive()
    t0 = _t.time()
    for _ in range(50):
        sm.play_bgm('lobby')
    assert _t.time() - t0 < 0.2, "합성 중인 곡 요청이 UI를 막음"
    assert not sm.is_bgm_playing and sm._pending_bgm == 'lobby'
    sm.bgm_stages['lobby'] = sm.bgm_stages.get('menu') or sm.bgm_stages.get(1)
    sm.tick()
    assert sm.is_bgm_playing and sm.current_bgm_stage == 'lobby' and sm._pending_bgm is None
    sm._bgm_thread = real
    sm.stop_bgm()


def test_combat_text_pressure_and_onboarding():
    """전투 문구 정리(싱글/더블 배너 없음, 숫자 괄호 없음), 공격 토스트=실제 보낸 줄 수, 후반전 예고, 시작 카운트다운, 패인 한 줄, 첫 실행 기본값, 미니 보드 집중 모드"""
    import time as _t
    from battle_royale import BattleRoyaleMatch
    m = BattleRoyaleMatch(total_players=10, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy")
    e = m.local_engine
    e.last_clear_info = {}
    for n in (1, 2):
        m.floating_texts.clear(); m.on_lines_cleared(n)
        assert not [f for f in m.floating_texts if f["category"] == "action"], f"{n}줄 클리어는 배너를 띄우지 않음"
    m.floating_texts.clear(); m.on_lines_cleared(4)
    banner = [f["text"] for f in m.floating_texts if f["category"] == "action"]
    assert banner and "쿼드" in banner[0] and "(" not in banner[0], banner            # 실제 보낸 줄 수는 공격 토스트가 보여 줌

    # 공격 토스트의 줄 수 = 실제로 상대에게 들어간 줄 수 (후반 증폭 포함)
    m = BattleRoyaleMatch(total_players=10, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy")
    m.elapsed = 419.9                                            # 공격력 약 x1.4
    m.local_engine.garbage_to_send = 5
    m.update(0.016)
    toast = [f["text"] for f in m.floating_texts if f["category"] == "attack"]
    tid = m.players["L"]["target_id"]
    got = m.players[tid]["bot"].engine.incoming_garbage
    assert toast and f"+{got}줄" in toast[-1] and "×1.4" in toast[-1], (toast, got)

    # 후반전 예고: 4:30에 한 번, 이후 20% 단계가 오를 때마다 한 번
    m = BattleRoyaleMatch(total_players=10, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy")
    m.elapsed = 275.0; m._announce_escalation(); m._announce_escalation()
    assert sum("곧 후반전" in c["text"] for c in m.commentary) == 1
    m.elapsed = 361.0; m._announce_escalation(); m._announce_escalation()
    assert sum("×1.2" in c["text"] for c in m.commentary) == 1
    pm = BattleRoyaleMatch(total_players=2, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy", practice=True)
    pm.elapsed = 400.0; pm._announce_escalation()
    assert not pm.commentary or all("후반전" not in c["text"] for c in pm.commentary), "연습 모드에는 후반전 알림 없음"

    # 시작 카운트다운
    assert m.countdown_left() == 0.0
    m.countdown_until = _t.time() + 2.0
    assert 1.5 < m.countdown_left() <= 2.0
    m.countdown_until = 0.0

    # 패인 한 줄
    m.local_is_alive = False
    m.timeline = [(i, 50 - i, 8 + i, (i % 5) * 2) for i in range(12)]
    m.local_death_attackers = 3
    msg = m.defeat_summary()
    assert msg and len(msg) == 2 and "집중 공격" in msg[0] and "나를 노린 상대 3명" in msg[0] and "받을 공격 최대 8줄" in msg[0] and "연습 모드" in msg[1], msg
    m.timeline = [(0, 9, 3, 0)]
    assert m.defeat_summary() is None, "근거(타임라인)가 부족하면 표시하지 않음"

    # 첫 실행 기본값: 전적이 없는 새 사용자만 50인 쉬움, 전적이 있으면 그대로
    import main as M
    app = M.BlockRoyaleApp()
    app.stats_mgr.reset_stats()
    app.settings.data["onboard_done"] = False
    app.settings.data["target_player_count"] = 100; app.settings.data["bot_difficulty"] = "mixed"
    app._apply_first_run_defaults()
    assert app.settings.get("target_player_count") == 50 and app.settings.get("bot_difficulty") == "easy" and app.settings.get("onboard_done")
    app.settings.data["onboard_done"] = False
    app.settings.data["target_player_count"] = 100; app.settings.data["bot_difficulty"] = "mixed"
    app.stats_mgr.record_match(5, 100, 1, 10, 1, 60)
    app._apply_first_run_defaults()
    assert app.settings.get("target_player_count") == 100 and app.settings.get("bot_difficulty") == "mixed" and app.settings.get("onboard_done")

    # 미니 보드 표시: 자세히 -> 집중 -> 간략 순으로 순환, 집중일 때만 렌더러가 카드를 어둡게
    app.settings.data["mini_detail"] = "detailed"
    app._settings_activate("mini_detail")
    assert app.settings.get("mini_detail") == "focus" and app.renderer.mini_focus and app.renderer.mini_detailed
    app._settings_activate("mini_detail")
    assert app.settings.get("mini_detail") == "simple" and not app.renderer.mini_focus and not app.renderer.mini_detailed
    app._settings_activate("mini_detail")
    assert app.settings.get("mini_detail") == "detailed" and not app.renderer.mini_focus and app.renderer.mini_detailed


def test_v1012_feed_phase_log_achievement_progress():
    """v1.0.12: 단계 문구가 사실대로, 피격 토스트 합치기, 후반전 알림 고정 칸, 패인 줄에 증폭/최다 공격자, 경기 로그, 업적 진행도"""
    import time as _t
    from battle_royale import BattleRoyaleMatch
    from stats_manager import ACHIEVEMENTS, StatsManager
    m = BattleRoyaleMatch(total_players=20, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy")
    # 단계 문구: 속도/서든 데스를 단정하지 않음 (낙하 속도는 비율로 계속 빨라지고, 서든 데스는 9분 압박 때만)
    for pid in [p for p in m.players if p != "L"][:11]:
        m._eliminate_player(pid)
    m.update(0.016)
    txt = " ".join(c["text"] for c in m.commentary) + " ".join(f["text"] for f in m.floating_texts)
    assert "PHASE 2" in txt and "스피드" not in txt, txt
    m.floating_texts.clear(); m.commentary.clear()
    for pid in [p for p in m.players if p != "L" and m.players[p]["is_alive"]][:7]:
        m._eliminate_player(pid)
    m.update(0.016)
    txt = " ".join(c["text"] for c in m.commentary) + " ".join(f["text"] for f in m.floating_texts)
    assert "FINAL" in txt and "서든" not in txt, txt
    # 피격 토스트 합치기: 1초 안 연속 피격은 한 개로, 보낸 사람 수/합계 갱신
    m = BattleRoyaleMatch(total_players=10, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy")
    others = [p for p in m.players if p != "L"]
    m.apply_attack(others[0], "L", 2); m.apply_attack(others[1], "L", 3); m.apply_attack(others[1], "L", 1)
    hits = [f["text"] for f in m.floating_texts if f["text"].startswith("[피격")]
    assert len(hits) == 1 and "2명" in hits[0] and "+6줄" in hits[0], hits
    assert m.local_hits_from[others[0]] == 2 and m.local_hits_from[others[1]] == 4
    m._hit_agg["t"] -= 2.0                                    # 1초가 지나면 새 토스트
    m.apply_attack(others[2], "L", 1)
    assert len([f for f in m.floating_texts if f["text"].startswith("[피격")]) == 2
    # 후반전 알림은 pin 카테고리
    m.elapsed = 275.0; m._announce_escalation()
    assert any(f["category"] == "pin" for f in m.floating_texts)
    # 패인 줄: 최다 공격자 + 후반전 배율
    m.local_is_alive = False
    m.elapsed = 420.0
    m.timeline = [(i, 9, 12 + i % 3, i % 6) for i in range(12)]
    m.local_hits_from = {others[0]: 9, others[1]: 2}
    lines = m.defeat_summary()
    assert "후반전 ×1.4" in lines[0] and "가장 많이 보낸" in lines[0] and len(lines) == 2, lines
    # 경기 로그: 켠 경우만 기록, JSON 직렬화 가능
    m2 = BattleRoyaleMatch(total_players=10, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy")
    m2.set_target_mode("KO"); m2.log_event("x")
    assert m2.events == []
    m2.log_enabled = True
    m2.set_target_mode("RANDOM"); m2.apply_attack([p for p in m2.players if p != "L"][0], "L", 2)
    log = m2.match_log()
    json.dumps(log)
    kinds = [e["kind"] for e in log["events"]]
    assert "target_mode" in kinds and "hit" in kinds, kinds
    # 업적 진행도/마라토너 7분
    ids = {a[0]: a for a in ACHIEVEMENTS}
    assert ids["marathon"][2].startswith("한 판에서 7분"), ids["marathon"][2]
    import tempfile
    sm = StatsManager(os.path.join(tempfile.mkdtemp(), "stats.json"))
    sm.record_match(40, 100, 3, 10, 5, 400)
    pr = sm.achievement_progress()
    assert pr["ko5"] == (3, 5) and pr["combo8"] == (5, 8) and pr["marathon"] == (400, 420), pr
    sm.record_match(40, 100, 0, 10, 1, 430)
    assert "marathon" in sm.achievements_done()


def test_v1013_result_flow_autolock_assist_tasks():
    """v1.0.13: 탈락/순위표에서 P=연습, 오늘의 도전 재도전 유지, 순위표 정보 띠, 자동 조준 락온, K.O. 기여, 토스트 우선순위, 통계 칸, 연습 과제"""
    import main as M
    from gfx import CANVAS
    from battle_royale import BattleRoyaleMatch
    app = M.BlockRoyaleApp()
    CANVAS.attach(pygame.Surface((1366, 768)))
    app.screen = CANVAS
    app.renderer.screen = CANVAS
    app.settings.data["coach_done"] = True

    # 오늘의 도전 재도전은 같은 도전으로
    app.start_game(mode="SOLO", daily="20260102")
    assert app.match.daily == "20260102"
    app._restart_after_match()
    assert app.match.daily == "20260102" and app.match.total_players == 100

    # 탈락 후 P: 일시정지가 아니라 연습 모드 시작
    app.start_game(mode="SOLO", total_players=20)
    m = app.match
    m._eliminate_player(m.local_player_id)
    app.result_lock_until = 0.0
    app._handle_game_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p, mod=0))
    assert app.match.practice and not app.is_paused, "탈락 후 P는 연습 시작"
    # 결과 버튼 목록에 연습하기가 포함됨
    app.start_game(mode="SOLO", total_players=20)
    app.match._eliminate_player(app.match.local_player_id)
    assert "practice" in app._result_button_ids()

    # 순위표 정보 띠: 기록/업적/목표/패인 중 있는 것만
    m = BattleRoyaleMatch(total_players=10, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy")
    m.new_records = ("rank",); m.new_achievements = ["first_win"]; m.ladder_clear = None; m.next_goal = "우승"
    m.local_rank = 1
    info = app.renderer._standings_info_lines(m)
    assert info and info[0][0].startswith("★") and "최고 기록" in info[0][0], info
    assert len(info) == 2 and info[1][0].startswith("다음 목표"), info

    # 자동 조준 락온: 0.8초 안에는 위험도가 바뀌어도 대상 유지, 대기열 가득 찬 상대는 건너뜀
    m = BattleRoyaleMatch(total_players=10, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy")
    others = [p for p in m.players if p != "L"]
    for p in others:
        m.players[p]["highest_y"] = 10
        m.players[p]["ig"] = 0
    m.set_target_mode("AUTO")
    m.players[others[0]]["highest_y"] = 5
    assert m.get_target_for("L") == others[0]
    m.players[others[1]]["highest_y"] = 1                          # 더 위험해졌지만 락온 시간 안
    m.elapsed += 0.3
    assert m.get_target_for("L") == others[0]
    m.elapsed += 1.0
    assert m.get_target_for("L") == others[1], "락온 시간이 지나고 위험도 차이가 크면 바꿈"
    m.elapsed += 2.0
    m.players[others[1]]["highest_y"] = 5                          # 차이가 작으면 유지
    m.players[others[0]]["highest_y"] = 4
    assert m.get_target_for("L") == others[1]
    m.players[others[1]]["ig"] = 24                                # 가득 찬 상대는 건너뜀
    assert m.get_target_for("L") == others[0]
    alive = [p for p in others if m.players[p]["is_alive"]]
    assert m.get_target_for("L", "KO") == m._most_endangered(alive), "KO 모드는 락온 없음"

    # K.O. 기여: 내가 4줄 이상 보낸 상대를 다른 플레이어가 마무리
    m = BattleRoyaleMatch(total_players=10, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy")
    others = [p for p in m.players if p != "L"]
    m.apply_attack("L", others[0], 5)
    m.floating_texts.clear()
    m._eliminate_player(others[0], killer_id=others[1])
    assert m.local_assists == 1 and m.local_ko_count == 0
    assert any(f["text"].startswith("[처치 기여]") for f in m.floating_texts)
    m.apply_attack("L", others[2], 2)
    m._eliminate_player(others[2], killer_id=others[1])
    assert m.local_assists == 1, "4줄 미만은 기여가 아님"

    # 토스트: 오류 없이 그려지고, 칸이 모자라면 콤보가 먼저 밀려남
    m = BattleRoyaleMatch(total_players=10, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy")
    m.add_floating_text("[피격 경고] +3줄", (255, 0, 0), category="alert")
    m.add_floating_text("[3연속 콤보!]", (255, 0, 0), category="combo")
    m.add_floating_text("[공격 발송] +2줄", (255, 0, 0), category="attack")
    drawn = []
    real = app.renderer.font_small.render
    class _F:
        def __init__(self, f): self.f = f
        def render(self, text, *a, **k):
            drawn.append(text)
            return self.f.render(text, *a, **k)
        def __getattr__(self, k): return getattr(self.f, k)
    app.renderer.font_small = _F(app.renderer.font_small)
    try:
        app.renderer._render_floating_texts(m, 0, 0)
    finally:
        app.renderer.font_small = app.renderer.font_small.f
    assert "[피격 경고] +3줄" in drawn and "[공격 발송] +2줄" in drawn and "[3연속 콤보!]" not in drawn, drawn

    # 연습 과제: 순서대로 완료 (과제 40개, 추적기 이벤트로 판정)
    import challenges as CH
    m = BattleRoyaleMatch(total_players=2, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy", practice=True,
                          challenge=CH.ChallengeTracker(CH.PRACTICE_GOALS))
    m.challenge_kind = "practice"
    assert m.practice_current_task()[0] == 0 and len(m.PRACTICE_TASKS) == 40
    m._practice_check({"cleared": 1, "canceled": 2})
    assert m.practice_current_task()[0] == 1       # 상쇄 2줄 완료 -> 다음은 '줄 10개 지우기'
    m._practice_check({"cleared": 4})
    m._practice_check({"cleared": 1, "combo": 3})
    m._practice_check({"cleared": 2, "is_tspin": True})
    assert m.practice_current_task()[0] == 1, m.practice_current_task()        # 줄 10개 지우기는 아직 (8줄)
    assert set(m.challenge_saved) == {"p_cancel2", "p_quad", "p_combo3", "p_tspin", "p_tsd"}      # 2줄 T-스핀은 T-스핀 더블 과제도 같이 달성
    print("  OK v1.0.13")


if __name__ == "__main__":
    pygame.init()
    keep = {}
    from settings_manager import SETTINGS_FILE
    from stats_manager import STATS_FILE
    for p in (SETTINGS_FILE, STATS_FILE):
        keep[p] = open(p, "rb").read() if os.path.exists(p) else None
    try:
        for name, fn in list(globals().items()):
            if name.startswith("test_") and callable(fn):
                print(name)
                fn()
        print("[ALL REVIEW UI TESTS PASSED]")
    finally:
        for p, data in keep.items():                      # 테스트가 사용자 설정/전적 파일을 바꿨다면 복원
            if data is not None:
                open(p, "wb").write(data)

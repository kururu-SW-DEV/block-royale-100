"""
코드 분석 보고서(2026-10-05)에서 코드로 확인해 고친 항목의 회귀 테스트
- 고정 직후 쓰레기 줄이 올라올 때 억울한 탈락, LAN 봇 인계 크래시, 리플레이 기록의 L 사건 상태, 쉬운 봇 스폰 높이, T-스핀 천장 판정,
  텍스트 입력 ESC 취소, 설정 탭 초기화(조작키 보존), 영어 템플릿 우선순위, SFX 끄기와 콤보 층, 설정값 검증
실행: python tests/test_report_fixes.py (SDL dummy 드라이버)
"""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from block_engine import BlockEngine


def test_no_false_death_when_garbage_rises_after_lock():
    e = BlockEngine(seed=1)
    for y in range(6, 20):
        e.grid[y][0] = "J"
    e.current_piece = "I"
    placed = False
    for rot in range(4):
        for x in range(-2, 9):
            if e._check_collision(x, 0, rot):
                continue
            blocks = e._get_blocks("I", rot, x, 0)
            if len({bx for bx, _ in blocks}) == 1 and blocks[0][0] == 0:
                e.current_rot, e.current_x = rot, x
                placed = True
                break
        if placed:
            break
    assert placed
    y = 0
    while not e._check_collision(e.current_x, y + 1, e.current_rot):
        y += 1
    e.current_y = y
    e.queue_garbage(1, instant=True)
    e.lock_down()
    assert not e.game_over, "방금 고정한 블록 자리 때문에 억울하게 탈락하면 안 됨"
    assert e.current_piece is not None


def test_take_over_with_bot_without_current_piece():
    import bot_brain
    import battle_royale as br
    m = br.BattleRoyaleMatch(total_players=4, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="normal")
    pid = [p for p in m.players if p != "L"][0]
    m.players[pid]["bot"] = None
    m.players[pid]["is_ai"] = False
    snap = {"g": ["." * 10] * 20, "p": None, "h": None, "n": ["I", "O", "T"], "ig": 0, "c": -1, "b": 0, "bc": 0, "go": 0, "lp": 0.0}
    assert m.take_over_with_bot(pid, snap)
    bot = m.players[pid]["bot"]
    assert bot.engine.current_piece is not None
    for _ in range(60):                                          # 블록이 없는 채로 탐색하면 KeyError로 죽던 경로
        bot_brain.begin_frame(1e9)
        bot.update(1 / 30)


def test_replay_recorder_keeps_state_when_garbage_follows_lock():
    from replay import ReplayRecorder
    rec = ReplayRecorder()
    e = BlockEngine(seed=2)
    rec.update(e, 0.0)                                           # 엔진 기준 잡기
    e.replay_log = [{"k": "L", "p": "O", "c": [], "r": [], "s": 0}, {"k": "G", "n": 1, "h": [3]}]
    rec.update(e, 1.0)
    l_ev = [ev for ev in rec.events if ev["k"] == "L"][0]
    assert "nx" in l_ev and "cp" in l_ev and "ig" in l_ev, l_ev


def test_easy_bot_uses_spawn_height_and_tspin_ceiling_rule():
    from ai_bot import AIBot
    import bot_brain
    from config import SPAWN_Y
    bot = AIBot("B", "bot", "easy", seed=1)
    e = bot.engine
    for y in (0, 1):                                             # 위쪽 두 줄에 한쪽 벽 칸을 채워 y=0 시작이면 후보가 모두 사라지는 상황
        for x in (0, 1, 2, 7, 8, 9):
            e.grid[y][x] = "G"
    e.current_piece = "O"
    tx, rot = bot._find_best_move()
    assert (tx, rot) != (3, 0) or not e._check_collision(3, SPAWN_Y, 0)
    # 천장 위(y<0)는 엔진과 같이 빈 칸
    rows = [0] * 20
    assert bot_brain._tspin_kind(rows, 3, -2, 0, 1) is None


def test_text_input_escape_cancels_and_reset_keeps_keys():
    import main as M
    from gfx import CANVAS
    app = M.BlockRoyaleApp()
    CANVAS.attach(pygame.Surface((1366, 768)))
    app.screen = CANVAS
    app.player_name = "Alice"
    app._begin_text("player_name")
    app._text_set("player_name", "Bobby")
    app._end_text(commit=False)
    assert app.player_name == "Alice" and app.player_name_input == "Alice" and app.text_focus is None
    app._begin_text("player_name")
    app._text_set("player_name", "Carol")
    app._end_text()
    assert app.player_name == "Carol"
    # 규칙/기타 탭의 '이 탭 기본값으로'는 조작키를 건드리지 않음
    app.settings.set_action_key("hard_drop", pygame.K_x)
    for tab in ("rules", "help"):
        app.settings_tab = tab
        app._reset_current_tab()
        assert app.settings.get_action_keys("hard_drop") == [pygame.K_x], tab
    app.settings_tab = "keys"
    app._reset_current_tab()
    assert app.settings.get_action_keys("hard_drop") != [pygame.K_x]
    # 초기화하면 언어/경고음 같은 런타임 상태도 같이 돌아감
    import i18n
    app.settings.set("language", "en")
    i18n.set_language("en")
    app.settings_tab = "match"
    app._reset_current_tab()
    assert i18n.language() == "ko"


def test_i18n_template_priority_and_sfx_combo_layer():
    import i18n
    i18n.set_language("en")
    try:
        assert i18n.tr("최고 120초") == "Best 120s", i18n.tr("최고 120초")
        assert i18n.tr("30초") == "30s"
        assert i18n.tr("단위") == "단위", "숫자가 아닌 말은 '{#}위' 틀에 걸리지 않음"
    finally:
        i18n.set_language("ko")
    from sound_fx import SoundManager
    sm = SoundManager()

    class _Snd:
        vol = None

        def set_volume(self, v):
            self.vol = v
    a, b = _Snd(), _Snd()
    sm.sounds = {"combo_layer": a, "clear_c0": b}
    sm.enabled = True
    sm.sfx_enabled = False
    sm.set_sfx_volume(0.5)
    assert a.vol == 1.0 and b.vol == 0.0, (a.vol, b.vol)


def test_settings_validation_new_keys():
    from settings_manager import SettingsManager
    d = tempfile.mkdtemp()
    sm = SettingsManager(os.path.join(d, "s.json"))
    import json
    with open(os.path.join(d, "s.json"), "w", encoding="utf-8") as f:
        json.dump({"mini_detail": "bogus", "key_preset": "bogus", "name_color": 999}, f)
    sm = SettingsManager(os.path.join(d, "s.json"))
    assert sm.get("mini_detail") == "focus" and sm.get("key_preset") == "arcade"
    from config import NAME_COLORS
    assert 0 <= sm.get("name_color") < len(NAME_COLORS)


def test_update_check_removed_and_errlog_button_works():
    import os as _os
    import main as M
    from gfx import CANVAS
    assert not _os.path.exists(_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "update_check.py"))
    app = M.BlockRoyaleApp()
    CANVAS.attach(pygame.Surface((1366, 768)))
    app.screen = CANVAS
    app.state, app.settings_tab, app.previous_state = "SETTINGS", "help", "MENU"
    app._render_settings()
    assert not any("update" in k for k in app.settings_buttons), list(app.settings_buttons)
    app.state = "MENU"
    app._render_menu()
    assert not any("update" in k for k in app.menu_buttons)
    opened = []
    orig = getattr(_os, "startfile", None)
    _os.startfile = lambda path, *a, **k: opened.append(path)             # 테스트 중에 탐색기 창이 실제로 뜨지 않게
    try:
        app._settings_activate("open_errlog")
    finally:
        if orig is None:
            del _os.startfile
        else:
            _os.startfile = orig


def test_easy_cards_keep_a_hold_slot_in_detailed_mini_view():
    import main as M
    from gfx import CANVAS
    app = M.BlockRoyaleApp()
    CANVAS.attach(pygame.Surface((1366, 768)))
    app.screen = CANVAS
    app.settings.set("mini_detail", "detailed", autosave=False)
    app.renderer.mini_detailed = True
    app.bot_difficulty = "easy"
    app.start_game(mode="SOLO", total_players=50)
    m = app.match
    m.countdown_until = 0.0
    for _ in range(120):
        app._tick_game(1 / 60)
    assert not any(p.get("hold") for pid, p in m.players.items() if pid != m.local_player_id), "쉬움 봇은 홀드를 쓰지 않는 것이 이 테스트의 전제"
    app.state = "GAME"
    drawn = []
    orig = app.renderer._render_preview_piece
    app.renderer._render_preview_piece = lambda *a, **k: drawn.append(1)
    app.renderer._card_info.clear()
    app.renderer._card_layers.clear()
    app.renderer.render(m, app.sound_mgr)
    app.renderer._render_preview_piece = orig
    infos = [v for v in app.renderer._card_info.values()]
    assert infos and all(v[7] == "" for v in infos if v[7] is not None) and any(v[7] == "" for v in infos), "빈 홀드 칸이 예약돼야 함"


def test_gamepad_rescan_finds_devices_without_add_events():
    from gamepad import GamepadMapper
    pad = GamepadMapper(lambda a: [], lambda: True)
    opened = []
    pad.on_device_event = lambda e: (opened.append(e.device_index), pad.joys.__setitem__(e.device_index, object()))
    orig = pygame.joystick.get_count
    pygame.joystick.get_count = lambda: 1
    try:
        assert pad.rescan(interval=0) is True and pad.connected() and opened == [0]
        assert pad.rescan(interval=0) is False, "이미 연결돼 있으면 다시 열지 않음"
    finally:
        pygame.joystick.get_count = orig


if __name__ == "__main__":
    pygame.init()
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print("[ALL REPORT FIX TESTS PASSED]")

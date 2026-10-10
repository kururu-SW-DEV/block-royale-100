"""레벨 보상(보드 테두리 장식)과 조준 모드/열기 이름 변경 테스트. 실행: python tests/test_levelperks.py"""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import stats_manager as sm


def test_border_perks_follow_level():
    assert sm.border_perk_for_level(7) is None
    assert sm.border_perk_for_level(8)[1] is False
    assert sm.border_perk_for_level(20)[0] != sm.border_perk_for_level(8)[0]
    assert sm.border_perk_for_level(35)[1] is True and sm.border_perk_for_level(50)[1] is True
    got = sm.perks_unlocked_between(7, 8)
    assert got == ["내 보드에 은빛 테두리 장식이 붙습니다"], got
    assert len(sm.perks_unlocked_between(0, 50)) == len(sm.LEVEL_PERKS) + len(sm.BORDER_PERKS)


def test_heat_tiers_are_ascending_and_renamed():
    needs = [n for n, _ in config.BADGE_TIERS]
    rates = [r for _, r in config.BADGE_TIERS]
    assert needs == sorted(needs) and rates == sorted(rates) and needs[1] == 3
    import ui_renderer
    assert ui_renderer.TARGET_MODE_LABELS == {"AUTO": "자동", "KO": "추격", "ATTACKERS": "응수", "BADGES": "거물", "RANDOM": "운명"}
    for k, v in ui_renderer.TARGET_MODE_HELP.items():
        assert v.startswith(ui_renderer.TARGET_MODE_LABELS[k] + ":"), (k, v)


def test_new_mode_names_are_translated():
    import i18n
    i18n.set_language("en")
    try:
        for ko in ("추격", "응수", "거물", "운명", "열기"):
            assert i18n.tr(ko) != ko, ko
    finally:
        i18n.set_language("ko")


def test_display_fonts_exist_and_fall_back_safely():
    import pygame
    import font_utils
    pygame.font.init()
    assert font_utils.face_font("display", 24) is not None
    assert font_utils.face_can_draw("display", "게임 환경 설정 123")
    assert font_utils.face_font("zzz", 20) is None
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for lic in ("OFL-BlackHanSans.txt",):
        assert "SIL OPEN FONT LICENSE" in open(os.path.join(root, "assets", "fonts", lic), encoding="utf-8", errors="replace").read().upper()
    from gfx import HiFont
    f = HiFont("malgungothic", 20, bold=True, face="display")
    assert f.size("123")[0] > 0 and f.size("한글 123")[0] > 0
    assert not os.path.exists(os.path.join(root, "assets", "fonts", "Rajdhani-Bold.ttf")), "글꼴을 섞지 않기로 해서 Rajdhani는 동봉하지 않음"


def test_small_text_is_not_bold_but_large_text_is():
    """12~15px 굵은 한글은 획이 뭉개져 읽기 어려워서 작은 글씨는 보통 굵기, 16px 이상만 굵게"""
    import pygame
    from gfx import HiFont, CANVAS
    pygame.font.init()
    S = CANVAS.S
    small = HiFont("malgungothic", 12, bold=True)
    big = HiFont("malgungothic", 22, bold=True)
    small._real()
    big._real()
    px_small, px_big = max(6, int(round(12 * S))), max(6, int(round(22 * S)))
    keys = {k[1]: k[2] for k in HiFont._fonts if k[0] == "malgungothic"}
    assert keys[px_small] is False or px_small >= 16, keys
    assert keys[px_big] is True, keys


def test_spotlight_picks_threats_then_target_then_titan():
    import random
    import main as M
    from gfx import CANVAS
    import pygame
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app = M.BlockRoyaleApp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.screen = CANVAS
    app.settings.set("coach_done", True)
    app.state = "GAME"
    app.start_game(mode="SOLO", total_players=40)
    m = app.match
    m.countdown_until = 0.0
    me = m.local_player_id
    bots = [k for k, p in m.players.items() if k != me]
    r = app.renderer
    for k in bots:
        m.players[k]["target_id"] = None
    m.players[me]["target_id"] = bots[5]
    got = r._spotlight_picks(m)
    assert [g[0] for g in got] == [bots[5]] and got[0][1] == "표적", got
    m.players[bots[1]]["target_id"] = me
    m.players[bots[2]]["target_id"] = me
    m.players[bots[1]]["highest_y"], m.players[bots[2]]["highest_y"] = 12, 3
    got = r._spotlight_picks(m)
    assert [g[0] for g in got] == [bots[2], bots[1]] and all(g[1] == "위협" for g in got), got          # 더 높이 쌓인 상대가 앞, 최대 2명
    m.players[bots[1]]["is_alive"] = False
    assert bots[1] not in [g[0] for g in r._spotlight_picks(m)]
    for _ in range(3):
        r.render(m, app.sound_mgr)                                                                     # 그리기에서 오류가 나지 않음


def test_in_game_tips_are_translated_in_english():
    """경기 중 팁은 'TIP  ' + 안내문으로 그려져서, 앞에 붙은 'TIP  ' 때문에 영어에서 한글로 남던 것"""
    import i18n
    from screens.game import GameMixin
    i18n.set_language("en")
    try:
        import re
        for _kind, text in GameMixin.TIPS:
            out = i18n.tr("TIP  " + text)
            assert out.startswith("TIP  ") and not re.search(r"[가-힣]", out), out
    finally:
        i18n.set_language("ko")


def test_slow_first_frame_after_match_start_does_not_auto_pause():
    """Steam Deck처럼 느린 PC에서 시작 직후 첫 장면 준비로 0.5초 넘게 걸려도 일시정지가 뜨지 않고, 유예가 지난 뒤의 긴 정지는 예전처럼 일시정지"""
    import time
    import pygame
    import main as M
    from gfx import CANVAS
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app = M.BlockRoyaleApp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app.screen = CANVAS
    app.settings.set("coach_done", True)
    app.state = "GAME"
    app.start_game(mode="SOLO", total_players=30, quick=True)
    app._on_long_frame(1.2)
    assert not app.is_paused, "시작 직후의 느린 프레임은 일시정지 사유가 아님"
    app._long_frame_grace_until = time.time() - 1.0
    app._on_long_frame(1.2)
    assert app.is_paused, "유예가 지난 뒤 창이 멈췄다 돌아오면 솔로 경기는 일시정지"


def test_leaving_a_match_switches_to_menu_music_quickly():
    """경기에서 메인 메뉴/대기실로 나갈 때 이전 곡이 1.8초 남지 않고 0.3초에 전환"""
    import pygame
    import main as M
    from gfx import CANVAS
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app = M.BlockRoyaleApp()
    app.screen = CANVAS
    calls = []
    orig = app.sound_mgr.play_bgm
    app.sound_mgr.play_bgm = lambda stage=1, crossfade_ms=1800: calls.append((stage, crossfade_ms))
    app.sound_mgr.play_menu_bgm(quick=True)
    app.sound_mgr.play_menu_bgm()
    app.sound_mgr.play_bgm = orig
    assert calls == [("menu", 300), ("menu", 1800)], calls
    assert M.BlockRoyaleApp.return_to_menu.__code__.co_consts.count(True) >= 0
    import inspect
    assert "play_menu_bgm(quick=True)" in inspect.getsource(M.BlockRoyaleApp.return_to_menu)


def test_grace_keeps_held_keys_and_auto_pause_reason_is_logged():
    import tempfile
    import time
    import pygame
    import main as M
    import crash_log
    from gfx import CANVAS
    d = tempfile.mkdtemp()
    os.environ["BR_DATA_DIR"] = d
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app = M.BlockRoyaleApp()
    app.screen = CANVAS
    app.settings.set("coach_done", True)
    app.state = "GAME"
    app.start_game(mode="SOLO", total_players=30, quick=True)
    app.key_left_down = True
    app._on_long_frame(1.2)                                          # 유예 중: 눌러 둔 키도 일시정지도 건드리지 않음
    assert app.key_left_down and not app.is_paused
    app._long_frame_grace_until = time.time() - 1.0
    app._on_long_frame(1.2)
    assert app.is_paused and not app.key_left_down
    log = open(os.path.join(d, "pause.log"), encoding="utf-8").read()
    assert "긴 프레임" in log, log
    assert "pause.log" in crash_log.diagnostics_text()
    app.match.brief_open = True
    app._close_brief()
    assert app._long_frame_grace_until > time.time() + 3, "브리핑을 닫을 때도 유예"


def test_heat_bonus_uses_carry_not_ceil_and_protocol_was_bumped():
    from block_engine import BlockEngine as TetrisEngine
    import inspect
    import network
    import battle_royale
    assert network.PROTOCOL_VERSION >= 4, "열기 수치가 바뀌어 옛 버전과는 같은 방에 못 들어오게"
    assert battle_royale.BattleRoyaleMatch.BOT_BADGE_CAP == 0.4
    src = inspect.getsource(TetrisEngine)
    assert "badge_carry" in src and "math.ceil(attack_lines * self.badge_rate)" not in src


def test_first_run_defaults_apply_before_first_frame_and_reset_keeps_crown():
    import tempfile
    import pygame
    import main as M
    import settings_manager as SM
    from gfx import CANVAS
    os.environ["BR_DATA_DIR"] = tempfile.mkdtemp()
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app = M.BlockRoyaleApp()
    app.screen = CANVAS
    app.settings.set("onboard_done", False, autosave=False)             # 처음 설치한 상태를 흉내 (데이터 폴더는 import 때 정해져 이 테스트에서 바꿀 수 없음)
    app.settings.set("block_skin", "classic", autosave=False)
    app.stats_mgr.data["total_games"] = 0
    app.stats_mgr.data.setdefault("survival", {})["total_games"] = 0
    app._apply_first_run_defaults()
    app.apply_visual_options()
    assert app.renderer.block_skin == "crown", "처음 설치한 사람은 왕관석"
    assert SM.DEFAULT_SETTINGS["block_skin"] == "crown"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print("[ALL LEVEL PERK TESTS PASSED]")

"""
Opus 제안 반영(골든 타깃 순환, 입문 미션, 평소 대비, 패드 오른쪽 스틱, 빠른 시작 카드 클릭, 되감기, 우승 예측, 번쩍임 설정,
주간 변형 3종, LAN 세션 승점, 레벨 보상, F12 스크린샷, 번역 누락 기록) 검증
실행: python tests/test_suggestions.py (SDL dummy 드라이버)
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


def test_golden_target_rotates_on_expiry_claim_and_death():
    app = _app()
    app.start_game(mode="SOLO", total_players=30)
    app.state = "GAME"
    m = app.match
    first = m.bounty_id
    assert first and m.bounty_secs_left() is not None and m.bounty_secs_left() <= m.BOUNTY_SECS
    m.elapsed = m.bounty_until + 0.1                       # 시간이 다 됨 -> 다른 봇으로
    m._update_bounty()
    assert m.bounty_id != first and not m.bounty_claimed
    second = m.bounty_id
    m.players[second]["is_alive"] = False                  # 다른 봇이 먼저 탈락시킴 -> 바로 교체
    m._update_bounty()
    assert m.bounty_id != second and m.players[m.bounty_id]["is_alive"]
    m.bounty_claimed = True                                # 처치한 뒤에는 잠깐 쉬고 다음 타깃
    m.bounty_until = m.elapsed + m.BOUNTY_GAP
    cur = m.bounty_id
    m._update_bounty()
    assert m.bounty_id == cur and m.bounty_secs_left() is None
    m.elapsed = m.bounty_until + 0.1
    m._update_bounty()
    assert m.bounty_id != cur and not m.bounty_claimed
    m.bounty_kills = m.BOUNTY_MAX_REWARDS                  # 경험치 보상은 한 판에 최대 5번
    m.bounty_claimed = True
    m.bounty_until = m.elapsed - 1
    cur = m.bounty_id
    m._update_bounty()
    assert m.bounty_id == cur


def test_onboarding_missions_order_and_one_time_xp():
    from stats_manager import StatsManager, ONBOARDING, ONBOARDING_XP
    sm = StatsManager()
    sm.filepath = os.path.join(tempfile.mkdtemp(), "s.json")
    sm.data["total_games"], sm.data["total_kos"] = 0, 0
    assert sm.onboarding_next()[0] == 1
    sm.data["total_games"] = 1
    assert sm.onboarding_next()[0] == 2
    sm.data["total_kos"] = 1
    sm.mark_onboarding("practice_g")                       # 3번(조준)을 건너뛰고 4번을 먼저 해도 3번이 다음 미션
    assert sm.onboarding_next()[0] == 3
    xp0 = sm.data.get("xp", 0)
    first = sm.claim_onboarding()
    assert len(first) == 3 and sm.data["xp"] == xp0 + 3 * ONBOARDING_XP
    assert sm.claim_onboarding() == [] and sm.data["xp"] == xp0 + 3 * ONBOARDING_XP, "보상은 한 번만"
    sm.mark_onboarding("aim")
    sm.data["recent_matches"] = [{"total_players": 60, "rank": 5}]
    assert len(sm.claim_onboarding()) == 2 and sm.onboarding_next() is None
    assert len(ONBOARDING) == 5


def test_vs_usual_text_needs_history_and_real_difference():
    from stats_manager import vs_usual_text
    hist = [{"total_players": 50, "survival_sec": 100}] * 5
    assert vs_usual_text(hist[:2], 5, 50, 300) is None, "기록이 3판 미만이면 말하지 않음"
    assert vs_usual_text(hist, 5, 50, 103) is None, "차이가 작으면 말하지 않음"
    assert vs_usual_text(hist, 5, 50, 160) == "평소 대비 생존 ▲ 60초"
    assert vs_usual_text(hist, 5, 50, 40) == "평소 대비 생존 ▼ 60초"
    assert vs_usual_text(hist, 5, 4, 300) is None, "8인 미만은 비교하지 않음"


def test_pad_right_stick_selects_target_mode_keys():
    import gamepad
    gm = gamepad.GamepadMapper(lambda a: [pygame.K_a])
    ev = lambda axis, v: pygame.event.Event(gamepad._CAXIS, axis=axis, value=v, instance_id=1)
    out = gm.translate([ev(gamepad._CAX_RY, -32000)], True)                 # 위로 기울임 -> K.O. 모드(숫자 2)
    assert [e.key for e in out if e.type == pygame.KEYDOWN] == [pygame.K_2]
    assert gm.translate([ev(gamepad._CAX_RY, -32000)], True) == [], "기울인 채로는 한 번만"
    gm.translate([ev(gamepad._CAX_RY, 0)], True)                            # 중립으로 돌려야 다시 반응
    out = gm.translate([ev(gamepad._CAX_RX, 32000)], True)
    assert [e.key for e in out if e.type == pygame.KEYDOWN] == [pygame.K_3]
    gm.translate([ev(gamepad._CAX_RX, 0)], True)
    assert gm.translate([ev(gamepad._CAX_RX, -32000)], False) == [], "메뉴에서는 무시"


def test_menu_quick_start_card_buttons():
    app = _app()
    app.state = "MENU"
    app._menu_intro_t = 9
    app._render_menu()
    n0 = app.target_player_count
    started = []
    app.start_game = lambda **kw: started.append(kw)
    plus, minus, diff = (app.menu_buttons[k] for k in ("qp_plus", "qp_minus", "qp_diff"))
    ev = lambda type, **kw: pygame.event.Event(type, **kw)
    app._handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=plus.center))
    app._handle_event(ev(pygame.MOUSEBUTTONUP, button=1, pos=plus.center))
    assert app.target_player_count == n0 + 1 and not started, "+ 를 눌러도 게임이 시작되지 않고 인원만 늘어남"
    app._handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=minus.center))
    app._handle_event(ev(pygame.MOUSEBUTTONUP, button=1, pos=minus.center))
    assert app.target_player_count == n0
    d0 = app.settings.get("bot_difficulty")
    app._handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=diff.center))
    app._handle_event(ev(pygame.MOUSEBUTTONUP, button=1, pos=diff.center))
    assert app.settings.get("bot_difficulty") != d0 and not started
    card = app.menu_buttons["quick_play"]
    app._handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=(card.x + 40, card.centery)))
    app._handle_event(ev(pygame.MOUSEBUTTONUP, button=1, pos=(card.x + 40, card.centery)))
    assert started, "카드의 다른 곳을 누르면 시작"


def test_killcam_toggle_and_prediction_flow():
    app = _app()
    app.start_game(mode="SOLO", total_players=12)
    app.state = "GAME"
    m = app.match
    m.countdown_until = 0.0
    m.coach_until = 0.0
    for _ in range(120):
        app._tick_game(1 / 60)
    killer = next(pid for pid in m.players if pid != m.local_player_id)
    m._eliminate_player(m.local_player_id, killer)
    assert not m.local_is_alive
    assert m.prediction_id is not None and m.players[m.prediction_id]["is_alive"], "탈락하면 우승 예측이 기본으로 정해짐"
    other = next(pid for pid, p in m.players.items() if p["is_alive"] and pid != m.prediction_id and pid != m.local_player_id)
    assert m.set_prediction(other) and m.prediction_id == other
    m.players[other]["rank"] = 1
    assert m.prediction_xp() == m.PREDICTION_WIN_XP
    m.players[other]["rank"] = 3
    assert m.prediction_xp() == m.PREDICTION_TOP3_XP
    m.players[other]["rank"] = 7
    assert m.prediction_xp() == 0
    from replay import ReplayPlayer
    data = {"events": [{"k": "G", "n": 1, "h": [3], "t": 1.0}], "secs": 10, "date": "", "rank": 1, "total": 1, "kos": 0, "score": 0}
    app.killcam = ReplayPlayer(data)
    app.killcam_start = 2.0
    app.killcam_on = False
    app.result_lock_until = 0
    m.is_spectating = False
    app._handle_game_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_v, mod=0, unicode=""))
    assert app.killcam_on, "V로 되감기가 켜짐"
    app._update_killcam(1 / 60)
    assert app.renderer.killcam is app.killcam


def test_screen_flash_is_independent_of_shake_setting():
    app = _app()
    assert app.settings.get("screen_flash") is True
    app.start_game(mode="SOLO", total_players=10)
    app.settings.set("screen_shake", "off")
    app.apply_gameplay_options()
    assert app.match.flash_enabled is True and app.match.shake_scale == 0, "흔들림을 꺼도 번쩍임은 따로"
    app.settings.set("screen_flash", False)
    app.apply_gameplay_options()
    assert app.match.flash_enabled is False


def test_new_weekly_rules_have_goals_and_work():
    import config
    import challenges
    ids = [m["id"] for m in config.WEEKLY_MUTATORS]
    assert {"heavy", "swift", "nohold"} <= set(ids) and len(ids) == 7
    for rid in ids:
        assert len(challenges.WEEKLY_GOALS[rid]) == 3, rid
    from battle_royale import BattleRoyaleMatch
    mut = next(x for x in config.WEEKLY_MUTATORS if x["id"] == "nohold")
    m = BattleRoyaleMatch(total_players=10, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy", mutator=mut)
    m.local_engine.hold_piece = None
    assert m.local_engine.hold() is False, "홀드 금지"
    heavy = next(x for x in config.WEEKLY_MUTATORS if x["id"] == "heavy")
    m2 = BattleRoyaleMatch(total_players=10, local_player_id="L", local_player_name="me", net_mgr=None, sound_mgr=None, bot_difficulty="easy", mutator=heavy)
    assert m2._custom("garbage", "normal") == "heavy" and m2.custom_rules is None, "변형 규칙은 전적 기록을 막지 않음"


def test_session_scores_accumulate_and_reset():
    import network
    nm = network.NetworkManager()
    nm.host_add_session_scores([{"name": "A", "rank": 1, "ko": 3, "is_ai": False}, {"name": "B", "rank": 2, "ko": 0, "is_ai": False},
                                {"name": "BOT", "rank": 3, "ko": 5, "is_ai": True}])
    nm.host_add_session_scores([{"name": "A", "rank": 3, "ko": 1, "is_ai": False}])
    assert nm.session_scores == {"A": 10 + 3 + 4 + 1, "B": 6}, nm.session_scores
    nm.stop()
    assert nm.session_scores == {}


def test_level_perks_change_orb_theme():
    from stats_manager import orb_theme_for_level, perks_unlocked_between
    assert orb_theme_for_level(1) == "gold" and orb_theme_for_level(15) == "sky" and orb_theme_for_level(30) == "pink" and orb_theme_for_level(50) == "rainbow"
    assert perks_unlocked_between(14, 15) and not perks_unlocked_between(15, 16)


def test_f12_saves_screenshot_and_i18n_missing_log():
    app = _app()
    app.state = "MENU"
    app._render_menu()
    app._save_screenshot()
    from app_paths import data_path
    folder = data_path("screenshots")
    assert os.path.isdir(folder) and any(f.endswith(".png") for f in os.listdir(folder))
    import i18n
    i18n._MISSING_LOG = True
    i18n.set_language("en")
    try:
        i18n._cache.clear()
        i18n._missing_seen.clear()
        i18n.tr("번역표에 절대 없는 이상한 한글 문구 qwerty")
        log = data_path("i18n_missing.txt")
        assert os.path.exists(log) and "번역표에 절대 없는" in open(log, encoding="utf-8").read()
    finally:
        i18n._MISSING_LOG = False
        i18n.set_language("ko")


if __name__ == "__main__":
    pygame.init()
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print("[ALL SUGGESTION TESTS PASSED]")

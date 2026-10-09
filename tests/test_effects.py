"""
게임 효과 개선(v1.4.33) 테스트: 미니 T-스핀, 진동 설정/패턴, 피격 연출 시점 통일, B2B 끊김, 공격 누적, 좌우 패닝,
파티클 예산, 줄 삭제 와이프 종류, 번쩍임/흔들림 설정 존중, 텍스트 캐시.
실행: python tests/test_effects.py
"""
import os
import sys
import tempfile
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from gfx import CANVAS


def _app():
    import main as M
    pygame.display.set_mode((1366, 768))
    CANVAS.attach(pygame.display.get_surface())
    app = M.BlockRoyaleApp()
    app.screen = CANVAS
    app.stats_mgr.filepath = os.path.join(tempfile.mkdtemp(), "s.json")
    app.settings.filepath = os.path.join(tempfile.mkdtemp(), "set.json")
    app.settings.reset_to_defaults()
    return app


def _game(app, n=20):
    app.start_game(mode="SOLO", total_players=n)
    m = app.match
    m.countdown_until = 0.0
    return m


def _texts(m):
    return [f["text"] for f in m.floating_texts]


def test_mini_tspin_is_small_celebration_and_big_tspin_rumbles_as_quad():
    app = _app()
    m = _game(app)
    rumbles = []
    m.rumble_cb = lambda p, kind="hit": rumbles.append((p, kind))
    eng = m.local_engine
    eng.last_clear_info = {"cleared": 1, "is_tspin": True, "is_mini": True, "is_b2b": False, "b2b_chain": 0}
    impact0 = m.impact_t
    m.on_lines_cleared(1)
    assert any("T-스핀 미니" in t for t in _texts(m)), _texts(m)
    assert not any("T-스핀 싱글" in t for t in _texts(m))
    assert m.impact_t == impact0, "미니는 화면 번쩍임 없음"
    assert not rumbles and m.screen_shake < 8.0, "미니는 진동/큰 흔들림 없음"
    m.floating_texts.clear()
    eng.last_clear_info = {"cleared": 2, "is_tspin": True, "is_mini": False, "is_b2b": False, "b2b_chain": 0}
    m.on_lines_cleared(2)
    assert any("T-스핀 더블" in t for t in _texts(m))
    assert rumbles and rumbles[-1][1] == "quad"


def test_rumble_setting_is_separate_from_shake_and_wired_to_match():
    app = _app()
    m = _game(app)
    app.settings.set("screen_shake", "off")
    app.settings.set("pad_rumble", "low")
    app.apply_gameplay_options()
    assert m.shake_scale == 0.0 and abs(m.rumble_scale - 0.5) < 1e-9
    assert app.settings.cycle_pad_rumble(1) == "normal" and app.settings.cycle_pad_rumble(1) == "off"


def test_gamepad_rumble_patterns_differ():
    from gamepad import GamepadMapper
    got = []

    class Dev:
        def rumble(self, lo, hi, ms):
            got.append((lo, hi, ms))
    gm = GamepadMapper(lambda a: [])
    gm.ctrls, gm.joys = {1: Dev()}, {}
    gm.rumble(0.6, "drop")
    assert got[-1][1] == 0 and got[-1][2] < 60, "하드 드롭: 낮은 모터만, 짧게"
    gm._rumble_t = 0.0
    gm.rumble(0.6, "quad")
    assert got[-1][1] > 0 and got[-1][2] > 150, "쿼드: 두 모터, 길게"
    gm._rumble_t = 0.0
    gm.rumble(0.6, "ko")
    assert got[-1][1] > got[-1][0], "K.O.: 고음 모터가 더 세게"
    n = len(got)
    gm.rumble(0.3, "hit")                                  # 바로 이어진 약한 호출은 무시
    assert len(got) == n
    gm.rumble(0.9, "hit")                                  # 더 센 호출은 끼어듦
    assert len(got) == n + 1


def test_incoming_hit_effects_land_with_the_beam():
    app = _app()
    m = _game(app)
    ids = [k for k, p in m.players.items() if p.get("bot")]
    played = []
    m.sound_mgr.play = lambda name, *a, **k: played.append(name)
    rumbles = []
    m.rumble_cb = lambda p, kind="hit": rumbles.append(p)
    m.screen_shake = 0.0
    m.apply_attack(ids[0], m.local_player_id, 4)
    assert m.screen_shake == 0.0 and not rumbles and not any(p.startswith("hit_") for p in played), "날아오는 동안은 조용"
    assert m.flight_lines() == 4
    m._pending_hits = [(0.0,) + h[1:] for h in m._pending_hits]
    m._process_pending_hits()
    assert m.screen_shake > 0 and rumbles and any(p.startswith("hit_") for p in played)
    assert m.flight_lines() == 0
    # 렌더러: 날아오는 줄은 흐리게, 빔은 게이지 쪽으로
    m.local_engine.queue_garbage(3, source="x")
    m.apply_attack(ids[1], m.local_player_id, 2)
    app.renderer.render(m)
    ax, ay = app.renderer._incoming_anchor(m)
    assert ax < app.renderer.main_board_x and app.renderer.main_board_y < ay <= app.renderer.main_board_y + app.renderer.main_board_h


def test_b2b_break_feedback():
    app = _app()
    m = _game(app)
    played = []
    m.sound_mgr.play = lambda name, *a, **k: played.append(name)
    eng = m.local_engine
    eng.b2b, eng.b2b_chain = True, 2
    m.update(0.01)
    assert m.b2b_break_seq == 0
    eng.b2b, eng.b2b_chain = False, 0                      # 일반 클리어로 끊김
    m.update(0.01)
    assert m.b2b_break_seq == 1 and "b2b_break" in played and any("B2B ×2 끝" in t for t in _texts(m))
    m.update(0.01)
    assert m.b2b_break_seq == 1, "한 번만"
    app.renderer.render(m)                                 # 렌더러 반응도 예외 없이


def test_send_counter_accumulates_and_escalates():
    app = _app()
    m = _game(app)
    played = []
    m.sound_mgr.play = lambda name, *a, **k: played.append((name, k.get("combo")))
    m._add_send_agg(4)
    m._add_send_agg(4)
    assert m.send_agg["lines"] == 8 and not any(n == "attack_big" for n, _ in played)
    m._add_send_agg(3)
    assert ("attack_big", 1) in played
    m._add_send_agg(10)
    assert ("attack_big", 2) in played and m.send_agg["lines"] == 21
    m.send_agg["t"] -= 5.0                                 # 창이 지나면 새로 시작
    m._add_send_agg(2)
    assert m.send_agg["lines"] == 2
    m.send_agg["lines"], m.send_agg["t"] = 12, time.time()
    app.renderer.render(m)
    assert "attack_big_1" in app.sound_mgr.sounds and "attack_big_2" in app.sound_mgr.sounds and "b2b_break" in app.sound_mgr.sounds


def test_pan_follows_card_position_and_is_optional():
    app = _app()
    m = _game(app)
    app.renderer.render(m)
    pids = [p for p in app.renderer.mini_board_rects]
    assert pids
    left = min(pids, key=lambda p: app.renderer.mini_board_rects[p].centerx)
    right = max(pids, key=lambda p: app.renderer.mini_board_rects[p].centerx)
    assert app._card_pan(left) < app._card_pan(right) and -1.0 <= app._card_pan(left) <= 1.0
    assert app._card_pan("없는 아이디") is None
    got = []
    m.sound_mgr.play = lambda name, *a, **k: got.append(k.get("pan"))
    m.pan_fn = app._card_pan
    m._play_fx("attack", right)
    m._play_fx("attack", "없는 아이디")
    assert got[0] is not None and got[1] is None
    app.sound_mgr = type(app.sound_mgr)(enabled=True) if False else app.sound_mgr
    app.sound_mgr.play("attack", pan=-1.0)                 # 실제 재생 경로도 예외 없이
    app.sound_mgr.play("attack", pan=1.0)


def test_particle_budget_protects_own_effects():
    from ui_renderer import ParticleManager
    pm = ParticleManager()
    for _ in range(20):
        pm.add_sparks(0, 0, (255, 255, 255), count=20, ambient=True)
    assert len(pm.particles) <= ParticleManager.AMBIENT_MAX, "배경 파티클은 상한이 따로 있음"
    for _ in range(10):
        pm.add_sparks(0, 0, (255, 255, 255), count=40)
    own = sum(1 for p in pm.particles if not p.get("amb"))
    assert len(pm.particles) <= 320 and own >= 280, (len(pm.particles), own)   # 내 파티클이 밀려나지 않음
    pm.low = True
    n = len(pm.particles)
    pm.add_sparks(0, 0, (255, 255, 255), count=10, glow=True)
    assert len(pm.particles) == n, "느릴 때는 발광 파티클 생략"


def test_wipe_kinds_and_flash_setting():
    app = _app()
    m = _game(app)
    r = app.renderer
    eng = m.local_engine
    for kind, info in (("quad", {"cleared": 4}), ("tspin", {"cleared": 2, "is_tspin": True}), ("clear", {"cleared": 1}),
                       ("clear", {"cleared": 1, "is_tspin": True, "is_mini": True})):
        eng.last_clear_info = dict(info)
        eng.cleared_row_indices = [18, 19][:info["cleared"] if info["cleared"] < 3 else 2]
        eng.lines_cleared_total += 1
        for flash in (True, False):
            m.flash_enabled = flash
            r.line_clear_flashes.clear()
            eng.cleared_row_indices = [18, 19][:2]
            r.render(m)
            kinds = {f["kind"] for f in r.line_clear_flashes}
            assert kinds == {kind}, (kind, kinds)
            time.sleep(0.02)
            r.render(m)
    m.flash_enabled = False
    m.shake_scale = 0.0
    ids = [k for k, p in m.players.items() if p.get("bot")]
    r.board_impact_flashes[ids[0]] = time.time()
    r.render(m)                                            # 번쩍임/흔들림이 꺼져도 미니 카드 반응이 예외 없이 그려짐


def test_text_cache_reuses_surfaces_and_resets_on_language():
    app = _app()
    r = app.renderer
    a = r._cached_text(r.font_small, "테스트 문구", (255, 255, 255))
    b = r._cached_text(r.font_small, "테스트 문구", (255, 255, 255))
    assert a is b
    c = r._cached_text(r.font_small, "테스트 문구", (255, 0, 0))
    assert c is not a
    import i18n
    i18n.set_language("en")
    try:
        d = r._cached_text(r.font_small, "테스트 문구", (255, 255, 255))
        assert d is not a, "언어가 바뀌면 다시 렌더링"
    finally:
        i18n.set_language("ko")


def test_cached_text_is_opaque_again_after_a_fade_out():
    app = _app()
    r = app.renderer
    s = r._cached_text(r.font_banner[2], "★ 쿼드! ★", (255, 215, 0))
    s.set_alpha(0)                                         # 배너가 사라질 때 호출자가 남기는 값
    again = r._cached_text(r.font_banner[2], "★ 쿼드! ★", (255, 215, 0))
    assert again is s and again.get_alpha() == 255
    big = r._scaled_hi(again, 1.3)                         # 팝인(확대) 연출이 쓰는 경로: 글자가 실제로 그려져야 함
    tgt = pygame.Surface(pygame.Surface.get_size(big))
    pygame.Surface.blit(tgt, big, (0, 0))
    assert any(tgt.get_at((x, y))[:3] != (0, 0, 0) for x in range(0, tgt.get_width(), 2) for y in range(0, tgt.get_height(), 2))


def test_danger_breath_draws_runs_without_error():
    app = _app()
    m = _game(app)
    eng = m.local_engine
    for y in range(8, 20):
        for x in range(10):
            eng.grid[y][x] = "I" if (x + y) % 3 else None
    app.renderer.render(m)


if __name__ == "__main__":
    pygame.init()
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print("[ALL EFFECTS TESTS PASSED]")

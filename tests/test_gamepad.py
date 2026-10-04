"""
게임패드(조이스틱/표준 컨트롤러/이중 이벤트)와 리플레이 메타
실행: python test_gamepad.py
"""
import os
import sys
import time
import json
import tempfile

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
    return app


def test_gamepad_mapper():
    from gamepad import GamepadMapper
    keys = {"move_left": [pygame.K_a], "move_right": [pygame.K_d], "soft_drop": [pygame.K_s], "hard_drop": [pygame.K_SPACE],
            "rotate_cw": [pygame.K_k], "rotate_ccw": [pygame.K_j], "hold": [pygame.K_l], "rotate_180": [], "pause": [pygame.K_p], "target_cycle": [pygame.K_TAB]}
    on = [True]
    gm = GamepadMapper(lambda a: keys.get(a, []), lambda: on[0])
    E = pygame.event.Event
    hat = lambda v: E(pygame.JOYHATMOTION, instance_id=0, hat=0, value=v)
    out = gm.translate([hat((-1, 0))], True)
    assert [(e.type, e.key) for e in out] == [(pygame.KEYDOWN, pygame.K_a)], "십자키 왼쪽 = 이동 키(배정된 키를 따름)"
    out = gm.translate([hat((0, 0))], True)
    assert [(e.type, e.key) for e in out] == [(pygame.KEYUP, pygame.K_a)]
    # 스틱: 이력 있는 데드존 (0.55에서 켜지고 0.35 아래로 내려와야 꺼짐)
    ax = lambda a, v: E(pygame.JOYAXISMOTION, instance_id=0, axis=a, value=v)
    assert gm.translate([ax(0, 0.4)], True) == []
    assert [e.key for e in gm.translate([ax(0, 0.7)], True)] == [pygame.K_d]
    assert gm.translate([ax(0, 0.45)], True) == [], "경계에서 떨려도 유지"
    assert [(e.type, e.key) for e in gm.translate([ax(0, 0.1)], True)] == [(pygame.KEYUP, pygame.K_d)]
    btn = lambda b, down=True: E(pygame.JOYBUTTONDOWN if down else pygame.JOYBUTTONUP, instance_id=0, button=b)
    assert [e.key for e in gm.translate([btn(0)], True)] == [pygame.K_k]
    assert [e.key for e in gm.translate([btn(1)], True)] == [pygame.K_j]
    assert gm.translate([btn(3)], True) == [], "배정된 키가 없는 동작(180도)은 무시"
    assert [e.key for e in gm.translate([btn(5)], True)] == [pygame.K_SPACE]
    gm.translate([btn(0, False), btn(1, False), btn(5, False)], True)
    # 눌린 채 모드가 바뀌어도 뗄 때는 눌렀던 키를 뗌 (키가 눌린 채 남지 않음)
    assert [e.key for e in gm.translate([hat((1, 0))], True)] == [pygame.K_d]
    out = gm.translate([hat((0, 0))], False)
    assert [(e.type, e.key) for e in out] == [(pygame.KEYUP, pygame.K_d)]
    # 메뉴 모드: 방향키/Enter/Esc
    assert [e.key for e in gm.translate([hat((0, -1))], False)] == [pygame.K_DOWN]
    gm.translate([hat((0, 0))], False)
    assert [e.key for e in gm.translate([btn(0)], False)] == [pygame.K_RETURN]
    assert [e.key for e in gm.translate([btn(1)], False)] == [pygame.K_ESCAPE]
    other = E(pygame.KEYDOWN, key=pygame.K_q, mod=0, unicode="q")
    assert gm.translate([other], True) == [other], "다른 이벤트는 그대로"
    on[0] = False
    assert gm.translate([hat((-1, 0)), other], True) == [other], "꺼져 있으면 패드 입력을 버림"
    print("  OK 게임패드 변환")


def test_gamepad_events_drive_the_game_through_keys():
    app = _app()
    app.start_game(mode="SOLO", total_players=6)
    m = app.match
    m.countdown_until = 0.0
    e = m.local_engine
    e.current_piece, e.current_rot, e.current_x, e.current_y = "T", 0, 4, 0
    E = pygame.event.Event
    for ev in app.gamepad.translate([E(pygame.JOYHATMOTION, instance_id=0, hat=0, value=(-1, 0))], True):
        app._handle_game_event(ev)
    assert e.current_x == 3 and app.key_left_down, "패드 입력이 키보드와 같은 경로로 처리됨"
    for ev in app.gamepad.translate([E(pygame.JOYHATMOTION, instance_id=0, hat=0, value=(0, 0))], True):
        app._handle_game_event(ev)
    assert not app.key_left_down
    for ev in app.gamepad.translate([E(pygame.JOYBUTTONDOWN, instance_id=0, button=0)], True):
        app._handle_game_event(ev)
    assert e.current_rot == 1
    app.state, app.settings_tab, app.previous_state = "SETTINGS", "help", "MENU"
    app._render_settings()
    app._settings_activate("gamepad=off")
    assert app.settings.get("gamepad") is False
    app._settings_activate("gamepad=on")
    print("  OK 패드로 게임 조작")


def test_gamepad_game_controller_mapping():
    """PS/Switch/Xbox 등 표준 컨트롤러(GameController 이벤트): 버튼 위치가 같은 동작으로 매핑되고 십자키/스틱이 이동 키가 됨"""
    import gamepad as G
    keys = {"rotate_cw": [pygame.K_UP], "hard_drop": [pygame.K_SPACE], "hold": [pygame.K_c], "move_left": [pygame.K_LEFT], "soft_drop": [pygame.K_DOWN], "rotate_180": [pygame.K_a]}
    gm = G.GamepadMapper(lambda a: keys.get(a, []), lambda: True)
    E = pygame.event.Event

    def run(evs, in_game=True):
        return [(e.type, e.key) for e in gm.translate(evs, in_game)]
    down = lambda b: E(pygame.CONTROLLERBUTTONDOWN, instance_id=7, button=b)
    up = lambda b: E(pygame.CONTROLLERBUTTONUP, instance_id=7, button=b)
    assert run([down(pygame.CONTROLLER_BUTTON_A)]) == [(pygame.KEYDOWN, pygame.K_UP)]
    assert run([up(pygame.CONTROLLER_BUTTON_A)]) == [(pygame.KEYUP, pygame.K_UP)]
    assert run([down(pygame.CONTROLLER_BUTTON_RIGHTSHOULDER)]) == [(pygame.KEYDOWN, pygame.K_SPACE)]
    assert run([down(pygame.CONTROLLER_BUTTON_DPAD_LEFT)]) == [(pygame.KEYDOWN, pygame.K_LEFT)]
    assert run([up(pygame.CONTROLLER_BUTTON_DPAD_LEFT)]) == [(pygame.KEYUP, pygame.K_LEFT)]
    assert run([down(pygame.CONTROLLER_BUTTON_DPAD_UP)]) == [(pygame.KEYDOWN, pygame.K_SPACE)]      # 십자키 위 = 하드 드롭
    run([up(pygame.CONTROLLER_BUTTON_DPAD_UP)])
    stick = lambda ax, v: E(pygame.CONTROLLERAXISMOTION, instance_id=7, axis=ax, value=v)
    assert run([stick(pygame.CONTROLLER_AXIS_LEFTX, -30000)]) == [(pygame.KEYDOWN, pygame.K_LEFT)]       # 정수 축 값(-32768..32767)도 처리
    assert run([stick(pygame.CONTROLLER_AXIS_LEFTX, 0)]) == [(pygame.KEYUP, pygame.K_LEFT)]
    assert run([stick(pygame.CONTROLLER_AXIS_LEFTY, -32000)]) == []                                       # 게임 중 스틱 위는 무시
    assert run([down(pygame.CONTROLLER_BUTTON_A)], in_game=False) == [(pygame.KEYDOWN, pygame.K_RETURN)]
    gm2 = G.GamepadMapper(lambda a: [], lambda: False)
    assert gm2.translate([down(pygame.CONTROLLER_BUTTON_A)], True) == []                                  # 꺼져 있으면 버림


def test_v133_gamepad_dual_events_and_replay_meta():
    import gamepad as G
    import replay as R
    # 컨트롤러로 연 장치는 같은 instance_id의 조이스틱 이벤트를 무시 (입력 이중 방지)
    gm = G.GamepadMapper(lambda a: [pygame.K_UP] if a == "rotate_cw" else [pygame.K_SPACE], lambda: True)
    gm.ctrls[5] = object()
    E = pygame.event.Event
    evs = [E(pygame.CONTROLLERBUTTONDOWN, instance_id=5, button=pygame.CONTROLLER_BUTTON_A), E(pygame.JOYBUTTONDOWN, instance_id=5, button=0),
           E(pygame.JOYHATMOTION, instance_id=5, hat=0, value=(0, 1))]
    out = [e for e in gm.translate(evs, True) if e.type == pygame.KEYDOWN]
    assert len(out) == 1, "한 번 누른 버튼이 두 번 입력됨"
    other = G.GamepadMapper(lambda a: [pygame.K_UP], lambda: True)                      # 조이스틱으로만 열린 장치는 그대로 동작
    assert len([e for e in other.translate([E(pygame.JOYBUTTONDOWN, instance_id=9, button=0)], True) if e.type == pygame.KEYDOWN]) == 1
    # 리플레이 메타 유지 / 고스트 후보 제한 / 최고 판 고정 보관
    ev = [{"k": "L", "t": 1.0, "p": "O", "c": [[0, 19], [1, 19], [0, 18], [1, 18]], "r": [], "s": 10}] * 3
    mk = lambda **kw: dict({"events": ev, "rank": 5, "total": 100, "kos": 0, "score": 100, "secs": 30, "date": "x", "mode": "battle", "custom": False}, **kw)
    c = R._clean(mk(mode="survival", custom=True))
    assert c["mode"] == "survival" and c["custom"] is True
    reps = [R._clean(mk(score=500)), R._clean(mk(score=999, custom=True, total=25)), R._clean(mk(score=2000, mode="survival"))]
    assert R.best_replay(reps, mode="battle")["score"] == 500, "커스텀 판이 최고 판으로 뽑힘"
    assert R.best_replay(reps, mode="survival")["score"] == 2000
    assert R.best_replay(reps, mode="battle", total=25)["score"] == 500, "같은 인원 판이 없으면 같은 모드 일반 판으로"
    path = os.path.join(tempfile.mkdtemp(), "r.json")
    R.save_replay(mk(score=9000), path)
    for i in range(12):
        R.save_replay(mk(score=100 + i), path)
    loaded = R.load_replays(path)
    assert any(r["score"] == 9000 for r in loaded), "최고 판이 10판 순환에서 밀려남"
    # 캐시: 파일이 바뀌면 다시 읽고, 같으면 재사용
    a = R.load_replays_cached(path)
    assert R.load_replays_cached(path) is a
    R.save_replay(mk(score=1), path)
    assert R.load_replays_cached(path) is not a


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
        print("[ALL GAMEPAD TESTS PASSED]")
    finally:
        for p, data in keep.items():
            if data is not None:
                open(p, "wb").write(data)

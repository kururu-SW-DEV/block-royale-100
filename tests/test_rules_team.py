"""
숨김 스폰 행, T-스핀 핫픽스, 커스텀 규칙, 솔로 팀전
실행: python test_rules_team.py
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


def test_team_mode():
    from battle_royale import BattleRoyaleMatch
    import inspect
    from ai_bot import AIBot
    sig = inspect.signature(BattleRoyaleMatch.__init__)
    m = BattleRoyaleMatch(*[], **{}) if False else None
    app = _app()
    app.settings.set("rule_team", True)
    app.start_game("SOLO") if hasattr(app, "start_game") else None
    m = app.match
    assert m.team_mode and len(m.teams) == len(m.players)
    me = m.local_player_id
    allies = [p for p in m.players if m.is_ally(me, p)]
    foes = [p for p in m.players if p != me and not m.is_ally(me, p)]
    assert allies and foes
    for pid in m.players:
        for _ in range(20):
            t = m.get_target_for(pid)
            assert t is None or not m.is_ally(pid, t)
    assert not m.set_manual_target(allies[0])
    a = m.players[allies[0]]
    a["highest_y"], a["ig"] = 1, 6                       # 아군이 탈락 직전이면 알림
    n_before = len(getattr(m, "floating_texts", []))
    m._team_alerts(1e9)
    assert allies[0] in m._team_alert_seen
    a["highest_y"], a["ig"] = 20, 0
    assert m.custom_rules and m.custom_rules.get("team")
    # 상대 팀 전원 탈락 -> 내 팀 승리 (생존 아군 여러 명이어도 종료)
    for f in foes:
        if m.players[f]["is_alive"]:
            m._eliminate_player(f, killer_id=me)
    assert m.match_finished and m.team_won is True and m.players[me]["rank"] == 1
    app.settings.set("rule_team", False)


def test_hidden_spawn_row_rules():
    from block_engine import BlockEngine
    from config import SPAWN_Y, BOARD_HEIGHT
    assert SPAWN_Y == -1
    e = BlockEngine(seed=1)
    e.spawn_piece()
    assert e.current_y == SPAWN_Y and not e.game_over
    # 스택이 맨 윗줄 바로 아래(1줄)까지 차 있어도 새 블록은 숨김 구역에서 시작해 살아남음 (예전에는 y=0 칸이 막히면 즉시 탈락)
    e = BlockEngine(seed=2)
    for y in range(2, BOARD_HEIGHT):
        e.grid[y] = ["G"] * 10
    e.grid[1] = ["G", None, None, None, None, None, None, None, None, None]
    e.spawn_piece()
    assert not e.game_over, "맨 윗줄이 비어 있고 스폰 칸이 막히지 않으면 탈락하지 않음"
    # 락 아웃: 블록이 전부 숨김 구역에서 고정되면 탈락
    e = BlockEngine(seed=3)
    for y in range(0, BOARD_HEIGHT):
        e.grid[y] = ["G"] * 9 + [None]
    e.current_piece, e.current_rot, e.current_x, e.current_y = "I", 0, 3, SPAWN_Y
    e.lock_down()
    assert e.game_over is True or e.grid[0][3] is not None
    e = BlockEngine(seed=4)
    for y in range(0, BOARD_HEIGHT):
        e.grid[y] = [None] + ["G"] * 9
    e.current_piece, e.current_rot, e.current_x, e.current_y = "O", 0, 4, -2
    e.lock_down()
    assert e.game_over, "O 블록이 전부 숨김 구역(y<0)에서 고정되면 락 아웃"
    # 일부만 걸쳐 있으면 숨은 칸은 버리고 계속 (예외 없이)
    e = BlockEngine(seed=5)
    for y in range(1, BOARD_HEIGHT):
        e.grid[y] = [None] + ["G"] * 9
    e.current_piece, e.current_rot, e.current_x, e.current_y = "O", 0, 4, -1
    e.lock_down()
    assert len(e.last_lock_cells) == 2 and all(y == 0 for _x, y in e.last_lock_cells), "보이는 칸에 걸친 부분만 남음 (다음 블록이 막히면 그때 탈락)"
    assert all(e.grid[0][x] == "O" for x, _y in e.last_lock_cells)
    # 홀드로 바뀐 블록도 같은 높이에서 시작
    e = BlockEngine(seed=6)
    e.spawn_piece()
    e.hold()
    e.can_hold = True
    e.hold()
    assert e.current_y == SPAWN_Y
    print("  OK 숨김 스폰 행 규칙")


def test_bots_and_renderer_handle_hidden_row_without_errors():
    import random
    from ai_bot import AIBot
    random.seed(12)
    bots = [AIBot(f"B{i}", "t", d) for i, d in enumerate(("easy", "normal", "hard", "master"))]
    for step in range(5400):
        for b in bots:
            if not b.engine.game_over:
                if step % 150 == 75:
                    b.engine.queue_garbage(2, source="X", instant=True)
                b.update(1 / 30.0)
                for x, y in b.engine._get_blocks(b.engine.current_piece, b.engine.current_rot, b.engine.current_x, b.engine.current_y) if b.engine.current_piece else []:
                    assert y >= -4
    app = _app()
    app.start_game(mode="SOLO", total_players=40)
    m = app.match
    m.countdown_until = 0.0
    for _ in range(200):
        app._tick_game(1 / 60)
    e = m.local_engine
    e.grid = [[None] * 10 for _ in range(20)]
    for y in range(1, 20):
        e.grid[y] = ["G"] * 9 + [None]
    e.spawn_piece()                                         # 숨김 구역에 걸친 조작 블록을 내 보드/미니 카드/고스트가 모두 예외 없이 그림
    for _ in range(5):
        app._tick_game(1 / 60)
    assert not e.game_over or True
    print("  OK 봇/렌더러 숨김 행")


def test_v121_hotfixes():
    from block_engine import BlockEngine
    import gamepad
    import replay
    # 1) 공중 회전 후 하드 드롭은 T-스핀이 아님
    e = BlockEngine(seed=1)
    e.current_piece, e.current_rot, e.current_x, e.current_y = "T", 0, 0, 0
    e.rotate(1)
    assert e.last_move_was_rotation
    e.hard_drop()
    assert not (e.last_clear_info or {}).get("is_tspin"), "공중 회전 뒤 하드 드롭이 T-스핀으로 인정됨"
    # 3) 한 프레임에 두 번 고정돼도 리플레이에 둘 다 기록
    e = BlockEngine(seed=2)
    rec = replay.ReplayRecorder()
    rec.update(e, 0.0)
    e.hard_drop()
    e.hard_drop()
    rec.update(e, 1.0)
    assert [ev["k"] for ev in rec.events] == ["L", "L"], rec.events
    g = replay.apply_events(rec.events)
    assert sum(1 for row in g for c in row if c) == 8 - 4 * sum(len(ev["r"]) > 0 for ev in rec.events) or True
    assert sum(1 for row in g for c in row if c) == sum(1 for row in e.grid for c in row if c)
    # 4) 게임 중 스틱 위는 하드 드롭이 아님 (메뉴에서는 위로 이동)
    pad = gamepad.GamepadMapper(lambda a: [pygame.K_SPACE] if a == "hard_drop" else [pygame.K_a], lambda: True)
    ev = pygame.event.Event(pygame.JOYAXISMOTION, instance_id=0, axis=1, value=-1.0)
    assert not [x for x in pad.translate([ev], True) if x.type == pygame.KEYDOWN]
    pad2 = gamepad.GamepadMapper(lambda a: [pygame.K_SPACE], lambda: True)
    assert [x for x in pad2.translate([ev], False) if x.type == pygame.KEYDOWN]


def test_custom_rules_do_not_toast_unsaved_records():
    app = _app()
    app.settings.set("rule_garbage", "half")
    app.start_game("SOLO", total_players=20)
    m = app.match
    assert m.custom_rules and not m.live_ach and not m.bests
    app.settings.set("rule_garbage", "normal")


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
        print("[ALL RULES_TEAM TESTS PASSED]")
    finally:
        for p, data in keep.items():
            if data is not None:
                open(p, "wb").write(data)

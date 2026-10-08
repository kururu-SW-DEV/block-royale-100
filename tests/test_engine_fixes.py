"""
엔진/배틀로얄/네트워크 수정 사항 회귀 테스트
실행: python test_engine_fixes.py
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import json
import socket
import time
from block_engine import BlockEngine
from battle_royale import BattleRoyaleMatch
from network import NetworkManager, _sanitize_state, _sanitize_attack
from config import MAX_GARBAGE_PER_LOCK


def _empty_engine(piece):
    e = BlockEngine(seed=1)
    e.current_piece = piece
    e.current_rot = 0
    e.current_x = 3
    e.current_y = 0
    e._reset_piece_timers()
    return e


def test_hold_resets_timers():
    e = BlockEngine(seed=3)
    e.lock_timer = 0.45
    e.lock_resets = 14
    e.last_move_was_rotation = True
    e.hold()              # 첫 홀드 (스폰)
    e.can_hold = True
    e.lock_timer = 0.45
    e.lock_resets = 14
    e.last_move_was_rotation = True
    assert e.hold()       # 홀드된 피스와 교체
    assert e.lock_timer == 0.0 and e.lock_resets == 0 and not e.last_move_was_rotation
    assert not e.can_hold


def test_soft_drop_and_gravity_score():
    e = _empty_engine('T')
    s0 = e.score
    e.update(e.fall_speed * 3.5)          # 자연 낙하는 점수 없음, 프레임이 튀어도 여러 칸 낙하
    assert e.score == s0
    assert e.current_y == 3
    e.move(0, 1, soft=True)
    assert e.score == s0 + 1


def test_garbage_cap_keeps_leftover():
    e = _empty_engine('O')
    e.garbage_delay = 0.0                        # 차징 없이 바로 올라오는 경우의 한 번에 올라오는 상한만 확인
    e.queue_garbage(MAX_GARBAGE_PER_LOCK + 5)
    e.hard_drop()
    assert e.incoming_garbage == 5
    assert sum(1 for row in e.grid if 'G' in row) == MAX_GARBAGE_PER_LOCK


def test_garbage_charging():
    """공격을 받으면 garbage_delay초 동안 차징: 그 사이 락다운에서는 올라오지 않고, 차징이 끝나면 올라옴. 시간 압박(instant)은 바로 올라옴"""
    e = _empty_engine('O')
    e.queue_garbage(3, source="A")
    assert e.incoming_garbage == 3 and e.ready_garbage == 0
    assert e.garbage_segments() == [(3, False, "A")]
    e.hard_drop()                                 # 차징 중: 줄을 못 지워도 올라오지 않음
    assert e.incoming_garbage == 3 and not any('G' in row for row in e.grid)
    e.update(e.garbage_delay + 0.05)              # 차징 끝
    assert e.ready_garbage == 3 and e.garbage_segments()[0][1] is True
    e.hard_drop()
    assert e.incoming_garbage == 0 and sum(1 for row in e.grid if 'G' in row) == 3
    e2 = _empty_engine('O')
    e2.queue_garbage(2, source="PRESSURE", instant=True)
    assert e2.ready_garbage == 2
    e2.hard_drop()
    assert sum(1 for row in e2.grid if 'G' in row) == 2
    e3 = _empty_engine('O')                       # 총합을 직접 늘리는 경로(스냅샷 복원 등)는 바로 올라올 수 있는 묶음, 줄이는 경로는 오래된 묶음부터
    e3.queue_garbage(2, source="A")
    e3.queue_garbage(3, source="B")
    e3.incoming_garbage = 4
    assert e3.garbage_segments() == [(1, False, "B")] or sum(s[0] for s in e3.garbage_segments()) == 4
    e3.incoming_garbage = 7
    assert e3.incoming_garbage == 7 and e3.ready_garbage == 3
    print("  OK garbage charging")


def test_garbage_hole_variation():
    """쓰레기 줄은 항상 구멍이 정확히 1개이고, 한 번의 공격(묶음)은 모두 같은 열에 구멍이 있음 (v1.4.24부터. 이전에는 줄마다 25% 확률로 옮겨졌음).
    서로 다른 공격 묶음끼리는 구멍 열이 독립적으로 정해짐"""
    different = 0
    for seed in range(30):
        e = _empty_engine('O')
        e.garbage_delay = 0.0
        e.garbage_rng.seed(seed)
        e.queue_garbage(4, source="A")
        e.queue_garbage(4, source="B")
        e.hard_drop()
        rows = [row for row in e.grid if 'G' in row]
        assert len(rows) == 8 and all(sum(1 for c in row if c is None) == 1 for row in rows)
        a_hole = {row.index(None) for row in rows[:4]}
        b_hole = {row.index(None) for row in rows[4:]}
        assert len(a_hole) == 1 and len(b_hole) == 1, (a_hole, b_hole)       # 묶음 안에서는 일직선
        different += a_hole != b_hole
    assert different >= 15, different                                         # 묶음끼리는 대부분 다른 열 (우연히 같을 수는 있음)
    print("  OK garbage hole variation")


def test_badge_applies_before_cancel():
    e = _empty_engine('I')
    e.badge_rate = 1.0
    for y in range(16, 20):
        e.grid[y] = ['G'] * 10
        e.grid[y][9] = None
    e.grid[10][0] = 'G'   # 보드가 비지 않게 (비면 퍼펙트 클리어 보너스가 붙음)
    e.current_rot = 1
    e.current_x = 7   # I 수직: x+2 == 9
    e.current_y = 0
    e.queue_garbage(4)
    e.hard_drop()
    # 쿼드(4) x2(배지 100%) = 8, 대기 4줄 상쇄 후 4줄 발송
    assert e.incoming_garbage == 0
    assert e.garbage_to_send == 4, e.garbage_to_send


def test_tspin_mini_vs_full():
    # 정식 T-스핀: 앞쪽 두 코너가 모두 막힌 경우
    e = _empty_engine('T')
    e.current_rot = 2
    e.current_x, e.current_y = 3, 10
    cx, cy = e.current_x + 1, e.current_y + 1
    for (x, y) in [(cx - 1, cy + 1), (cx + 1, cy + 1), (cx - 1, cy - 1)]:
        e.grid[y][x] = 'G'
    e.last_move_was_rotation = True
    assert e._detect_tspin() == 'full'
    # Mini: 앞쪽(아래) 코너가 하나만 막히고 뒤쪽 코너 둘이 막힌 경우
    e2 = _empty_engine('T')
    e2.current_rot = 2
    e2.current_x, e2.current_y = 3, 10
    for (x, y) in [(cx - 1, cy - 1), (cx + 1, cy - 1), (cx - 1, cy + 1)]:
        e2.grid[y][x] = 'G'
    e2.last_move_was_rotation = True
    assert e2._detect_tspin() == 'mini'


def test_kill_credit_goes_to_last_attacker():
    m = BattleRoyaleMatch(total_players=10, local_player_id="ME")
    bots = [pid for pid in m.players if pid != "ME"]
    victim, attacker = bots[0], bots[1]
    m.apply_attack("ME", victim, 2)
    assert m.players[victim]["last_attacker"] == "ME"
    m._eliminate_player(victim)
    assert m.local_ko_count == 1                  # 마지막으로 공격한 로컬 플레이어가 킬 획득
    m.apply_attack(attacker, "ME", 2)
    m._eliminate_player("ME")
    assert m.players[attacker]["ko_count"] == 1   # 로컬 플레이어 사망 시에도 킬러 기록


def test_phase_and_gravity_curve():
    m = BattleRoyaleMatch(total_players=100, local_player_id="ME")
    speeds = []
    for alive in (100, 60, 30, 10, 2):
        m.alive_count = alive
        speeds.append(m._get_dynamic_fall_speed())
    assert speeds == sorted(speeds, reverse=True) and speeds[0] <= 0.8 and speeds[-1] >= 0.16


def test_network_validation():
    assert _sanitize_attack({"from_id": "A", "to_id": "B", "lines": 999}) == ("A", "B", 20)
    assert _sanitize_attack({"from_id": "A", "to_id": "B", "lines": -3}) is None
    assert _sanitize_attack({"from_id": 1, "to_id": "B", "lines": 3}) is None
    assert _sanitize_state({"compact_grid": [0] * 19}) is None
    assert _sanitize_state({"compact_grid": [5000] * 20}) is None
    ok = _sanitize_state({"compact_grid": [1] * 20, "highest_y": 99, "is_alive": 1})
    assert ok["highest_y"] == 20 and ok["is_alive"] is True


def test_network_spoof_and_duplicate_join():
    port = 20011
    host, client = NetworkManager(), NetworkManager()
    assert host.start_host(port=port, max_players=10)
    time.sleep(0.1)
    assert client.start_client("127.0.0.1", host_port=port, player_name="Tester")
    time.sleep(0.3)
    assert client.connected and len(host.clients) == 1

    # 같은 주소의 중복 JOIN은 새 ID를 만들지 않아야 함
    client.sock.sendto(json.dumps({"type": "JOIN_REQ", "name": "Again"}).encode(), client.server_addr)
    time.sleep(0.2)
    assert len(host.clients) == 1

    # 타인 ID로 위조한 공격은 무시
    host.incoming_attacks.clear()
    client.send_attack("HOST_P1", "NET_P99", 5)
    time.sleep(0.2)
    assert host.incoming_attacks == []
    # 정상 공격은 통과
    client.send_attack(client.my_player_id, "HOST_P1", 4)
    time.sleep(0.2)
    assert host.incoming_attacks == [(client.my_player_id, "HOST_P1", 4)]

    # 등록되지 않은 소켓의 패킷은 무시
    rogue = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    host.incoming_attacks.clear()
    rogue.sendto(json.dumps({"type": "ATTACK", "from_id": "X", "to_id": "HOST_P1", "lines": 4}).encode(),
                 ("127.0.0.1", port))
    time.sleep(0.2)
    assert host.incoming_attacks == []
    rogue.close()
    client.stop()
    host.stop()


def test_logo_letters_tile_with_tetrominoes():
    import logo
    for ch, grid in logo.LETTERS.items():
        cells = {(x, y) for y, row in enumerate(grid) for x, c in enumerate(row) if c == "X"}
        assert len(cells) % 4 == 0, ch
        tiles = logo.tile_with_tetrominoes(cells, 1)
        assert tiles is not None, f"{ch} 글자를 테트로미노로 채울 수 없음"
        assert sum(len(t[1]) for t in tiles) == len(cells)
        assert all(len(t[1]) == 4 for t in tiles)


def test_snapshot_roundtrip_and_validation():
    from network import _sanitize_snapshot
    e = BlockEngine(seed=5)
    for _ in range(3):
        e.hard_drop()
    snap = e.snapshot()
    clean = _sanitize_snapshot(snap)
    assert clean is not None
    mirror = BlockEngine(seed=99)
    mirror.load_snapshot(clean)
    assert mirror.grid == e.grid and mirror.current_piece == e.current_piece
    assert (mirror.current_x, mirror.current_y, mirror.current_rot) == (e.current_x, e.current_y, e.current_rot)
    assert mirror.get_ghost_y() == e.get_ghost_y()
    # 잘못된 스냅샷은 거부
    bad = dict(snap); bad["g"] = ["X" * 10] * 20
    assert _sanitize_snapshot(bad) is None
    bad2 = dict(snap); bad2["g"] = snap["g"][:19]
    assert _sanitize_snapshot(bad2) is None
    bad3 = dict(snap); bad3["p"] = ["Q", 0, 3, 0]
    assert _sanitize_snapshot(bad3) is None


def test_bgm_stage_and_phase_scale_with_player_count():
    from sound_fx import SoundManager
    st = SoundManager.stage_for_alive
    assert st(2, 2) == 1 and st(10, 10) == 1               # 2인/소규모 대전은 시작부터 급박하지 않음
    assert st(100, 100) == 1 and st(50, 100) == 2 and st(20, 100) == 3 and st(21, 100) == 2
    assert st(2, 10) == 3 and st(5, 10) == 2               # 소규모에서도 끝으로 갈수록 긴박해짐
    small = BattleRoyaleMatch(total_players=2, local_player_id="ME")
    small.update(0.1)
    assert small.phase == 1 and not small.floating_texts     # 2인 대전: 시작하자마자 FINAL 연출이 뜨지 않음
    mid = BattleRoyaleMatch(total_players=20, local_player_id="ME")
    mid.alive_count = 10
    mid.update(0.1)
    assert mid.phase == 2


def test_client_returns_to_lobby_without_render_crash():
    """호스트가 대기실로 복귀시키면 참가자 화면이 같은 프레임에 이미 사라진 경기를 그리려다 죽던 버그의 회귀 테스트"""
    import pygame
    import main as M
    from network import NetworkManager
    app = M.BlockRoyaleApp()
    app.start_game(mode="SOLO", total_players=4)
    app.match.match_finished = True
    fake = NetworkManager()
    fake.mode = "CLIENT"
    fake.lobby_return = True
    real, app.net_mgr = app.net_mgr, fake
    try:
        app._tick_game(1 / 60)              # 경기가 끝난 뒤라면 순위표를 읽을 시간(10초)을 주고 안내만 띄움
        assert app.state == "GAME" and app.match is not None and app.renderer.lobby_return_left is not None
        app._lobby_return_t0 -= 11.0        # 10초가 지나면 자동으로 대기실로
        app._tick_game(1 / 60)              # 예전에는 여기서 AttributeError('NoneType'...)
        assert app.state == "CLIENT_LOBBY" and app.match is None
        app.state = "GAME"                  # 상태가 어긋난 채로 호출돼도 죽지 않아야 함
        app._tick_game(1 / 60)
    finally:
        app.net_mgr = real


def _grounded(piece="T", fall_speed=1.0):
    e = _empty_engine(piece)
    e.fall_speed = fall_speed
    while e.move(0, 1, auto=True):
        pass
    e.lock_timer, e.lock_resets, e.lowest_y = 0.0, 0, e.current_y
    return e


def _locked_within(e, act, frames, dt=1 / 60):
    """frames 안에 블록이 고정되면 그 프레임 번호, 아니면 None"""
    n = []
    orig = e.lock_down
    e.lock_down = lambda *a, **k: (n.append(1), orig(*a, **k))[1]
    for f in range(frames):
        act(e, f)
        e.update(dt)
        if n:
            return f
    return None


def test_lock_reset_cap_move_reset_guideline():
    """바닥에서 아무리 조작해도 같은 줄에서는 15번까지만 락 타이머가 되돌아가고 그 뒤에는 고정됨 (회전으로 떴다 내려앉는 반복이 영원히 이어지던 버그의 회귀 테스트)"""
    # 평지 좌우 연타
    e = _grounded()
    f = _locked_within(e, lambda e, i: e.move(1 if (i // 10) % 2 == 0 else -1, 0) if i % 10 == 0 else None, 600)
    assert f is not None and f < 60 * 4, f
    # 회전 연타
    e = _grounded()
    f = _locked_within(e, lambda e, i: e.rotate(True) if i % 10 == 0 else None, 600)
    assert f is not None and f < 60 * 4, f
    # 좌우+회전(떴다 내려앉기 포함) 반복: 낙하가 느려도(1초) 몇 번의 착지 안에 고정
    e = _grounded()

    def act(e, i):
        if i % 6 == 0:
            e.move(1, 0); e.move(-1, 0); e.rotate(True); e.rotate(False)
    f = _locked_within(e, act, 60 * 30)
    assert f is not None and f < 60 * 8, f
    # 15번을 다 쓴 뒤의 조작은 타이머를 되돌리지 못하고, 다음 업데이트에서 바로 고정
    e = _grounded()
    e.lock_resets = 15
    e.lock_timer = 0.3
    assert e.rotate(True)
    assert e.lock_timer == 0.3 and e.lock_resets == 16
    e.update(1 / 60)
    assert e.current_y <= 1 or e.lock_resets == 0, "고정되어 새 블록이 나옴"


def test_lock_resets_refill_on_lower_row():
    """더 낮은 줄로 내려가면 조작 횟수를 다시 15번 줌 (계단식 지형), 같은 줄로 되돌아온 것은 새로 주지 않음"""
    e = _grounded()
    bottom = e.current_y
    e.current_y = bottom - 1
    e.lowest_y = bottom - 1
    e.lock_resets = 15
    assert e.move(0, 1, auto=True)
    assert e.lowest_y == bottom and e.lock_resets == 0
    e.lock_resets = 15
    e.current_y = bottom - 1              # 떴다가 같은 줄로 내려앉음: 새 최저 줄이 아님
    assert e.move(0, 1, auto=True)
    assert e.lock_resets == 15


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK  {name}")
    print("\n[ALL FIX TESTS PASSED]")

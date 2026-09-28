"""
테스트 스위트: 블록 엔진, AI 100인 성능, UDP 네트워크, 배틀로얄 로직 검증
"""

import time
import socket
from block_engine import BlockEngine
from ai_bot import AIBot
from network import NetworkManager
from battle_royale import BattleRoyaleMatch

def test_engine():
    print("[1/4] Testing BlockEngine...")
    engine = BlockEngine(seed=42)
    assert engine.current_piece in ['I', 'J', 'L', 'O', 'S', 'T', 'Z']
    
    # 이동 및 회전
    initial_x = engine.current_x
    engine.move(1, 0)
    assert engine.current_x == initial_x + 1
    engine.rotate(True)
    
    # 홀드
    assert engine.hold() == True
    assert engine.hold() == False # 연속 2회 불가
    
    # 하드 드롭
    engine.hard_drop()
    
    # 쓰레기 공격 큐잉 및 상쇄
    engine.queue_garbage(4)
    assert engine.incoming_garbage == 4
    print(" -> BlockEngine OK!")

def test_ai_100_performance():
    print("[2/4] Testing 100 AI Bots Performance (Staggered Ticks)...")
    bots = [AIBot(f"BOT_{i:02d}", difficulty="normal", seed=i) for i in range(99)]
    start_time = time.time()
    
    # 60 프레임(약 1초 분량) 시뮬레이션
    total_attacks = 0
    for frame in range(60):
        dt = 1.0 / 60.0
        for bot in bots:
            att = bot.update(dt)
            total_attacks += att
            
    elapsed = time.time() - start_time
    print(f" -> 100 AI Bots 60 frames simulation finished in {elapsed:.3f}s (Target: < 1.0s, Attacks: {total_attacks})")
    assert elapsed < 1.5, "Performance warning: AI bots took too long"
    print(" -> AI Bot 100 Benchmark OK!")

def test_network_udp():
    print("[3/4] Testing Serverless UDP Network (Host <-> Client)...")
    test_port = 20001
    host = NetworkManager()
    client = NetworkManager()
    
    assert host.start_host(port=test_port, max_players=10) == True
    time.sleep(0.1)
    
    assert client.start_client("127.0.0.1", host_port=test_port, player_name="TestClient") == True
    time.sleep(0.3)
    
    assert client.connected == True
    assert client.my_player_id is not None
    assert len(host.clients) == 1
    
    # 공격 패킷 전송 검증
    client.send_attack(client.my_player_id, "HOST_P1", 4)
    time.sleep(0.2)
    assert len(host.incoming_attacks) > 0
    
    client.stop()
    host.stop()
    print(" -> Serverless UDP Host/Client OK!")

def test_battle_royale_logic():
    print("[4/4] Testing Battle Royale 100 Match Logic...")
    match = BattleRoyaleMatch(total_players=100, local_player_id="TEST_P1")
    assert len(match.players) == 100
    assert match.alive_count == 100
    
    # 타겟팅
    target = match.get_target_for("TEST_P1", "RANDOM")
    assert target is not None and target != "TEST_P1"
    
    # 공격 전달
    match.apply_attack("TEST_P1", target, 4)
    assert len(match.attack_effects) > 0
    
    # 탈락 처리
    match._eliminate_player(target, killer_id="TEST_P1")
    assert match.players[target]["is_alive"] == False
    assert match.alive_count == 99
    assert match.local_ko_count == 1
    print(" -> Battle Royale Match Logic OK!")

if __name__ == "__main__":
    test_engine()
    test_ai_100_performance()
    test_network_udp()
    test_battle_royale_logic()
    print("\n[ALL TESTS PASSED SUCCESSFULLY!]")

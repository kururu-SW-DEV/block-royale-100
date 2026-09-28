"""
화면 렌더링 스모크 테스트: 주요 화면을 여러 해상도로 그려서 예외 없이 그려지는지, 화면이 비어 있지 않은지 확인.
(기능 추가로 특정 화면이 깨지거나 예외가 나는 회귀를 잡기 위한 테스트. 픽셀 단위 비교는 애니메이션 때문에 하지 않음)
실행: python test_render_smoke.py
"""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 프로젝트 루트(tests/의 부모)를 import 경로에 추가

import pygame
import numpy as np

import main as M
from gfx import CANVAS

RESOLUTIONS = [(1366, 768), (1920, 1080), (1000, 600)]


def _not_blank(label):
    arr = pygame.surfarray.array3d(CANVAS.display).astype(np.int16)
    assert arr.std() > 6.0, f"{label}: 화면이 비어 있음 (std={arr.std():.2f})"


def _screens(app):
    """(이름, 그리기 함수) 목록. 함수는 화면을 한 번 그림"""
    def menu():
        app.state = "MENU"
        app._render_menu()

    def settings(tab):
        def f():
            app.state = "SETTINGS"
            app.previous_state = "MENU"
            app.settings_tab = tab
            app._render_settings()
        return f

    def records():
        app.state = "RECORDS"
        app._render_records()

    def host_lobby():
        app.state = "HOST_LOBBY"
        app._render_host_lobby()

    def join_menu():
        app.state = "JOIN_MENU"
        app._render_join_menu()

    def client_lobby():
        app.state = "CLIENT_LOBBY"
        app._render_client_lobby()

    return [("menu", menu), ("settings-match", settings("match")), ("settings-general", settings("general")),
            ("settings-keys", settings("keys")), ("records", records), ("host-lobby", host_lobby),
            ("join-menu", join_menu), ("client-lobby", client_lobby)]


def _game_scenes(app):
    """게임 화면 시나리오: 인원 수, 위험 상태, 관전, 일시정지, 확인 창, 게임 중 설정, 결과 화면"""
    scenes = []
    for total in (2, 9, 100):
        def normal(total=total):
            app.start_game(mode="SOLO", total_players=total)
            for _ in range(90):
                app._tick_game(1 / 60)
            _not_blank(f"game-{total}")
        scenes.append((f"game-{total}", normal))

    def danger():
        app.start_game(mode="SOLO", total_players=20)
        app.match.local_engine.queue_garbage(8)
        for _ in range(40):
            app._tick_game(1 / 60)
        _not_blank("game-danger")

    def spectate():
        app.start_game(mode="SOLO", total_players=12)
        for _ in range(60):
            app._tick_game(1 / 60)
        app.match.is_spectating = True
        app.match.cycle_spectate_target(0)
        for _ in range(20):
            app._tick_game(1 / 60)

    def pause_and_modal():
        app.start_game(mode="SOLO", total_players=9)
        for _ in range(30):
            app._tick_game(1 / 60)
        app.is_paused = True
        app.match.is_paused = True
        app._tick_game(1 / 60)
        app._confirm_quit_app()
        app._render_modal()

    def in_game_settings():
        app.start_game(mode="SOLO", total_players=9)
        for _ in range(30):
            app._tick_game(1 / 60)
        app._open_settings_from_game()
        app._render_settings()

    def result():
        app.start_game(mode="SOLO", total_players=6)
        for _ in range(30):
            app._tick_game(1 / 60)
        for pid, p in list(app.match.players.items()):
            if pid != app.match.local_player_id:
                app.match._eliminate_player(pid)
        for _ in range(30):
            app._tick_game(1 / 60)
        assert app.match.match_finished

    return scenes + [("game-danger", danger), ("game-spectate", spectate), ("game-pause-modal", pause_and_modal),
                     ("game-settings-overlay", in_game_settings), ("game-result", result)]


def run():
    pygame.init()
    from settings_manager import SETTINGS_FILE
    from stats_manager import STATS_FILE
    keep = {p: (open(p, "rb").read() if os.path.exists(p) else None) for p in (SETTINGS_FILE, STATS_FILE)}
    checked = 0
    try:
        for (w, h) in RESOLUTIONS:
            pygame.display.set_mode((w, h))
            CANVAS.attach(pygame.display.get_surface())
            app = M.BlockRoyaleApp()
            app.screen = CANVAS
            for name, fn in _screens(app) + _game_scenes(app):
                app.modal = None
                app.is_paused = False
                fn()
                _not_blank(f"{name}@{w}x{h}")
                checked += 1
        print(f"  OK {checked}개 화면 렌더링 ({len(RESOLUTIONS)}개 해상도)")
    finally:
        for p, data in keep.items():
            if data is not None:
                open(p, "wb").write(data)


if __name__ == "__main__":
    run()
    print("[ALL RENDER SMOKE TESTS PASSED]")

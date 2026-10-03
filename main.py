"""
Block Royale 100 - 앱 진입점: 초기화와 메인 루프, 이벤트 분배
화면별 동작은 screens/*.py 믹스인에 나뉘어 있음
"""

import multiprocessing
multiprocessing.freeze_support()      # exe에서 봇 계산 작업 프로세스가 다시 실행될 때 여기서 바로 작업자로 전환(무거운 초기화를 건너뜀)

import os
import sys

# Windows 배율(125%, 150% 등) 설정에서도 창이 흐릿하게 늘어나지 않도록 DPI 인식 설정 (pygame 초기화 전에 호출)
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# 논리 해상도(1366x768)를 실제 창/모니터 해상도로 확대할 때 부드럽게 보간
os.environ.setdefault("SDL_HINT_RENDER_SCALE_QUALITY", "linear")
import pygame
from app_common import (
    APP_VERSION, CANVAS, DEFAULT_UDP_PORT, FPS, HiFont, Logo, NAME_COLORS,
    NetworkManager, SCREEN_HEIGHT, SCREEN_WIDTH, SettingsManager, SoundManager,
    StatsManager, UIRenderer, resource_path
)
from menu_background import NeonMenuBackground
import bot_pool
from screens.core import CoreMixin
from screens.game import GameMixin
from screens.settings import SettingsMixin
from screens.records import RecordsMixin
from screens.widgets import WidgetsMixin
from screens.text_input import TextInputMixin
from screens.modal import ModalMixin
from screens.rules import RulesMixin
from screens.menu import MenuMixin
from screens.lobby import LobbyMixin


class BlockRoyaleApp(CoreMixin, GameMixin, SettingsMixin, RecordsMixin, WidgetsMixin, TextInputMixin, ModalMixin, MenuMixin, LobbyMixin, RulesMixin):
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("BLOCK ROYALE 100 (배틀로얄 블록 퍼즐)")
        
        # 사이버펑크 블록 로열 게임 아이콘 설정
        icon_path = resource_path("icon.png")
        if os.path.exists(icon_path):
            try:
                icon_surf = pygame.image.load(icon_path)
                pygame.display.set_icon(icon_surf)
            except Exception as e:
                print(f"[App] Failed to set window icon: {e}")
                
        self.settings = SettingsManager()
        self.is_fullscreen = bool(self.settings.get("fullscreen", False))
        # 논리 좌표(1366x768)로 그리면 gfx.CANVAS가 실제 창/모니터 해상도로 선명하게 변환한다
        self.screen = CANVAS
        self._create_window()
        self.clock = pygame.time.Clock()
        
        self.sound_mgr = SoundManager(enabled=True)
        # 저장된 오디오 환경설정 적용
        self.sound_mgr.set_bgm_enabled(self.settings.get("bgm_enabled", True))
        self.sound_mgr.set_sfx_enabled(self.settings.get("sfx_enabled", True))
        self.sound_mgr.set_bgm_volume(self.settings.get("bgm_volume", 60) / 100.0)
        self.sound_mgr.set_sfx_volume(self.settings.get("sfx_volume", 70) / 100.0)
        self.sound_mgr.set_warn_scale(self.settings.get("warn_volume", 100) / 100.0)
        
        self.net_mgr = NetworkManager()
        try:
            pygame.key.stop_text_input()         # 입력칸을 열기 전에는 IME를 꺼 둠 (한글 모드에서 조작키가 조합으로 먹히는 것 방지)
        except Exception:
            pass
        self.renderer = UIRenderer(self.screen)
        self.renderer.mini_detailed = self.settings.get("mini_detail", "focus") != "simple"
        self.renderer.mini_focus = self.settings.get("mini_detail", "focus") == "focus"
        self.apply_visual_options()
        self.menu_bg = NeonMenuBackground(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.menu_bg.renderer = self.renderer
        self.logo = Logo(self.renderer, "malgungothic,segoeui,arial")
        
        # 키 반복 입력 (DAS: 160ms 후 40ms 간격으로 반복)
        # 토너먼트 규격 DAS / ARR 키 조작 시스템
        self.key_left_down = False
        self.key_right_down = False
        self.key_down_down = False
        self.h_dir = 0                  # 현재 유효한 좌우 방향 (-1/0/+1). 나중에 누른 키 우선
        self.das_timer = 0.0
        self.arr_timer = 0.0
        self.soft_drop_timer = 0.0
        self.ARR_INSTANT = False        # ARR 0(즉시 이동) 여부 (apply_handling이 설정)
        self.DAS_DELAY = 0.135          # 초기 지연 (설정의 조작키 탭에서 조절: apply_handling)
        self.ARR_INTERVAL = 0.033       # 연속 반복 간격
        self.SOFT_DROP_INTERVAL = 0.035 # 소프트 드롭 간격
        self.apply_handling()           # 저장된 DAS/ARR/소프트드롭 값 적용
        
        # 폰트
        font_name = "malgungothic,segoeui,arial"
        self.font_title = HiFont(font_name, 44, bold=True)
        self.font_menu = HiFont(font_name, 22, bold=True)
        self.font_mid = HiFont(font_name, 18, bold=True)
        self.font_info = HiFont(font_name, 16, bold=False)
        self.font_small = HiFont(font_name, 13, bold=True)
        self.font_tiny = HiFont(font_name, 12, bold=False)
        self.font_hero = HiFont(font_name, 26, bold=True)     # 메인 메뉴: 주 카드 제목
        self.font_row = HiFont(font_name, 17, bold=True)      # 설정 화면: 행 이름
        self.font_val = HiFont(font_name, 15, bold=True)      # 설정 화면: 컨트롤 값
        self.font_help = HiFont(font_name, 14, bold=False)    # 설정 화면: 도움말/보조 줄
        self.font_sec = HiFont(font_name, 13, bold=True)      # 설정 화면: 섹션 제목
        self.font_input = HiFont("consolas", 22, bold=True)
        self._menu_font_base = {n: getattr(self, n).size_pt for n in ("font_small", "font_tiny", "font_help", "font_sec", "font_info")}
        
        # 상태 관리: 'MENU', 'SETTINGS', 'RECORDS', 'HOST_LOBBY', 'JOIN_MENU', 'CLIENT_LOBBY', 'GAME'
        self.state = "MENU"
        self.rules_open = False             # F1 규칙 요약 카드가 열려 있는가
        self.previous_state = "MENU"
        self.is_paused = False
        
        # 전적 및 설정 탭 관리
        self.stats_mgr = StatsManager()
        self._apply_first_run_defaults()
        self.match_recorded = False
        self.match_start_time = 0.0
        self.records_buttons = {}
        self.settings_focus = {"match": 0, "general": 0, "audio": 0, "keys": 0}      # 설정 화면 키보드 탐색 위치
        self._kb_nav = False             # 설정 화면에서 키보드로 탐색 중인지 (포커스 표시용)
        self._row_rects = {}
        self._quit_confirmed = False
        self._pending_quit = False
        self.records_scroll = 0          # 전적 기록실 목록 스크롤 (행 단위)
        self.records_mode = "battle"     # 전적 기록실에서 보는 모드: battle(배틀로얄) / survival(서바이벌)
        self.records_size = None         # 전적 기록실 필터: 인원 규모 (None=전체 / "small" / "mid" / "large")
        self.records_diff = None         # 전적 기록실 필터: 봇 난이도 (None=전체 / "mixed" / "easy" / ...)
        self.records_max_scroll = 0
        self._hard_drop_pending = False
        self._last_lock_events = 0
        self._last_garbage_rows = 0
        self._was_touching = False
        self._land_cooldown = 0.0
        self.text_focus = None            # 글자 입력 중인 칸: None / "chat" / "room_name"
        self.chat_input = ""
        self.chat_comp = ""                # IME 조합 중인 글자 (한글)
        self.room_name_input = self.settings.get("room_name", "") or ""
        self.player_name_input = ""       # 이름 입력 중인 글자
        try:
            self.name_color = max(0, min(len(NAME_COLORS) - 1, int(self.settings.get("name_color", 0))))
        except (TypeError, ValueError):
            self.name_color = 0
        self.net_mgr.my_color = self.name_color
        self.color_rects = []             # 이름 색 선택 칸 (화면 그릴 때 갱신)
        self.text_rects = {}              # 클릭으로 입력 시작할 수 있는 칸 (화면 그릴 때 갱신)
        self.modal = None                 # 확인/알림 창 {title, lines, buttons, rects}
        self._notice_shown = False        # 호스트 종료 알림을 이미 띄웠는지
        self.result_lock_until = 0.0      # 탈락/종료 직후 실수로 결과 화면을 닫지 않도록 잠시 입력 무시
        self.menu_focus = 0             # 메인 메뉴 포커스 위치 (MENU_FOCUS_ORDER 인덱스; 키보드/마우스 공용)
        self._menu_hl = {}              # 메뉴 항목별 강조 정도 (0~1, 부드럽게 전환)
        self._menu_press = None         # 마우스로 누르고 있는 메뉴 항목
        self._menu_kb = False           # 키보드로 탐색 중인지 (포커스 링 표시용)
        self._menu_flash = 0.0          # 인원/난이도가 바뀐 시각 (숫자 강조용)
        self._menu_active = False       # 메뉴 화면이 활성 상태인지 (들어올 때 등장 연출 재시작용)
        self._menu_intro_t = 0.0
        self.settings_tab = "match"     # "match"(게임 설정) / "general"(화면·소리) / "keys"(조작키)
        self.rebinding_action = None    # 키 리바인딩 대기 중인 액션
        
        # UI 마우스 버튼 인터랙션 관리용 딕셔너리
        self.menu_buttons = {}
        self.lobby_buttons = {}
        self.settings_buttons = {}
        
        # 매치 설정
        self.target_player_count = self.settings.get("target_player_count", 100)
        self.bot_difficulty = self.settings.get("bot_difficulty", "mixed")
        self.player_name = (self.settings.get("player_name", "") or "").strip()[:16] or "Player_1"
        self.host_port = DEFAULT_UDP_PORT
        self.join_ip_input = self.settings.get("last_host", "") or ""
        self.active_input_field = "ip"
        
        self.match = None
        self.last_sync_time = 0.0
        
        # 자동 LAN 검색 시작
        self.net_mgr.start_discovery_listener()
        
        # 로컬 IP 확인
        self.local_ip = self._get_local_ip()
        
        # 승리/패배 효과음 1회 재생 제어 플래그 (중복 루프 방지)
        self.victory_played = False
        self.gameover_played = False

        # 오프닝 / 타이틀 화면 BGM 즉시 재생
        self.sound_mgr.play_menu_bgm()

    MAX_FRAME_DT = 0.1                   # 한 프레임으로 처리할 최대 시간(초): 멈췄다 돌아와도 블록이 한 번에 떨어지지 않게
    LONG_FRAME_PAUSE = 0.5               # 이 이상 멈췄다면 솔로 경기는 자동 일시정지

    def _on_long_frame(self, raw_dt):
        self.key_left_down = self.key_right_down = self.key_down_down = False
        self.h_dir = 0
        if (raw_dt >= self.LONG_FRAME_PAUSE and self.state == "GAME" and self.match is not None
                and self.net_mgr.mode == "NONE" and not self.is_paused
                and self.match.local_is_alive and not self.match.match_finished):
            self.is_paused = True
            self.match.is_paused = True
            self.renderer.pause_focus = 0
            self.sound_mgr.pause_bgm()

    def run(self):
        self.use_bot_pool = True                 # 실제 실행에서만 봇 계산 작업 프로세스를 사용 (테스트/시뮬레이션은 직접 계산)
        running = True
        while running:
            raw_dt = self.clock.tick(FPS) / 1000.0
            if raw_dt > self.MAX_FRAME_DT:
                self._on_long_frame(raw_dt)              # 창 드래그/크기 조절로 루프가 멈췄다 돌아온 경우
            dt = min(raw_dt, self.MAX_FRAME_DT)
            self.sound_mgr.tick()
            
            # 이벤트 처리
            for event in pygame.event.get():
                # 마우스 좌표를 논리 좌표(1366x768)로 변환 / 창 크기 변경 시 배율 재계산
                if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
                    event.pos = CANVAS.to_logical(event.pos)
                elif event.type in (pygame.VIDEORESIZE, getattr(pygame, "WINDOWRESIZED", -1),
                                    getattr(pygame, "WINDOWSIZECHANGED", -1)):
                    if pygame.display.get_surface() is not None:
                        CANVAS.attach(pygame.display.get_surface())
                if event.type == pygame.QUIT:
                    if self._quit_confirmed:
                        running = False
                    elif self.modal is None:
                        self._confirm_quit_app()                 # 창 X 버튼도 바로 끄지 않고 확인
                    elif not any(b[0] == "quit_app" for b in self.modal["buttons"]):
                        self._pending_quit = True                # 떠 있는 다른 알림 창을 덮어쓰지 않고, 닫은 뒤에 종료 확인
                elif self.rules_open and event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    self._handle_rules_event(event)
                elif self.rules_open and event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL):
                    pass
                elif self.modal is not None and event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    self._handle_modal_event(event)
                elif self.modal is not None and event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL):
                    pass                                         # 알림 창이 떠 있는 동안 아래 화면의 호버/포커스가 바뀌지 않게 함
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                    self.toggle_fullscreen()
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_m and self.state != "JOIN_MENU" and self.text_focus is None and self.rebinding_action is None:
                    self.toggle_mute()
                else:
                    self._handle_event(event)
                    
            if self.net_mgr.mode == "CLIENT":
                self.net_mgr.client_keepalive()          # 어떤 화면에서도 호스트에게 생존 신호 전송

            if self.state != "MENU":
                self._menu_active = False               # 다음에 메뉴로 돌아오면 등장 연출을 다시 재생

            # 상태별 업데이트 및 렌더링
            if self.state == "MENU":
                self.sound_mgr.play_bgm('menu')
                self._update_menu(dt)
                self._render_menu()
            elif self.state == "SETTINGS":
                if self.previous_state == "GAME" and self.match is not None and self.net_mgr.mode != "NONE":
                    self._update_game(dt)              # 네트워크 게임은 설정 중에도 계속 진행 (호스트 시뮬레이션/동기화 유지)
                self._update_settings(dt)
                if self.state == "SETTINGS":
                    self._render_settings()
            elif self.state == "RECORDS":
                self._update_records(dt)
                self._render_records()
            elif self.state == "HOST_LOBBY":
                self.sound_mgr.play_bgm('lobby')
                self._update_host_lobby(dt)
                self._render_host_lobby()
            elif self.state == "JOIN_MENU":
                self.sound_mgr.play_bgm('lobby')
                self._update_join_menu(dt)
                self._render_join_menu()
            elif self.state == "CLIENT_LOBBY":
                self.sound_mgr.play_bgm('lobby')
                self._update_client_lobby(dt)
                self._render_client_lobby()
            elif self.state == "GAME":
                self._tick_game(dt)
                
            if self.modal is not None:
                self._render_modal()
            if self.rules_open:
                self._render_rules()
            pygame.display.flip()
            
        self.settings.save()
        self.net_mgr.stop()
        bot_pool.stop()
        pygame.quit()
        sys.exit()

    def _apply_first_run_defaults(self):
        """처음 설치한 사람: 100인 혼합 난이도(가장 어려운 쪽)로 바로 던지지 않고 50인 쉬움 봇으로 시작 (난이도 사다리 1단계와 같은 규모). 이미 전적이 있으면 설정은 그대로 둠"""
        if self.settings.get("onboard_done"):
            return
        if (self.stats_mgr.data.get("total_games", 0) == 0
                and self.stats_mgr.data.get("survival", {}).get("total_games", 0) == 0):
            self.settings.set("target_player_count", 50, autosave=False)
            self.settings.set("bot_difficulty", "easy", autosave=False)
        self.settings.set("onboard_done", True, autosave=False)

    def _handle_event(self, event):
        if (event.type == pygame.KEYDOWN and event.key == pygame.K_F1 and self.text_focus is None
                and self.rebinding_action is None and self.state != "JOIN_MENU"):
            self._open_rules()                                   # F1: 규칙 요약 카드 (어느 화면에서든)
            return
        if self._text_input_event(event):
            return
        if self.state == "SETTINGS":
            self._handle_settings_event(event)
            return
        elif self.state == "RECORDS":
            self._handle_records_event(event)
            return

        elif self.state == "MENU":
            self._handle_menu_event(event)

        elif self.state == "HOST_LOBBY":
            self._handle_host_lobby_event(event)

        elif self.state == "JOIN_MENU":
            self._handle_join_menu_event(event)

        elif self.state == "CLIENT_LOBBY":
            self._handle_client_lobby_event(event)

        elif self.state == "GAME":
            self._handle_game_event(event)


def _selftest_pool():
    """봇 계산 작업 프로세스가 (exe 안에서도) 뜨고, 직접 계산과 같은 결과를 내는지 확인"""
    import time
    import bot_brain
    from block_engine import BlockEngine
    bot_pool.start(2)
    if not bot_pool.wait_ready(25.0):
        bot_pool.stop()
        return "FAILED(workers not ready)"
    e = BlockEngine(seed=5)
    args = (bot_brain.rows_from_grid(e.grid), e.current_piece, e.hold_piece, list(e.next_queue[:5]), True, -1, False, 0, 2, 3, True, True)
    rid = bot_pool.submit(*args, dict(bot_brain.PARAMS))
    got = None
    t0 = time.time()
    while got is None and time.time() - t0 < 10:
        bot_pool.pump()
        got = bot_pool.take(rid)
        time.sleep(0.01)
    want = bot_brain.plan_rows(*args)[:6]
    workers = bot_pool.ready_workers()
    bot_pool.stop()
    return ("OK(%d workers)" % workers) if got == want else "FAILED(result mismatch)"


def _selftest():
    """--selftest: 창 없이(SDL dummy) 초기화, 메뉴/게임 렌더링, 저장 경로를 점검하고 종료 (빌드된 exe 검증용)"""
    app = BlockRoyaleApp()
    for _ in range(30):
        app.menu_bg.update(1 / 60)
        app._render_menu()
    app.start_game(mode="SOLO", total_players=20)
    for _ in range(120):
        app._update_game(1 / 60)
        app.renderer.key_hints = app._build_key_hints()
        app.renderer.render(app.match, app.sound_mgr)
    pool_note = _selftest_pool()
    if app.sound_mgr._bgm_thread is not None:
        app.sound_mgr._bgm_thread.join(timeout=15.0)     # BGM 합성이 끝난 뒤의 정확한 수를 남김 (빌드 검증용)
    from settings_manager import SETTINGS_FILE
    from stats_manager import STATS_FILE
    msg = ("SELFTEST OK | settings: %s | stats: %s | sounds: %d | bgm: %d | frozen: %s | botpool: %s"
           % (SETTINGS_FILE, STATS_FILE, len(app.sound_mgr.sounds), len(app.sound_mgr.bgm_stages),
              bool(getattr(sys, "frozen", False)), pool_note))
    print(msg)
    try:                                   # 콘솔이 없는 exe에서도 결과를 확인할 수 있도록 파일로도 기록
        from app_paths import data_path
        with open(data_path("selftest.log"), "w", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    import crash_log
    if "--version" in sys.argv:
        print(f"BLOCK ROYALE 100 v{APP_VERSION}")
        sys.exit(0)
    crash_log.install()
    if "--selftest" in sys.argv:
        _selftest()
        pygame.quit()
        sys.exit(0)
    try:
        app = BlockRoyaleApp()
        app.run()
    except Exception:
        import traceback
        text = traceback.format_exc()
        crash_log.write_error("Fatal error in main loop", text)      # 오류 원인을 파일에 남기고 안내 후 종료
        crash_log.show_fatal_message(text)
        sys.exit(1)

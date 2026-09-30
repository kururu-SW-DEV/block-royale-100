"""
Block Royale 100 - 창/해상도/게임 시작·종료 등 앱 공통 동작
BlockRoyaleApp(main.py)이 상속하는 믹스인: 메서드 본문은 원래 main.py에 있던 그대로이며 self로 앱 상태를 공유함
"""

from app_common import (
    BattleRoyaleMatch, CANVAS, MAX_PLAYERS, MIN_PLAYERS, RESOLUTION_OPTIONS,
    SCREEN_HEIGHT, SCREEN_WIDTH, pygame, short_key_name, socket, time
)
import bot_pool
from config import bot_display_name


class CoreMixin:
    def apply_visual_options(self):
        """설정의 색상 모드(기본/색약 보정)와 게임 화면 글자 크기를 적용"""
        from config import apply_color_mode
        apply_color_mode(self.settings.get("color_mode"))
        self.renderer.block_skin = self.settings.get("block_skin")
        self.renderer.set_text_boost(2 if self.settings.get("text_size") == "large" else 0)
        self.renderer.clear_visual_caches()                     # 색이 바뀐 블록/패널 캐시를 비워 새 색으로 다시 만들게 함

    def apply_gameplay_options(self):
        """진행 중인 경기에 설정(화면 흔들림 배율)을 반영. 조준 모드는 경기 시작 때와 모드를 바꿀 때만 저장/복원"""
        from app_common import SHAKE_SCALE
        if self.match is not None:
            self.match.shake_scale = SHAKE_SCALE.get(self.settings.get("screen_shake"), 1.0)

    def apply_handling(self):
        """설정의 DAS/ARR/소프트드롭(ms)을 실제 입력 처리에 반영"""
        self.DAS_DELAY = self.settings.get("das_ms") / 1000.0
        self.ARR_INSTANT = self.settings.get("arr_ms") <= 0                            # ARR 0: 자동 반복이 시작되면 벽/블록에 닿을 때까지 한 번에 이동
        self.ARR_INTERVAL = max(0.005, self.settings.get("arr_ms") / 1000.0)          # 0으로 나누지 않도록 반복 루프용 값은 최소 5ms
        self.SOFT_DROP_INTERVAL = max(0.005, self.settings.get("sdf_ms") / 1000.0)

    def adjust_player_count(self, delta):
        self.target_player_count = max(MIN_PLAYERS, min(MAX_PLAYERS, self.target_player_count + delta))
        self.settings.set("target_player_count", self.target_player_count)

    def _host_start_game_action(self):
        players_summary = [
            {"id": "HOST_P1", "name": self.player_name, "is_ai": False}
        ]
        for addr, cinfo in list(self.net_mgr.clients.items()):
            players_summary.append({"id": cinfo["id"], "name": cinfo["name"], "is_ai": False})
        
        bot_num = 1
        while len(players_summary) < self.target_player_count:
            bid = f"BOT_{bot_num:02d}"
            bname = bot_display_name(bot_num)
            players_summary.append({"id": bid, "name": bname, "is_ai": True})
            bot_num += 1
            
        self.net_mgr.host_send_start_game(players_summary, attacks_enabled=self.settings.get("game_mode") != "survival")
        self.start_game(mode="HOST", total_players=self.target_player_count, initial_players=players_summary)

    def _target_window_size(self):
        """설정된 해상도를 모니터 크기 안에 들어가도록(16:9 유지) 보정한 창 크기"""
        try:
            dw, dh = pygame.display.get_desktop_sizes()[0]
        except Exception:
            dw, dh = 1920, 1080
        max_w, max_h = dw - 40, dh - 100      # 작업표시줄/타이틀바 여유
        choice = self.settings.get("resolution", "auto")
        if choice in RESOLUTION_OPTIONS and choice != "auto":
            w, h = (int(v) for v in choice.split("x"))
            scale = min(1.0, max_w / w, max_h / h)          # 모니터보다 크면 16:9 유지하며 축소
        else:
            w, h = SCREEN_WIDTH, SCREEN_HEIGHT
            scale = min(max_w / w, max_h / h)                # 자동: 모니터에 꽉 차는 최대 크기
        w, h = int(w * scale), int(h * scale)
        return max(640, w), max(360, h), dw, dh

    def _create_window(self):
        """현재 설정(전체화면 / 창 해상도)에 맞춰 디스플레이를 (재)생성하고 CANVAS에 연결"""
        if self.is_fullscreen:
            surf = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            w, h, dw, dh = self._target_window_size()
            surf = pygame.display.set_mode((w, h), pygame.RESIZABLE)
            try:
                from pygame import _sdl2
                win = _sdl2.video.Window.from_display_module()
                win.position = (max(0, (dw - w) // 2), max(0, (dh - h) // 2 - 20))
            except Exception:
                pass
        CANVAS.attach(surf)
        self.screen = CANVAS

    def _apply_window_size(self):
        """창 모드에서 설정된 해상도로 창 크기를 변경"""
        self._create_window()

    def _available_resolutions(self):
        """현재 모니터의 창 모드에 들어가는 해상도만 선택지로 제공 (더 큰 해상도는 전체 화면이 담당)"""
        try:
            dw, dh = pygame.display.get_desktop_sizes()[0]
        except Exception:
            dw, dh = 1920, 1080
        return [r for r in RESOLUTION_OPTIONS
                if r == "auto" or (int(r.split("x")[0]) <= dw - 40 and int(r.split("x")[1]) <= dh - 100)]

    def change_resolution(self, step):
        new = self.settings.cycle_resolution(step, self._available_resolutions())
        if not self.is_fullscreen:
            self._apply_window_size()
        return new

    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        self.settings.set("fullscreen", self.is_fullscreen)
        self._create_window()

    def toggle_mute(self):
        self.sound_mgr.toggle_sound()

    def return_to_menu(self):
        self.settings.save()                     # 경기 중 바꾼 조준 모드 등 (조작 중에는 저장하지 않고 여기서 한 번에)
        self.victory_played = False
        self.gameover_played = False
        self.key_left_down = False
        self.key_right_down = False
        self.key_down_down = False
        self.h_dir = 0
        self.das_timer = 0.0
        self.arr_timer = 0.0
        self.soft_drop_timer = 0.0
        self.sound_mgr.play_menu_bgm()
        self.logo.restart(fast=True)
        self._end_text(commit=False)
        self.net_mgr.stop()
        self.match = None
        self.is_paused = False
        self.modal = None
        self._notice_shown = False
        self.state = "MENU"

    def _build_key_hints(self):
        """인게임 하단 조작 안내 바에 표시할 (동작, 키) 목록 (현재 키 설정 반영)"""
        def keys(action, limit=2):
            return "/".join(short_key_name(k) for k in self.settings.get_action_keys(action)[:limit])
        hints = [
            (keys("move_left", 1) + " " + keys("move_right", 1), "이동"),
            (keys("rotate_cw") , "회전"),
            (keys("rotate_ccw", 1), "역회전"),
            (keys("soft_drop", 1), "소프트"),
            (keys("hard_drop", 1), "하드드롭"),
            (keys("hold"), "홀드"),
            (keys("target_cycle", 1), "조준"),
            ("1~5", "조준모드"),
        ]
        if self.match is not None and not self.match.attacks_enabled:
            hints = [h for h in hints if h[1] not in ("조준", "조준모드")]      # 서바이벌: 조준 개념 없음
        if self.match is not None and self.match.practice:
            hints += [("G/Shift+G", "쓰레기 4/8줄"), ("B", "초기화")]        # 항목이 10개를 넘으면 안내 바가 3줄이 되어 화면 아래로 잘림
        if self.net_mgr.mode == "NONE":
            hints.append((keys("pause", 1), "일시정지"))
        hints.append(("T", "설정"))
        return hints

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def start_game(self, mode="SOLO", total_players=100, initial_players=None, practice=False, daily=None):
        """practice=True: 연습 모드(혼자, 전적 없음). daily="YYYYMMDD": 오늘의 도전(같은 날은 같은 블록 순서/상대 구성, 100인 혼합 난이도 배틀로얄)"""
        self._end_text(commit=False)
        self.renderer.reset_standings()
        self._finish_lock_set = False
        self._defeat_played = False
        self.net_mgr.lobby_return = False
        my_id = "HOST_P1" if mode == "HOST" else ("NET_P" if mode == "CLIENT" else "LOCAL_P1")
        if mode == "CLIENT" and self.net_mgr.my_player_id:
            my_id = self.net_mgr.my_player_id
            
        self.is_paused = False
        self.victory_played = False
        self.gameover_played = False
        self.match_recorded = False
        self._hard_drop_pending = False
        self._last_lock_events = 0
        self._last_garbage_rows = 0
        self._was_touching = False
        self.match_start_time = time.time()
        self.key_left_down = False
        self.key_right_down = False
        self.key_down_down = False
        self.h_dir = 0
        self.das_timer = 0.0
        self.arr_timer = 0.0
        self.soft_drop_timer = 0.0
        seed = int(daily) if daily else None
        self.match = BattleRoyaleMatch(
            total_players=2 if practice else (100 if daily else total_players),
            local_player_id=my_id,
            local_player_name=self.player_name,
            net_mgr=self.net_mgr if mode in ["HOST", "CLIENT"] else None,
            initial_players=initial_players,
            sound_mgr=self.sound_mgr,
            bot_difficulty="mixed" if daily else self.bot_difficulty,
            # 게임 모드: 참가자는 호스트가 정한 값을 따르고, 그 외에는 내 설정을 씀 (오늘의 도전은 항상 배틀로얄)
            attacks_enabled=True if daily else (self.net_mgr.match_attacks if mode == "CLIENT" else self.settings.get("game_mode") != "survival"),
            practice=practice, seed=seed, daily=daily
        )
        self.match.local_color = self.name_color
        self.match.set_target_mode(self.settings.get("target_mode"))        # 마지막으로 쓴 조준 모드를 이어서 사용
        if not practice and not self.settings.get("coach_done"):                             # 처음 하는 경기: HUD 핵심 3곳을 15초 동안 설명 (한 번만)
            self.match.coach_until = time.time() + 15.0
            self.settings.set("coach_done", True)
        self.apply_gameplay_options()
        if getattr(self, "use_bot_pool", False) and mode != "CLIENT":
            bot_pool.start()                       # 봇 계산을 여러 CPU 코어에 나눠 맡김 (준비될 때까지는 직접 계산)
        self.renderer.last_cleared_count = 0
        self.renderer.particles.particles.clear()
        self.renderer.particles.rings.clear()
        self.state = "GAME"
        self.sound_mgr.roll_stage_set(self.settings.get("bgm_stage_set", "random"))
        self.sound_mgr.play_bgm(stage=1)
        print(f"[Game] Started match with {total_players} players! (Mode: {mode})")

    def _restart_after_match(self):
        """경기 종료 후 '재도전': 솔로는 새 게임, 네트워크는 같은 방의 대기실로 복귀 (경기 중 탈락 상태에서는 무시)"""
        if self.net_mgr.mode == "NONE":
            self.start_game(mode="SOLO", total_players=self.target_player_count)
        elif self.match is not None and self.match.match_finished:
            self._return_to_lobby()

    def _return_to_lobby(self):
        """네트워크 경기 종료 후 대기실로: 호스트는 방을 다시 열고(참가자 유지), 참가자는 호스트의 다음 시작을 기다림"""
        nm = self.net_mgr
        self._end_text(commit=False)
        self.match = None
        self.is_paused = False
        self.modal = None
        self._notice_shown = False
        self.key_left_down = self.key_right_down = self.key_down_down = False
        self.h_dir = 0
        self.sound_mgr.play_menu_bgm()
        self.logo.restart(fast=True)
        if nm.mode == "HOST":
            nm.host_reopen_room()
            self.state = "HOST_LOBBY"
        elif nm.mode == "CLIENT":
            nm.lobby_return = False
            nm.game_started = False
            nm.initial_players = []
            nm.remote_players_state.clear()
            nm.remote_details.clear()
            nm.incoming_attacks.clear()
            self.state = "CLIENT_LOBBY"
        else:
            self.state = "MENU"

    def _play_lock_feedback(self, dt):
        """블록 착지 / 고정 / 쓰레기 상승 효과음 (하드 드롭은 묵직하게, 자연 고정은 '탁')"""
        e = self.match.local_engine
        self._land_cooldown = max(0.0, self._land_cooldown - dt)

        if e.lock_events != self._last_lock_events:
            self._last_lock_events = e.lock_events
            cleared = (e.last_clear_info or {}).get('cleared', 0)
            if self._hard_drop_pending:
                self.sound_mgr.play('drop')
            if cleared == 0:
                self.sound_mgr.play('lock', piece=e.last_locked_piece)
            self._hard_drop_pending = False
            self._was_touching = False
        if e.garbage_pushed_total != self._last_garbage_rows:
            self._last_garbage_rows = e.garbage_pushed_total
            self.sound_mgr.play('rise')

        touching = (not e.game_over) and e._is_touching_ground()
        if touching and not self._was_touching and self._land_cooldown <= 0.0 and self.match.local_is_alive:
            self.sound_mgr.play('land', piece=e.current_piece)
            self._land_cooldown = 0.12
        self._was_touching = touching

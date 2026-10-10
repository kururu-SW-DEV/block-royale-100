"""
Block Royale 100 - 창/해상도/게임 시작·종료 등 앱 공통 동작
BlockRoyaleApp(main.py)이 상속하는 믹스인: 메서드 본문은 원래 main.py에 있던 그대로이며 self로 앱 상태를 공유함
"""

import sys

from app_common import (
    BattleRoyaleMatch, CANVAS, MAX_PLAYERS, MIN_PLAYERS, RESOLUTION_OPTIONS,
    SCREEN_HEIGHT, SCREEN_WIDTH, pygame, short_key_name, socket, time
)
import bot_pool
from app_paths import running_under_wine
from config import bot_display_name


class CoreMixin:
    def apply_visual_options(self):
        """설정의 색상 모드(기본/색약 보정)와 게임 화면 글자 크기를 적용"""
        from config import apply_color_mode
        apply_color_mode(self.settings.get("color_mode"))
        from stats_manager import unlocked_skin_ids
        skin = self.settings.get("block_skin")
        stats = getattr(self, "stats_mgr", None)                  # 앱 초기화 중에는 전적이 아직 없을 수 있음
        self.renderer.block_skin = skin if (stats is None or skin in unlocked_skin_ids(stats.data)) else "crown"      # 잠긴 스킨(전적 초기화 등)은 기본으로
        self.renderer.skyline = bool(self.settings.get("board_skyline", False))      # 지형 윤곽선 (기본 꺼짐)
        boost = 2 if self.settings.get("text_size") == "large" else 0
        self.renderer.set_text_boost(boost)
        for name, base in getattr(self, "_menu_font_base", {}).items():       # 메뉴/설정/로비의 작은 글씨도 같이 키움
            getattr(self, name).size_pt = base + boost
        self.renderer.clear_visual_caches()                     # 색이 바뀐 블록/패널 캐시를 비워 새 색으로 다시 만들게 함

    def _save_screenshot(self):
        """현재 화면을 저장 폴더의 screenshots/ 에 PNG로 저장하고 잠깐 알림 (실패해도 게임은 계속)"""
        import datetime
        import os
        from app_paths import data_path
        try:
            folder = data_path("screenshots")
            os.makedirs(folder, exist_ok=True)
            name = datetime.datetime.now().strftime("BlockRoyale_%Y%m%d_%H%M%S.png")
            pygame.image.save(pygame.display.get_surface(), os.path.join(folder, name))
            self._shot_msg = (f"스크린샷 저장: {name}", time.time() + 2.6)
            self.sound_mgr.play('move')
        except Exception:
            self._shot_msg = ("스크린샷을 저장하지 못했어요", time.time() + 2.6)

    def _draw_shot_msg(self):
        msg = getattr(self, "_shot_msg", None)
        if not msg or time.time() > msg[1]:
            return
        r = self.renderer
        text = msg[0]
        w = r.font_small.size(text if text.startswith("스크린샷을") else f"스크린샷 저장: {text.split(': ', 1)[-1]}")[0] + 32
        rect = pygame.Rect(0, 0, min(w, 600), 34)
        rect.midbottom = (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 62)
        CANVAS.alpha_rect(rect, (10, 13, 24, 225), radius=10)
        CANVAS.alpha_rect(rect, (110, 200, 255, 200), width=1, radius=10)
        r._draw_text(text, r.font_small, (225, 235, 255), rect.centerx, rect.centery, "center")

    def _card_pan(self, pid):
        """플레이어 카드가 화면 가로 어디에 있는지 -1(왼쪽)~1(오른쪽). 카드가 안 보이면 None"""
        rect = self.renderer.mini_board_rects.get(pid)
        if rect is None:
            return None
        return max(-1.0, min(1.0, (rect.centerx / float(SCREEN_WIDTH)) * 2.0 - 1.0))

    def apply_gameplay_options(self):
        """진행 중인 경기에 설정(화면 흔들림 배율)을 반영. 조준 모드는 경기 시작 때와 모드를 바꿀 때만 저장/복원"""
        from app_common import SHAKE_SCALE, RUMBLE_SCALE
        if self.match is not None:
            from stats_manager import orb_theme_for_level
            self.renderer.orb_theme = orb_theme_for_level(self.stats_mgr.level()[0])            # 레벨 보상: K.O. 구슬 색
            from stats_manager import border_perk_for_level
            self.renderer.border_perk = border_perk_for_level(self.stats_mgr.level()[0])        # 레벨 보상: 내 보드 테두리 장식
            self.match.rumble_cb = lambda power, kind="hit": self.gamepad.rumble(power, kind) if self._pad_hints_active() else None      # 마지막으로 패드를 쓴 경우에만 진동 (키보드로 하는 중에는 연결된 패드가 울리지 않게)
            self.match.shake_scale = SHAKE_SCALE.get(self.settings.get("screen_shake"), 1.0)
            self.match.pan_fn = self._card_pan
            self.match.visual_fx = self.settings.get("visual_fx", "normal")                      # 빛 연출 단계 (ui_glow)
            self.match.rumble_scale = RUMBLE_SCALE.get(self.settings.get("pad_rumble"), 1.0)      # 패드 진동은 흔들림 설정과 따로
            self.match.flash_enabled = bool(self.settings.get("screen_flash", True))      # 번쩍임은 흔들림과 별개로 켜고 끔

    def apply_handling(self):
        """설정의 DAS/ARR/소프트드롭(ms)을 실제 입력 처리에 반영"""
        self.DAS_DELAY = self.settings.get("das_ms") / 1000.0
        self.ARR_INSTANT = self.settings.get("arr_ms") <= 0                            # ARR 0: 자동 반복이 시작되면 벽/블록에 닿을 때까지 한 번에 이동
        self.ARR_INTERVAL = max(0.005, self.settings.get("arr_ms") / 1000.0)          # 0으로 나누지 않도록 반복 루프용 값은 최소 5ms
        self.SOFT_DROP_INTERVAL = max(0.005, self.settings.get("sdf_ms") / 1000.0)
        self.SOFT_DROP_INSTANT = self.settings.get("sdf_ms") <= 0                      # 소프트드롭 0: 키를 누르는 동안 바닥까지 즉시 내림 (고정은 락 딜레이를 따름)
        self.DCD_DELAY = self.settings.get("dcd_ms") / 1000.0
        self.DAS_CANCEL = bool(self.settings.get("das_cancel"))

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
            
        battle = self.settings.get("game_mode") != "survival"
        self.net_mgr.host_send_start_game(players_summary, attacks_enabled=battle,
                                          team=bool(self.settings.get("rule_team", False)) and battle and self.target_player_count >= 4)
        self.start_game(mode="HOST", total_players=max(self.target_player_count, len(players_summary)), initial_players=players_summary)

    @staticmethod
    def _work_area():
        """(x, y, w, h, 창 장식 여백 w, h): Windows 작업 영역(작업표시줄 제외)과 제목줄/테두리 크기. 알 수 없으면 None"""
        if sys.platform != "win32":
            return None
        try:
            import ctypes
            from ctypes import wintypes
            rc = wintypes.RECT()
            if not ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rc), 0):      # SPI_GETWORKAREA
                return None
            gm = ctypes.windll.user32.GetSystemMetrics
            border = (gm(33) + gm(92)) * 2                       # SM_CYSIZEFRAME + SM_CXPADDEDBORDER (DPI 배율 반영된 값)
            return rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top, border, gm(4) + border
        except Exception:
            return None

    def _usable_area(self):
        """창이 들어갈 수 있는 최대 크기와 작업 영역 (x, y, w, h)"""
        wa = self._work_area()
        if wa and wa[2] > 0 and wa[3] > 0:
            x, y, w, h, bw, bh = wa
            return max(640, w - bw), max(360, h - bh), (x, y, w, h)
        try:
            dw, dh = pygame.display.get_desktop_sizes()[0]
        except Exception:
            dw, dh = 1920, 1080
        return dw - 40, dh - 100, (0, 0, dw, dh)                  # 작업표시줄/타이틀바 여유(추정)

    def _target_window_size(self):
        """설정된 해상도를 모니터 크기 안에 들어가도록(16:9 유지) 보정한 창 크기"""
        max_w, max_h, (ax, ay, dw, dh) = self._usable_area()
        choice = self.settings.get("resolution", "auto")
        if choice in RESOLUTION_OPTIONS and choice != "auto":
            w, h = (int(v) for v in choice.split("x"))
            scale = min(1.0, max_w / w, max_h / h)          # 모니터보다 크면 16:9 유지하며 축소
        else:
            w, h = SCREEN_WIDTH, SCREEN_HEIGHT
            scale = min(max_w / w, max_h / h)                # 자동: 모니터에 꽉 차는 최대 크기
        w, h = int(w * scale), int(h * scale)
        return max(640, w), max(360, h), (ax, ay, dw, dh)

    @staticmethod
    def _set_mode_retry(size, flags, fallback=None, tries=3):
        """창 만들기: 실패하면 잠깐 쉬었다가 다시 시도 (SteamOS/Proton에서 게임 시작 직후 화면 시스템이 아직 준비되지 않아 간헐적으로 실패하던 경우 대비).
        끝까지 안 되면 가장 단순한 창으로 한 번 더 (그것도 안 되면 원래 오류를 그대로 냄)"""
        last = None
        for i in range(tries):
            try:
                return pygame.display.set_mode(size, flags)
            except pygame.error as e:
                last = e
                try:
                    import crash_log
                    crash_log.write_error(f"display.set_mode failed (try {i + 1}/{tries}, size={size}, flags={flags})", str(e))
                except Exception:
                    pass
                time.sleep(0.4)
        if fallback is not None:
            return pygame.display.set_mode(*fallback)
        raise last

    def _create_window(self):
        """현재 설정(전체화면 / 창 해상도)에 맞춰 디스플레이를 (재)생성하고 CANVAS에 연결"""
        if self.is_fullscreen and not running_under_wine():
            surf = self._set_mode_retry((0, 0), pygame.FULLSCREEN, fallback=((1366, 768), pygame.RESIZABLE))
        else:
            w, h, (ax, ay, dw, dh) = self._target_window_size()
            surf = self._set_mode_retry((w, h), pygame.RESIZABLE, fallback=((1366, 768), 0))
            try:
                from pygame import _sdl2
                win = _sdl2.video.Window.from_display_module()
                win.minimum_size = (640, 360)                      # 배율 하한(0.25)에 걸려 화면이 잘리는 것 방지
                win.position = (ax + max(0, (dw - w) // 2), ay + max(0, (dh - h) // 2))
            except Exception:
                pass
        CANVAS.attach(surf)
        self.screen = CANVAS

    def _apply_window_size(self):
        """창 모드에서 설정된 해상도로 창 크기를 변경"""
        self._create_window()

    def _available_resolutions(self):
        """현재 모니터의 창 모드에 들어가는 해상도만 선택지로 제공 (더 큰 해상도는 전체 화면이 담당)"""
        max_w, max_h, _ = self._usable_area()
        return [r for r in RESOLUTION_OPTIONS
                if r == "auto" or (int(r.split("x")[0]) <= max_w and int(r.split("x")[1]) <= max_h)]

    def change_resolution(self, step):
        new = self.settings.cycle_resolution(step, self._available_resolutions())
        if not self.is_fullscreen:
            self._apply_window_size()
        return new

    def toggle_fullscreen(self):
        if running_under_wine():
            return                                            # Proton: 전체 화면이면 입력이 막히므로 창 모드로 고정 (게이밍 모드에서는 창이 화면을 가득 채움)
        self.is_fullscreen = not self.is_fullscreen
        self.settings.set("fullscreen", self.is_fullscreen)
        self._create_window()

    def _apply_sound_settings(self):
        """저장된/초기화된 오디오 설정(음악·효과음 켜기와 음량, 경보 음량, 아나운서)을 사운드 매니저에 반영"""
        s, sm = self.settings, self.sound_mgr
        sm.set_bgm_enabled(s.get("bgm_enabled", True))
        sm.set_sfx_enabled(s.get("sfx_enabled", True))
        sm.set_bgm_volume(s.get("bgm_volume", 60) / 100.0)
        sm.set_sfx_volume(s.get("sfx_volume", 70) / 100.0)
        sm.set_warn_scale(s.get("warn_volume", 100) / 100.0)
        sm.set_announcer(s.get("announcer", False))

    def _clear_input_state(self):
        """눌려 있던 방향/소프트드롭 입력 상태를 모두 비움 (화면이 바뀌거나 창/입력 초점이 바뀔 때)"""
        self.key_left_down = self.key_right_down = self.key_down_down = False
        self.h_dir = 0

    def _auto_pause_solo(self, reason=""):
        """혼자 하는 경기가 진행 중이면 일시정지로 만들고 True (네트워크 경기/끝난 경기/탈락 뒤에는 아무것도 하지 않음).
        reason: 자동 일시정지 원인 (pause.log와 진단 정보에 남겨 스팀덱 등에서 원인을 알 수 있게)"""
        m = self.match
        if (self.state == "GAME" and m is not None and self.net_mgr.mode == "NONE" and not self.is_paused
                and not m.match_finished and m.local_is_alive):
            try:
                import crash_log
                crash_log.note_auto_pause(reason or "(사유 없음)", getattr(m, "elapsed", 0.0))
            except Exception:
                pass
            self.is_paused = True
            m.is_paused = True
            self.renderer.pause_focus = 0
            self.sound_mgr.pause_bgm()
            return True
        return False

    def _on_pad_lost(self):
        """마지막 패드가 빠짐 (블루투스 끊김/배터리 방전/케이블): 패드로 하던 솔로 경기는 바로 죽지 않게 일시정지 (키보드로 하던 중이면 그대로)"""
        pad_was_active = self.gamepad.last_pad_t > getattr(self, "_last_kb_t", 0.0)
        if pad_was_active and self._auto_pause_solo("패드 연결 끊김"):
            self.match.add_floating_text("패드 연결이 끊겨 일시정지했습니다", (255, 190, 90), duration=3.0, size=22, category="alert")

    def toggle_mute(self):
        self.sound_mgr.toggle_sound()

    def _request_menu_exit(self):
        """결과/관전 화면에서 메인 메뉴로: 참가자가 있는 방장이 나가면 방이 닫히므로 확인 창을 먼저 띄움"""
        if self.net_mgr.mode == "HOST" and self.net_mgr.clients:
            self._confirm_leave_network_game()
        else:
            self.return_to_menu()

    def return_to_menu(self):
        self.settings.save()                     # 경기 중 바꾼 조준 모드 등 (조작 중에는 저장하지 않고 여기서 한 번에)
        self.victory_played = False
        self.gameover_played = False
        self._clear_input_state()
        self.das_timer = 0.0
        self.arr_timer = 0.0
        self.soft_drop_timer = 0.0
        self.sound_mgr.play_menu_bgm(quick=True)       # 경기에서 나올 때는 이전 곡이 길게 겹치지 않게 짧게 전환
        self.logo.restart(fast=True)
        self._end_text(commit=False)
        self.rebinding_action = None                     # 화면이 바뀌면 키 바인딩 대기/규칙 창을 닫음 (켜진 채 남으면 M/F1 키가 먹통)
        self.rules_open = False
        self._sound_due = []                             # 이전 판 결과 화면에 예약된 효과음(도장/레벨 업)이 새 판 카운트다운이나 메뉴에서 터지지 않게
        self._paused_by_rules = False
        self.net_mgr.stop()
        self.match = None
        self.is_paused = False
        self.modal = None
        self._notice_shown = False
        self.state = "MENU"

    def _pad_hints_active(self):
        """게임 중 하단 키 안내를 패드 버튼으로 보일지: 컨트롤러가 연결돼 있고 패드 입력이 켜져 있으며,
        조작 프리셋이 '게임패드'이거나 가장 최근 입력이 패드(키보드보다 최근)일 때"""
        pad = getattr(self, "gamepad", None)
        if pad is None or not pad.connected() or not self.settings.get("gamepad", True):
            return False
        if self.settings.get("key_preset", "arcade") == "gamepad":
            return True
        return pad.last_pad_t > getattr(self, "_last_kb_t", 0.0)

    def _build_key_hints(self):
        """인게임 하단 조작 안내 바에 표시할 (동작, 키) 목록 (현재 키 설정 반영). 설정이 '끔'(또는 '처음 10판만'인데 이미 익숙함)이면 빈 목록"""
        mode = self.settings.get("key_hints", "always")
        if mode == "off" or (mode == "novice" and self.stats_mgr.data.get("total_games", 0) >= 10):
            return []
        if self._pad_hints_active():
            from gamepad import pad_hint_items
            hints = pad_hint_items(self.settings.get_pad_map())
            if self.match is not None and not self.match.attacks_enabled:
                hints = [h for h in hints if h[1] != "조준"]
            if self.net_mgr.mode != "NONE":
                hints = [h for h in hints if h[1] != "일시정지"]
            return hints
        def keys(action, limit=2):
            return "/".join(short_key_name(k) for k in self.settings.get_action_keys(action)[:limit])
        hints = [
            (keys("move_left", 1) + " " + keys("move_right", 1), "이동"),
            (keys("rotate_cw") , "회전"),
            (keys("rotate_ccw", 1), "역회전"),
            (keys("soft_drop", 1), "소프트"),
            (keys("hard_drop", 1), "하드드롭"),
            (keys("hold"), "홀드"),
            (keys("target_cycle", 1) + "/1~5", "조준"),                    # 조준 대상 순환 + 조준 모드 바로 선택(1~5)을 한 칸에 (안내 바가 3줄이 되면 화면 아래로 잘려서)
        ]
        if self.settings.get_action_keys("rotate_180"):
            hints.insert(3, (keys("rotate_180", 1), "180°"))                 # 키를 지정한 사람에게만 안내
        if self.match is not None and not self.match.attacks_enabled:
            hints = [h for h in hints if h[1] != "조준"]      # 서바이벌: 조준 개념 없음
        if self.match is not None and self.match.practice:
            hints += [("G · B · V", "쓰레기 · 초기화 · 압박 드릴")]        # 항목이 10개를 넘으면 안내 바가 3줄이 되어 화면 아래로 잘림
        if self.net_mgr.mode == "NONE":
            hints.append((keys("pause", 1), "일시정지"))
        else:
            hints.append(("Enter", "채팅"))                                  # 네트워크 경기에서는 일시정지가 없고 대신 채팅 키가 있음 (안내가 없었음)
        hints.append(("F1", "규칙"))                                          # 게임 중에도 열 수 있는 규칙 요약 (일시정지 화면에만 안내가 있었음)
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

    def start_game(self, mode="SOLO", total_players=100, initial_players=None, practice=False, daily=None, weekly=None, brief=True, quick=False):
        """practice=True: 연습 모드(혼자, 전적 없음). daily="YYYYMMDD": 오늘의 도전(같은 날은 같은 블록 순서/상대 구성, 100인 혼합 난이도 배틀로얄)"""
        self._grace_from_first_frame = True
        self._long_frame_grace_until = time.time() + self.LONG_FRAME_GRACE      # 시작 직후 첫 장면 준비로 프레임이 길어져도 일시정지하지 않음
        self._end_text(commit=False)
        self.rebinding_action = None                     # 화면이 바뀌면 키 바인딩 대기/규칙 창을 닫음 (켜진 채 남으면 M/F1 키가 먹통)
        self.rules_open = False
        self._sound_due = []                             # 이전 판 결과 화면에 예약된 효과음(도장/레벨 업)이 새 판 카운트다운이나 메뉴에서 터지지 않게
        self._paused_by_rules = False
        self.renderer.reset_standings()
        self._lobby_return_t0 = None
        self.renderer.lobby_return_left = None
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
        self._clear_input_state()
        self.das_timer = 0.0
        self.arr_timer = 0.0
        self.soft_drop_timer = 0.0
        import config as _cfg
        mutator = None
        if weekly:                                                      # 주간 변형 규칙: 같은 주는 같은 블록 순서/상대 구성
            mutator = next((m for m in _cfg.WEEKLY_MUTATORS if m["id"] == weekly[1]), None) if isinstance(weekly, tuple) else _cfg.weekly_mutator()
            weekly = weekly[0] if isinstance(weekly, tuple) else _cfg.week_key()
            total_players = mutator.get("players", 100)
        seed = int(daily) if daily else (_cfg.weekly_seed(weekly) if weekly else None)
        solo_rules = (mode == "SOLO" and not practice)
        rival = self.stats_mgr.rival_id() if solo_rules and not daily else None
        ghost = self.stats_mgr.daily_ghost(daily) if daily else None
        import challenges as _chl
        tracker, kind = None, None                                        # 도전 과제: 연습/오늘의 도전/주간 변형(혼자 하는 경기)만
        if mode == "SOLO":
            if practice:
                tracker, kind = _chl.ChallengeTracker(_chl.PRACTICE_GOALS, self.stats_mgr.challenge_done("practice")), "practice"
            elif daily:
                ids = self.stats_mgr.daily_goal_ids(daily)
                tracker, kind = _chl.ChallengeTracker([_chl.DAILY_BY_ID[i] for i in ids], self.stats_mgr.challenge_done("daily", daily)), "daily"
            elif weekly and mutator:
                tracker, kind = _chl.ChallengeTracker(_chl.WEEKLY_GOALS[mutator["id"]], self.stats_mgr.challenge_done("weekly", weekly)), "weekly"
        self.match = BattleRoyaleMatch(
            total_players=2 if practice else (100 if daily else total_players),
            local_player_id=my_id,
            local_player_name=self.player_name,
            net_mgr=self.net_mgr if mode in ["HOST", "CLIENT"] else None,
            initial_players=initial_players,
            sound_mgr=self.sound_mgr,
            bot_difficulty="mixed" if daily else (mutator.get("difficulty", self.bot_difficulty) if mutator else ((self.net_mgr.match_difficulty or self.bot_difficulty) if mode == "CLIENT" else self.bot_difficulty)),      # 참가자는 호스트가 정한 봇 난이도로 기록(전적/사다리가 자기 설정으로 잘못 기록되던 문제)
            # 게임 모드: 참가자는 호스트가 정한 값을 따르고, 그 외에는 내 설정을 씀 (오늘의 도전은 항상 배틀로얄)
            attacks_enabled=True if (daily or weekly) else (self.net_mgr.match_attacks if mode == "CLIENT" else self.settings.get("game_mode") != "survival"),
            practice=practice, seed=seed, daily=daily, weekly=weekly, mutator=mutator, rival_id=rival, ghost=ghost, challenge=tracker,
            team_mode=(self.net_mgr.match_team if mode == "CLIENT" else
                       bool(self.settings.get("rule_team", False)) and mode in ("SOLO", "HOST") and not practice and not daily and not weekly
                       and (mode == "SOLO" or self.settings.get("game_mode") != "survival"))
        )
        self.match.challenge_kind = kind
        self.match.race_ghost = None
        if mode == "SOLO" and self.settings.get("ghost_race", False):                # 고스트 레이스: 저장된 내 리플레이 중 최고 점수 판
            from replay import load_replays_cached, best_replay, ReplayPlayer
            best = best_replay(load_replays_cached(), mode=("survival" if not self.match.attacks_enabled else "battle"), total=self.match.total_players)
            if best is not None:
                self.match.race_ghost = ReplayPlayer(best)
                self.match.race_ghost.paused = True                                  # 재생 시각은 경기 시간(elapsed)에 맞춰 직접 이동
        if mode in ("HOST", "CLIENT") and self.match.team_mode:                    # LAN 팀전: 쓰레기량/중력은 기본 규칙 (참가자마다 설정이 다르면 어긋남), 기록하지 않음
            self.match.custom_rules = {"garbage": "normal", "gravity": "normal", "badges": True, "team": True}
        if mode == "SOLO" and not practice and not daily and not weekly:           # 커스텀 규칙: 혼자 하는 배틀로얄에만 적용, 기본값이 아닐 때만 켜짐
            rg, rv, rb = self.settings.get("rule_garbage", "normal"), self.settings.get("rule_gravity", "normal"), bool(self.settings.get("rule_badges", True))
            if (rg, rv, rb) != ("normal", "normal", True) or self.match.team_mode:
                self.match.custom_rules = {"garbage": rg, "gravity": rv, "badges": rb, "team": self.match.team_mode}
                bits = [f"쓰레기 {({'half': '×0.5', 'normal': '×1', 'heavy': '×1.5'})[rg]}", f"낙하 {({'slow': '느리게', 'normal': '기본', 'fast': '빠르게'})[rv]}", "열기 " + ("켬" if rb else "끔")]
                from i18n import tr as _tr                                       # 조각마다 번역한 뒤 이어 붙임 (바뀌는 값이 낀 한 줄을 통째로 번역할 수 없으므로)
                self.match.add_commentary(_tr("커스텀 규칙") + " · " + " · ".join(_tr(b) for b in bits) + " " + _tr("(기록되지 않음)"), (255, 190, 90), prio=1)
        if practice:
            self.match.ta_bests = dict(self.stats_mgr.ch()["practice"]["ta"])
        self.match.local_color = self.name_color
        self.match.drill_best = int(self.settings.get("drill_best", 0) or 0)
        self.match.set_target_mode(self.settings.get("target_mode"))        # 마지막으로 쓴 조준 모드를 이어서 사용
        self.match.novice = (not practice) and self.stats_mgr.data.get("total_games", 0) < 3        # 처음 3판: 조준 칩은 자동만 또렷하게
        self.match.log_enabled = bool(self.settings.get("match_log", False)) and not practice
        from replay import ReplayRecorder
        self.killcam, self.killcam_on = None, False                          # 이전 판의 '마지막 8초 되감기'를 새 판에 가져오지 않음
        self.renderer.killcam, self.renderer.killcam_available = None, False
        self.replay_rec = None if practice else ReplayRecorder({"mode": "survival" if not self.match.attacks_enabled else "battle", "custom": bool(self.match.custom_rules)})      # 내 보드 리플레이 (연습 제외)
        if self.replay_rec is not None:
            self.match.local_engine.replay_log = []        # 카운트다운 직후 첫 프레임에 고정된 블록도 기록에서 빠지지 않게 처음부터 켬
        lead = 0.0
        show_brief = bool(kind in ("daily", "weekly") and brief and getattr(self, "use_bot_pool", False))
        if show_brief:                                                   # 오늘의 도전/주간 변형: 규칙과 목표를 먼저 보여 주고, 아무 키나 누르면 카운트다운 시작
            self.match.brief_open = True
        elif mode == "SOLO" and not practice and getattr(self, "use_bot_pool", False):                                                  # 혼자 하는 경기: 3-2-1 동안 경기를 멈추고 화면을 먼저 보여 줌 (네트워크는 동기화 때문에 제외, 테스트/헤드리스 실행은 건너뜀)
            lead = 2.0 if quick else self.match.COUNTDOWN_SECS      # 결과 화면에서 바로 '재도전'한 경우는 카운트다운을 2초로 줄여 '한 판 더'까지의 마찰을 줄임
            self.match.countdown_until = time.time() + lead
        if not practice and not self.settings.get("coach_done"):                             # 처음 하는 경기: HUD 핵심 3곳을 15초 동안 설명 (한 번만, 카운트다운 동안에도 보임)
            self.match.coach_until = time.time() + lead + 12.0
            self.match.coach_pending = True                  # coach_done은 코치를 볼 시간이 지난 뒤에(_check_tips) 저장: 바로 나가면 다음에 다시 보임
        self._cd_n = None                                    # 카운트다운 효과음 진행 (3-2-1-GO)
        if not practice and self.match.attacks_enabled and not self.match.custom_rules:      # (커스텀 규칙 경기는 기록되지 않으므로 업적/최고 기록 알림도 띄우지 않음) 경기 중에 알려 줄 수 있는 아직 못 얻은 업적 / 평생 첫 K.O. 여부 (저장과 정식 판정은 경기가 끝날 때)
            from stats_manager import ACHIEVEMENTS
            _done = set(self.stats_mgr.achievements_done())
            self.match.live_ach = {aid: title for aid, title, _d, _ok in ACHIEVEMENTS if aid in self.match.LIVE_ACH and aid not in _done}
            self.match.first_ko_ever = int(self.stats_mgr.data.get("total_kos", 0)) == 0 and "first_ko" not in _done
            self.match.bests = {"max_ko": int(self.stats_mgr.data.get("max_ko", 0)), "best_score": int(self.stats_mgr.data.get("best_score", 0)),
                                "best_rank": int(self.stats_mgr.best_in_size("battle", self.match.total_players) or 0)}      # 경기 중 근접 실패/돌파 알림용
        self.apply_gameplay_options()
        if getattr(self, "use_bot_pool", False) and mode != "CLIENT":
            bot_pool.revive()
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
            daily = getattr(self.match, "daily", None) if self.match is not None else None
            weekly = getattr(self.match, "weekly", None) if self.match is not None else None
            if daily:
                self.start_game(mode="SOLO", daily=daily, brief=False, quick=True)             # 오늘의 도전은 재도전도 같은 도전(같은 블록 순서/상대), 브리핑은 건너뜀
            elif weekly:
                self.start_game(mode="SOLO", weekly=(weekly, self.match.mutator["id"]), brief=False, quick=True)      # 주간 변형 규칙도 같은 규칙으로 재도전
            else:
                self.start_game(mode="SOLO", total_players=self.target_player_count, quick=True)
        elif self.match is not None and self.match.match_finished:
            self._return_to_lobby()

    def _challenge_next_difficulty(self):
        """난이도 클리어 직후 '다음 난이도 도전': 봇 난이도를 다음 단계로 바꾸고 같은 규모로 새 판 (설정에도 반영됨)"""
        nxt = getattr(self.match, "next_ladder", None) if self.match is not None else None
        if not nxt or self.net_mgr.mode != "NONE":
            return
        self.settings.set("bot_difficulty", nxt)
        self.bot_difficulty = self.settings.get("bot_difficulty")
        self.start_game(mode="SOLO", total_players=self.target_player_count, quick=True)

    def _practice_after_match(self):
        """결과 화면 '연습하기'(P): 솔로 경기에서만 바로 연습 모드로 (네트워크 경기에서는 무시)"""
        if self.net_mgr.mode == "NONE":
            self.start_game(mode="SOLO", practice=True)

    def _return_to_lobby(self):
        """네트워크 경기 종료 후 대기실로: 호스트는 방을 다시 열고(참가자 유지), 참가자는 호스트의 다음 시작을 기다림"""
        nm = self.net_mgr
        self._end_text(commit=False)
        self.rebinding_action = None                     # 화면이 바뀌면 키 바인딩 대기/규칙 창을 닫음 (켜진 채 남으면 M/F1 키가 먹통)
        self.rules_open = False
        self._sound_due = []                             # 이전 판 결과 화면에 예약된 효과음(도장/레벨 업)이 새 판 카운트다운이나 메뉴에서 터지지 않게
        self._paused_by_rules = False
        self.match = None
        self.is_paused = False
        self.modal = None
        self._notice_shown = False
        self._lobby_return_t0 = None
        self.renderer.lobby_return_left = None
        self._clear_input_state()
        self.sound_mgr.play_bgm('lobby', crossfade_ms=300)       # 경기에서 나올 때는 이전 곡이 길게 겹치지 않게 짧게 전환
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
                self.match.rumble(0.35, "drop")                # 하드 드롭: 짧고 낮은 '쿵' (진동 설정이 켜져 있을 때만)
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

"""
Block Royale 100 - 게임 화면: 입력 처리, 프레임 갱신, 렌더링, 네트워크 상태 점검
BlockRoyaleApp(main.py)이 상속하는 믹스인: 메서드 본문은 원래 main.py에 있던 그대로이며 self로 앱 상태를 공유함
"""

from stats_manager import next_goal_text
from app_common import (
    ACTION_NAMES,
    TARGET_MODES,
    pygame,
    time
)


class GameMixin:
    # 숫자키(위쪽 숫자열/숫자패드) -> 조준 모드 번호 (config.TARGET_MODES 순서)
    TARGET_NUM_KEYS = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3, pygame.K_5: 4,
                       pygame.K_KP1: 0, pygame.K_KP2: 1, pygame.K_KP3: 2, pygame.K_KP4: 3, pygame.K_KP5: 4}

    def _handle_game_event(self, event):
        """게임 화면의 입력 처리 (키보드/마우스/창 포커스)"""
        # 창 포커스를 잃으면 눌린 키 상태를 비우고, 싱글 플레이는 자동 일시정지
        if event.type == pygame.WINDOWFOCUSLOST:
            self.key_left_down = self.key_right_down = self.key_down_down = False
            self.h_dir = 0
            if (self.match and self.net_mgr.mode == "NONE" and not self.is_paused
                    and self.match.local_is_alive and not self.match.match_finished):
                self.is_paused = True
                self.match.is_paused = True
                self.renderer.pause_focus = 0
                self.sound_mgr.pause_bgm()
            return
        # 인게임 조작
        if event.type == pygame.KEYDOWN:
            # T: 설정 열기 (싱글은 자동 일시정지, 네트워크는 게임 진행). 조작키로 T를 배정한 경우는 조작키가 우선
            if event.key == pygame.K_t and self.text_focus is None and not any(
                    pygame.K_t in self.settings.get_action_keys(a) for a, _n in ACTION_NAMES):
                self._open_settings_from_game()
                return
            # 첫 경기 코치 마크: Enter로 바로 닫기 (조작키로 쓰고 있지 않을 때만)
            if (event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and getattr(self.match, "coach_until", 0.0) > time.time()
                    and self.text_focus is None and not any(event.key in self.settings.get_action_keys(a) for a, _n in ACTION_NAMES)):
                self.match.coach_until = 0.0
                return
            # 연습 모드: G = 쓰레기 줄 받기(Shift+G는 8줄), B = 보드 초기화. 조작키로 쓰고 있는 키는 조작키가 우선
            if (self.match.practice and event.key in (pygame.K_g, pygame.K_b) and self.text_focus is None
                    and not any(event.key in self.settings.get_action_keys(a) for a, _n in ACTION_NAMES)):
                if event.key == pygame.K_b:
                    self.match.practice_reset()
                else:
                    self.match.practice_inject_garbage(8 if (event.mod & pygame.KMOD_SHIFT) else 4)
                    self.match._play_hit_alarm(8 if (event.mod & pygame.KMOD_SHIFT) else 4)
                return
            # 탈락 또는 게임 종료 시 처리
            if self.match.match_finished:
                # 최종 순위표: 스크롤 / 재도전 / 메인 메뉴
                if event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_PAGEUP, pygame.K_PAGEDOWN, pygame.K_HOME, pygame.K_END):
                    step = {pygame.K_UP: -1, pygame.K_DOWN: 1, pygame.K_PAGEUP: -8, pygame.K_PAGEDOWN: 8,
                            pygame.K_HOME: -999, pygame.K_END: 999}[event.key]
                    self.renderer.scroll_standings(step)
                elif event.key == pygame.K_r:
                    self.sound_mgr.play('move')
                    self._restart_after_match()
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_ESCAPE):
                    if time.time() >= self.result_lock_until:
                        self.return_to_menu()
                return
            if self.match.match_finished or not self.match.local_is_alive:
                if getattr(self.match, 'is_spectating', False):
                    if event.key == pygame.K_LEFT:
                        self.match.cycle_spectate_target(-1)
                        self.sound_mgr.play('move')
                        return
                    elif event.key == pygame.K_RIGHT:
                        self.match.cycle_spectate_target(1)
                        self.sound_mgr.play('move')
                        return
                    elif event.key == pygame.K_s:
                        self.match.is_spectating = False
                        self.sound_mgr.play('move')
                        return
                    elif event.key == pygame.K_r:
                        self.sound_mgr.play('move')
                        self._restart_after_match()
                        return
                    elif event.key == pygame.K_ESCAPE:
                        if self.net_mgr.mode != "NONE" and not self.match.match_finished:
                            self._confirm_leave_network_game()
                        elif self.net_mgr.mode == "NONE" and not self.is_paused:
                            self.is_paused = True                 # 관전 중에도 일시정지 메뉴로 나가기/설정 선택 가능(P 키와 동일하게 동작)
                            self.match.is_paused = True
                            self.renderer.pause_focus = 0
                            self.sound_mgr.pause_bgm()
                        else:
                            self.return_to_menu()
                        return
                else:
                    if event.key in (pygame.K_r, pygame.K_s) and time.time() < self.result_lock_until:
                        return                                    # 탈락 직후 습관적인 키(WASD 프리셋의 S 소프트 드롭 등)로 재도전/관전이 바로 실행되지 않게
                    if event.key == pygame.K_r:
                        self.sound_mgr.play('move')
                        self._restart_after_match()
                        return
                    elif event.key == pygame.K_s and not self.match.match_finished and self.match.alive_count > 1:
                        self.match.is_spectating = True
                        self.match.cycle_spectate_target(0)
                        self.sound_mgr.play('move')
                        return
                    elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                        ids = self._result_button_ids()
                        step = -1 if event.key == pygame.K_LEFT else 1
                        i = ids.index(self.renderer.result_focus_id) if self.renderer.result_focus_id in ids else 0
                        self.renderer.result_focus_id = ids[(i + step) % len(ids)]
                        self.sound_mgr.play('move')
                        return
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if time.time() < self.result_lock_until:      # 탈락 직후 하드드롭 연타로 결과 화면이 닫히는 것 방지
                            return
                        self._activate_result_focus()
                        return
                    elif event.key == pygame.K_ESCAPE:
                        if time.time() < self.result_lock_until:
                            return
                        self.return_to_menu()
                        return

            if self.is_paused:
                if event.key in (pygame.K_UP, pygame.K_DOWN):
                    step = -1 if event.key == pygame.K_UP else 1
                    self.renderer.pause_focus = (self.renderer.pause_focus + step) % 3
                    self.sound_mgr.play('move')
                    return
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    self._activate_pause_focus()
                    return
                if not self.settings.is_action_key(event.key, "pause") and event.key != pygame.K_ESCAPE:
                    return
            if self.settings.is_action_key(event.key, "move_left"):
                self.key_left_down = True
                self.h_dir = -1
                self.das_timer = 0.0
                self.arr_timer = 0.0
                if self.match.local_engine.move(-1, 0):
                    self.sound_mgr.play('move')
            elif self.settings.is_action_key(event.key, "move_right"):
                self.key_right_down = True
                self.h_dir = 1
                self.das_timer = 0.0
                self.arr_timer = 0.0
                if self.match.local_engine.move(1, 0):
                    self.sound_mgr.play('move')
            elif self.settings.is_action_key(event.key, "soft_drop"):
                self.key_down_down = True
                self.soft_drop_timer = 0.0
                if self.match.local_engine.move(0, 1, soft=True):
                    self.sound_mgr.play('move')
            elif self.settings.is_action_key(event.key, "rotate_cw"):
                if self.match.local_engine.rotate(clockwise=True):
                    self.sound_mgr.play('rotate')
            elif self.settings.is_action_key(event.key, "rotate_ccw"):
                if self.match.local_engine.rotate(clockwise=False):
                    self.sound_mgr.play('rotate')
            elif self.settings.is_action_key(event.key, "hard_drop"):
                cleared = self.match.local_engine.hard_drop()
                self._hard_drop_pending = True      # 착지 소리는 프레임 루프에서 잠금 이벤트와 함께 재생
                if cleared > 0:
                    self.match.on_lines_cleared(cleared)
            elif self.settings.is_action_key(event.key, "hold"):
                if self.match.local_engine.hold():
                    self.sound_mgr.play('hold')
            elif self.settings.is_action_key(event.key, "pause") and self.net_mgr.mode == "NONE":
                # 싱글 플레이 시 일시정지 토글
                self.is_paused = not self.is_paused
                if self.match:
                    self.match.is_paused = self.is_paused
                if self.is_paused:
                    self.renderer.pause_focus = 0
                    self.sound_mgr.pause_bgm()
                else:
                    self.sound_mgr.unpause_bgm()
            elif self.settings.is_action_key(event.key, "target_cycle"):
                mode = self.match.cycle_target_mode()
                self.settings.set("target_mode", mode, autosave=False)          # 조작 중에는 디스크에 쓰지 않음 (메뉴로 나갈 때/종료할 때 저장)
                self.sound_mgr.play('rotate')
            elif event.key in self.TARGET_NUM_KEYS and not any(
                    event.key in self.settings.get_action_keys(a) for a, _n in ACTION_NAMES):
                self.settings.set("target_mode", self.match.set_target_mode(TARGET_MODES[self.TARGET_NUM_KEYS[event.key]]), autosave=False)      # 1~5: 자동/K.O./반격/배지/랜덤 바로 선택 (다음 경기에도 유지)
                self.sound_mgr.play('rotate')
            elif event.key == pygame.K_ESCAPE:
                if self.net_mgr.mode == "NONE" and not self.is_paused and not self.match.match_finished and self.match.local_is_alive:
                    self.is_paused = True
                    if self.match:
                        self.match.is_paused = True
                    self.renderer.pause_focus = 0
                    self.sound_mgr.pause_bgm()
                    return
                if not self.match.match_finished and self.match.local_is_alive:
                    self._confirm_leave_network_game()      # 진행 중인 경기는 실수로 ESC를 눌러도 바로 나가지 않고 확인 (솔로/네트워크 공통)
                    return
                self.return_to_menu()
                return
                
        elif event.type == pygame.KEYUP:
            if self.settings.is_action_key(event.key, "move_left"):
                self.key_left_down = False
                if self.h_dir == -1:
                    # 반대쪽 키가 아직 눌려 있으면 그 방향으로 즉시 이어서 이동 (DAS 유지)
                    self.h_dir = 1 if self.key_right_down else 0
            elif self.settings.is_action_key(event.key, "move_right"):
                self.key_right_down = False
                if self.h_dir == 1:
                    self.h_dir = -1 if self.key_left_down else 0
            elif self.settings.is_action_key(event.key, "soft_drop"):
                self.key_down_down = False
                
        elif event.type == pygame.MOUSEWHEEL and self.match.match_finished:
            self.renderer.scroll_standings(-event.y * 2)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if getattr(self.match, "coach_until", 0.0) > time.time():
                self.match.coach_until = 0.0                    # 첫 경기 코치 마크는 클릭으로도 닫힘 (클릭은 그대로 다른 동작에도 전달)
            
            # 1. 일시정지 중 팝업 버튼 인터랙션
            if self.is_paused:
                if getattr(self.renderer, 'pause_resume_btn', None) and self.renderer.pause_resume_btn.collidepoint(mx, my):
                    self._activate_pause_focus(0)
                    return
                if getattr(self.renderer, 'pause_settings_btn', None) and self.renderer.pause_settings_btn.collidepoint(mx, my):
                    self._activate_pause_focus(1)
                    return
                if getattr(self.renderer, 'pause_exit_btn', None) and self.renderer.pause_exit_btn.collidepoint(mx, my):
                    self._activate_pause_focus(2)
                    return
            
            # 게임 종료/탈락 시 결과 오버레이 버튼 클릭
            if self.match.match_finished or (not self.match.local_is_alive and not getattr(self.match, 'is_spectating', False)):
                if hasattr(self.renderer, 'result_restart_btn') and self.renderer.result_restart_btn and self.renderer.result_restart_btn.collidepoint(mx, my):
                    self.sound_mgr.play('move')
                    self._restart_after_match()
                    return
                if hasattr(self.renderer, 'result_spectate_btn') and self.renderer.result_spectate_btn and self.renderer.result_spectate_btn.collidepoint(mx, my):
                    self.match.is_spectating = True
                    self.match.cycle_spectate_target(0)
                    self.sound_mgr.play('move')
                    return
                if hasattr(self.renderer, 'result_return_btn') and self.renderer.result_return_btn and self.renderer.result_return_btn.collidepoint(mx, my):
                    self.sound_mgr.play('move')
                    self.return_to_menu()
                    return

            # 관전 모드 중 미니 보드 클릭 시 해당 생존자 관전으로 즉시 전환
            if getattr(self.match, 'is_spectating', False):
                for pid, rect in self.renderer.mini_board_rects.items():
                    if rect.collidepoint(mx, my) and self.match.players.get(pid, {}).get("is_alive"):
                        self.match.spectate_target_id = pid
                        self.sound_mgr.play('move')
                        return

            # 일반 인게임: 미니 보드 클릭으로 수동 타겟 지정
            for pid, rect in self.renderer.mini_board_rects.items():
                if rect.collidepoint(mx, my):
                    self.match.set_manual_target(pid)
                    self.sound_mgr.play('attack')
                    break

    def _result_button_ids(self):
        """결과 화면(K.O.)에 실제로 보이는 버튼 id 목록 (왼쪽부터). ui_renderer._render_result_overlay의 분기와 맞춰야 함"""
        net_on = self.net_mgr.mode != "NONE"
        can_spectate = self.match.alive_count > 1
        if net_on:
            return (["spectate"] if can_spectate else []) + ["return"]
        elif can_spectate:
            return ["restart", "spectate", "return"]
        else:
            return ["restart", "return"]

    def _activate_result_focus(self, bid=None):
        """결과 화면(K.O.) 버튼 실행 (키보드 엔터/마우스 클릭 공용)"""
        if bid is None:
            bid = self.renderer.result_focus_id
        self.sound_mgr.play('move')
        if bid == "restart":
            self._restart_after_match()
        elif bid == "spectate":
            self.match.is_spectating = True
            self.match.cycle_spectate_target(0)
        elif bid == "return":
            self.return_to_menu()

    def _activate_pause_focus(self, idx=None):
        """일시정지 메뉴 항목 실행 (0=계속하기 1=환경설정 2=나가기). 키보드 엔터/마우스 클릭 공용"""
        if idx is None:
            idx = self.renderer.pause_focus
        self.sound_mgr.play('move')
        if idx == 0:
            self.is_paused = False
            if self.match:
                self.match.is_paused = False
            self.sound_mgr.unpause_bgm()
        elif idx == 1:
            self.previous_state = "GAME"
            self.state = "SETTINGS"
        elif idx == 2:
            if not self.match.match_finished and self.match.local_is_alive:
                self._confirm_leave_network_game()
            else:
                self.return_to_menu()

    def _open_settings_from_game(self):
        self.sound_mgr.play('move')
        self.key_left_down = self.key_right_down = self.key_down_down = False
        self.h_dir = 0
        if self.net_mgr.mode == "NONE" and self.match and not self.match.match_finished and self.match.local_is_alive                 and not self.is_paused:
            self.is_paused = True
            self.match.is_paused = True
            self.sound_mgr.pause_bgm()
        self._end_text(commit=False)
        self.previous_state = "GAME"
        self.state = "SETTINGS"

    def _tick_game(self, dt):
        """게임 화면 한 프레임: 업데이트 후 렌더링. 업데이트 중 대기실/메뉴로 전환되면(match 없음) 렌더링하지 않음."""
        # 프레임이 느려지면(평균 25ms 초과) 나와 무관한 봇끼리의 공격 연출을 생략해 조작이 느려지지 않게 함 (다시 빨라지면 복귀)
        self._dt_ema = getattr(self, "_dt_ema", 1 / 60) * 0.9 + min(dt, 0.25) * 0.1
        if self.match is not None:
            self.match.fx_low = self._dt_ema > 1 / 38 or (self.match.fx_low and self._dt_ema > 1 / 48)
        self._update_game(dt)
        if self.state != "GAME" or self.match is None:
            return
        self._render_game_frame()

    def _render_game_frame(self):
        """게임 화면 한 장 그리기 (게임 중 설정 창의 배경으로도 사용)"""
        self.renderer.key_hints = self._build_key_hints()
        net_on = self.net_mgr.mode != "NONE"
        self.renderer.chat_entries = list(self.net_mgr.chat_log) if net_on else []
        self.renderer.chat_input = self.chat_input if self.text_focus == "chat" else None
        self.renderer.chat_comp = self.chat_comp if self.text_focus == "chat" else ""
        self.renderer.chat_my_id = self.net_mgr.my_player_id or ""
        self.renderer.render(self.match, self.sound_mgr)

    def _update_game(self, dt):
        if not self.match:
            return
            
        if self.is_paused:
            return
            
        # 1. DAS / ARR 연속 좌우 이동 및 초고속 소프트드롭
        if self.match.local_is_alive and not self.match.local_engine.game_over:
            if (self.h_dir == -1 and self.key_left_down) or (self.h_dir == 1 and self.key_right_down):
                direction = self.h_dir
            else:
                direction = -1 if self.key_left_down else (1 if self.key_right_down else 0)
            if direction != 0:
                self.das_timer += dt
                if self.das_timer >= self.DAS_DELAY:
                    moved = False
                    if self.ARR_INSTANT:                             # ARR 0: 막힐 때까지 한 번에 이동
                        while self.match.local_engine.move(direction, 0):
                            moved = True
                        self.arr_timer = 0.0
                    else:
                        self.arr_timer += dt
                        while self.arr_timer >= self.ARR_INTERVAL:
                            self.arr_timer -= self.ARR_INTERVAL
                            if self.match.local_engine.move(direction, 0):
                                moved = True
                            else:
                                self.arr_timer = 0.0
                                break
                    if moved:
                        self.sound_mgr.play('move')                  # 한 프레임에 여러 칸 움직여도 소리는 한 번
            else:
                self.das_timer = 0.0
                self.arr_timer = 0.0

            if self.key_down_down:
                self.soft_drop_timer += dt
                while self.soft_drop_timer >= self.SOFT_DROP_INTERVAL:
                    self.soft_drop_timer -= self.SOFT_DROP_INTERVAL
                    if not self.match.local_engine.move(0, 1, soft=True):
                        self.soft_drop_timer = 0.0
                        break
            else:
                self.soft_drop_timer = 0.0

        if self._check_network_status():      # 대기실로 복귀한 경우 이번 프레임의 게임 처리는 건너뜀
            return
        prev_alive = self.match.local_is_alive
        prev_ko = self.match.local_ko_count
        
        self.match.update(dt)
        self._play_lock_feedback(dt)
        
        # 생존자 수에 따른 동적 BGM 스테이지 업데이트 (100인 -> 50인 -> 20인 이하)
        self.sound_mgr.update_bgm_for_alive(self.match.alive_count, self.match.total_players)
        
        # 피격 / KO / 탈락 효과음
        if self.match.local_ko_count > prev_ko:
            self.sound_mgr.play('ko')
        if prev_alive and not self.match.local_is_alive and not self.gameover_played:
            self.gameover_played = True
            self._gameover_time = time.time()
            self.result_lock_until = time.time() + 1.2
            self.sound_mgr.play_gameover()
        if self.match.match_finished and not getattr(self, "_finish_lock_set", False):
            self._finish_lock_set = True
            self.result_lock_until = time.time() + 1.5      # 종료 직후 연타로 순위표가 바로 닫히는 것 방지
        if self.match.match_finished and self.match.local_rank != 1 and not getattr(self, "_defeat_played", False):
            self._defeat_played = True
            if self.gameover_played and time.time() - getattr(self, "_gameover_time", 0.0) > 3.0:
                self.sound_mgr.stop_bgm()          # 한참 전에 탈락해 관전하던 사람에겐 패배음을 또 들려주지 않음
                self.sound_mgr.play_results_bgm()  # 대신 바로 순위표 곡을 켬
            else:
                self.sound_mgr.play_defeat()
        if self.match.match_finished and self.match.local_rank == 1 and not self.victory_played:
            self.victory_played = True
            self.result_lock_until = time.time() + 1.2
            self.sound_mgr.play_victory()
            
        # 경기 종료/탈락 시 전적 통계 자동 갱신 (1회)
        if not self.match_recorded and not self.match.practice and (self.match.match_finished or not self.match.local_is_alive):
            self.match_recorded = True
            survival_sec = self.match.survival_seconds()   # 탈락 순간의 시간 (일시정지 시간 제외)
            if self.match.match_finished and self.match.local_rank == 1:
                final_rank = 1
            elif self.match.local_rank > 0:
                final_rank = self.match.local_rank
            else:
                final_rank = self.match.alive_count + 1
                
            self.match.new_records = self.stats_mgr.record_match(
                rank=final_rank,
                total_players=self.match.total_players,
                kos=self.match.local_ko_count,
                lines=self.match.local_engine.lines_cleared_total,
                max_combo=getattr(self.match.local_engine, 'max_combo', 0),
                survival_sec=survival_sec,
                mode="battle" if self.match.attacks_enabled else "survival",
                difficulty=self.match.bot_difficulty,
                daily=self.match.daily
            )
            _mode = "battle" if self.match.attacks_enabled else "survival"
            self.match.ladder_clear = self.stats_mgr.last_ladder_clear
            self.match.next_goal = (f"오늘의 도전 최고 #{self.stats_mgr.daily_best(self.match.daily)}위" if self.match.daily and not self.match.ladder_clear else None) or next_goal_text(final_rank, self.match.local_ko_count, self.match.total_players,
                                                  self.stats_mgr.best_in_size(_mode, self.match.total_players),
                                                  difficulty=self.match.bot_difficulty if _mode == "battle" else None,
                                                  cleared=self.stats_mgr.ladder_cleared(_mode), ladder_clear=self.match.ladder_clear)
            
        # 주기적 네트워크 패킷 동기화 (15Hz)
        now = time.time()
        if now - self.last_sync_time >= (1.0 / 15.0):
            self.last_sync_time = now
            if self.net_mgr.mode == "CLIENT":
                # 내 상태 전송
                st = {
                    "is_alive": self.match.local_is_alive,
                    "compact_grid": self.match.local_engine.get_compact_grid(),
                    "highest_y": self.match.local_engine.get_highest_block_row(),
                    "score": self.match.local_engine.score,
                    "lines": self.match.local_engine.lines_cleared_total,
                    "snap": self.match.local_engine.snapshot(),          # 다른 클라이언트가 나를 관전할 때 쓰는 상세 상태
                    "spec": self.match.spectate_target_id if getattr(self.match, "is_spectating", False) else None,
                }
                self.net_mgr.client_send_state(st)
            elif self.net_mgr.mode == "HOST":
                # 전체 상태 취합 브로드캐스트
                all_st = []
                for pid, p in self.match.players.items():
                    all_st.append({
                        "id": pid,
                        "name": p["name"],
                        "is_alive": p["is_alive"],
                        "compact_grid": p["compact_grid"],
                        "highest_y": p["highest_y"],
                        "ko_count": p["ko_count"],
                        "rank": p["rank"],
                        "score": self.match.player_stats(pid)["score"],
                        "lines": self.match.player_stats(pid)["lines"],
                        "atk": self.match.player_stats(pid)["attacks"],
                        "surv": p.get("survival"),
                        "cg": "".join(p["cg"]) if len(p.get("cg") or []) == 20 else "",
                        "cp": list(p["cpiece"]) if p.get("cpiece") else None,
                        "nx": "".join(p.get("next") or []),
                        "hd": p.get("hold") or "",
                        "ig": p.get("ig", 0),
                    })
                details = {}
                for sid in self.net_mgr.get_spectated_ids():         # 클라이언트가 관전 중인 대상만 상세 정보 전송
                    snap = self.match.snapshot_for(sid)
                    if snap:
                        details[sid] = snap
                self.net_mgr.host_sync_world(all_st, details)

    def _check_network_status(self):
        """게임 중: (클라이언트) 호스트 종료/연결 끊김 알림, (호스트) 참가자 이탈 알림 및 정리"""
        nm = self.net_mgr
        if nm.mode == "CLIENT" and nm.lobby_return:
            self._return_to_lobby()
            return True
        if nm.mode == "CLIENT" and not self._notice_shown:
            if nm.host_left:
                self._notice_shown = True
                self._open_modal("호스트가 게임을 종료했습니다", ["방장이 게임을 나가서 이 게임이 종료되었습니다.", "메인 메뉴로 돌아갑니다."],
                                 [("ok_menu", "메인 메뉴로", "blue", "ENTER")])
            elif nm.seconds_since_host_packet() > 8.0:
                self._notice_shown = True
                self._open_modal("호스트와 연결이 끊겼습니다", ["8초 이상 호스트에게서 응답이 없습니다.", "호스트가 종료되었거나 네트워크에 문제가 있을 수 있습니다."],
                                 [("ok_menu", "메인 메뉴로", "blue", "ENTER")])
        elif nm.mode == "HOST":
            if not self.match.match_finished:            # 경기가 끝난 뒤 결과 화면을 보는 동안에는 참가자를 정리하지 않음
                nm.reap_clients()
            while nm.left_events:
                name = nm.left_events.pop(0)
                self.match.add_floating_text(f"{name} 님이 게임을 나갔습니다", (255, 190, 90), duration=3.0, size=22, category="alert")
        return False

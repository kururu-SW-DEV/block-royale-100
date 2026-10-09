"""
Block Royale 100 - 방 만들기/참가/대기실 화면
BlockRoyaleApp(main.py)이 상속하는 믹스인: 메서드 본문은 원래 main.py에 있던 그대로이며 self로 앱 상태를 공유함
"""

from app_common import (
    C_ACCENT, C_DANGER, C_DIM, C_GOLD, C_GREEN, C_ORANGE, C_TEXT, NAME_COLORS,
    SCREEN_WIDTH, pygame, time
)
from settings_manager import BOT_DIFFICULTY_LABELS


def _diff_short(diff):
    return BOT_DIFFICULTY_LABELS.get(diff, "혼합").split(" (")[0]


def _mode_label(mode):
    return "서바이벌" if mode == "survival" else "배틀로얄"


from i18n import tr as _tr


class LobbyMixin:
    def _handle_host_lobby_event(self, event):
        """방장 대기실 입력 처리 (키보드/마우스)"""
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                self._host_start_game_action()
            elif event.key == pygame.K_ESCAPE:
                self._host_leave_lobby()
            elif event.key == pygame.K_d:
                self._lobby_cycle_difficulty(1)
            elif event.key == pygame.K_g:
                self._lobby_toggle_mode()
            elif event.key == pygame.K_t:
                self._lobby_toggle_team()
            elif event.key == pygame.K_c and (event.mod & pygame.KMOD_CTRL):
                self._copy_room_address()
            elif event.key in [pygame.K_LEFT, pygame.K_DOWN]:
                self.adjust_player_count(-1)
            elif event.key in [pygame.K_RIGHT, pygame.K_UP]:
                self.adjust_player_count(1)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            chip = getattr(self, "addr_chip_rect", None)
            if chip is not None and chip.collidepoint(mx, my):
                self._copy_room_address()
                return
            for btn_id, rect in self.lobby_buttons.items():
                if rect.collidepoint(mx, my):
                    self.sound_mgr.play('move')
                    if btn_id == "start_game":
                        self._host_start_game_action()
                    elif btn_id == "back_menu":
                        self._host_leave_lobby()
                    elif btn_id in ("diff_prev", "diff_next"):
                        self._lobby_cycle_difficulty(-1 if btn_id == "diff_prev" else 1)
                    elif btn_id in ("mode_prev", "mode_next"):
                        self._lobby_toggle_mode()
                    elif btn_id == "team_toggle":
                        self._lobby_toggle_team()
                    elif btn_id == "dec_10":
                        self.adjust_player_count(-10)
                    elif btn_id == "dec_1":
                        self.adjust_player_count(-1)
                    elif btn_id == "inc_1":
                        self.adjust_player_count(1)
                    elif btn_id == "inc_10":
                        self.adjust_player_count(10)
                    break

    def _host_leave_lobby(self):
        """방장 대기실 나가기: 참가자가 있으면 방이 닫힌다는 확인을 먼저 받음"""
        n = len(self.net_mgr.clients)
        if n > 0:
            self._open_modal("방을 닫을까요?", [f"방장이 나가면 방이 닫히고 접속한 {n}명이 대기실에서 나가게 됩니다.", "정말 나가시겠습니까?"],
                             [("stay", "방 유지", "blue", "ESC"), ("close_room", "방 닫기", "red", "Y")])
        else:
            self.net_mgr.stop()
            self.state = "MENU"

    def _lobby_cycle_difficulty(self, step):
        self.settings.cycle_bot_difficulty(step)
        self.bot_difficulty = self.settings.get("bot_difficulty")
        self.sound_mgr.play('move')

    def _lobby_toggle_mode(self):
        new = "battle" if self.settings.get("game_mode") == "survival" else "survival"
        self.settings.set("game_mode", new)
        self.sound_mgr.play('move')

    def _lobby_toggle_team(self):
        self.settings.set("rule_team", not bool(self.settings.get("rule_team", False)))
        self.sound_mgr.play('move')

    def _copy_room_address(self):
        """접속 주소(IP:포트)를 클립보드에 복사 (실패해도 게임은 계속)"""
        text = f"{self.local_ip}:{self.host_port}"
        try:
            pygame.scrap.init()
            pygame.scrap.put_text(text)
            self._copy_notice_until = time.time() + 2.0
            self.sound_mgr.play('rotate')
        except Exception:
            self._copy_notice_until = 0.0

    def _handle_join_menu_event(self, event):
        """접속 화면(IP 입력/방 목록) 입력 처리 (키보드/마우스)"""
        if event.type == pygame.KEYDOWN:
            rows = getattr(self, "join_rows", None) or []
            if event.key == pygame.K_ESCAPE:
                self.join_sel = None
                self.state = "MENU"
            elif event.key in (pygame.K_UP, pygame.K_DOWN) and rows:
                cur = getattr(self, "join_sel", None)           # ↑↓(패드 십자키): 방 목록 선택, 첫 줄에서 ↑이면 선택 해제(주소 입력 상태로)
                if event.key == pygame.K_DOWN:
                    cur = 0 if cur is None else min(len(rows) - 1, cur + 1)
                else:
                    cur = None if (cur is None or cur <= 0) else cur - 1
                self.join_sel = cur
                self.sound_mgr.play('move')
            elif event.key == pygame.K_BACKSPACE:
                self.join_sel = None
                self.join_ip_input = self.join_ip_input[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                sel = getattr(self, "join_sel", None)
                if sel is not None and sel < len(rows):
                    self._join_row(rows[sel])                   # 고른 방에 참가
                elif not self.join_ip_input.strip() and rows:
                    self._join_row(rows[0])                     # 주소를 안 적었으면 목록의 첫 방 (패드 A만으로도 참가)
                else:
                    self._join_by_input()
            elif event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL):
                try:                                    # Ctrl+V 붙여넣기 (클립보드의 IP 주소)
                    pygame.scrap.init()
                    clip = pygame.scrap.get_text() or ""
                    clip = "".join(ch for ch in clip.strip() if ch.isalnum() or ch in ".:-")
                    self.join_ip_input = clip[:40] or self.join_ip_input
                except Exception:
                    pass
            else:
                if len(self.join_ip_input) < 40 and (event.unicode.isalnum() or event.unicode in ".:-"):
                    self.join_sel = None
                    self.join_ip_input += event.unicode
                    
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            # 뒤로가기 버튼
            if hasattr(self, 'join_back_btn') and self.join_back_btn.collidepoint(mx, my):
                self.sound_mgr.play('move')
                self.state = "MENU"
                return
            # 접속 버튼
            if hasattr(self, 'join_connect_btn') and self.join_connect_btn.collidepoint(mx, my):
                self.sound_mgr.play('move')
                self._join_by_input()
                return
            # 목록의 방 클릭 시 접속
            for row in getattr(self, "join_rows", []):
                rect = row.get("rect")
                if rect and rect.collidepoint(mx, my):
                    self._join_row(row)
                    break

    def _join_row(self, row):
        """방 목록의 한 줄에 참가 (마우스 클릭/키보드·패드 선택 공용)"""
        self.sound_mgr.play('move')
        self.join_ip_input = row["host"] if row["port"] == self.host_port else f"{row['host']}:{row['port']}"
        self._join_by_input()

    def _handle_client_lobby_event(self, event):
        """참가자 대기실 입력 처리 (키보드/마우스)"""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.net_mgr.stop()
                self.state = "MENU"
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if hasattr(self, 'client_leave_btn') and self.client_leave_btn.collidepoint(mx, my):
                self.sound_mgr.play('move')
                self.net_mgr.stop()
                self.state = "MENU"
                

    def _update_host_lobby(self, dt):
        self.menu_bg.update(dt)
        rs = self.net_mgr.room_settings
        if self.net_mgr.mode == "HOST":
            self.net_mgr.reap_clients(lobby=True)              # 대기실에서 응답이 끊긴 참가자 정리
            diff, mode = self.settings.get("bot_difficulty", "mixed"), self.settings.get("game_mode", "battle")
            team = bool(self.settings.get("rule_team", False)) and mode != "survival"
            if rs.get("max_players") != self.target_player_count and self.net_mgr.mode == "HOST":
                rs["max_players"] = self.target_player_count         # 방 목록 표시와 입장 제한이 방장이 고른 인원을 따르게
            if rs.get("target") != self.target_player_count or rs.get("diff") != diff or rs.get("mode") != mode or rs.get("team") != team:
                rs["target"], rs["diff"], rs["mode"], rs["team"] = self.target_player_count, diff, mode, team
                self.net_mgr.host_broadcast_roster()           # 인원/난이도/모드가 바뀌면 참가자 대기실에도 바로 알림

    def _update_join_menu(self, dt):
        self.menu_bg.update(dt)
        # 입력한 주소(입력이 멈춘 뒤)와 최근 주소들을 주기적으로 조회해서 방이 열려 있으면 목록에 바로 표시
        if self.join_ip_input != getattr(self, "_join_last_text", None):
            self._join_last_text = self.join_ip_input
            self._join_stable = 0.0
        else:
            self._join_stable = getattr(self, "_join_stable", 0.0) + dt
        self._join_probe_tick = getattr(self, "_join_probe_tick", 0.0) + dt
        if self._join_probe_tick >= 0.4:
            self._join_probe_tick = 0.0
            targets = []
            if self.join_ip_input.strip() and self._join_stable >= 0.35:
                targets.append(self._parse_host_input(self.join_ip_input))
            for text in (self.settings.get("recent_hosts", []) or [])[:4]:
                targets.append(self._parse_host_input(text))
            for host, port in dict.fromkeys(targets):
                self.net_mgr.probe_async(host, port)

    def _update_client_lobby(self, dt):
        self.menu_bg.update(dt)
        ack = self.net_mgr.profile_ack
        if ack:                                    # 호스트가 확정해 준 이름/색 (이름이 겹치면 #번호가 붙음)
            self.net_mgr.profile_ack = None
            self.player_name = ack["name"]
            self.name_color = ack["color"]
        if self.net_mgr.host_left and not self._notice_shown:
            self._notice_shown = True
            self._open_modal("방이 닫혔습니다", ["방장이 대기실을 나가서 방이 닫혔습니다."],
                             [("ok_menu", "메인 메뉴로", "blue", "ENTER")])
        elif self.net_mgr.join_rejected and not self._notice_shown:
            self._notice_shown = True
            why = {"full": "방이 가득 찼습니다.", "started": "이미 경기가 진행 중입니다. 다음 경기를 기다려 주세요.",
                   "version": "게임 버전이 호스트와 달라 입장할 수 없습니다. 같은 버전으로 맞춰 주세요.",
                   "unresolved": "입력한 주소를 찾을 수 없습니다. 주소를 다시 확인해 주세요."}[self.net_mgr.join_rejected]
            self._open_modal("입장할 수 없습니다", [why], [("ok_menu", "메인 메뉴로", "blue", "ENTER")])
        elif self.net_mgr.connected and not self._notice_shown and self.net_mgr.seconds_since_host_packet() > 8.0:
            self._notice_shown = True                   # 호스트가 사라졌는데 대기실에 영원히 남는 것 방지
            self._open_modal("호스트와 연결이 끊겼습니다", ["8초 이상 호스트에게서 응답이 없습니다.", "호스트가 종료되었거나 네트워크에 문제가 있을 수 있습니다."],
                             [("ok_menu", "메인 메뉴로", "blue", "ENTER")])
        # 호스트 응답이 없으면 1초마다 참가 요청을 다시 보냄 (첫 패킷이 유실되거나 호스트가 늦게 열려도 접속됨)
        if not self.net_mgr.connected:
            self._join_retry_timer = getattr(self, "_join_retry_timer", 0.0) + dt
            if self._join_retry_timer >= 1.0:
                self._join_retry_timer = 0.0
                self.net_mgr.client_retry_join()
        # 호스트가 게임을 시작하면 클라이언트도 게임 시작
        if self.net_mgr.game_started:
            init_players = getattr(self.net_mgr, 'initial_players', None)
            total_p = len(init_players) if init_players else self.net_mgr.room_settings.get("max_players", self.target_player_count)
            self.start_game(mode="CLIENT", total_players=total_p, initial_players=init_players)

    def _parse_host_input(self, text):
        """'192.168.0.5' 또는 '192.168.0.5:19999' 형태를 (호스트, 포트)로 분리. 포트가 없거나 잘못되면 기본 포트."""
        text = (text or "").strip()
        host, port = text, self.host_port
        if ":" in text:
            h, _, p = text.rpartition(":")
            if h and p.isdigit() and 1 <= int(p) <= 65535:
                host, port = h.strip(), int(p)
            elif h and (not p or p.isdigit()):      # 포트가 비었거나 범위를 벗어나면 주소만 사용
                host = h.strip()
        return (host or "127.0.0.1"), port

    def _enter_join_menu(self):
        """방 참가 화면 진입: 마지막으로 입력한 주소를 채워 넣고 조회 시작"""
        last = self.settings.get("last_host", "") or ""
        if last:
            self.join_ip_input = last
        self._join_last_text = None
        self._join_stable = 0.0
        self._join_probe_tick = 0.0
        self.state = "JOIN_MENU"

    def _remember_host(self, host, port):
        """접속을 시도한 주소를 저장 (다음에 화면을 열면 자동 입력 + 최근 목록에 표시)"""
        text = host if port == self.host_port else f"{host}:{port}"
        recents = [r for r in (self.settings.get("recent_hosts", []) or []) if r != text]
        recents.insert(0, text)
        self.settings.set("recent_hosts", recents[:6], autosave=False)
        self.settings.set("last_host", text)

    def _build_join_rows(self):
        """참가 화면 목록: 입력한 주소 -> LAN에서 발견된 방 -> 최근 접속 주소 (중복 제거, 최대 4개)"""
        rows, seen = [], set()
        rooms = list(self.net_mgr.discovered_rooms.values())

        def add(host, port, tag):
            key = (host, port)
            if not host or key in seen:
                return
            seen.add(key)
            row = {"host": host, "port": port, "tag": tag, "ok": False}
            lan = next((r for r in rooms if r["ip"] == host and r["port"] == port), None)
            probe = self.net_mgr.probe_results.get(key)
            if lan:
                row.update(ok=True, name=lan["room_name"], players=lan["players"], max=lan["max_players"], open=True)
            elif probe and probe.get("ok"):
                row.update(ok=True, name=probe["room_name"], players=probe["players"], max=probe["max_players"],
                           open=probe.get("open", True))
            rows.append(row)

        if self.join_ip_input.strip():
            add(*self._parse_host_input(self.join_ip_input), "입력한 주소")
        for r in rooms:
            add(r["ip"], r["port"], "LAN")
        for text in (self.settings.get("recent_hosts", []) or []):
            add(*self._parse_host_input(text), "최근 접속")
        return rows[:4]

    def _join_by_input(self):
        host, port = self._parse_host_input(self.join_ip_input)
        self._remember_host(host, port)
        self._notice_shown = False
        if self.net_mgr.start_client(host, port, self.player_name):
            self._join_retry_timer = 0.0
            self.state = "CLIENT_LOBBY"
        else:
            self._open_modal("접속할 수 없습니다", [f"'{host}' 주소를 찾을 수 없거나 연결을 시작하지 못했습니다.", "주소를 다시 확인해 주세요."],
                             [("stay", "확인", "blue", "ENTER")])

    def _start_host_room(self):
        """방 만들기: 저장된 방 제목(없으면 기본 제목)으로 호스트를 시작"""
        name = (self.room_name_input or "").strip() or self._default_room_name()
        self.room_name_input = name
        if self.net_mgr.start_host(port=self.host_port, room_name=name, max_players=self.target_player_count):
            self.net_mgr.room_settings["host_name"] = self.player_name
            self._end_text(commit=False)
            self.state = "HOST_LOBBY"
            return True
        self._open_modal("방을 만들 수 없습니다", [f"포트 {self.host_port}을(를) 사용할 수 없습니다.", "이미 실행 중인 다른 방이 있거나 다른 프로그램이 포트를 쓰고 있습니다."],
                         [("stay", "확인", "blue", "ENTER")])
        return False

    def _render_host_lobby(self):
        self.menu_bg.draw(self.screen)
        self.text_rects.clear()
        mx, my = pygame.mouse.get_pos()
        cx = SCREEN_WIDTH // 2
        self._menu_header("대기실  ·  호스트", None, accent=C_GREEN)

        addr = self.renderer._text(f"접속 주소  {self.local_ip}:{self.host_port}", self.font_mid, C_ACCENT)
        chip = pygame.Rect(cx - addr.get_width() // 2 - 16, 114, addr.get_width() + 32, 32)
        pygame.draw.rect(self.screen, (22, 30, 52), chip, border_radius=16)
        pygame.draw.rect(self.screen, (60, 100, 160), chip, 1, border_radius=16)
        self.screen.blit(addr, (chip.x + 16, chip.centery - addr.get_height() // 2))
        self.addr_chip_rect = chip                           # 클릭하면 복사
        copied = time.time() < getattr(self, "_copy_notice_until", 0.0)
        if copied or chip.collidepoint(mx, my):                  # 평소에는 숨기고 올렸을 때만 안내 (화면이 덜 산만하게)
            self._t("복사됨!" if copied else "클릭해서 복사", self.font_tiny, C_GREEN if copied else C_DIM, chip.right + 12, chip.centery, "midleft")

        box_w, box_h = 720, 604
        box_x = 133
        box_y = 156
        self._glass((box_x, box_y, box_w, box_h), accent=(50, 150, 105), radius=18)
        self._draw_chat_panel(pygame.Rect(box_x + box_w + 20, box_y, 360, box_h))

        # 방 제목 (클릭해서 수정): 라벨은 입력칸 안쪽에 작게
        name_box = pygame.Rect(box_x + 28, box_y + 18, box_w - 56, 42)
        self.text_rects["room_name"] = name_box
        editing = (self.text_focus == "room_name")
        pygame.draw.rect(self.screen, (11, 13, 24), name_box, border_radius=10)
        pygame.draw.rect(self.screen, C_ACCENT if editing else (60, 74, 110), name_box, 2 if editing else 1, border_radius=10)
        label_r = self._t("방 제목", self.font_small, C_DIM, name_box.x + 16, name_box.centery, "midleft")
        shown_name = self.room_name_input + (self.chat_comp if editing else "")
        if not editing and not shown_name.strip():
            shown_name = self._default_room_name()
        t = self._t(shown_name, self.font_mid, C_TEXT, max(name_box.x + 92, label_r.right + 14), name_box.centery, "midleft")         # 영어 라벨이 길어도 방 이름과 붙지 않게
        if editing and int(time.time() * 2) % 2 == 0:
            pygame.draw.rect(self.screen, C_ACCENT, (t.right + 3, name_box.y + 9, 2, name_box.h - 18))

        # 참가자: 제목 한 줄(인원 + 봇 충원) + 목록
        clients = list(self.net_mgr.clients.values())
        human_count = 1 + len(clients)
        bot_fill = max(0, self.target_player_count - human_count)
        self._t("참가자", self.font_menu, C_TEXT, box_x + 32, box_y + 80)
        self._t(f"{human_count} / {self.target_player_count} 명", self.font_menu, C_GOLD, box_x + 120, box_y + 80)
        self._t(f"나머지 {bot_fill}명은 AI 봇", self.font_small, C_DIM, box_x + box_w - 32, box_y + 86, "topright")

        rows = [(f"{self.player_name}", "방장", NAME_COLORS[self.name_color][1])]
        rows += [(c["name"], c["id"], NAME_COLORS[c.get("color", 0)][1]) for c in clients]
        shown = rows[:4]
        for i, (name, tag, col) in enumerate(shown):
            row = pygame.Rect(box_x + 28, box_y + 118 + i * 34, box_w - 56, 30)
            pygame.draw.rect(self.screen, (24, 32, 54) if i else (22, 48, 44), row, border_radius=8)
            pygame.draw.circle(self.screen, col, (row.x + 16, row.centery), 5)
            self._t(name, self.font_info, col, row.x + 32, row.centery, "midleft")
            tag_r = self._t(tag, self.font_small, C_DIM, row.right - 14, row.centery, "midright")
            sp = self.net_mgr.session_scores.get(name, 0)
            if sp:                                                                      # 같은 방에서 연달아 한 판들의 승점 (이긴 판에 10점, K.O.마다 +1)
                self._t(f"{sp}점", self.font_small, C_GOLD, tag_r.x - 14, row.centery, "midright")
        if len(rows) > len(shown):
            self._t(f"외 {len(rows) - len(shown)}명 더 접속 중", self.font_small, C_DIM, box_x + 34, box_y + 118 + 4 * 34 + 2)

        # 경기 설정: 한 장의 카드 안에 같은 간격의 4행 (방을 닫지 않고 여기서 바로 바꿈, 참가자 대기실에도 표시됨)
        card = pygame.Rect(box_x + 28, box_y + 272, box_w - 56, 242)
        pygame.draw.rect(self.screen, (13, 17, 31), card, border_radius=12)
        pygame.draw.rect(self.screen, (40, 52, 82), card, 1, border_radius=12)
        self._t("경기 설정", self.font_small, C_DIM, card.x + 18, card.y + 12)
        cur_diff = self.settings.get("bot_difficulty", "mixed")
        cur_mode = "survival" if self.settings.get("game_mode") == "survival" else "battle"
        team_on = bool(self.settings.get("rule_team", False)) and cur_mode != "survival"
        ry = card.y + 40
        cx0 = card.x + 170
        self._t("대전 인원", self.font_mid, C_TEXT, card.x + 18, ry + 17, "midleft")
        self._stepper(self.lobby_buttons, "", ry, cx0, f"{self.target_player_count} 명", C_GOLD,
                      [("dec_10", "-10", 48), ("dec_1", "-1", 42)], [("inc_1", "+1", 42), ("inc_10", "+10", 48)])
        self._t("봇 난이도", self.font_mid, C_TEXT, card.x + 18, ry + 44 + 17, "midleft")
        self._stepper(self.lobby_buttons, "", ry + 44, cx0, _diff_short(cur_diff), C_ORANGE,
                      [("diff_prev", "◀", 48)], [("diff_next", "▶", 48)])
        self._t("게임 모드", self.font_mid, C_TEXT, card.x + 18, ry + 88 + 17, "midleft")
        self._stepper(self.lobby_buttons, "", ry + 88, cx0, _mode_label(cur_mode), C_GREEN,
                      [("mode_prev", "◀", 48)], [("mode_next", "▶", 48)])
        self._t("팀전 (2팀)", self.font_mid, C_TEXT, card.x + 18, ry + 132 + 17, "midleft")
        trect = pygame.Rect(cx0, ry + 132, 214, 34)
        self.lobby_buttons["team_toggle"] = trect
        pygame.draw.rect(self.screen, (24, 52, 46) if team_on else (14, 17, 30), trect, border_radius=8)
        pygame.draw.rect(self.screen, (90, 225, 150) if team_on else (70, 82, 112), trect, 2 if trect.collidepoint(mx, my) else 1, border_radius=8)
        self._t("켜짐" if team_on else "꺼짐", self.font_small, (120, 235, 170) if team_on else C_DIM, trect.centerx, trect.centery, "center")
        if team_on:
            self._t("같은 편은 공격 안 함", self.font_small, C_DIM, trect.right + 14, trect.centery, "midleft")
        self._t("단축키   D 난이도  ·  G 모드  ·  T 팀전  ·  ← → 인원", self.font_tiny, C_DIM, card.centerx, card.bottom - 15, "center")

        start = pygame.Rect(box_x + 28, box_y + box_h - 74, 440, 52)
        back = pygame.Rect(start.right + 14, start.y, box_w - 56 - 440 - 14, 52)
        self.lobby_buttons['start_game'] = start
        self.lobby_buttons['back_menu'] = back
        self.renderer._button(start, "게임 시작", "green", start.collidepoint(mx, my), "ENTER")
        self.renderer._button(back, "나가기", "red", back.collidepoint(mx, my), "ESC")

    def _render_join_menu(self):
        self.menu_bg.draw(self.screen)
        mx, my = pygame.mouse.get_pos()
        cx = SCREEN_WIDTH // 2
        self._menu_header("방 참가", "호스트 IP를 입력하거나 LAN에서 발견된 방을 선택하세요", accent=C_GOLD)

        box_w, box_h = 720, 520
        box_x = (SCREEN_WIDTH - box_w) // 2
        box_y = 150
        self._glass((box_x, box_y, box_w, box_h), accent=(170, 130, 60), radius=18)

        self._t("호스트 IP 주소", self.font_mid, C_TEXT, box_x + 32, box_y + 24)
        input_rect = pygame.Rect(box_x + 32, box_y + 56, 440, 48)
        pygame.draw.rect(self.screen, (11, 13, 24), input_rect, border_radius=10)
        pygame.draw.rect(self.screen, C_ACCENT, input_rect, 2, border_radius=10)
        # 입력 글자는 고정하고 캐럿만 별도로 깜박여서 글자가 흔들리지 않게 함
        txt_rect = self._t(self.join_ip_input, self.font_input, C_TEXT, input_rect.x + 16, input_rect.centery, "midleft")
        if int(time.time() * 2) % 2 == 0:
            pygame.draw.rect(self.screen, C_ACCENT, (txt_rect.right + 3, input_rect.y + 10, 2, input_rect.h - 20))
        host, port = self._parse_host_input(self.join_ip_input)
        self._t(f"접속 대상  {host}:{port}   (포트를 생략하면 {self.host_port})", self.font_tiny, C_DIM, input_rect.x, input_rect.bottom + 8)

        self.join_connect_btn = pygame.Rect(input_rect.right + 14, input_rect.y, box_w - 64 - 440 - 14, 48)
        self.renderer._button(self.join_connect_btn, "접속하기", "blue", self.join_connect_btn.collidepoint(mx, my), "ENTER")

        self._t("방 목록", self.font_mid, C_ACCENT, box_x + 32, box_y + 150)
        self._t("입력한 주소, LAN에서 찾은 방, 최근 접속한 주소가 표시됩니다  ·  클릭하면 참가", self.font_tiny, C_DIM,
                box_x + box_w - 32, box_y + 154, "topright")

        self.join_rows = self._build_join_rows()
        if not self.join_rows:
            dots = "." * (int(time.time() * 2) % 4)
            self._t(f"주소를 입력하거나, LAN의 방을 찾는 중{dots}", self.font_info, C_DIM, cx, box_y + 240, "midtop")
        for i, row in enumerate(self.join_rows):
            r_rect = pygame.Rect(box_x + 32, box_y + 186 + i * 62, box_w - 64, 54)
            row["rect"] = r_rect
            hover = r_rect.collidepoint(mx, my) or getattr(self, "join_sel", None) == i        # 키보드/패드로 고른 줄도 같은 강조
            ok = row["ok"]
            pygame.draw.rect(self.screen, (34, 46, 76) if hover else (24, 32, 54), r_rect, border_radius=10)
            pygame.draw.rect(self.screen, C_ACCENT if hover else ((52, 90, 108) if ok else (46, 56, 86)), r_rect,
                             2 if hover else 1, border_radius=10)
            pygame.draw.circle(self.screen, C_GREEN if ok else (90, 98, 125), (r_rect.x + 20, r_rect.y + 19), 5)
            if ok:
                name = str(row["name"])
                name = name if len(name) <= 24 else name[:23] + "…"
                self._t(name, self.font_mid, C_TEXT, r_rect.x + 36, r_rect.y + 8)
                right = f"{row['players']} / {row['max']} 명" if row.get("open", True) else "게임 진행 중"
                self._t(right, self.font_mid, C_GOLD if row.get("open", True) else C_DANGER, r_rect.right - 18, r_rect.centery, "midright")
            else:
                self._t("응답 없음 (그래도 클릭하면 접속을 시도합니다)", self.font_small, C_DIM, r_rect.x + 36, r_rect.y + 9)
            tag_col = {"입력한 주소": C_ACCENT, "LAN": C_GREEN, "최근 접속": C_GOLD}.get(row["tag"], C_DIM)
            self._t(f"{row['host']}:{row['port']}", self.font_small, C_DIM, r_rect.x + 36, r_rect.y + 32)
            self._t(row["tag"], self.font_tiny, tag_col, r_rect.x + 36 + 190, r_rect.y + 34)

        self.join_back_btn = pygame.Rect(box_x + 32, box_y + box_h - 68, box_w - 64, 46)
        self.renderer._button(self.join_back_btn, "메인 메뉴로", "blue", self.join_back_btn.collidepoint(mx, my), "ESC")

    def _render_client_lobby(self):
        self.menu_bg.draw(self.screen)
        self.text_rects.clear()
        mx, my = pygame.mouse.get_pos()
        self._menu_header("대기실  ·  참가자", None, accent=C_ACCENT)

        box_w, box_h = 620, 500
        box_x = 183
        box_y = 150
        connected = self.net_mgr.connected
        self._glass((box_x, box_y, box_w, box_h), accent=C_GREEN if connected else C_ORANGE, radius=18)
        self._draw_chat_panel(pygame.Rect(box_x + box_w + 20, box_y, 360, box_h))
        pcx = box_x + box_w // 2

        if connected:
            pygame.draw.circle(self.screen, C_GREEN, (box_x + 40, box_y + 38), 8)
            self._t("호스트 방에 접속했습니다", self.font_menu, C_GREEN, box_x + 58, box_y + 24)
            room = str(self.net_mgr.room_settings.get("room_name", "") or "")
            if room:
                self._t(f"방 제목   {room[:30]}", self.font_mid, C_TEXT, box_x + 32, box_y + 66)
            dots = "." * (int(time.time() * 2) % 4)
            self._t(f"방장이 게임을 시작하면 자동으로 시작됩니다{dots}", self.font_small, C_DIM, box_x + 32, box_y + 98)

            # 전체 참가자 명단 (호스트가 보내준 목록)
            roster = self.net_mgr.roster or []
            target = self.net_mgr.roster_target or self.net_mgr.room_settings.get("max_players", 0)
            self._t("접속한 플레이어", self.font_menu, C_TEXT, box_x + 32, box_y + 134)
            self._t(f"{len(roster)} / {target} 명" if target else f"{len(roster)} 명", self.font_menu, C_GOLD,
                    box_x + box_w - 32, box_y + 134, "topright")
            my_id = self.net_mgr.my_player_id
            shown = roster[:5]
            for i, e in enumerate(shown):
                row = pygame.Rect(box_x + 28, box_y + 176 + i * 36, box_w - 56, 32)
                is_me = (e["id"] == my_id)
                pygame.draw.rect(self.screen, (22, 48, 44) if e["host"] else ((22, 42, 60) if is_me else (24, 32, 54)), row, border_radius=8)
                col = NAME_COLORS[e["color"]][1]
                pygame.draw.circle(self.screen, col, (row.x + 16, row.centery), 5)
                self._t(e["name"] + ("  (나)" if is_me else ""), self.font_info, col, row.x + 32, row.centery, "midleft")
                tag_r = self._t("방장" if e["host"] else e["id"], self.font_small, C_GOLD if e["host"] else C_DIM,
                                row.right - 14, row.centery, "midright")
                sp = self.net_mgr.session_scores.get(e["name"], 0)
                if sp:
                    self._t(f"{sp}점", self.font_small, C_GOLD, tag_r.x - 14, row.centery, "midright")
            if len(roster) > len(shown):
                self._t(f"외 {len(roster) - len(shown)}명 더 접속 중", self.font_small, C_DIM, box_x + 32, box_y + 176 + 5 * 36 + 2)
            if not roster:
                self._t("명단을 불러오는 중...", self.font_small, C_DIM, box_x + 32, box_y + 180)
        else:
            pygame.draw.circle(self.screen, C_ORANGE, (pcx, box_y + 52), 9)
            self._t("호스트 응답을 기다리는 중", self.font_menu, C_ORANGE, pcx, box_y + 76, "midtop")
            self._t("주소와 포트가 맞는지, 방화벽이 UDP를 막지 않는지 확인하세요", self.font_small, C_DIM, pcx, box_y + 116, "midtop")

        if connected:
            rules = self.net_mgr.room_rules or {}
            tg = self.net_mgr.roster_target or self.net_mgr.room_settings.get("max_players", 0)
            parts = ([f"{tg}인"] if tg else []) + [_mode_label(rules.get("mode", "battle")), f"{_diff_short(rules.get('diff', 'mixed'))} 봇"] + (["팀전"] if rules.get("team") else [])
            self._t(_tr("경기 규칙") + "   " + " · ".join(_tr(x) for x in parts), self.font_mid, C_GOLD, box_x + 32, box_y + box_h - 120)
        self.client_leave_btn = pygame.Rect(pcx - 140, box_y + box_h - 74, 280, 50)
        self.renderer._button(self.client_leave_btn, "방 나가기", "red", self.client_leave_btn.collidepoint(mx, my), "ESC")

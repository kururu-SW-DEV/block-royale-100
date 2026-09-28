"""
Block Royale 100 - 방 만들기/참가/대기실 화면
BlockRoyaleApp(main.py)이 상속하는 믹스인: 메서드 본문은 원래 main.py에 있던 그대로이며 self로 앱 상태를 공유함
"""

from app_common import (
    C_ACCENT, C_DANGER, C_DIM, C_GOLD, C_GREEN, C_ORANGE, C_TEXT, NAME_COLORS,
    SCREEN_WIDTH, pygame, time
)


class LobbyMixin:
    def _update_host_lobby(self, dt):
        self.menu_bg.update(dt)
        if self.net_mgr.mode == "HOST" and self.net_mgr.room_settings.get("target") != self.target_player_count:
            self.net_mgr.room_settings["target"] = self.target_player_count
            self.net_mgr.host_broadcast_roster()

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
            why = {"full": "방이 가득 찼습니다.", "started": "이미 경기가 진행 중입니다. 다음 경기를 기다려 주세요."}[self.net_mgr.join_rejected]
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

        box_w, box_h = 720, 500
        box_x = 133
        box_y = 156
        self._glass((box_x, box_y, box_w, box_h), accent=(50, 150, 105), radius=18)
        self._draw_chat_panel(pygame.Rect(box_x + box_w + 20, box_y, 360, box_h))

        # 방 제목 (클릭해서 수정)
        self._t("방 제목", self.font_mid, C_TEXT, box_x + 32, box_y + 28)
        name_box = pygame.Rect(box_x + 118, box_y + 18, box_w - 150, 40)
        self.text_rects["room_name"] = name_box
        editing = (self.text_focus == "room_name")
        pygame.draw.rect(self.screen, (11, 13, 24), name_box, border_radius=10)
        pygame.draw.rect(self.screen, C_ACCENT if editing else (60, 74, 110), name_box, 2 if editing else 1, border_radius=10)
        shown_name = self.room_name_input + (self.chat_comp if editing else "")
        if not editing and not shown_name.strip():
            shown_name = self._default_room_name()
        t = self._t(shown_name, self.font_mid, C_TEXT, name_box.x + 14, name_box.centery, "midleft")
        if editing and int(time.time() * 2) % 2 == 0:
            pygame.draw.rect(self.screen, C_ACCENT, (t.right + 3, name_box.y + 8, 2, name_box.h - 16))
        if not editing:
            self._t("클릭해서 수정", self.font_tiny, C_DIM, name_box.right - 12, name_box.centery, "midright")

        clients = list(self.net_mgr.clients.values())
        human_count = 1 + len(clients)
        self._t("접속한 플레이어", self.font_menu, C_TEXT, box_x + 32, box_y + 76)
        self._t(f"{human_count} / {self.target_player_count} 명", self.font_menu, C_GOLD, box_x + box_w - 32, box_y + 76, "topright")

        rows = [(f"{self.player_name}", "방장 (나)", NAME_COLORS[self.name_color][1])]
        rows += [(c["name"], c["id"], NAME_COLORS[c.get("color", 0)][1]) for c in clients]
        shown = rows[:5]
        for i, (name, tag, col) in enumerate(shown):
            row = pygame.Rect(box_x + 28, box_y + 116 + i * 36, box_w - 56, 32)
            pygame.draw.rect(self.screen, (24, 32, 54) if i else (22, 48, 44), row, border_radius=8)
            pygame.draw.circle(self.screen, col, (row.x + 16, row.centery), 5)
            self._t(name, self.font_info, col, row.x + 32, row.centery, "midleft")
            self._t(tag, self.font_small, C_DIM, row.right - 14, row.centery, "midright")
        if len(rows) > len(shown):
            self._t(f"외 {len(rows) - len(shown)}명 더 접속 중", self.font_small, C_DIM, box_x + 32, box_y + 116 + 5 * 36 + 2)

        bot_fill = max(0, self.target_player_count - human_count)
        self._t(f"부족한 {bot_fill}명은 AI 봇으로 자동 충원됩니다", self.font_small, C_ORANGE, box_x + box_w // 2, box_y + 342, "midtop")

        self._t("대전 인원", self.font_mid, C_TEXT, box_x + 32, box_y + 372)
        self._stepper(self.lobby_buttons, "", box_y + 366, box_x + 180, f"{self.target_player_count} 명", C_GOLD,
                      [("dec_10", "-10", 48), ("dec_1", "-1", 42)], [("inc_1", "+1", 42), ("inc_10", "+10", 48)])

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
            hover = r_rect.collidepoint(mx, my)
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

        box_w, box_h = 620, 470
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
                self._t("방장" if e["host"] else e["id"], self.font_small, C_GOLD if e["host"] else C_DIM,
                        row.right - 14, row.centery, "midright")
            if len(roster) > len(shown):
                self._t(f"외 {len(roster) - len(shown)}명 더 접속 중", self.font_small, C_DIM, box_x + 32, box_y + 176 + 5 * 36 + 2)
            if not roster:
                self._t("명단을 불러오는 중...", self.font_small, C_DIM, box_x + 32, box_y + 180)
        else:
            pygame.draw.circle(self.screen, C_ORANGE, (pcx, box_y + 52), 9)
            self._t("호스트 응답을 기다리는 중", self.font_menu, C_ORANGE, pcx, box_y + 76, "midtop")
            self._t("주소와 포트가 맞는지, 방화벽이 UDP를 막지 않는지 확인하세요", self.font_small, C_DIM, pcx, box_y + 116, "midtop")

        self.client_leave_btn = pygame.Rect(pcx - 140, box_y + box_h - 74, 280, 50)
        self.renderer._button(self.client_leave_btn, "방 나가기", "red", self.client_leave_btn.collidepoint(mx, my), "ESC")

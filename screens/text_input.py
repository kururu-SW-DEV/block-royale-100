"""
Block Royale 100 - 텍스트 입력(채팅/방 제목/이름) 처리 - 한글 IME 포함
BlockRoyaleApp(main.py)이 상속하는 믹스인: 메서드 본문은 원래 main.py에 있던 그대로이며 self로 앱 상태를 공유함
"""

from app_common import pygame


class TextInputMixin:
    TEXT_LIMITS = {"chat": 120, "room_name": 24, "player_name": 16}

    def _default_room_name(self):
        return f"{self.player_name}의 방"

    def _begin_text(self, field):
        self.text_focus = field
        if field == "player_name":
            self.player_name_input = self.player_name
        self.chat_comp = ""
        self.key_left_down = self.key_right_down = self.key_down_down = False
        self.h_dir = 0
        try:
            pygame.key.start_text_input()
            pygame.key.set_repeat(400, 45)          # 지우기 키 반복
        except Exception:
            pass

    def _end_text(self, commit=True):
        if self.text_focus is None:
            return
        if self.text_focus == "room_name":
            name = (self.room_name_input or "").strip()[:self.TEXT_LIMITS["room_name"]] or self._default_room_name()
            self.room_name_input = name
            if self.net_mgr.mode == "HOST":
                self.net_mgr.room_settings["room_name"] = name
            self.settings.set("room_name", name)
        if self.text_focus == "player_name":
            name = "".join(ch for ch in (self.player_name_input or "") if ch.isprintable()).strip()[:16] or "Player_1"
            self.player_name = name
            self.settings.set("player_name", "" if name == "Player_1" else name)
            self._sync_profile()
        self.text_focus = None
        self.chat_comp = ""
        try:
            pygame.key.stop_text_input()
            pygame.key.set_repeat(0)
        except Exception:
            pass

    def _text_get(self, field):
        return {"chat": self.chat_input, "room_name": self.room_name_input, "player_name": self.player_name_input}[field]

    def _text_set(self, field, value):
        if field == "chat":
            self.chat_input = value
        elif field == "player_name":
            self.player_name_input = value
        else:
            self.room_name_input = value
            if self.net_mgr.mode == "HOST":          # 입력하는 즉시 LAN 검색/방 조회에 반영
                self.net_mgr.room_settings["room_name"] = value.strip() or self._default_room_name()

    def _text_input_event(self, event):
        """방 제목/채팅 입력 처리. 입력 중이면 게임/메뉴 키가 실행되지 않도록 이벤트를 소비(True 반환)."""
        in_lobby = self.state in ("HOST_LOBBY", "CLIENT_LOBBY")
        in_net_game = self.state == "GAME" and self.net_mgr.mode != "NONE" and self.match is not None
        in_settings = self.state == "SETTINGS" and self.settings_tab == "match"
        if not (in_lobby or in_net_game or in_settings):
            if self.text_focus:
                self._end_text(commit=False)
            return False
        if self.modal is not None:
            return False
        field = self.text_focus

        if event.type == pygame.TEXTINPUT and field:
            cur = self._text_get(field)
            add = "".join(ch for ch in event.text if ch.isprintable())
            self._text_set(field, (cur + add)[:self.TEXT_LIMITS[field]])
            self.chat_comp = ""
            return True
        if event.type == pygame.TEXTEDITING and field:
            self.chat_comp = event.text
            return True

        if event.type == pygame.KEYDOWN:
            if field:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if field == "chat":
                        text = self.chat_input.strip()
                        if text:
                            self.net_mgr.send_chat(text, self.player_name)
                        self.chat_input = ""
                        if in_net_game:
                            self._end_text()
                    else:
                        self._end_text()
                elif event.key == pygame.K_ESCAPE:
                    self._end_text()
                elif event.key == pygame.K_BACKSPACE and not self.chat_comp:
                    self._text_set(field, self._text_get(field)[:-1])
                return True
            if in_lobby and event.key == pygame.K_TAB:
                self._begin_text("chat")
                return True
            if in_net_game and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and not self.match.match_finished \
                    and (self.match.local_is_alive or getattr(self.match, "is_spectating", False)):
                self._begin_text("chat")
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and (in_lobby or in_settings):
            for idx, rect in enumerate(self.color_rects):
                if rect.collidepoint(event.pos):
                    self._set_name_color(idx)
                    return True
            for name, rect in self.text_rects.items():
                if rect.collidepoint(event.pos):
                    self._begin_text(name)
                    return True
            if field:
                self._end_text()
        return False

    def _set_name_color(self, idx):
        self.name_color = idx
        self.settings.set("name_color", idx)
        self.net_mgr.my_color = idx
        self.sound_mgr.play('rotate')
        self._sync_profile()

    def _sync_profile(self):
        """대기실에서 이름/색을 바꾸면 방에도 반영 (호스트는 즉시, 참가자는 호스트에 알린 뒤 확정값을 받음)"""
        nm = self.net_mgr
        if self.state not in ("HOST_LOBBY", "CLIENT_LOBBY", "SETTINGS"):
            return
        if nm.mode == "HOST":
            self.player_name = nm.host_set_profile(self.player_name, self.name_color)
        elif nm.mode == "CLIENT":
            nm.send_profile(self.player_name, self.name_color)
        else:
            nm.my_color = self.name_color

"""
Block Royale 100 - 화상 키보드 (이름/방 제목/채팅/접속 주소 입력용)
BlockRoyaleApp(main.py)이 상속하는 믹스인.
SteamOS(Proton)에서는 Steam 오버레이가 켜져 있으면 입력칸을 눌러도 Steam 키보드가 뜨지 않는다. 그래서 Proton에서만
게임이 직접 키보드를 그린다 (터치/마우스 클릭, 십자키+A, 패드 X = 지우기 · Y = 대문자 · LB = 한/영 · RB = 기호, Back = 완료, B = 취소).
키는 실제 입력 이벤트(TEXTINPUT/KEYDOWN)로 바꿔 기존 입력 처리에 그대로 넘기므로 입력칸마다 따로 만들 필요가 없다.
물리 키보드로 글자를 치면 화상 키보드는 저절로 닫힌다.
"""

from app_common import CANVAS, SCREEN_HEIGHT, SCREEN_WIDTH, pygame
from app_paths import running_under_wine
import osk as _osk

OSK_FIELD_LABELS = {"chat": "채팅", "room_name": "방 제목", "player_name": "플레이어 이름", "initials": "이니셜", "join_ip": "호스트 주소"}
_ARROWS = (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN)
KEY_W, KEY_H, KEY_GAP = 64, 46, 6


class OskMixin:
    osk = None                                              # 열려 있으면 {"page", "shift", "sel", "keys", "kind", "comp"}

    # ---------------------------------------------------------------- 열고 닫기
    def _osk_wanted(self):
        """화상 키보드를 띄울 환경인가: Proton(SteamOS)에서만 (Windows 등에서는 원래 키보드/Steam 키보드를 그대로 씀)"""
        try:
            return bool(running_under_wine())
        except Exception:
            return False

    def _osk_open(self, kind="text"):
        """kind: 'text'(text_focus 칸) / 'join_ip'(접속 화면의 주소 칸)"""
        self.osk = {"page": "en", "shift": False, "sel": (1, 0), "keys": [], "kind": kind, "comp": _osk.HangulComposer(), "prev_page": "en"}
        self._osk_focus_default()

    def _osk_close(self):
        self.osk = None

    def _osk_focus_default(self):
        self.osk["sel"] = (1, 0)

    def _osk_field(self):
        return "join_ip" if (self.osk and self.osk["kind"] == "join_ip") else self.text_focus

    def _osk_text(self):
        f = self._osk_field()
        if f == "join_ip":
            return self.join_ip_input
        return (self._text_get(f) + self.chat_comp) if f else ""

    # ---------------------------------------------------------------- 키 -> 입력 이벤트
    def _osk_fire(self, ev_type, **kw):
        ev = pygame.event.Event(ev_type, **kw)
        ev.osk = True
        self._handle_event(ev)

    def _osk_backspace(self):
        self._osk_fire(pygame.KEYDOWN, key=pygame.K_BACKSPACE, mod=0, unicode="\b", scancode=0)

    def _osk_insert(self, text):
        for ch in text:
            if self._osk_field() == "join_ip":
                self._osk_fire(pygame.KEYDOWN, key=ord(ch) if ch.isascii() else 0, mod=0, unicode=ch, scancode=0)
            else:
                self._osk_fire(pygame.TEXTINPUT, text=ch)

    def _osk_press(self, key):
        """키 하나를 누름. key = (보통, Shift) 글자 쌍 또는 기능 키 이름"""
        o = self.osk
        if o is None:
            return
        self.sound_mgr.play('move')
        comp = o["comp"]
        if isinstance(key, tuple):
            ch = key[1] if o["shift"] else key[0]
            if o["page"] == "ko" and ch in _osk.CHO + _osk.JUNG:
                ndel, new = comp.feed(ch)
                for _ in range(ndel):
                    self._osk_backspace()
                self._osk_insert(new)
            else:
                comp.reset()
                self._osk_insert(ch)
            o["shift"] = False
        elif key == "BACK":
            r = comp.backspace() if o["page"] == "ko" else None
            if r is not None:
                ndel, new = r
                for _ in range(ndel):
                    self._osk_backspace()
                self._osk_insert(new)
            else:
                comp.reset()
                self._osk_backspace()
        elif key == "SPACE":
            comp.reset()
            if self._osk_field() != "join_ip":
                self._osk_insert(" ")
        elif key == "SHIFT":
            o["shift"] = not o["shift"]
        elif key == "LANG":
            comp.reset()
            if self._osk_field() != "join_ip":                                     # 접속 주소는 영문/숫자만
                o["page"] = "ko" if o["page"] != "ko" else "en"
                o["prev_page"] = o["page"]
        elif key == "SYM":
            comp.reset()
            if o["page"] == "sym":
                o["page"] = o["prev_page"]
            else:
                o["prev_page"] = o["page"]
                o["page"] = "sym"
        elif key == "CANCEL":
            self._osk_cancel()
        elif key == "DONE":
            self._osk_done()

    def _osk_done(self):
        """완료: 입력칸이면 Enter(확정/전송), 접속 주소면 닫기만 (접속은 따로 누름)"""
        join = self._osk_field() == "join_ip"
        self._osk_close()
        if not join and self.text_focus:
            self._osk_fire(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="\r", scancode=0)

    def _osk_cancel(self):
        join = self._osk_field() == "join_ip"
        self._osk_close()
        if not join and self.text_focus:
            self._osk_fire(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="", scancode=0)      # 입력 취소 (이전 값으로)

    # ---------------------------------------------------------------- 이벤트 (True = 처리함)
    def _osk_event(self, event):
        o = self.osk
        if o is None or getattr(event, "osk", False):
            return False
        t = event.type
        if t == pygame.TEXTINPUT:
            self._osk_close()                              # 물리 키보드(또는 Steam 키보드)로 치기 시작함: 화상 키보드는 닫음
            return False
        if t == pygame.KEYDOWN:
            pad = getattr(event, "pad", False)
            k = event.key
            if k in _ARROWS:
                self._osk_move(k)
                return True
            if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._osk_press_selected()
                return True
            if k == pygame.K_ESCAPE:
                self._osk_cancel()
                return True
            if pad:                                        # 패드 버튼 (게임 밖 메뉴 방식으로 들어옴): X = 지우기, Y = Shift, LB = 한/영, RB = 기호, Back = 완료
                action = {pygame.K_SPACE: "BACK", pygame.K_p: "SHIFT", pygame.K_PAGEUP: "LANG", pygame.K_PAGEDOWN: "SYM", pygame.K_TAB: "DONE"}.get(k)
                if action:
                    self._osk_press(action)
                return True                                # 그 밖의 패드 버튼은 아래 화면으로 새지 않게 소비
            if k in (pygame.K_LSHIFT, pygame.K_RSHIFT, pygame.K_LCTRL, pygame.K_RCTRL, pygame.K_LALT, pygame.K_RALT, pygame.K_CAPSLOCK):
                return False
            o["comp"].reset()
            self._osk_close()                              # 물리 키보드 입력: 화상 키보드는 닫고 그 키는 그대로 처리
            return False
        if t in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION, pygame.MOUSEWHEEL):
            pos = getattr(event, "pos", None)
            panel = self._osk_panel_rect()
            if t == pygame.MOUSEMOTION:
                if pos is not None and panel.collidepoint(pos):
                    for rect, key, r, c in o["keys"]:
                        if rect.collidepoint(pos):
                            o["sel"] = (r, c)
                            break
                    return True
                return False
            if t == pygame.MOUSEBUTTONDOWN and event.button == 1 and pos is not None and panel.collidepoint(pos):
                for rect, key, r, c in o["keys"]:
                    if rect.collidepoint(pos):
                        o["sel"] = (r, c)
                        self._osk_press(key)
                        break
                return True
            return pos is not None and panel.collidepoint(pos) if t != pygame.MOUSEWHEEL else False
        return False

    def _osk_press_selected(self):
        o = self.osk
        r, c = o["sel"]
        for rect, key, rr, cc in o["keys"]:
            if (rr, cc) == (r, c):
                self._osk_press(key)
                return

    def _osk_move(self, k):
        """십자키: 화면에 보이는 키 위치(가로 중심)를 기준으로 가장 가까운 키로 이동"""
        o = self.osk
        keys = o["keys"]
        if not keys:
            return
        r, c = o["sel"]
        cur = next(((rect, rr, cc) for rect, key, rr, cc in keys if (rr, cc) == (r, c)), None)
        if cur is None:
            o["sel"] = (keys[0][2], keys[0][3])
            return
        rect, r, c = cur
        rows = sorted({rr for _, _, rr, _ in keys})
        if k in (pygame.K_LEFT, pygame.K_RIGHT):
            same = sorted((kk for kk in keys if kk[2] == r), key=lambda kk: kk[0].centerx)
            i = next(i for i, kk in enumerate(same) if kk[3] == c)
            i = (i + (1 if k == pygame.K_RIGHT else -1)) % len(same)
            o["sel"] = (r, same[i][3])
        else:
            nr = rows[(rows.index(r) + (1 if k == pygame.K_DOWN else -1)) % len(rows)]
            cand = [kk for kk in keys if kk[2] == nr]
            best = min(cand, key=lambda kk: abs(kk[0].centerx - rect.centerx))
            o["sel"] = (nr, best[3])
        self.sound_mgr.play('move')

    # ---------------------------------------------------------------- 그리기
    def _osk_panel_rect(self):
        w = 12 * KEY_W + 11 * KEY_GAP + 44                    # 맨 윗줄(숫자 10개 + 지우기 2칸)이 가장 넓음
        h = 40 + 5 * (KEY_H + KEY_GAP) + 22
        return pygame.Rect((SCREEN_WIDTH - w) // 2, SCREEN_HEIGHT - h - 6, w, h)

    def _osk_update(self):
        """매 프레임: 입력칸이 닫혔거나 화면이 바뀌었으면 화상 키보드도 닫음"""
        o = self.osk
        if o is None:
            return
        if o["kind"] == "join_ip":
            if self.state != "JOIN_MENU" or self.modal is not None:
                self._osk_close()
        elif self.text_focus is None or self.modal is not None:
            self._osk_close()

    def _render_osk(self):
        self._osk_update()
        o = self.osk
        if o is None:
            return
        from i18n import tr
        panel = self._osk_panel_rect()
        self._glass(panel, accent=(110, 200, 255), radius=16, alpha=246, border_w=2)
        label = tr(OSK_FIELD_LABELS.get(self._osk_field(), ""))
        self._t(label, self.font_small, (140, 200, 255), panel.x + 22, panel.y + 12)
        box = pygame.Rect(panel.x + 150, panel.y + 6, panel.w - 150 - 20, 28)
        pygame.draw.rect(self.screen, (11, 13, 24), box, border_radius=8)
        pygame.draw.rect(self.screen, (70, 90, 130), box, 1, border_radius=8)
        txt = self._osk_text()
        shown = txt
        while len(shown) > 1 and self.font_mid.size(shown)[0] > box.w - 28:
            shown = shown[1:]                                       # 길면 끝부분(방금 친 글자)이 보이게
        r = self._t(shown, self.font_mid, (235, 240, 255), box.x + 12, box.centery, "midleft")
        if int(pygame.time.get_ticks() / 500) % 2 == 0:
            pygame.draw.rect(self.screen, (110, 200, 255), (r.right + 3, box.y + 5, 2, box.h - 10))
        page, shift = o["page"], o["shift"]
        rows = _osk.layout(page)
        o["keys"] = []
        y = panel.y + 42
        sel = o["sel"]
        mx, my = pygame.mouse.get_pos()
        names = {"BACK": "지우기", "SHIFT": "Shift", "SYM": "ABC" if page == "sym" else "#+=", "SPACE": "공백", "CANCEL": "취소", "DONE": "완료",
                 "LANG": ("ABC" if page == "ko" else "한글") if self._osk_field() != "join_ip" else ""}
        for ri, row in enumerate(rows):
            widths = []
            for k in row:
                if isinstance(k, tuple):
                    widths.append(KEY_W)
                else:
                    widths.append({"BACK": KEY_W * 2 + KEY_GAP, "SHIFT": int(KEY_W * 1.5), "SPACE": KEY_W * 4, "LANG": KEY_W + 20, "SYM": KEY_W + 20,
                                   "CANCEL": KEY_W + 20, "DONE": KEY_W + 36}.get(k, KEY_W))
            total = sum(widths) + KEY_GAP * (len(row) - 1)
            x = panel.centerx - total // 2
            for ci, (k, w) in enumerate(zip(row, widths)):
                rect = pygame.Rect(x, y, w, KEY_H)
                o["keys"].append((rect, k, ri, ci))
                is_sel = (sel == (ri, ci))
                special = not isinstance(k, tuple)
                on = (k == "SHIFT" and shift)
                fill = (48, 64, 104) if is_sel else ((40, 54, 90) if on else ((30, 38, 64) if special else (24, 32, 54)))
                pygame.draw.rect(self.screen, fill, rect, border_radius=8)
                pygame.draw.rect(self.screen, (110, 200, 255) if is_sel else ((255, 215, 90) if on else (52, 66, 100)), rect, 2 if is_sel else 1, border_radius=8)
                if isinstance(k, tuple):
                    ch = k[1] if shift else k[0]
                    self._t(ch, self.font_mid, (240, 244, 255), rect.centerx, rect.centery, "center")
                else:
                    col = (120, 255, 170) if k == "DONE" else ((255, 130, 130) if k == "CANCEL" else (200, 214, 240))
                    if names.get(k, k):
                        self._t(tr(names.get(k, k)), self.font_small, col, rect.centerx, rect.centery, "center")
                x += w + KEY_GAP
            y += KEY_H + KEY_GAP
        hint = "십자키 이동  ·  A 입력  ·  X 지우기  ·  Y 대문자  ·  LB 한/영  ·  RB 기호  ·  Back 완료  ·  B 취소" if getattr(self.renderer, "pad_ui", False) \
            else "터치/클릭으로 입력  ·  다 쓰면 '완료'를 누르세요  ·  물리 키보드로 치면 이 키보드는 닫힙니다"
        self._t(tr(hint), self.font_tiny, (130, 145, 175), panel.centerx, panel.bottom - 8, "midbottom")

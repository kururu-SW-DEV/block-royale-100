"""
Block Royale 100 - 게임패드 지원 (v1.1.14)
패드 입력(십자키/스틱/버튼)을 '키 입력 이벤트'로 바꿔서 기존 키보드 처리(DAS/ARR/소프트드롭, 메뉴 이동, 키 재배정)를 그대로 쓴다.
- 게임 중 (v1.4.8부터 Tetris 99 / Tetris Effect와 같은 배치): 십자키/왼쪽 스틱 = 좌우 이동·소프트드롭, 십자키 위 = 하드 드롭(스틱 위는 실수 방지로 게임 중 무시),
  오른쪽 버튼(B)·왼쪽 버튼(X) = 시계 회전, 아래 버튼(A)·위 버튼(Y) = 반시계 회전, LB/RB = 홀드, R3(오른쪽 스틱 누름) = 180도 회전,
  Start = 일시정지, Back = 조준 대상 바꾸기. 동작에 배정된 첫 번째 키를 눌렀다 뗀 것처럼 처리하므로 설정의 키 배정을 따른다.
- 메뉴/설정/결과 화면: 십자키/스틱 = 방향키, A/Start = Enter, B = Esc.
SDL이 '표준 컨트롤러'로 아는 장치(Xbox / PlayStation / Switch Pro 등)는 GameController API로 열어 버튼 위치(A=아래, B=오른쪽, X=왼쪽, Y=위)가
어느 제조사든 같게 매핑된다. 그 밖의 장치만 예전 조이스틱 번호(Xbox 계열: A0 B1 X2 Y3 LB4 RB5 Back6 Start7)로 처리한다. 문제가 있으면 설정의 '게임패드'를 끌 수 있다.
"""

import time

import pygame

try:
    from pygame._sdl2 import controller as _sdl_ctrl      # SDL GameController (표준 버튼 배치). 없으면 조이스틱 방식만 사용
except Exception:                                          # pragma: no cover
    _sdl_ctrl = None

STICK_ON = 0.55          # 스틱이 이만큼 기울면 방향 입력으로 봄
STICK_OFF = 0.35         # 이만큼 아래로 돌아오면 입력 해제 (경계에서 떨리지 않게 이력을 둠)

# 게임 중 패드 버튼 배치 (사용자가 설정 > 조작 > 게임패드에서 바꿀 수 있음). 버튼 이름은 표준 컨트롤러 기준: A=아래 B=오른쪽 X=왼쪽 Y=위, LB/RB=어깨, L3/R3=스틱 누름
PAD_BUTTONS = ("A", "B", "X", "Y", "LB", "RB", "BACK", "START", "L3", "R3")
PAD_BUTTON_LABELS = {"BACK": "Back", "START": "Start"}
# 기본 배치 (Tetris 99 / Tetris Effect와 같음). 이동/소프트 드롭/하드 드롭(십자키 위)은 십자키·왼쪽 스틱 고정이고, 하드 드롭은 버튼을 더 줄 수 있음
DEFAULT_PAD_MAP = {"rotate_cw": ["B", "X"], "rotate_ccw": ["A", "Y"], "hold": ["LB", "RB"], "rotate_180": ["R3"],
                   "target_cycle": ["BACK"], "pause": ["START"], "hard_drop": []}
PAD_REBINDABLE = ("hard_drop", "rotate_cw", "rotate_ccw", "hold", "rotate_180", "pause", "target_cycle")      # 버튼을 바꿀 수 있는 동작
# 조이스틱(표준 컨트롤러가 아닌 장치, Xbox 계열 번호) 번호 -> 버튼 이름
_JOY_NAME = {0: "A", 1: "B", 2: "X", 3: "Y", 4: "LB", 5: "RB", 6: "BACK", 7: "START", 8: "L3", 9: "R3"}
# 메뉴 등 버튼 -> 키
MENU_BUTTONS = {0: pygame.K_RETURN, 1: pygame.K_ESCAPE, 7: pygame.K_RETURN, 6: pygame.K_TAB,
                2: pygame.K_SPACE, 3: pygame.K_p, 4: pygame.K_PAGEUP, 5: pygame.K_PAGEDOWN}          # X=Space(리플레이 일시정지) Y=P(여기서부터 연습/연습) LB/RB=페이지 넘기기(업적/목록)
MENU_DIRS = {"left": pygame.K_LEFT, "right": pygame.K_RIGHT, "up": pygame.K_UP, "down": pygame.K_DOWN}
GAME_DIRS = {"left": "move_left", "right": "move_right", "down": "soft_drop", "up": "hard_drop"}


# GameController 표준 버튼 -> 동작 / 키 (조이스틱 번호 표와 같은 의미)
CB = {name: getattr(pygame, "CONTROLLER_BUTTON_" + name, -1) for name in
      ("A", "B", "X", "Y", "BACK", "START", "LEFTSHOULDER", "RIGHTSHOULDER", "LEFTSTICK", "RIGHTSTICK", "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT")}
_CTRL_NAME = {CB["A"]: "A", CB["B"]: "B", CB["X"]: "X", CB["Y"]: "Y", CB["LEFTSHOULDER"]: "LB", CB["RIGHTSHOULDER"]: "RB",
              CB["BACK"]: "BACK", CB["START"]: "START", CB["LEFTSTICK"]: "L3", CB["RIGHTSTICK"]: "R3"}
CTRL_MENU_BUTTONS = {CB["A"]: pygame.K_RETURN, CB["B"]: pygame.K_ESCAPE, CB["START"]: pygame.K_RETURN, CB["BACK"]: pygame.K_TAB,
                     CB["X"]: pygame.K_SPACE, CB["Y"]: pygame.K_p, CB["LEFTSHOULDER"]: pygame.K_PAGEUP, CB["RIGHTSHOULDER"]: pygame.K_PAGEDOWN}
CTRL_DPAD = {CB["DPAD_UP"]: "up", CB["DPAD_DOWN"]: "down", CB["DPAD_LEFT"]: "left", CB["DPAD_RIGHT"]: "right"}
_CBTN = (getattr(pygame, "CONTROLLERBUTTONDOWN", -1), getattr(pygame, "CONTROLLERBUTTONUP", -1))
_CAXIS = getattr(pygame, "CONTROLLERAXISMOTION", -1)
_CAX_X, _CAX_Y = getattr(pygame, "CONTROLLER_AXIS_LEFTX", 0), getattr(pygame, "CONTROLLER_AXIS_LEFTY", 1)
PAD_EVENT_TYPES = (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP, pygame.JOYHATMOTION, pygame.JOYAXISMOTION) + _CBTN + (_CAXIS,)


# 메뉴/결과/일시정지 화면의 버튼 옆 키 표시를 패드 버튼으로 바꾸는 표 (패드로 누를 수 없는 키 R/S/C/T 등은 표시하지 않음. MENU_BUTTONS와 같아야 함)
PAD_KEY_LABELS = {"ESC": "B", "Esc": "B", "ENTER": "A", "Enter": "A", "SPACE": "X", "Space": "X", "P": "Y", "TAB": "Back", "Tab": "Back", "↑↓←→": "십자키"}


def pad_key_label(key):
    return PAD_KEY_LABELS.get(key)


_PADIFY = None


def padify(text):
    """패드로 하는 중에 화면 글자 속의 키보드 키 이름을 패드 버튼 이름으로 바꿈 ("메인 메뉴로 (ESC)" -> "(B)", "Enter 재생" -> "A 재생" 등. MENU_BUTTONS와 같은 대응)"""
    global _PADIFY
    if "키보드" in text or "keyboard" in text.lower():
        return text                                           # "키보드 ESC로 취소"처럼 키보드를 가리키는 문구는 그대로 (패드 버튼 배정 중에는 B도 배정할 수 있는 버튼이라 취소는 키보드 ESC)
    if _PADIFY is None:
        import re
        _PADIFY = [(re.compile(p), r) for p, r in ((r"\(ESC\)", "(B)"), (r"\bESC\b", "B"), (r"\bEsc\b", "B"), (r"\bEnter\b", "A"),
                                                   (r"\bSpace\b", "X"), (r"PgUp/PgDn", "LB/RB"))]
    for rx, rep in _PADIFY:
        text = rx.sub(rep, text)
    return text


def pad_button_label(name):
    return PAD_BUTTON_LABELS.get(name, name)


def pad_names(pad_map, action):
    """동작에 배정된 패드 버튼 이름들을 'B/X' 꼴로 (없으면 빈 글자)"""
    return "/".join(pad_button_label(n) for n in (pad_map or {}).get(action, []))


def pad_hint_items(pad_map=None):
    """게임 중 하단 키 안내에 쓰는 패드 버튼 안내 [(버튼, 설명)]. 사용자가 바꾼 배치(pad_map)를 따름 (표준 컨트롤러 기준: A=아래 B=오른쪽 X=왼쪽 Y=위). 버튼이 없는 동작은 뺌"""
    m = pad_map or DEFAULT_PAD_MAP
    items = [("←→", "이동")]
    for act, label in (("rotate_cw", "회전"), ("rotate_ccw", "역회전")):
        if pad_names(m, act):
            items.append((pad_names(m, act), label))
    items.append(("↓", "소프트"))
    extra = pad_names(m, "hard_drop")
    items.append(("↑" + ("/" + extra if extra else ""), "하드드롭"))
    for act, label in (("hold", "홀드"), ("rotate_180", "180°"), ("target_cycle", "조준"), ("pause", "일시정지")):
        if pad_names(m, act):
            items.append((pad_names(m, act), label))
    return items


class GamepadMapper:
    """패드 이벤트 -> 키 이벤트 변환기. 방향은 눌림 상태를 기억해 한 번만 KEYDOWN, 떼면 KEYUP을 냄"""

    def __init__(self, keys_for_action, enabled=lambda: True, pad_map=None):
        self.keys_for_action = keys_for_action          # 동작 이름 -> 키 코드 목록
        self.enabled = enabled
        self.pad_map = pad_map or (lambda: DEFAULT_PAD_MAP)       # 동작 이름 -> 패드 버튼 이름 목록 (설정에서 바꾼 배치)
        self.capture = None                             # 함수(버튼 이름): 설정 화면에서 버튼 배정을 기다리는 동안 설정되며, 버튼 누름을 게임 입력으로 바꾸지 않고 여기로 보냄
        self.joys = {}                                  # instance_id -> Joystick (참조를 잡고 있어야 이벤트가 옴)
        self._dirs = {}                                 # (instance_id, 'hat'|'stick') -> 지금 눌린 방향 집합
        self._axes = {}                                 # (instance_id, axis) -> -1/0/1
        self._sent = {}                                 # 누른 입력 -> 보낸 키 코드
        self.ctrls = {}                                 # instance_id -> 열어 둔 GameController
        self._dpad = {}                                 # instance_id -> 눌린 십자키 방향 집합 (GameController는 십자키가 버튼으로 옴)
        self.last_pad_t = 0.0                           # 마지막으로 패드 입력(또는 연결)이 있었던 시각 (게임 중 키 안내를 패드/키보드 중 어느 쪽으로 보일지 정하는 데 씀)

    # ---- 장치 연결/해제
    def on_device_event(self, event):
        try:
            if event.type == pygame.JOYDEVICEADDED:
                if _sdl_ctrl is not None and self._open_controller(event.device_index):
                    return                                  # 표준 컨트롤러는 GameController로만 받음 (같은 입력이 두 번 오지 않게 조이스틱으로는 열지 않음)
                joy = pygame.joystick.Joystick(event.device_index)
                self.joys[joy.get_instance_id()] = joy
            elif event.type == pygame.JOYDEVICEREMOVED:
                inst = getattr(event, "instance_id", None)
                self.joys.pop(inst, None)
                ctrl = self.ctrls.pop(inst, None)
                if ctrl is not None:
                    try:
                        ctrl.quit()
                    except Exception:
                        pass
                self._dpad.pop(inst, None)
                for k in [k for k in self._dirs if k[0] == inst]:
                    self._dirs.pop(k, None)
        except Exception:
            pass

    def _open_controller(self, index):
        """표준 컨트롤러면 열어서 보관하고 True. 아니거나 실패하면 False (조이스틱으로 처리)"""
        try:
            if not _sdl_ctrl.get_init():
                _sdl_ctrl.init()
            if not _sdl_ctrl.is_controller(index):
                return False
            ctrl = _sdl_ctrl.Controller(index)
            self.ctrls[ctrl.as_joystick().get_instance_id()] = ctrl
            return True
        except Exception:
            return False

    # ---- 키 이벤트 만들기: 누른 순간에 보낸 키를 기억해 뗄 때도 똑같은 키를 뗌 (그 사이에 일시정지/탈락으로 매핑이 바뀌어도 키가 눌린 채 남지 않게)
    def _resolve_key(self, name, in_game):
        if in_game:
            action = GAME_DIRS.get(name, name) if isinstance(name, str) else None
            keys = self.keys_for_action(action) if action else []
            return keys[0] if keys else None
        return MENU_DIRS.get(name) if isinstance(name, str) else name

    def _press(self, token, name, in_game):
        key = self._resolve_key(name, in_game)
        if key is None or token in self._sent:
            return None
        self._sent[token] = key
        ev = pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0)
        ev.pad = True                                    # 진짜 키보드 입력과 구별하기 위한 표시
        return ev

    def _release(self, token):
        key = self._sent.pop(token, None)
        if key is None:
            return None
        ev = pygame.event.Event(pygame.KEYUP, key=key, mod=0, scancode=0)
        ev.pad = True
        return ev

    def game_action(self, name):
        """버튼 이름 -> 게임 중 동작 (설정의 패드 배치를 따름). 배정이 없으면 None"""
        if not name:
            return None
        for action, names in (self.pad_map() or {}).items():
            if name in names:
                return action
        return None

    def connected(self):
        """연결된 컨트롤러가 하나라도 있는지"""
        return bool(self.joys or self.ctrls)

    @staticmethod
    def _token_inst(token):
        head = token[0]
        return head[0] if isinstance(head, tuple) else head           # 방향 토큰은 ((장치, 'hat'|'stick'), 방향), 버튼 토큰은 (장치, 종류, 번호)

    def release_all(self, inst=None):
        """눌린 채로 남은 입력(패드가 뽑히거나 패드 입력을 껐을 때)의 KEYUP을 만들고 눌림 상태를 비움. inst를 주면 그 장치만"""
        out = []
        for token in [t for t in self._sent if inst is None or self._token_inst(t) == inst]:
            ev = self._release(token)
            if ev is not None:
                out.append(ev)
        for store in (self._dirs, self._axes):
            for k in [k for k in store if inst is None or k[0] == inst]:
                store.pop(k, None)
        for k in [k for k in self._dpad if inst is None or k == inst]:
            self._dpad.pop(k, None)
        return out

    def _set_dirs(self, kind_key, new_dirs, in_game):
        old = self._dirs.get(kind_key, set())
        out = [self._release((kind_key, d)) for d in sorted(old - new_dirs)]
        out += [self._press((kind_key, d), d, in_game) for d in sorted(new_dirs - old)]
        self._dirs[kind_key] = set(new_dirs)
        return out

    @staticmethod
    def _hat_dirs(value):
        x, y = value
        d = set()
        if x < 0:
            d.add("left")
        elif x > 0:
            d.add("right")
        if y > 0:
            d.add("up")
        elif y < 0:
            d.add("down")
        return d

    def _axis_update(self, inst, axis, value):
        """왼쪽 스틱(축 0, 1) -> 방향 집합 (이력을 둔 데드존)"""
        cur = self._axes.get((inst, axis), 0)
        if cur == 0:
            new = 1 if value > STICK_ON else (-1 if value < -STICK_ON else 0)
        else:
            new = cur if abs(value) > STICK_OFF and (value > 0) == (cur > 0) else 0
        self._axes[(inst, axis)] = new
        d = set()
        for ax, (neg, pos) in ((0, ("left", "right")), (1, ("up", "down"))):
            v = self._axes.get((inst, ax), 0)
            if v < 0:
                d.add(neg)
            elif v > 0:
                d.add(pos)
        return d

    def _controller_button(self, inst, e, in_game):
        down = e.type == _CBTN[0]
        if e.button in CTRL_DPAD:                                    # 십자키: 눌린 방향 집합을 갱신해 조이스틱 hat과 같은 경로로
            cur = self._dpad.setdefault(inst, set())
            (cur.add if down else cur.discard)(CTRL_DPAD[e.button])
            return self._set_dirs((inst, "hat"), set(cur), in_game)
        token = (inst, "cbtn", e.button)
        if not down:
            return [self._release(token)]
        if self.capture is not None and _CTRL_NAME.get(e.button):
            self.capture(_CTRL_NAME[e.button])                           # 버튼 배정 대기 중: 이 누름은 배정에만 쓰고 입력으로 처리하지 않음
            return []
        if in_game:
            action = self.game_action(_CTRL_NAME.get(e.button))
            return [self._press(token, action, True)] if action else []
        key = CTRL_MENU_BUTTONS.get(e.button)
        return [self._press(token, key, False)] if key is not None else []

    def translate(self, events, in_game):
        """이벤트 목록을 받아 패드 이벤트는 키 이벤트로 바꾼 새 목록을 돌려줌 (나머지는 그대로)"""
        if not self.enabled():
            for e in events:                                   # 꺼 둔 동안에도 연결/해제는 기억해 둠 (안 그러면 나중에 켜도 이미 꽂힌 패드를 열지 못해 뽑았다 꽂아야 함)
                if e.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                    self.on_device_event(e)
            return self.release_all() + [e for e in events if e.type not in PAD_EVENT_TYPES]      # 끄는 순간 눌려 있던 입력은 떼 줌 (안 그러면 블록이 계속 한쪽으로 움직임)
        out = []
        for e in events:
            if e.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                self.on_device_event(e)
                if e.type == pygame.JOYDEVICEADDED:
                    self.last_pad_t = time.time()                      # 새로 연결하면 바로 패드 키 안내로
                if e.type == pygame.JOYDEVICEREMOVED and getattr(e, "instance_id", None) is not None:
                    out.extend(self.release_all(e.instance_id))        # 누른 채로 패드를 뽑아도 키가 눌린 채 남지 않게
                continue
            inst = getattr(e, "instance_id", 0)
            if inst in self.ctrls and e.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP, pygame.JOYHATMOTION, pygame.JOYAXISMOTION):
                continue                                      # SDL은 GameController로 연 장치도 조이스틱 이벤트를 함께 보냄: 컨트롤러 이벤트만 처리해야 입력이 두 번 오지 않음
            made = []
            if e.type == pygame.JOYHATMOTION:
                made = self._set_dirs((inst, "hat"), self._hat_dirs(e.value), in_game)
            elif e.type == pygame.JOYAXISMOTION and e.axis in (0, 1):
                sd = self._axis_update(inst, e.axis, e.value)
                if in_game:
                    sd.discard("up")                           # 게임 중 스틱 위 = 하드 드롭이면 대각선으로 밀 때 실수로 떨어짐: 하드 드롭은 십자키 위/버튼만
                made = self._set_dirs((inst, "stick"), sd, in_game)
            elif e.type in _CBTN:
                made = self._controller_button(inst, e, in_game)
            elif e.type == _CAXIS:
                if e.axis in (_CAX_X, _CAX_Y):
                    v = e.value / 32767.0 if abs(e.value) > 1.0 else e.value        # 이벤트 값은 -32768..32767 정수일 수 있음
                    sd = self._axis_update(inst, 0 if e.axis == _CAX_X else 1, max(-1.0, min(1.0, v)))
                    if in_game:
                        sd.discard("up")
                    made = self._set_dirs((inst, "stick"), sd, in_game)
            elif e.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
                token = (inst, "btn", e.button)
                if e.type == pygame.JOYBUTTONUP:
                    made = [self._release(token)]
                elif self.capture is not None and _JOY_NAME.get(e.button):
                    self.capture(_JOY_NAME[e.button])
                    made = []
                elif in_game:
                    action = self.game_action(_JOY_NAME.get(e.button))
                    made = [self._press(token, action, True)] if action else []
                else:
                    key = MENU_BUTTONS.get(e.button)
                    made = [self._press(token, key, False)] if key is not None else []
            else:
                out.append(e)
                continue
            made = [m for m in made if m is not None]
            if made and any(m.type == pygame.KEYDOWN for m in made):
                self.last_pad_t = time.time()
            out.extend(made)
        return out

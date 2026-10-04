"""
Block Royale 100 - 게임패드 지원 (v1.1.14)
패드 입력(십자키/스틱/버튼)을 '키 입력 이벤트'로 바꿔서 기존 키보드 처리(DAS/ARR/소프트드롭, 메뉴 이동, 키 재배정)를 그대로 쓴다.
- 게임 중: 십자키/왼쪽 스틱 = 좌우 이동·소프트드롭, 위 = 하드 드롭, A = 시계 회전, B = 반시계 회전, X/LB = 홀드, Y = 180도 회전,
  RB = 하드 드롭, Start = 일시정지, Back = 조준 대상 바꾸기. 동작에 배정된 첫 번째 키를 눌렀다 뗀 것처럼 처리하므로 설정의 키 배정을 따른다.
- 메뉴/설정/결과 화면: 십자키/스틱 = 방향키, A/Start = Enter, B = Esc.
버튼 번호는 SDL 조이스틱 기본(Xbox 계열: A0 B1 X2 Y3 LB4 RB5 Back6 Start7). 컨트롤러마다 다를 수 있어 문제가 있으면 설정의 '게임패드'를 끌 수 있다.
"""

import pygame

STICK_ON = 0.55          # 스틱이 이만큼 기울면 방향 입력으로 봄
STICK_OFF = 0.35         # 이만큼 아래로 돌아오면 입력 해제 (경계에서 떨리지 않게 이력을 둠)

# 게임 중 버튼 -> 동작 이름 (settings의 ACTION 이름)
GAME_BUTTONS = {0: "rotate_cw", 1: "rotate_ccw", 2: "hold", 3: "rotate_180", 4: "hold", 5: "hard_drop", 6: "target_cycle", 7: "pause"}
# 메뉴 등 버튼 -> 키
MENU_BUTTONS = {0: pygame.K_RETURN, 1: pygame.K_ESCAPE, 7: pygame.K_RETURN, 6: pygame.K_TAB}
MENU_DIRS = {"left": pygame.K_LEFT, "right": pygame.K_RIGHT, "up": pygame.K_UP, "down": pygame.K_DOWN}
GAME_DIRS = {"left": "move_left", "right": "move_right", "down": "soft_drop", "up": "hard_drop"}


class GamepadMapper:
    """패드 이벤트 -> 키 이벤트 변환기. 방향은 눌림 상태를 기억해 한 번만 KEYDOWN, 떼면 KEYUP을 냄"""

    def __init__(self, keys_for_action, enabled=lambda: True):
        self.keys_for_action = keys_for_action          # 동작 이름 -> 키 코드 목록
        self.enabled = enabled
        self.joys = {}                                  # instance_id -> Joystick (참조를 잡고 있어야 이벤트가 옴)
        self._dirs = {}                                 # (instance_id, 'hat'|'stick') -> 지금 눌린 방향 집합
        self._axes = {}                                 # (instance_id, axis) -> -1/0/1
        self._sent = {}                                 # 누른 입력 -> 보낸 키 코드

    # ---- 장치 연결/해제
    def on_device_event(self, event):
        try:
            if event.type == pygame.JOYDEVICEADDED:
                joy = pygame.joystick.Joystick(event.device_index)
                self.joys[joy.get_instance_id()] = joy
            elif event.type == pygame.JOYDEVICEREMOVED:
                self.joys.pop(getattr(event, "instance_id", None), None)
                for k in [k for k in self._dirs if k[0] == getattr(event, "instance_id", None)]:
                    self._dirs.pop(k, None)
        except Exception:
            pass

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
        return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0)

    def _release(self, token):
        key = self._sent.pop(token, None)
        return None if key is None else pygame.event.Event(pygame.KEYUP, key=key, mod=0, scancode=0)

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

    def translate(self, events, in_game):
        """이벤트 목록을 받아 패드 이벤트는 키 이벤트로 바꾼 새 목록을 돌려줌 (나머지는 그대로)"""
        if not self.enabled():
            return [e for e in events if e.type not in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP, pygame.JOYHATMOTION, pygame.JOYAXISMOTION)]
        out = []
        for e in events:
            if e.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                self.on_device_event(e)
                continue
            inst = getattr(e, "instance_id", 0)
            made = []
            if e.type == pygame.JOYHATMOTION:
                made = self._set_dirs((inst, "hat"), self._hat_dirs(e.value), in_game)
            elif e.type == pygame.JOYAXISMOTION and e.axis in (0, 1):
                made = self._set_dirs((inst, "stick"), self._axis_update(inst, e.axis, e.value), in_game)
            elif e.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
                token = (inst, "btn", e.button)
                if e.type == pygame.JOYBUTTONUP:
                    made = [self._release(token)]
                elif in_game:
                    action = GAME_BUTTONS.get(e.button)
                    made = [self._press(token, action, True)] if action else []
                else:
                    key = MENU_BUTTONS.get(e.button)
                    made = [self._press(token, key, False)] if key is not None else []
            else:
                out.append(e)
                continue
            out.extend(m for m in made if m is not None)
        return out

"""
Block Royale 100 - 입력 진단 기록 (v1.4.16)
Wine/Proton(스팀덱)에서만(또는 환경변수 BR_INPUT_DIAG=1일 때) 시작 후 2분 동안 입력/창 상태를 input_diag.txt에 기록한다.
Proton 10 이후 게이밍 모드에서 입력이 안 되는 원인을 추측이 아니라 실제 값으로 찾기 위한 것: 어떤 이벤트가 오는지, 창이 포커스를 가졌는지, 장치가 보이는지.
파일은 실행 파일(exe)이 있는 폴더에 쓰고(스팀덱 데스크톱 모드에서 찾기 쉬움), 쓸 수 없으면 데이터 폴더에 씀. 개인 정보는 기록하지 않음.
"""

import os
import sys
import time

import pygame

DURATION = 120.0          # 시작 후 이 시간(초)까지만 기록
MAX_BYTES = 200_000
NAME = "input_diag.txt"


def wine_signals():
    """Wine/Proton 안에서 실행 중인지 판단하는 여러 신호 (어느 것이 맞는지 로그로 확인하려고 모두 남김)"""
    sig = {}
    try:
        import ctypes
        sig["ntdll.wine_get_version"] = hasattr(ctypes.windll.ntdll, "wine_get_version")
    except Exception as e:
        sig["ntdll.wine_get_version"] = "error: %r" % (e,)
    for k in ("WINEPREFIX", "WINELOADER", "STEAM_COMPAT_DATA_PATH", "SteamAppId", "SteamGameId", "PROTON_VERSION", "WINE_VERSION", "SteamDeck", "SteamOS"):
        if os.environ.get(k):
            sig["env." + k] = os.environ[k]
    try:
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Wine"))
        sig["registry.HKCU\\Software\\Wine"] = True
    except Exception:
        sig["registry.HKCU\\Software\\Wine"] = False
    return sig


def under_wine(sig=None):
    sig = sig if sig is not None else wine_signals()
    return bool(sig.get("ntdll.wine_get_version") is True or sig.get("registry.HKCU\\Software\\Wine") is True
                or any(k.startswith("env.") for k in sig))


class InputDiag:
    def __init__(self):
        self.sig = wine_signals() if sys.platform == "win32" else {}
        self.on = bool(os.environ.get("BR_INPUT_DIAG")) or (sys.platform == "win32" and under_wine(self.sig))
        self.t0 = time.time()
        self.counts = {}
        self.last_flush = self.t0
        self.last_state = None
        self.f = None
        self.bytes = 0
        if self.on:
            self._open()
            self.log("start", f"app_version={self._version()} platform={sys.platform} py={sys.version.split()[0]} frozen={bool(getattr(sys, 'frozen', False))}")
            self.log("wine_signals", repr(self.sig))
            try:
                self.log("sdl", f"pygame={pygame.version.ver} sdl={pygame.version.SDL} video_driver={pygame.display.get_driver()}")
            except Exception as e:
                self.log("sdl", "error %r" % (e,))

    @staticmethod
    def _version():
        try:
            from config import APP_VERSION
            return APP_VERSION
        except Exception:
            return "?"

    def _open(self):
        dirs = []
        if getattr(sys, "frozen", False):
            dirs.append(os.path.dirname(sys.executable))
        try:
            from app_paths import data_path
            dirs.append(os.path.dirname(data_path(NAME)))
        except Exception:
            pass
        for d in dirs:
            try:
                path = os.path.join(d, NAME)
                if os.path.exists(path):
                    try:
                        os.replace(path, path + ".prev")
                    except OSError:
                        pass
                self.f = open(path, "w", encoding="utf-8")
                self.path = path
                return
            except OSError:
                continue
        self.on = False

    def log(self, tag, text):
        if not self.on or self.f is None:
            return
        line = "%7.2f %-12s %s\n" % (time.time() - self.t0, tag, text)
        self.bytes += len(line)
        if self.bytes > MAX_BYTES:
            self.on = False
            return
        try:
            self.f.write(line)
            self.f.flush()
        except OSError:
            self.on = False

    # ---- 매 프레임 호출
    def events(self, evs):
        if not self.on:
            return
        now = time.time()
        if now - self.t0 > DURATION:
            self.log("end", "기록 종료(시간 제한)")
            self.on = False
            return
        for e in evs:
            name = pygame.event.event_name(e.type)
            n = self.counts.get(name, 0) + 1
            self.counts[name] = n
            if n <= 3 or name.upper().startswith(("WINDOW", "JOYDEVICE", "CONTROLLERDEVICE", "ACTIVE")):
                self.log("event", f"{name} {self._brief(e)}")
        if now - self.last_flush >= 5.0:
            self.last_flush = now
            self.log("counts", repr(self.counts))
            self.counts = {}
        self._state(now)

    @staticmethod
    def _brief(e):
        d = {k: v for k, v in e.dict.items() if k in ("key", "button", "gain", "state", "device_index", "instance_id", "axis", "value", "pos", "type")}
        return repr(d)

    def _state(self, now):
        """1초마다 창/장치 상태를 보고 바뀌었을 때만 기록"""
        if now - getattr(self, "_state_t", 0.0) < 1.0:
            return
        self._state_t = now
        try:
            st = {
                "key_focused": pygame.key.get_focused(),
                "mouse_focused": pygame.mouse.get_focused(),
                "active": pygame.display.get_active(),
                "joysticks": pygame.joystick.get_count() if pygame.joystick.get_init() else "joystick module not init",
            }
            try:
                import ctypes
                hwnd = pygame.display.get_wm_info().get("window")
                fg = ctypes.windll.user32.GetForegroundWindow()
                st["win_hwnd"] = hwnd
                st["foreground_hwnd"] = fg
                st["is_foreground"] = bool(hwnd) and hwnd == fg
            except Exception:
                pass
        except Exception as e:
            st = {"error": repr(e)}
        if st != self.last_state:
            self.last_state = st
            self.log("state", repr(st))
            if isinstance(st.get("joysticks"), int) and st["joysticks"]:
                try:
                    names = [pygame.joystick.Joystick(i).get_name() for i in range(st["joysticks"])]
                    self.log("joystick", repr(names))
                except Exception as e:
                    self.log("joystick", "error %r" % (e,))

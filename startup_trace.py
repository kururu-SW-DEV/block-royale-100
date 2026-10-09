"""
Block Royale 100 - 시작 과정 기록
창이 뜨기 전에 프로세스가 그냥 사라지는 문제(SteamOS/Proton에서 간헐적으로 실행이 안 되는 경우 등)는 파이썬 예외로 남지 않아 error.log에 아무것도 없다.
그래서 시작 단계마다 startup.log에 한 줄씩 적고, 첫 화면이 그려지면 'OK'를 적는다.
다음 실행 때 지난번 기록이 OK 없이 끝나 있으면 어느 단계에서 멈췄는지를 error.log에 남긴다.
(저장 위치는 error.log와 같은 폴더. 기록 실패는 모두 무시)
"""

import os
import time

_state = {"path": None, "t0": 0.0, "done": False}


def _path():
    from app_paths import data_path
    return data_path("startup.log")


def begin():
    """프로그램 시작 직후 한 번. 지난번 실행이 시작 도중 끝났다면 error.log에 남기고, 새 기록을 시작"""
    try:
        path = _path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                prev = f.read()
            if prev.strip() and "OK" not in prev.splitlines()[-1]:
                import crash_log
                crash_log.write_error("Previous launch did not finish starting up", prev.strip()[-1500:])
        _state.update(path=path, t0=time.time(), done=False)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"launch {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    except Exception:
        _state["path"] = None


def mark(stage):
    """단계 하나를 기록 (begin()을 부르지 않았으면 아무것도 안 함: 테스트 등)"""
    path = _state["path"]
    if not path or _state["done"]:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{time.time() - _state['t0']:6.2f}s {stage}\n")
    except Exception:
        pass


def finish():
    """첫 화면이 그려진 직후: 시작에 성공했다고 적음"""
    mark("first frame drawn")
    path = _state["path"]
    if not path or _state["done"]:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{time.time() - _state['t0']:6.2f}s OK\n")
    except Exception:
        pass
    _state["done"] = True

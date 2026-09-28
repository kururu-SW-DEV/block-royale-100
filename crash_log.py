"""
Block Royale 100 - 오류 기록
창이 콘솔 없이 실행되는 exe에서도 예기치 않은 오류의 원인을 추적할 수 있도록, 처리되지 않은 예외를 error.log에 남김.
저장 위치: 소스 실행은 프로젝트 폴더, exe는 %APPDATA%\BlockRoyale100 (settings.json 등과 같은 곳)
"""

import os
import sys
import time
import threading
import traceback

from app_paths import data_path
from config import APP_VERSION

MAX_LOG_BYTES = 256 * 1024       # 로그가 이보다 커지면 오래된 절반을 버림


def log_path():
    return data_path("error.log")


def write_error(title, exc_text):
    """error.log 끝에 한 건 기록 (기록 실패는 무시)"""
    try:
        path = log_path()
        if os.path.exists(path) and os.path.getsize(path) > MAX_LOG_BYTES:
            with open(path, "rb") as f:
                data = f.read()
            with open(path, "wb") as f:
                f.write(data[len(data) // 2:])
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')}  v{APP_VERSION}  {title} =====\n{exc_text}\n")
    except Exception:
        pass


def _excepthook(exc_type, exc, tb):
    write_error("Unhandled exception", "".join(traceback.format_exception(exc_type, exc, tb)))
    sys.__excepthook__(exc_type, exc, tb)


def _thread_excepthook(args):
    write_error(f"Thread exception ({getattr(args.thread, 'name', '?')})",
                "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))


def install():
    """메인/백그라운드 스레드의 처리되지 않은 예외를 파일에 기록하도록 설정"""
    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook


def show_fatal_message(exc_text):
    """(Windows) 콘솔이 없는 exe에서 갑자기 꺼지지 않고, 로그 위치를 알려 주는 창을 띄움"""
    try:
        import ctypes
        last = exc_text.strip().splitlines()[-1] if exc_text.strip() else ""
        ctypes.windll.user32.MessageBoxW(
            0, f"예기치 않은 오류로 게임이 종료됩니다.\n\n{last}\n\n오류 기록: {log_path()}", "BLOCK ROYALE 100", 0x10)
    except Exception:
        pass

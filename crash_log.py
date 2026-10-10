r"""
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
                f.write(data[len(data) // 2:].decode("utf-8", "ignore").encode("utf-8"))      # 자를 때 글자 중간이 깨지지 않게 시작 부분의 잘린 바이트는 버림
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


_swallowed = {}


def note_swallowed(where):
    """조용히 넘기는 예외(패킷 처리 등): 곳마다 횟수를 세고 처음 한 번만 traceback을 error.log에 남김 (LAN 문제 추적용)"""
    n = _swallowed.get(where, 0) + 1
    _swallowed[where] = n
    if n == 1:
        write_error(f"Swallowed exception ({where}, first occurrence)", traceback.format_exc())


def diagnostics_text(extra=None, tail_lines=50):
    """문제를 알릴 때 붙여 넣을 진단 정보 한 덩어리: 버전, OS/Proton, 해상도, 빛 연출 설정, startup.log, error.log 끝 부분.
    (이름/주소/설정 파일 전체는 넣지 않음)"""
    import platform
    from app_paths import running_under_wine
    lines = [f"BLOCK ROYALE 100 v{APP_VERSION}", f"OS: {platform.platform()}  python {platform.python_version()}  proton/wine: {bool(running_under_wine())}"]
    for k, v in (extra or {}).items():
        lines.append(f"{k}: {v}")
    try:
        with open(data_path("startup.log"), "r", encoding="utf-8", errors="replace") as f:
            lines += ["", "--- startup.log ---", f.read().strip()[-1500:]]
    except OSError:
        pass
    try:
        with open(log_path(), "r", encoding="utf-8", errors="replace") as f:
            tail = f.read().splitlines()[-tail_lines:]
        lines += ["", f"--- error.log (last {len(tail)} lines) ---"] + tail
    except OSError:
        lines += ["", "--- error.log: (none) ---"]
    return "\n".join(lines)


def emergency_save(app):
    """치명적 오류로 종료하기 전에 설정/전적과 진행 중이던 판의 리플레이를 저장해 보려 함 (실패해도 무시)"""
    for fn in (lambda: app.settings.save(), lambda: app.stats_mgr.save()):
        try:
            fn()
        except Exception:
            pass
    try:
        rec, m = getattr(app, "replay_rec", None), getattr(app, "match", None)
        if rec is not None and m is not None and not rec.finished and not getattr(m, "practice", False):
            from replay import save_replay
            rank = m.local_rank if m.local_rank > 0 else m.alive_count + 1
            save_replay(rec.finish(rank, m.total_players, m.local_ko_count, m.local_engine.score, m.survival_seconds()))
    except Exception:
        pass


def show_fatal_message(exc_text):
    """(Windows) 콘솔이 없는 exe에서 갑자기 꺼지지 않고, 로그 위치를 알려 주는 창을 띄움"""
    try:
        import ctypes
        last = exc_text.strip().splitlines()[-1] if exc_text.strip() else ""
        try:
            import i18n
            en = i18n.language() == "en"
        except Exception:
            en = False
        msg = (f"The game will close because of an unexpected error.\n\n{last}\n\nError log: {log_path()}" if en
               else f"예기치 않은 오류로 게임이 종료됩니다.\n\n{last}\n\n오류 기록: {log_path()}")
        ctypes.windll.user32.MessageBoxW(0, msg, "BLOCK ROYALE 100", 0x10)
    except Exception:
        pass

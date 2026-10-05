r"""
Block Royale 100 - 경로 도우미
  - resource_path(): 함께 포장된 리소스(아이콘 등) 경로. 실행 파일(PyInstaller)로 묶이면 임시 압축해제 폴더를 가리킴.
  - data_path(): 설정/전적처럼 '저장되어야 하는' 파일 경로.
      * 환경변수 BR_DATA_DIR이 있으면 그 폴더 (테스트 격리용)
      * 소스 그대로 실행: 프로젝트 폴더
      * 실행 파일(exe) 실행: %APPDATA%\BlockRoyale100 (임시 폴더는 종료 시 삭제되므로 사용 불가)
"""

import os
import sys

APP_DIR_NAME = "BlockRoyale100"
_HERE = os.path.dirname(os.path.abspath(__file__))


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def resource_path(name):
    base = getattr(sys, "_MEIPASS", _HERE)
    return os.path.join(base, name)


def data_path(name):
    override = os.environ.get("BR_DATA_DIR")        # 테스트/실험용: 사용자 설정·전적 파일을 건드리지 않도록 다른 폴더를 쓰게 함
    if override:
        try:
            os.makedirs(override, exist_ok=True)
            return os.path.join(override, name)
        except OSError:
            pass
    if is_frozen():
        root = os.environ.get("APPDATA") or os.path.expanduser("~")
        folder = os.path.join(root, APP_DIR_NAME)
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            folder = os.path.dirname(sys.executable)
        return os.path.join(folder, name)
    return os.path.join(_HERE, name)

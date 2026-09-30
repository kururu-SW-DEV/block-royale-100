"""
Block Royale 100 - 앱 공용 import/헬퍼
main.py와 screens/*.py가 함께 쓰는 이름을 한 곳에 모아 둠 (화면 모듈은 여기서 필요한 이름만 가져감)
"""

import os
import sys
import time
import math
import random
import socket
import pygame
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS,
    DEFAULT_UDP_PORT, MIN_PLAYERS, MAX_PLAYERS, APP_VERSION,
    COLOR_TEXT,
    TETROMINOES
)
from sound_fx import SoundManager
from network import NetworkManager
from battle_royale import BattleRoyaleMatch
from gfx import CANVAS, HiFont
from app_paths import resource_path
from config import NAME_COLORS, TARGET_MODES
from logo import Logo
from ui_renderer import UIRenderer, _mix, C_PANEL_BORDER, C_TEXT, C_DIM, C_ACCENT, C_GOLD, C_GREEN, C_DANGER, C_ORANGE
from settings_manager import (
    SettingsManager,
    BOT_DIFFICULTY_LABELS, BOT_DIFFICULTY_DESCS,
    BGM_STAGE_SET_LABELS, BGM_STAGE_SET_DESCS,
    BLOCK_SKIN_LABELS, BLOCK_SKIN_DESCS,
    ACTION_NAMES, RESOLUTION_OPTIONS
)
from stats_manager import StatsManager


def short_key_name(key_code):
    """HUD용 짧은 키 이름"""
    short = {
        pygame.K_LEFT: "←", pygame.K_RIGHT: "→", pygame.K_UP: "↑", pygame.K_DOWN: "↓",
        pygame.K_SPACE: "SPACE", pygame.K_LSHIFT: "SHIFT", pygame.K_RSHIFT: "SHIFT",
        pygame.K_TAB: "TAB", pygame.K_ESCAPE: "ESC", pygame.K_RETURN: "ENTER",
    }
    if key_code in short:
        return short[key_code]
    try:
        name = pygame.key.name(key_code)
        if name:
            return name.upper()
    except Exception:
        pass
    return "?"

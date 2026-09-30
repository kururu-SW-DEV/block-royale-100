import os
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
pygame.init()
pygame.display.set_mode((1366, 768))

from battle_royale import BattleRoyaleMatch
from sound_fx import SoundManager
from ui_renderer import UIRenderer
from main import BlockRoyaleApp
from ai_bot import AIBot

print("=== 1. Testing Tournament DAS / ARR & Soft Drop ===")
app = BlockRoyaleApp()
app.settings.data.update(das_ms=135, arr_ms=33, sdf_ms=35)       # 이 테스트는 기본 조작 설정을 가정함 (사용자가 설정에서 DAS 등을 바꿔도 결과가 흔들리지 않게 고정)
app.apply_handling()
app.start_game(mode="SOLO", total_players=10)

# Simulate pressing and holding LEFT
app.key_left_down = True
init_x = app.match.local_engine.current_x
# Update 0.05s (less than DAS_DELAY 0.135s) -> should NOT auto-repeat yet
app._update_game(0.05)
assert app.match.local_engine.current_x == init_x, "Should not auto-repeat before DAS delay"

# Update 0.20s (passes DAS delay and multiple ARR intervals)
app._update_game(0.20)
assert app.match.local_engine.current_x < init_x, "Should have smoothly auto-repeated to the left"
print(f"DAS/ARR Move verified: X shifted from {init_x} to {app.match.local_engine.current_x}")

# Simulate holding DOWN (Soft Drop)
app.key_left_down = False
app.key_down_down = True
init_y = app.match.local_engine.current_y
init_score = app.match.local_engine.score
app._update_game(0.12)
assert app.match.local_engine.current_y > init_y, "Soft drop should continuously lower the piece"
assert app.match.local_engine.score > init_score, "Soft drop should award points"
print(f"Soft Drop verified: Y shifted from {init_y} to {app.match.local_engine.current_y}, score gained {app.match.local_engine.score - init_score}")

print("\n=== 2. Testing Combat Stats (APM, LPM, Timer) ===")
app.match.local_engine.lines_cleared_total = 12
app.match.total_attacks_sent = 16
apm, lpm, t_str = app.match.get_combat_stats()
print(f"Stats: APM={apm:.1f}, LPM={lpm:.1f}, Time={t_str}")
assert apm > 0 and lpm > 0 and ":" in t_str

print("\n=== 3. Testing Phase Milestones & Bot Difficulty Scaling ===")
match = app.match
bot = AIBot("BOT_TEST", difficulty="hard")
init_action_interval = bot.action_interval

# Scale for 50 players
bot.adjust_for_alive_count(50)
assert bot.action_interval < init_action_interval, "Bot should get faster at 50 players"

# Scale for 10 players
bot.adjust_for_alive_count(10)
assert bot.action_interval <= 0.09, "Hard bot should reach top tournament speed at 10 players"
print("Bot dynamic scaling verified!")

# Phase milestone check with 100 players
match100 = BattleRoyaleMatch(total_players=100)
assert match100.phase == 1, "Phase should start at 1"

match100.alive_count = 50
match100.update(0.1)
assert match100.phase == 2, "Phase should be 2 at <= 50 players"

match100.alive_count = 10
match100.update(0.1)
assert match100.phase == 3, "Phase should be 3 at <= 10 players"
print(f"Match Phase successfully transitioned from 1 -> 2 -> {match100.phase}!")

print("\n=== 4. Testing UIRenderer With Combat Stats Panel ===")
app.renderer.render(app.match, app.sound_mgr)
print("UI Render with combat stats panel & hard drop dust: OK!")

print("\n>>> ALL 100-POINT PERFECTION SUITE TESTS PASSED! <<<")

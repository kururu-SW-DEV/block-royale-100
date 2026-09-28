"""
Block Royale 100 - Battle Royale Manager
참가자 관리, 타겟팅 로직, K.O. 및 순위 산정, 스크린 셰이크 및 이펙트 이벤트 연동
"""

import time
import math
import random
from block_engine import BlockEngine
from ai_bot import AIBot
import bot_brain
import bot_pool
from config import TARGET_MODES, BOARD_HEIGHT, ATTACKER_BONUS, BADGE_TIERS, MULTI_TARGET_MAX, MAX_INCOMING_GARBAGE

def get_badge_info(ko_count):
    """K.O. 수 -> (배지 단계, 공격력 보너스 배율, 표시 문자열). 단계별 기준은 config.BADGE_TIERS"""
    level = 0
    for lv, (need, _bonus) in enumerate(BADGE_TIERS):
        if ko_count >= need:
            level = lv
    bonus = BADGE_TIERS[level][1]
    return level, bonus, f"{int(round(bonus * 100))}%"


_CG_CHARS = set("IJLOSTZG.")


def grid_rows(grid):
    """엔진 보드 -> 문자열 20줄 (블록 종류 문자, 빈칸은 '.')"""
    return ["".join(c if c else "." for c in row) for row in grid]


def piece_state(engine):
    """조작 중인 블록 (종류, 회전, x, y). 없으면 None"""
    if engine.current_piece and not engine.game_over:
        return (engine.current_piece, engine.current_rot, engine.current_x, engine.current_y)
    return None


BOT_SEARCH_BUDGET = 0.008      # 프레임당 봇 전원의 탐색 시간 상한(초). 100명이 동시에 생각해도 화면이 끊기지 않게 함


class BattleRoyaleMatch:
    def __init__(self, total_players=100, local_player_id="P1", local_player_name="Player", net_mgr=None, initial_players=None, sound_mgr=None, bot_difficulty="mixed", attacks_enabled=True):
        self.attacks_enabled = bool(attacks_enabled)   # False: 서바이벌 모드 (서로 공격/쓰레기 줄/K.O. 없이 각자 끝까지 생존)
        self.total_players = max(2, min(100, total_players))
        self.local_player_id = local_player_id
        self.local_player_name = local_player_name
        self.net_mgr = net_mgr
        self.initial_players = initial_players  # 클라이언트가 호스트로부터 전달받은 슬롯 목록
        self.sound_mgr = sound_mgr
        self.bot_difficulty = bot_difficulty
        
        # 로컬 플레이어 블록 엔진
        self.local_engine = BlockEngine()
        self.local_color = 0           # 내 이름 색 번호 (main에서 설정)
        self.local_target_mode = "RANDOM"
        self.local_manual_target_id = None
        self.local_ko_count = 0
        self.local_is_alive = True
        self.local_rank = 0
        self.is_paused = False
        
        # 관전 모드 상태
        self.is_spectating = False
        self.spectate_target_id = None
        self.spectate_notice = None       # 관전 대상이 탈락해 다른 대상으로 넘어갔을 때의 알림 {text, sub, t0}
        
        # 참가자 슬롯 관리
        self.players = {}
        
        # 탈락 순서 기록 (마지막 남은 사람이 1위)
        self.alive_count = self.total_players
        self.next_rank_to_assign = self.total_players
        self.match_finished = False
        self.winner_id = None
        
        # 공격 궤적 이펙트 리스트: [(from_id, to_id, lines, start_time, duration)]
        self.attack_effects = []
        self.fx_low = False                        # True면 화면이 느려 봇끼리의 공격 연출을 생략 (앱이 프레임 시간을 보고 설정)
        
        # e-스포츠 통계 및 페이즈 마일스톤 관리
        self._bot_rr = 0
        self.elapsed = 0.0  # 경기 진행 시간 (dt 누적: 일시정지 시 멈춤)
        self.local_survival_sec = None   # 내가 탈락/우승한 순간의 시간 (이후 통계는 이 값으로 고정)
        self.frozen_stats = None         # 탈락/우승 순간의 (APM, LPM) 스냅샷
        self.total_attacks_sent = 0
        self.phase = 1
        
        # 시각 연출: 화면 흔들림 및 팝업 텍스트
        self.screen_shake = 0.0
        self.floating_texts = []  # dict: text, color, birth, duration, size
        self.commentary = []      # 전광판 중계 기록: dict(text, color, birth)
        
        self._setup_participants()
        self.add_commentary(f"경기 시작!  {self.total_players}명 배틀로얄", (120, 235, 255))

    def get_combat_stats(self):
        """실시간 e-스포츠 지표 (APM: 분당 공격력, LPM: 분당 라인 클리어, 경기 시간) 산출"""
        if self.frozen_stats is not None:      # 탈락/우승 후에는 기록을 그대로 고정
            apm, lpm = self.frozen_stats
            elapsed = max(1.0, self.local_survival_sec)
        else:
            elapsed = max(1.0, self.elapsed)
            apm = (self.total_attacks_sent / elapsed) * 60.0
            lpm = (self.local_engine.lines_cleared_total / elapsed) * 60.0
        m = int(elapsed // 60)
        s = int(elapsed % 60)
        return apm, lpm, f"{m:02d}:{s:02d}"

    def freeze_local_stats(self):
        """내 경기가 끝난 순간(탈락 또는 우승)의 시간과 지표를 고정"""
        if self.local_survival_sec is not None:
            return
        elapsed = max(1.0, self.elapsed)
        self.local_survival_sec = self.elapsed
        self.frozen_stats = ((self.total_attacks_sent / elapsed) * 60.0,
                             (self.local_engine.lines_cleared_total / elapsed) * 60.0)

    def survival_seconds(self):
        return self.local_survival_sec if self.local_survival_sec is not None else self.elapsed

    def add_floating_text(self, text, color, duration=2.0, size=24, category="normal"):
        self.floating_texts.append({
            "text": text,
            "color": color,
            "birth": time.time(),
            "duration": duration,
            "size": size,
            "category": category
        })

    def add_commentary(self, text, color=(255, 190, 70), prio=0):
        """상단 전광판에 표시할 경기 중계 한 줄. prio=1(결승/우승/페이즈 등 중요 소식)은 대기 중인 일반 소식보다 먼저 방송됨"""
        self._commentary_seq = getattr(self, "_commentary_seq", 0) + 1
        self.commentary.append({"text": text, "color": color, "birth": time.time(), "seq": self._commentary_seq, "prio": prio})
        if len(self.commentary) > 40:
            del self.commentary[:-40]

    def _short_name(self, pid, n=9):
        return str(self.players.get(pid, {}).get("name", "?"))[:n]

    def trigger_screen_shake(self, amount=8.0):
        self.screen_shake = max(self.screen_shake, amount)

    # 배틀로얄 후반 공격력 증폭: 강한 봇끼리 오래 버티는 교착을 막기 위해, 이 시간(초)이 지나면 1분마다 공격 줄 수가 20%씩 늘어남 (최대 3배). None이면 끔
    BATTLE_PRESSURE_START = 540.0     # 배틀로얄 후반 시간 압박 시작(초)
    MAX_BOT_FX = 8                     # 나와 무관한 봇끼리의 공격 빔을 동시에 그릴 최대 개수
    ESCALATION_START = 300.0
    ESCALATION_PER_MIN = 0.20
    ESCALATION_MAX = 3.0

    def attack_multiplier(self):
        if self.ESCALATION_START is None or self.elapsed < self.ESCALATION_START:
            return 1.0
        return min(self.ESCALATION_MAX, 1.0 + (self.elapsed - self.ESCALATION_START) / 60.0 * self.ESCALATION_PER_MIN)

    SURVIVAL_PRESSURE_START = 180.0      # 이 시간(초) 이후부터 압박 시작
    SURVIVAL_PRESSURE_MIN_INTERVAL = 5.0
    SURVIVAL_PRESSURE_RAMP = 20.0        # 이 시간(초)마다 간격이 1초씩 줄어듦

    def _survival_pressure(self, dt, start=None, label="서바이벌 압박"):
        """시간 압박: start초 뒤부터 생존자 전원에게 쓰레기 줄을 주기적으로 올림. 간격은 20초에서 RAMP초마다 1초씩 줄어 5초까지 (서바이벌 3분 뒤, 배틀로얄은 후반 9분 뒤)"""
        start = self.SURVIVAL_PRESSURE_START if start is None else start
        if self.elapsed < start:
            return
        if not getattr(self, "_pressure_announced", False):
            self._pressure_announced = True
            self.add_floating_text(f"[경고] {label} 시작! 쓰레기 줄이 주기적으로 올라옵니다", (255, 190, 90), duration=3.5, size=26, category="action")
            self.add_commentary(f"{label} 시작 - 쓰레기 줄이 주기적으로 올라옵니다", (255, 190, 90), prio=1)
        self._pressure_t = getattr(self, "_pressure_t", 0.0) + dt
        interval = max(self.SURVIVAL_PRESSURE_MIN_INTERVAL, 20.0 - (self.elapsed - start) / self.SURVIVAL_PRESSURE_RAMP)
        if self._pressure_t < interval:
            return
        self._pressure_t = 0.0
        # 간격이 최소에 닿은 뒤에도 15초마다 한 번에 올라오는 줄이 1줄씩 늘어남(최대 10줄) (강한 봇도 결국 끝나도록)
        ramp_end = start + (20.0 - self.SURVIVAL_PRESSURE_MIN_INTERVAL) * self.SURVIVAL_PRESSURE_RAMP
        rows = min(10, 1 + int(max(0.0, self.elapsed - ramp_end) / 15.0))
        if self.local_is_alive:
            self.local_engine.queue_garbage(rows)
        for p in self.players.values():
            if p["is_alive"] and p.get("bot"):
                eng = p["bot"].engine
                eng.queue_garbage(rows)
                # 만약 대기열이 이미 24줄 상한까지 차 있다면 시간 압박 시 대기 쓰레기를 직접 보드로 밀어올려 확실한 서든데스 유도
                if eng.incoming_garbage >= MAX_INCOMING_GARBAGE:
                    push = min(eng.incoming_garbage, rows)
                    eng.incoming_garbage -= push
                    eng._push_garbage(push)
                    if eng.game_over:
                        p["bot"].is_alive = False

    def _get_dynamic_fall_speed(self):
        """생존자 비율에 따라 부드럽게 빨라지는 중력 (초 단위, 0.80s -> 0.16s)"""
        ratio = max(0.0, min(1.0, (self.alive_count - 1) / max(1, self.total_players - 1)))
        return 0.16 + (0.80 - 0.16) * (ratio ** 0.8)

    @staticmethod
    def _new_player(pid, name, is_ai, bot, compact_grid):
        """참가자 한 명의 초기 상태 (모든 등록 경로가 같은 필드를 갖도록 한 곳에서 생성)"""
        return {
            "id": pid,
            "name": name,
            "is_ai": is_ai,
            "bot": bot,
            "is_alive": True,
            "ko_count": 0,
            "rank": 0,
            "target_id": None,
            "last_attacker": None,
            "attacks": 0,
            "survival": None,
            "score": 0,
            "lines": 0,
            "compact_grid": compact_grid,
            "highest_y": 20,
        }

    def _difficulty_choices(self):
        """봇 난이도 설정에 따라 봇마다 무작위로 고를 난이도 목록"""
        if self.bot_difficulty in ("easy", "normal", "hard", "master"):
            return [self.bot_difficulty]
        return ["easy", "easy", "normal", "normal", "hard"]      # mixed (배틀로얄 표준 혼합)

    def _setup_participants(self):
        # 클라이언트 모드이고 호스트가 정해준 초기 참가자 명단이 있는 경우
        if self.initial_players:
            # 호스트만 봇을 직접 시뮬레이션한다. (클라이언트는 호스트가 보내는 월드 상태로 봇 화면만 표시)
            is_host = bool(self.net_mgr and self.net_mgr.mode == "HOST")
            diff_choices = self._difficulty_choices()
            for pinfo in self.initial_players:
                pid = pinfo["id"]
                pname = pinfo["name"]
                is_me = (pid == self.local_player_id)
                is_ai = pinfo.get("is_ai", False)
                bot = AIBot(bot_id=pid, name=pname, difficulty=random.choice(diff_choices)) if (is_host and is_ai) else None
                self.players[pid] = self._new_player(pid, pname, is_ai, bot, self.local_engine.get_compact_grid() if is_me else (bot.engine.get_compact_grid() if bot else [0] * BOARD_HEIGHT))
            self.total_players = len(self.players)
            self.alive_count = self.total_players
            self.next_rank_to_assign = self.total_players
            return

        # 1. 로컬 플레이어 등록
        self.players[self.local_player_id] = self._new_player(self.local_player_id, self.local_player_name, False, None, self.local_engine.get_compact_grid())
        
        # 2. 네트워크 플레이어들 등록 (호스트 모드)
        registered_count = 1
        if self.net_mgr and self.net_mgr.mode == "HOST":
            for addr, cinfo in list(self.net_mgr.clients.items()):
                cid = cinfo["id"]
                cname = cinfo["name"]
                self.players[cid] = self._new_player(cid, cname, False, None, [0] * BOARD_HEIGHT)
                registered_count += 1
                if registered_count >= self.total_players:
                    break
                    
        # 3. 부족한 슬롯을 사람다운 AI 봇으로 충원
        bot_idx = 1
        diff_choices = self._difficulty_choices()

        while registered_count < self.total_players:
            bid = f"BOT_{bot_idx:02d}"
            bname = f"CPU_{bot_idx:02d}"
            diff = random.choice(diff_choices)
            bot = AIBot(bot_id=bid, name=bname, difficulty=diff)
            self.players[bid] = self._new_player(bid, bname, True, bot, bot.engine.get_compact_grid())
            bot_idx += 1
            registered_count += 1

    def set_target_mode(self, mode):
        """조준 모드를 바로 지정 (숫자키). 수동으로 찍어 둔 대상은 해제"""
        if mode in TARGET_MODES:
            self.local_target_mode = mode
            self.local_manual_target_id = None
        return self.local_target_mode

    def cycle_target_mode(self):
        """타겟팅 모드 순환 (RANDOM -> KO -> ATTACKERS -> BADGES)"""
        idx = TARGET_MODES.index(self.local_target_mode)
        self.local_target_mode = TARGET_MODES[(idx + 1) % len(TARGET_MODES)]
        self.local_manual_target_id = None
        return self.local_target_mode

    def set_manual_target(self, target_id):
        """특정 플레이어 클릭 시 수동 타겟 지정"""
        if target_id in self.players and self.players[target_id]["is_alive"] and target_id != self.local_player_id:
            self.local_manual_target_id = target_id

    def get_attackers_count_for(self, pid):
        """특정 플레이어를 조준 중인 살아있는 상대방 수 계산 (카운터 보너스 산정용)"""
        return sum(1 for p in self.players.values() if p["is_alive"] and p.get("target_id") == pid)

    def get_badge_info(self, ko_count=None):
        """로컬 플레이어 또는 지정된 플레이어의 배지 등급 및 버프율 반환"""
        if ko_count is None:
            ko_count = self.local_ko_count
        return get_badge_info(ko_count)

    def get_attacker_bonus(self, count):
        """다수의 적에게 동시 조준당할 때의 반격 보너스 라인 반환"""
        return ATTACKER_BONUS.get(min(6, count), 0)

    def get_name_colors(self):
        """{플레이어 ID: 이름 색 번호} - 호스트는 참가자 목록, 클라이언트는 호스트가 보낸 명단에서 가져옴 (봇은 기본색)"""
        d = {}
        nm = self.net_mgr
        if nm:
            if nm.mode == "HOST":
                d[nm.my_player_id or "HOST_P1"] = nm.my_color
                for c in list(nm.clients.values()):
                    d[c["id"]] = c.get("color", 0)
            elif nm.mode == "CLIENT":
                for e in nm.roster:
                    d[e["id"]] = e.get("color", 0)
        d[self.local_player_id] = self.local_color
        return d

    def player_stats(self, pid):
        """플레이어 한 명의 성적: 시간(생존), APM, LPM, 점수, 라인, K.O. (관전 화면과 최종 순위표에서 사용)"""
        p = self.players.get(pid)
        if not p:
            return {"time": 0.0, "apm": 0.0, "lpm": 0.0, "score": 0, "lines": 0, "attacks": 0, "ko": 0}
        if pid == self.local_player_id:
            t = self.survival_seconds()
            lines, score, attacks = self.local_engine.lines_cleared_total, self.local_engine.score, self.total_attacks_sent
            ko = self.local_ko_count
        else:
            t = p["survival"] if p.get("survival") is not None else self.elapsed
            lines, score, ko = p.get("lines", 0), p.get("score", 0), p.get("ko_count", 0)
            bot = p.get("bot")
            # 봇은 상쇄로 소모된 공격력도 생성치로 집계 (들어오는 쓰레기를 막아내느라 APM이 0에 묶이는 것 방지)
            attacks = bot.engine.attack_generated_total if bot else p.get("attacks", 0)
        t = float(t)
        te = max(1.0, t)
        return {"time": t, "apm": attacks / te * 60.0, "lpm": lines / te * 60.0,
                "score": score, "lines": lines, "attacks": attacks, "ko": ko}

    def standings(self):
        """최종 순위표: 순위 오름차순. 순위가 없는 생존자는 점수 순으로 앞쪽에 둠."""
        rows = []
        for pid, p in self.players.items():
            st = self.player_stats(pid)
            rows.append({"id": pid, "name": p["name"], "is_local": pid == self.local_player_id, "is_ai": p.get("is_ai", False),
                         "rank": p.get("rank", 0), "alive": p["is_alive"], **st})
        rows.sort(key=lambda r: (r["rank"] if r["rank"] > 0 else 0, -r["score"]))
        return rows

    def get_spectate_engine(self, pid):
        """관전 대상의 '실제 플레이 화면'용 엔진.
        - 호스트에서 돌아가는 봇: 봇 엔진 그대로
        - 그 외(클라이언트 화면의 봇/다른 사람, 호스트 화면의 원격 사람): 네트워크로 받은 스냅샷을 복원한 엔진
        - 스냅샷이 아직 없으면 None (압축 그리드로 임시 표시)"""
        p = self.players.get(pid)
        if not p:
            return None
        if p.get("bot"):
            return p["bot"].engine
        snap = None
        if self.net_mgr:
            snap = self.net_mgr.remote_details.get(pid)
            if snap is None:
                snap = self.net_mgr.remote_players_state.get(pid, {}).get("snap")
        if snap is None:
            return None
        if not hasattr(self, "_spectate_engines"):
            self._spectate_engines = {}
        eng = self._spectate_engines.get(pid)
        if eng is None:
            eng = self._spectate_engines[pid] = BlockEngine(seed=0)
        try:
            eng.load_snapshot(snap)
        except Exception:
            return None
        return eng

    def snapshot_for(self, pid):
        """(호스트) pid 플레이어의 관전용 스냅샷"""
        if pid == self.local_player_id:
            return self.local_engine.snapshot()
        p = self.players.get(pid)
        if p and p.get("bot"):
            return p["bot"].engine.snapshot()
        if self.net_mgr:
            return self.net_mgr.remote_players_state.get(pid, {}).get("snap")
        return None

    def _check_spectate_target(self, now):
        """관전 중인 상대가 탈락하면 패배를 알리고, 다음 생존자(플레이어 순서상 바로 뒤)로 자동 전환"""
        if not getattr(self, "is_spectating", False) or self.match_finished:
            return
        tid = self.spectate_target_id
        if tid not in self.players or self.players[tid]["is_alive"]:
            return
        ids = [pid for pid in self.players if pid != self.local_player_id]
        alive = [pid for pid in ids if self.players[pid]["is_alive"]]
        if not alive:
            return
        after = ids[ids.index(tid) + 1:] + ids[:ids.index(tid)] if tid in ids else ids
        nxt = next((pid for pid in after if self.players[pid]["is_alive"]), alive[0])
        dead_name = self.players[tid]["name"]
        self.spectate_target_id = nxt
        self.spectate_notice = {"text": f"{dead_name} 패배!", "sub": f"관전 대상을 {self.players[nxt]['name']}(으)로 전환합니다", "t0": now}
        if self.sound_mgr:
            self.sound_mgr.play('ko')

    def cycle_spectate_target(self, direction=1):
        """탈락 후 관전 모드에서 다른 생존자 전환 (방향키 조작)"""
        alive_ids = [pid for pid, p in self.players.items() if p["is_alive"] and pid != self.local_player_id]
        if not alive_ids:
            return None
        if self.spectate_target_id in alive_ids:
            idx = alive_ids.index(self.spectate_target_id)
            self.spectate_target_id = alive_ids[(idx + direction) % len(alive_ids)]
        else:
            self.spectate_target_id = alive_ids[0]
        return self.spectate_target_id

    def get_target_for(self, attacker_id, strategy=None):
        """전략에 따른 대상 플레이어 ID 계산 (AUTO 모드 시 사람 플레이어 최우선 자동 조준)"""
        strat = strategy or self.local_target_mode
        alive_candidates = [
            pid for pid, p in self.players.items()
            if p["is_alive"] and pid != attacker_id
        ]
        if not alive_candidates:
            return None
            
        if attacker_id == self.local_player_id and self.local_manual_target_id:
            if self.local_manual_target_id in alive_candidates:
                return self.local_manual_target_id
            else:
                self.local_manual_target_id = None
                
        # AUTO 모드: 호스트-클라이언트 모드에서 다른 사람 플레이어를 무조건 자동 타겟팅!
        if strat == "AUTO":
            other_humans = [
                pid for pid in alive_candidates
                if not self.players[pid].get("is_ai", False)
            ]
            if other_humans:
                # 살아있는 인간 상대 중 가장 위협적인(블록이 높은) 사람 자동 타겟팅
                return min(other_humans, key=lambda pid: self.players[pid].get("highest_y", 20))
            # 인간 상대가 모두 탈락했거나 솔로일 때: K.O. 직전(가장 높이 쌓인) 적 자동 타겟팅
            return min(alive_candidates, key=lambda pid: self.players[pid].get("highest_y", 20))
            
        elif strat == "KO":
            return min(alive_candidates, key=lambda pid: self.players[pid].get("highest_y", 20))
        elif strat == "ATTACKERS":
            attackers = [pid for pid in alive_candidates if self.players[pid].get("target_id") == attacker_id]
            if attackers:
                cur = self.players.get(attacker_id, {}).get("target_id")
                if cur in attackers:
                    return cur                                   # 이미 겨누던 공격자가 계속 나를 노리면 유지 (조준선이 프레임마다 흔들리지 않게)
                return random.choice(attackers)
            return min(alive_candidates, key=lambda pid: self.players[pid].get("highest_y", 20))
        elif strat == "BADGES":
            return max(alive_candidates, key=lambda pid: self.players[pid].get("ko_count", 0))
        elif strat == "RANDOM":
            current_target = self.players[attacker_id].get("target_id")
            if current_target and current_target in alive_candidates:
                return current_target
            return random.choice(alive_candidates)
            
        return random.choice(alive_candidates)

    # 봇 조준 분산: 한 명에게 봇이 몰려 일점 타격이 되면 사람이 도저히 못 버티므로, 이미 노리는 봇이 많은 대상은 점수를 깎고 상한을 둠
    FOCUS_CAP = 3                    # 한 플레이어를 동시에 노릴 수 있는 봇 수의 기본 상한
    HUMAN_FOCUS_CAP = 2              # 사람 플레이어에게는 더 낮은 상한 (봇보다 상쇄 능력이 낮아 같은 압박이 훨씬 무겁기 때문)
    KILL_EXTRA = 2                   # 탈락시킬 수 있는 마무리 공격은 상한을 이만큼까지만 초과 허용
    FOCUS_PENALTY = 2.5              # 이미 노리는 봇 1명당 조준 점수 감점

    def _focus_cap(self, p):
        return self.FOCUS_CAP if p.get("is_ai") else self.HUMAN_FOCUS_CAP

    @staticmethod
    def _danger(p):
        """쌓인 높이 + 들어올 쓰레기 (한계에 가까울수록 큼)"""
        return (BOARD_HEIGHT - p.get("highest_y", BOARD_HEIGHT)) + p.get("ig", 0)

    def _target_loads(self, attacker_id):
        """지금 각 플레이어를 노리고 있는 (살아 있는) 봇 수"""
        loads = {}
        for q, pp in self.players.items():
            if q != attacker_id and pp["is_alive"] and pp.get("bot") is not None:
                t = pp.get("target_id")
                if t:
                    loads[t] = loads.get(t, 0) + 1
        return loads

    def _smart_target(self, attacker_id, attack=0):
        """봇의 조준 대상 선택: 위험도(쌓인 높이 + 들어올 쓰레기)가 높을수록, 나를 노리는 상대일수록, 이번 공격으로 탈락시킬 수 있을수록 우선.
        이미 노리는 봇이 많은 상대는 점수를 깎고 상한을 넘으면 제외(사람은 상한이 더 낮음). 대기 쓰레기가 이미 상한(MAX_INCOMING_GARBAGE)까지 찬 상대는
        더 보내도 버려지므로 뒤로 미루되, 고를 수 있는 상대가 그뿐이면 그래도 그 상대를 노림 (조준 대상이 없어져 공격이 사라지는 일 방지)"""
        loads = self._target_loads(attacker_id)
        best, best_s = None, -1e9
        fallback, fb_load = None, 1e9                    # 상한/포화로 못 고른 상대 중 노리는 봇이 가장 적은 상대
        for q, p in self.players.items():
            if not p["is_alive"] or q == attacker_id:
                continue
            danger = self._danger(p)
            load = loads.get(q, 0)
            cap = self._focus_cap(p)
            full = p.get("ig", 0) >= MAX_INCOMING_GARBAGE   # 대기열이 가득 참: 더 보내도 버려짐
            key_load = load + (100 if full else 0)
            if key_load < fb_load:
                fallback, fb_load = q, key_load
            if full and self.alive_count > 3:
                continue
            kill = bool(attack) and attack >= 3 and danger + attack >= BOARD_HEIGHT - 1
            if load >= cap + (self.KILL_EXTRA if kill else 0):
                continue                                         # 동시에 노리는 봇이 상한에 찼음 (마무리 공격만 KILL_EXTRA명까지 더 허용)
            sc = danger + p.get("ko_count", 0) * 0.7 + random.uniform(0.0, 1.5) - load * self.FOCUS_PENALTY
            if p.get("target_id") == attacker_id:
                sc += 4.0                                        # 나를 노리는 상대를 견제
            if kill:
                sc += 8.0                                        # 이번 공격으로 마무리 가능
            if sc > best_s:
                best, best_s = q, sc
        return best if best is not None else fallback

    def _spread_random_target(self, attacker_id):
        """무작위 조준(쉬움/보통 봇): 상한 안에서 노리는 봇이 적은 상대들 중에서 고름 (대기열이 가득 찬 상대는 후순위)"""
        loads = self._target_loads(attacker_id)
        alive = [(q, p) for q, p in self.players.items() if p["is_alive"] and q != attacker_id]
        if not alive:
            return None
        live = [(q, p) for q, p in alive if p.get("ig", 0) < MAX_INCOMING_GARBAGE] or alive
        allowed = [q for q, p in live if loads.get(q, 0) < self._focus_cap(p)]
        if not allowed:
            low = min(loads.get(q, 0) for q, _ in live)
            allowed = [q for q, _ in live if loads.get(q, 0) <= low]
        return random.choice(allowed)

    def apply_attack(self, from_id, to_id, lines, from_network=False, multi=1, order=0):
        """공격 라인 전달 및 궤적 이펙트 생성 (from_network: 네트워크로 수신한 공격은 재전송하지 않음)"""
        if lines <= 0 or not self.attacks_enabled:
            return                                                     # 서바이벌 모드: 어떤 공격도 전달/표시하지 않음
        if not from_network:
            mult = self.attack_multiplier()
            if mult > 1.0:
                lines = int(math.ceil(lines * mult))                   # 후반 공격력 증폭 (네트워크로 받은 공격은 보낸 쪽에서 이미 반영됨)
        if to_id in self.players and not self.players[to_id]["is_alive"]:
            return                                                     # 이미 탈락한 대상에게는 공격/이펙트를 보내지 않음 (죽은 카드가 번쩍이며 흔들리는 것 방지)
        if to_id in self.players:
            self.players[to_id]["last_attacker"] = from_id
        if from_id in self.players:
            self.players[from_id]["attacks"] += lines          # 플레이어별 공격력 합계 (APM 계산용)
            
        now = time.time()
        local_fx = from_id == self.local_player_id or to_id == self.local_player_id
        # 봇끼리의 공격 빔은 동시에 그리는 수를 제한 (마스터 100명일 때 화면 부하/프레임 저하 방지). 공격 자체(줄 전달, 네트워크 전송)는 그대로 처리됨
        if local_fx or (not self.fx_low and sum(1 for e in self.attack_effects if not e.get("local")) < self.MAX_BOT_FX):
            self.attack_effects.append({
                "local": local_fx,
                "from_id": from_id,
                "to_id": to_id,
                "lines": lines,
                "start_time": now + order * 0.07,                          # 다중 포격: 빔이 순서대로 부채꼴로 발사되는 연출
                "multi": multi,
                "duration": 0.58,
                "impacted": False
            })

        if lines >= (4 if self.total_players > 10 else 3) and from_id in self.players and to_id in self.players:
            self.add_commentary(f"{self._short_name(from_id)} → {self._short_name(to_id)}  {lines}줄 공격!", (255, 150, 80))

        # 1. 로컬 플레이어가 피격 대상인 경우
        if to_id == self.local_player_id and self.local_is_alive:
            self.local_engine.queue_garbage(lines)
            self.trigger_screen_shake(min(14.0, 5.0 + lines * 2.2))
            if self.sound_mgr:
                self.sound_mgr.play('garbage')
            attacker_p = self.players.get(from_id, {})
            attacker_name = attacker_p.get("name", "적 플레이어")
            self.add_floating_text(f"[피격 경고] +{lines}줄 공격 받음 (보낸이: {attacker_name})", (255, 75, 75), duration=2.4, size=22, category="alert")
            
        # 2. 로컬에서 관리하는 AI 봇이 피격 대상인 경우
        elif to_id in self.players:
            p = self.players[to_id]
            if p["is_ai"] and p["bot"] and p["is_alive"]:
                p["bot"].engine.queue_garbage(lines)
                
        # 3. 네트워크 모드일 경우 원격 클라이언트에 패킷 전송
        if self.net_mgr and self.net_mgr.running:
            if not from_network and (from_id == self.local_player_id or self.net_mgr.mode == "HOST"):
                self.net_mgr.send_attack(from_id, to_id, lines)

    def _eliminate_player(self, victim_id, killer_id=None):
        """플레이어 탈락 처리"""
        if victim_id not in self.players or not self.players[victim_id]["is_alive"]:
            return
        # 킬러 미지정 시 마지막으로 이 플레이어를 공격한 생존자에게 K.O. 부여
        if killer_id is None:
            last = self.players[victim_id].get("last_attacker")
            if last and last != victim_id and self.players.get(last, {}).get("is_alive"):
                killer_id = last
            
        self.players[victim_id]["is_alive"] = False
        self.players[victim_id]["survival"] = self.elapsed
        self.players[victim_id]["rank"] = self.next_rank_to_assign
        self.next_rank_to_assign -= 1
        self.alive_count -= 1

        vn = self._short_name(victim_id)
        if killer_id and killer_id in self.players:
            self.add_commentary(f"{self._short_name(killer_id)} → {vn} K.O.", (255, 110, 110))
        else:
            self.add_commentary(f"{vn} 탈락", (255, 110, 110))
        if self.total_players > self.alive_count >= 2 and self.alive_count in (2, 3, 5, 10):
            self.add_commentary("결승전!  최후의 2인" if self.alive_count == 2 else f"생존자 {self.alive_count}명!  접전", (255, 215, 90), prio=1)

        if victim_id == self.local_player_id:
            self.freeze_local_stats()
            self.local_is_alive = False
            self.local_rank = self.players[victim_id]["rank"]
            self.trigger_screen_shake(18.0)
            
        # 킬러에게 K.O. 부여 및 배지 등급 승급 판정
        if killer_id and killer_id in self.players:
            old_lvl, _, _ = get_badge_info(self.players[killer_id]["ko_count"])
            self.players[killer_id]["ko_count"] += 1
            if killer_id == self.local_player_id:
                self.local_ko_count += 1
                new_lvl, _, new_pct = get_badge_info(self.local_ko_count)
                self.trigger_screen_shake(10.0)
                victim_name = self.players.get(victim_id, {}).get("name", "상대")
                self.add_floating_text(f"[K.O. 처치!] +1 배지 획득 >> {victim_name}", (255, 220, 50), duration=2.5, size=24, category="ko")
                if new_lvl > old_lvl:
                    if self.sound_mgr:
                        self.sound_mgr.play('badge_up')
                    self.add_floating_text(f"★ 배지 승급 Lv.{new_lvl}! 공격력 +{new_pct} 강화! ★", (255, 235, 100), duration=3.0, size=26, category="action")
                
        # 승자 판정 (최후의 1인)
        if self.alive_count <= 1:
            self.match_finished = True
            for pid, p in self.players.items():
                if p["is_alive"]:
                    p["rank"] = 1
                    p["survival"] = self.elapsed
                    self.winner_id = pid
                    self.add_commentary(f"★ {self._short_name(pid)} 최종 우승! ★", (255, 230, 80), prio=1)
                    if pid == self.local_player_id:
                        self.freeze_local_stats()
                        self.local_rank = 1
                        self.trigger_screen_shake(20.0)
                        self.add_floating_text("★ 1위 최종 우승 로열 빅토리! ★", (255, 230, 80), duration=3.5, size=34, category="action")
                    break

    def on_lines_cleared(self, cleared):
        """라인 클리어 공통 핸들러 (하드 드롭, 소프트 드롭, 자연 낙하 공통 처리)"""
        if cleared <= 0:
            return
            
        info = getattr(self.local_engine, 'last_clear_info', None) or {}
        is_tspin = info.get('is_tspin', False)
        is_b2b = info.get('is_b2b', False)
        chain = info.get('b2b_chain', 0)
        
        if self.sound_mgr:
            combo = max(0, self.local_engine.combo)          # 0 = 첫 클리어, 이어질수록 증가 -> 삭제음이 한 음씩 올라감
            if is_tspin:
                self.sound_mgr.play('tspin', combo=combo)
            elif cleared >= 4:
                self.sound_mgr.play('quad', combo=combo)
            else:
                self.sound_mgr.play('clear', combo=combo)
            if combo >= 1:
                self.sound_mgr.play('combo', combo=combo)    # 콤보 차임 (콤보 단계에 맞는 음)
                
        me = self._short_name(self.local_player_id)
        if info.get('is_pc'):
            self.trigger_screen_shake(18.0)
            self.add_commentary(f"★ {me}  PERFECT CLEAR! ★", (255, 225, 90), prio=1)
            if self.sound_mgr:
                self.sound_mgr.play('perfect')
        if is_tspin:
            self.add_commentary(f"{me}  {f'B2B x{chain} ' if is_b2b and chain >= 1 else ''}T-스핀!", (255, 150, 255))
        elif cleared >= 4:
            self.add_commentary(f"{me}  {f'B2B x{chain} ' if is_b2b and chain >= 1 else ''}쿼드!", (255, 215, 0))
        if self.local_engine.combo >= 4:
            self.add_commentary(f"{me}  {self.local_engine.combo}연속 콤보!", (255, 120, 220))

        if is_tspin:
            self.trigger_screen_shake(14.0)
            prefix = f"★ B2B x{chain} " if (is_b2b and chain >= 1) else ("★ B2B " if is_b2b else "★ ")
            if cleared == 3:
                self.add_floating_text(f"{prefix}T-스핀 트리플! (6줄 공격) ★", (255, 130, 255), duration=2.5, size=32, category="action")
            elif cleared == 2:
                self.add_floating_text(f"{prefix}T-스핀 더블! (4줄 공격) ★", (255, 150, 255), duration=2.2, size=30, category="action")
            elif cleared == 1:
                self.add_floating_text(f"{prefix}T-스핀 싱글! (2줄 공격) ★", (255, 180, 255), duration=1.8, size=26, category="action")
            else:
                self.add_floating_text("★ T-스핀 보너스! ★", (255, 180, 255), duration=1.4, size=22, category="action")
        elif cleared >= 4:
            self.trigger_screen_shake(14.0)
            if is_b2b:
                self.add_floating_text(f"★ B2B x{chain} 쿼드! (5줄 공격) ★" if chain >= 1 else "★ B2B 쿼드! (5줄 공격) ★", (255, 235, 80), duration=2.4, size=34, category="action")
            else:
                self.add_floating_text("★ 쿼드! (4줄 제거) ★", (255, 215, 0), duration=2.2, size=32, category="action")
        elif cleared == 3:
            self.add_floating_text("★ 트리플 클리어! (3줄) ★", (100, 240, 255), duration=1.8, size=28, category="action")
        elif cleared == 2:
            self.add_floating_text("★ 더블 클리어! (2줄) ★", (120, 255, 120), duration=1.6, size=26, category="action")
        elif cleared == 1:
            self.add_floating_text("★ 싱글 클리어! (1줄) ★", (180, 220, 255), duration=1.2, size=22, category="action")
            
        if self.local_engine.combo > 0:
            self.add_floating_text(f"[{self.local_engine.combo}연속 콤보!]", (255, 120, 220), duration=1.8, size=22, category="combo")
        if info.get('is_pc'):                                                    # 일반 클리어 문구보다 나중에 넣어 가장 눈에 띄게 표시
            self.add_floating_text("★ PERFECT CLEAR! ★", (255, 225, 90), duration=3.2, size=44, category="action")

    def update(self, dt):
        """매칭 전체 프레임 업데이트"""
        if self.match_finished:
            return
            
        now = time.time()
        self.elapsed += dt
        
        # 스크린 셰이크 감쇠
        if self.screen_shake > 0:
            self.screen_shake = max(0.0, self.screen_shake - dt * 25.0)
            
        # 플로팅 텍스트 수명 체크
        self.floating_texts = [ft for ft in self.floating_texts if now - ft["birth"] < ft["duration"]]
        
        # 1. 로컬 플레이어 중력 동적 조절 및 엔진 틱 업데이트 (자연 낙하)
        if self.local_is_alive:
            self.local_engine.badge_rate = self.get_badge_info()[1]
            self.local_engine.fall_speed = self._get_dynamic_fall_speed()
            cleared = self.local_engine.update(dt)
            if cleared > 0:
                self.on_lines_cleared(cleared)

        # 2. 로컬 플레이어 타겟 갱신
        self.players[self.local_player_id]["target_id"] = self.get_target_for(self.local_player_id, self.local_target_mode)
        
        # 3. 로컬 플레이어 게임 오버 검사
        if self.local_is_alive and self.local_engine.game_over:
            self._eliminate_player(self.local_player_id)
            
        # 4. 로컬 플레이어 공격 발생 처리 (오토매틱 공격 + 배지 증폭 + 카운터 보너스)
        if self.local_engine.garbage_to_send > 0:
            target = self.players[self.local_player_id]["target_id"] if self.attacks_enabled else None
            if target:
                target_p = self.players.get(target, {})
                target_name = target_p.get("name", target)
                is_target_human = not target_p.get("is_ai", False)
                
                # 배지 증폭은 엔진에서 상쇄 이전에 이미 적용됨
                base_garbage = self.local_engine.garbage_to_send
                badge_lvl, badge_rate, badge_pct = get_badge_info(self.local_ko_count)
                
                # 조준당하고 있을 때 공격자 카운터 보너스
                att_count = self.get_attackers_count_for(self.local_player_id)
                attacker_bonus = ATTACKER_BONUS.get(min(6, att_count), 0)
                
                total_attack = base_garbage + attacker_bonus
                # 반격(ATTACKERS) 모드: 나를 노리는 플레이어가 둘 이상이면 전원에게 동시에 같은 공격을 보냄 (역전 기회)
                targets = [target]
                if self.local_target_mode == "ATTACKERS" and not self.local_manual_target_id:
                    attackers = [pid for pid, p in self.players.items()
                                 if p["is_alive"] and pid != self.local_player_id and p.get("target_id") == self.local_player_id]
                    if len(attackers) >= 2:
                        targets = attackers[:MULTI_TARGET_MAX]
                for i, t in enumerate(targets):
                    self.apply_attack(self.local_player_id, t, total_attack, multi=len(targets), order=i)
                self.total_attacks_sent += total_attack * len(targets)
                if self.sound_mgr:
                    self.sound_mgr.play('attack')
                if len(targets) >= 2:
                    self.add_floating_text(f"★ 다중 포격! +{total_attack}줄 × {len(targets)}명 ★", (255, 170, 90), duration=2.6, size=28, category="action")
                    self.add_commentary(f"{self._short_name(self.local_player_id)}  {len(targets)}명에게 동시 포격! {total_attack}줄", (255, 170, 90))
                    self.trigger_screen_shake(10.0)
                
                lbl = "[자동 반격]" if is_target_human else "[공격 발송]"
                bonus_str = ""
                if badge_lvl > 0 and attacker_bonus > 0:
                    bonus_str = f" (배지 Lv.{badge_lvl}, 카운터+{attacker_bonus})"
                elif badge_lvl > 0:
                    bonus_str = f" (배지 Lv.{badge_lvl})"
                elif attacker_bonus > 0:
                    bonus_str = f" (카운터+{attacker_bonus})"
                    
                if len(targets) < 2:                             # 다중 포격은 위의 전용 알림만 표시 (중복 방지)
                    self.add_floating_text(f"{lbl} +{total_attack}줄 >> {target_name}{bonus_str}", (255, 130, 130), duration=2.4, size=22, category="attack")
            elif not self.attacks_enabled:
                self.total_attacks_sent += self.local_engine.garbage_to_send     # 서바이벌: 실제로 보내지는 않지만 만들어 낸 공격력은 APM에 반영
            self.local_engine.garbage_to_send = 0
            
        # 로컬 플레이어 상태 갱신
        self.players[self.local_player_id]["compact_grid"] = self.local_engine.get_compact_grid()
        self.players[self.local_player_id]["highest_y"] = self.local_engine.get_highest_block_row()
        self.players[self.local_player_id]["is_alive"] = self.local_is_alive
        self.players[self.local_player_id]["ko_count"] = self.local_ko_count
        self.players[self.local_player_id]["score"] = self.local_engine.score
        self.players[self.local_player_id]["cg"] = grid_rows(self.local_engine.grid)
        self.players[self.local_player_id]["ig"] = self.local_engine.incoming_garbage
        self.players[self.local_player_id]["cpiece"] = piece_state(self.local_engine)
        self.players[self.local_player_id]["next"] = list(self.local_engine.next_queue[:3])
        self.players[self.local_player_id]["hold"] = self.local_engine.hold_piece
        self.players[self.local_player_id]["lines"] = self.local_engine.lines_cleared_total
        self.players[self.local_player_id]["attacks"] = self.total_attacks_sent

        # 서바이벌 모드: 공격이 없어 경기가 끝나지 않을 수 있으므로, 일정 시간 뒤부터 모두에게 주기적으로 쓰레기 줄이 올라옴 (상대의 공격이 아니라 시간 압박)
        if not self.attacks_enabled and not self.match_finished:
            self._survival_pressure(dt)
        elif self.attacks_enabled and not self.match_finished and self.elapsed >= self.BATTLE_PRESSURE_START:
            self._survival_pressure(dt, self.BATTLE_PRESSURE_START, "후반 압박")      # 배틀로얄도 9분이 지나면 시간 압박: 소수의 봇이 서로 끝내지 못해도 경기가 반드시 끝남

        # 생존자 수에 따른 페이즈 전환 마일스톤 연출
        # (인원이 적은 대전에서는 시작부터 '최후의 결전'이 되지 않도록 전체 인원 대비 비율로 판정. 8명 미만은 연출 없음)
        p2_thr = int(self.total_players * 0.5)
        p3_thr = max(2, int(round(self.total_players * 0.1)))
        if self.total_players >= 8 and self.alive_count <= p2_thr and self.phase < 2:
            self.phase = 2
            self.trigger_screen_shake(10.0)
            self.add_commentary("PHASE 2 돌입  ·  스피드 UP", (255, 215, 0), prio=1)
            self.add_floating_text(f"★ [PHASE 2] 생존자 {p2_thr}인 돌파! 스피드 UP! ★", (255, 215, 0), duration=3.0, size=32, category="action")
        if self.total_players >= 8 and self.alive_count <= p3_thr and self.phase < 3:
            self.phase = 3
            self.trigger_screen_shake(16.0)
            self.add_commentary(f"FINAL {p3_thr}  ·  서든 데스!", (255, 90, 90), prio=1)
            self.add_floating_text(f"★ [FINAL {p3_thr}] 서든 데스! 최후의 결전! ★", (255, 75, 75), duration=3.5, size=34, category="action")

        # 5. 네트워크 수신 공격 처리
        if self.net_mgr and self.net_mgr.incoming_attacks:
            while self.net_mgr.incoming_attacks:
                from_id, to_id, lines = self.net_mgr.incoming_attacks.pop(0)
                if from_id != self.local_player_id:
                    self.apply_attack(from_id, to_id, lines, from_network=True)

        # 6. AI 봇들 업데이트 (분산 실행 및 실시간 난이도 스케일링)
        bot_pool.pump()                                 # 작업 프로세스가 끝낸 봇 계산 결과를 받아옴
        bot_brain.begin_frame(BOT_SEARCH_BUDGET)        # 이번 프레임에 봇 전원이 함께 쓸 수 있는 탐색 시간
        items = list(self.players.items())
        if items:                                        # 예산이 모자라도 특정 봇만 굶지 않도록 시작 위치를 돌려 가며 처리
            off = self._bot_rr % len(items)
            items = items[off:] + items[:off]
            self._bot_rr += 5
        for pid, p in items:
            if self.match_finished:
                break                                  # 승자가 정해졌으면 남은 봇을 더 처리하지 않음
            if not p["is_alive"] or not p["is_ai"] or not p["bot"]:
                continue
                
            # 봇 난이도 가속도 인원 비율 기준 (100인 대전 기준으로 환산)
            p["bot"].adjust_for_alive_count(int(round(self.alive_count / max(1, self.total_players) * 100)))
                
            # AI 타겟팅
            if not p["target_id"] or random.random() < 0.03:
                if p["bot"].difficulty in ("hard", "master"):
                    # 강한 봇: 가끔은 나를 노리는 상대에게 반격, 대부분은 위험도(높이+들어올 쓰레기)가 높은 상대를 골라 마무리
                    attackers = [q for q, pp in self.players.items() if pp["is_alive"] and q != pid and pp.get("target_id") == pid] if random.random() < 0.25 else []
                    p["target_id"] = random.choice(attackers) if attackers else self._smart_target(pid)
                elif p["bot"].difficulty == "normal" and random.random() < 0.5:
                    p["target_id"] = self._smart_target(pid)
                else:
                    p["target_id"] = self._spread_random_target(pid)
                
            # AI 틱
            att = p["bot"].update(dt)
            if att > 0 and not self.attacks_enabled:
                p["attacks"] += att                                  # 서바이벌: 봇이 만들어 낸 공격력도 APM에 반영 (전달은 안 됨)
            if att >= 3 and p["bot"].difficulty in ("hard", "master"):
                p["target_id"] = self._smart_target(pid, att) or p["target_id"]      # 큰 공격은 탈락시킬 수 있는 상대에게 몰아줌
            if att > 0 and p["target_id"]:
                tgt = p["target_id"]
                if tgt not in self.players or not self.players[tgt]["is_alive"]:
                    tgt = p["target_id"] = self.get_target_for(pid, "KO")      # 조준하던 상대가 방금 탈락했으면 즉시 다시 조준
                if tgt:
                    self.apply_attack(pid, tgt, att)
            if p["bot"].engine.perfect_clears > p.get("_pc_seen", 0):
                p["_pc_seen"] = p["bot"].engine.perfect_clears
                self.add_commentary(f"★ {self._short_name(pid)}  PERFECT CLEAR! ★", (255, 225, 90), prio=1)
                
            # 상태 동기화
            p["score"] = p["bot"].engine.score
            p["lines"] = p["bot"].engine.lines_cleared_total
            p["ig"] = p["bot"].engine.incoming_garbage
            eng = p["bot"].engine
            gkey = (eng.lock_events, eng.garbage_pushed_total, eng.lines_cleared_total)
            if p.get("_cg_key") != gkey or "cg" not in p:              # 격자는 고정/쓰레기/줄 제거 때만 바뀜
                p["cg"] = grid_rows(eng.grid)                          # 미니 보드에 실제 블록 색/모양으로 표시
                p["_cg_key"] = gkey
                p["compact_grid"] = eng.get_compact_grid()             # 압축 격자/최고 높이도 보드가 바뀔 때만 다시 계산
                p["highest_y"] = eng.get_highest_block_row()
            p["cpiece"] = piece_state(p["bot"].engine)                 # 조작 중인 블록
            p["next"] = list(p["bot"].engine.next_queue[:3])           # 다음 블록 / 홀드 (미니 보드 옆에 표시)
            p["hold"] = p["bot"].engine.hold_piece
            
            # AI 게임 오버 검사
            if not p["bot"].is_alive:
                self._eliminate_player(pid)

        # 7. 네트워크 플레이어들의 상태 반영
        if self.net_mgr and self.net_mgr.remote_players_state:
            for r_id, r_state in list(self.net_mgr.remote_players_state.items()):
                if r_id in self.players:
                    self.players[r_id]["compact_grid"] = r_state.get("compact_grid", self.players[r_id]["compact_grid"])
                    self.players[r_id]["highest_y"] = r_state.get("highest_y", 20)
                    for key, src in (("score", "score"), ("lines", "lines"), ("attacks", "atk")):   # 호스트/클라이언트가 보낸 성적
                        v = r_state.get(src)
                        if isinstance(v, int) and not isinstance(v, bool):
                            self.players[r_id][key] = v
                    # 색이 있는 보드: 클라이언트가 보낸 스냅샷(호스트) 또는 호스트가 보낸 cg 문자열(클라이언트)
                    snap = r_state.get("snap")
                    cg = r_state.get("cg")
                    cp = snap.get("p") if isinstance(snap, dict) else r_state.get("cp")
                    if isinstance(cp, (list, tuple)) and len(cp) == 4 and cp[0] in "IJLOSTZ" and all(isinstance(v, int) for v in cp[1:]):
                        self.players[r_id]["cpiece"] = tuple(cp)
                    elif cp is None:
                        self.players[r_id]["cpiece"] = None
                    if isinstance(snap, dict):
                        nx, hd = snap.get("n"), snap.get("h")
                    else:
                        nx, hd = r_state.get("nx"), r_state.get("hd")
                    if isinstance(nx, str):
                        nx = list(nx)
                    if isinstance(nx, list) and all(isinstance(c, str) and c in "IJLOSTZ" for c in nx):
                        self.players[r_id]["next"] = nx[:3]
                    if hd is None or (isinstance(hd, str) and (hd == "" or hd in "IJLOSTZ")):
                        self.players[r_id]["hold"] = hd or None
                    if isinstance(snap, dict) and isinstance(snap.get("g"), list):
                        self.players[r_id]["cg"] = snap["g"]
                    elif isinstance(cg, str) and len(cg) == 200 and set(cg) <= _CG_CHARS:
                        self.players[r_id]["cg"] = [cg[i * 10:(i + 1) * 10] for i in range(20)]
                    ig = snap.get("ig") if isinstance(snap, dict) else r_state.get("ig")
                    if isinstance(ig, int) and not isinstance(ig, bool):
                        self.players[r_id]["ig"] = max(0, min(400, ig))
                    sv = r_state.get("surv")
                    if isinstance(sv, (int, float)) and not isinstance(sv, bool):
                        self.players[r_id]["survival"] = float(sv)
                    if not r_state.get("is_alive", True) and self.players[r_id]["is_alive"]:
                        self._eliminate_player(r_id)
                    hr = r_state.get("rank")               # (클라이언트) 호스트가 정한 순위를 따름: 여러 명이 한 패킷에 탈락해도 호스트와 같은 순위
                    if (self.net_mgr.mode == "CLIENT" and isinstance(hr, int) and not isinstance(hr, bool)
                            and 1 <= hr <= self.total_players and not self.players[r_id]["is_alive"]):
                        self.players[r_id]["rank"] = hr
                        self.next_rank_to_assign = min(self.next_rank_to_assign, hr - 1)

        if self.net_mgr and self.net_mgr.mode == "CLIENT" and not self.local_is_alive:
            hv = getattr(self.net_mgr, "host_view_of_me", None)      # 내 순위도 호스트 기준으로 맞춤 (내가 탈락한 뒤에만)
            hr = hv.get("rank") if isinstance(hv, dict) else None
            if (isinstance(hr, int) and not isinstance(hr, bool) and 1 <= hr <= self.total_players and hv.get("is_alive") is False
                    and self.local_player_id in self.players):
                self.local_rank = hr
                self.players[self.local_player_id]["rank"] = hr

        self._check_spectate_target(now)

        # 8. 이펙트 수명 정리
        self.attack_effects = [e for e in self.attack_effects if now - e["start_time"] < e["duration"]]

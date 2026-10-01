"""
Block Royale 100 - Stats & Records Manager
플레이어의 역대 경기 전적(우승 횟수, 최고 순위, 누적 KO, 최대 콤보, 최근 경기 목록)을 stats.json에 영구 저장 및 관리합니다.
"""

import os
import copy
import json
import datetime

from app_paths import data_path
from config import BADGE_TIERS

# 난이도 사다리: 배틀로얄에서 LADDER_MIN_PLAYERS명 이상 대전 중 LADDER_RANK위 안에 들면 그 난이도를 "클리어" (혼합 난이도는 사다리에 없음)
LADDER = ("easy", "normal", "hard", "master")
LADDER_MIN_PLAYERS = 50
LADDER_RANK = 10
LADDER_NAMES = {"easy": "쉬움", "normal": "보통", "hard": "어려움", "master": "마스터"}

# 경기 규모별 구분: 2인 대전 1위와 100인 대전 1위는 같은 성적이 아니므로 최고 순위/기록 갱신/다음 목표는 규모별로 비교
SIZE_BUCKETS = (("small", 2, 10, "소규모 2~10인"), ("mid", 11, 49, "중규모 11~49인"), ("large", 50, 100, "대규모 50~100인"))
SIZE_BUCKET_IDS = tuple(b[0] for b in SIZE_BUCKETS)
SIZE_BUCKET_LABELS = {b[0]: b[3] for b in SIZE_BUCKETS}


def size_bucket(total_players):
    for bid, lo, hi, _label in SIZE_BUCKETS:
        if lo <= int(total_players) <= hi:
            return bid
    return "large" if int(total_players) > 100 else "small"

STATS_FILE = data_path("stats.json")

# 업적 (배틀로얄 전적에만 기록, 한 번 달성하면 유지). (id, 제목, 설명, 달성 조건 ctx -> bool)
# ctx: rank, total, kos, lines, combo, secs, ladder_n(클리어한 난이도 수), daily_n(오늘의 도전을 한 날 수)
ACHIEVEMENTS = (
    ("first_ko", "첫 K.O.", "한 판에서 상대를 1명 처치", lambda c: c["kos"] >= 1),
    ("top10", "TOP 10 진입", "30인 이상 대전에서 10위 안", lambda c: c["total"] >= 30 and c["rank"] <= 10),
    ("victory", "로열 빅토리", "10인 이상 대전에서 우승", lambda c: c["total"] >= 10 and c["rank"] == 1),
    ("century", "백인의 왕", "100인 대전에서 우승", lambda c: c["total"] >= 100 and c["rank"] == 1),
    ("ko5", "사냥꾼", "한 판에서 5명 처치", lambda c: c["kos"] >= 5),
    ("ko10", "학살자", "한 판에서 10명 처치", lambda c: c["kos"] >= 10),
    ("combo8", "콤보 장인", "한 판에서 8연속 콤보", lambda c: c["combo"] >= 8),
    ("marathon", "마라토너", "한 판에서 7분 이상 생존", lambda c: c["secs"] >= 420),      # 8~9분에 끝나는 경기라 10분은 사실상 우승권만 가능했음 -> 7분
    ("ladder_all", "사다리 정복", "난이도 사다리 4단계 모두 클리어", lambda c: c["ladder_n"] >= 4),
    ("daily3", "꾸준한 도전자", "오늘의 도전을 3일 이상 플레이", lambda c: c["daily_n"] >= 3),
)
ACHIEVEMENT_IDS = tuple(a[0] for a in ACHIEVEMENTS)

DEFAULT_STATS = {
    "total_games": 0,
    "victories": 0,
    "top_5": 0,
    "top_10": 0,
    "best_rank": 0,
    "total_kos": 0,
    "max_ko": 0,
    "max_combo": 0,
    "total_lines": 0,
    "total_play_time_sec": 0,
    "recent_matches": [],
    "daily": {},                      # 오늘의 도전 날짜별 최고 순위 {"20260930": 12} (최근 30일만 유지)
    "ladder": [],                     # 클리어한 난이도 목록 (LADDER 중)
    "achievements": [],               # 달성한 업적 id (ACHIEVEMENTS 중, 배틀로얄 전적에만)
    "best_by_size": {}                # 규모별 최고 순위 {"small": 3, "mid": 8, "large": 28} (플레이한 규모만)
}

def _backup_corrupt(path):
    """읽을 수 없는 전적 파일은 덮어쓰기 전에 옆에 백업해 둠 (전적 영구 손실 방지)"""
    try:
        import shutil
        shutil.copy2(path, f"{path}.corrupt-{int(datetime.datetime.now().timestamp())}")
    except Exception:
        pass


def next_goal_text(rank, kos, total_players, best_in_size, difficulty=None, cleared=(), ladder_clear=None):
    """결과 화면의 '다음 목표: ...' 뒤에 붙는 문구. 우선순위: 방금 난이도 클리어 -> 배지 다음 단계가 2 K.O. 이내 -> 난이도 클리어까지 -> 순위 목표.
    best_in_size: 방금 경기를 포함한 같은 규모의 최고 순위 (없으면 0)"""
    if ladder_clear:
        nxt = next((x for x in LADDER if x not in cleared), None)
        return f"{LADDER_NAMES[ladder_clear]} 클리어! " + (f"다음은 {LADDER_NAMES[nxt]}에 도전" if nxt else "모든 난이도 클리어")
    need_ko = next((need - kos for need, _b in BADGE_TIERS if need > kos), None)
    lv_next = next((lv for lv, (need, _b) in enumerate(BADGE_TIERS) if need > kos), None)
    if need_ko is not None and 0 < need_ko <= 2 and total_players > 2:
        return f"배지 Lv.{lv_next}까지 {need_ko} K.O."
    if difficulty in LADDER and difficulty not in cleared and total_players >= LADDER_MIN_PLAYERS and rank > LADDER_RANK:
        return f"{LADDER_NAMES[difficulty]} 클리어까지 {rank - LADDER_RANK}계단 ({LADDER_RANK}위 안)"
    best = best_in_size if best_in_size > 0 else rank
    if rank > best:
        return f"최고 순위 #{best}까지 {rank - best}계단"
    if best > 10 and total_players > 10:
        return "10위 안 진입"
    if best > 5 and total_players > 5:
        return "5위 안 진입"
    if best > 1:
        return "우승"
    return "우승 연속 도전"


class StatsManager:
    def __init__(self, filepath=STATS_FILE):
        self.filepath = filepath
        self.data = copy.deepcopy(DEFAULT_STATS)          # 배틀로얄(공격 있음) 전적. 예전 파일과 호환되도록 최상위에 유지
        self.data["survival"] = copy.deepcopy(DEFAULT_STATS)   # 서바이벌(공격 없음) 전적: 같은 구조를 따로 보관
        self.last_ladder_clear = None
        self.last_new_achievements = []
        self.load()

    def _bucket(self, mode):
        return self.data["survival"] if mode == "survival" else self.data

    @staticmethod
    def _merge_saved(target, saved):
        """저장된 값 중 형식이 맞는 것만 target에 반영"""
        for k, v in saved.items():
            d = DEFAULT_STATS.get(k)
            if k == "daily":                               # 오늘의 도전: "YYYYMMDD" 키와 양의 정수만
                if isinstance(v, dict):
                    target[k] = {kk: int(vv) for kk, vv in v.items()
                                 if isinstance(kk, str) and len(kk) == 8 and kk.isdigit() and isinstance(vv, (int, float)) and not isinstance(vv, bool) and vv >= 1}
            elif k == "achievements":                      # 업적: 알려진 id만
                if isinstance(v, list):
                    target[k] = [x for x in ACHIEVEMENT_IDS if x in v]
            elif k == "ladder":                            # 클리어한 난이도: 알려진 난이도 이름만
                if isinstance(v, list):
                    target[k] = [x for x in LADDER if x in v]
            elif isinstance(d, list):                      # 최근 경기 목록: 리스트이고 각 항목이 dict일 때만
                if isinstance(v, list):
                    target[k] = [m for m in v if isinstance(m, dict)][-100:]
            elif isinstance(d, dict):                      # 규모별 최고 순위: 알려진 규모 이름 + 양의 정수만
                if isinstance(v, dict):
                    target[k] = {kk: int(vv) for kk, vv in v.items()
                                 if kk in SIZE_BUCKET_IDS and isinstance(vv, (int, float)) and not isinstance(vv, bool) and vv >= 1}
            elif isinstance(d, int):                       # 숫자 통계: 숫자일 때만
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    target[k] = int(v)

    def load(self):
        """stats.json 파일에서 전적 데이터 로드"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        self._merge_saved(self.data, {k: v for k, v in saved.items() if k != "survival"})
                        if isinstance(saved.get("survival"), dict):
                            self._merge_saved(self.data["survival"], saved["survival"])
                    else:
                        _backup_corrupt(self.filepath)
            except Exception as e:
                print(f"[StatsManager] Failed to load stats: {e}. Using defaults.")
                _backup_corrupt(self.filepath)
        else:
            self.save()

    def save(self):
        """현재 전적 데이터를 stats.json에 저장"""
        try:
            tmp = self.filepath + ".tmp"                      # 임시 파일에 쓴 뒤 교체: 저장 도중 종료돼도 원본이 깨지지 않음
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
            os.replace(tmp, self.filepath)
        except Exception as e:
            print(f"[StatsManager] Failed to save stats: {e}")

    def _best_by_size(self, d):
        """규모별 최고 순위 딕셔너리. 예전 전적 파일(이 항목이 없음)은 최근 경기 목록으로 처음 한 번 채움"""
        best_by = d.setdefault("best_by_size", {})
        if not best_by:
            for m in d.get("recent_matches", []):
                r, tp = m.get("rank"), m.get("total_players")
                if isinstance(r, int) and r >= 1 and isinstance(tp, int):
                    b = size_bucket(tp)
                    if b not in best_by or r < best_by[b]:
                        best_by[b] = r
        return best_by

    def achievement_progress(self):
        """아직 못 한 업적의 진행도 {id: (현재, 목표)} (숫자로 셀 수 있는 것만). 생존 시간은 초 단위"""
        d = self.data
        best_secs = max([m.get("survival_sec", 0) for m in d.get("recent_matches", []) if isinstance(m.get("survival_sec", 0), (int, float))] or [0])
        mk, cb = d.get("max_ko", 0), d.get("max_combo", 0)
        return {"first_ko": (min(mk, 1), 1), "ko5": (min(mk, 5), 5), "ko10": (min(mk, 10), 10), "combo8": (min(cb, 8), 8),
                "marathon": (min(int(best_secs), 420), 420), "ladder_all": (len(d.get("ladder", [])), 4), "daily3": (min(len(d.get("daily", {})), 3), 3)}

    def achievements_done(self):
        """달성한 업적 id 목록 (ACHIEVEMENTS 순서)"""
        return [x for x in ACHIEVEMENT_IDS if x in self.data.get("achievements", [])]

    def ladder_cleared(self, mode="battle"):
        """클리어한 난이도 목록 (쉬움 -> 마스터 순)"""
        return [x for x in LADDER if x in self._bucket(mode).get("ladder", [])]

    def best_in_size(self, mode, total_players):
        """이 인원 규모에서의 최고 순위 (기록이 없으면 0)"""
        return self._best_by_size(self._bucket(mode)).get(size_bucket(total_players), 0)

    def daily_best(self, date_key, mode="battle"):
        """오늘의 도전(date_key="YYYYMMDD")에서의 최고 순위 (아직 안 했으면 0)"""
        return self._bucket(mode).get("daily", {}).get(date_key, 0)

    def record_match(self, rank, total_players, kos, lines, max_combo, survival_sec, mode="battle", difficulty="mixed", daily=None):
        """경기 완료 시 전적 기록 및 통계 갱신 (mode: "battle" 배틀로얄 / "survival" 서바이벌)"""
        d = self._bucket(mode)
        prev_games = d.get("total_games", 0)
        prev_ko, prev_combo = d.get("max_ko", 0), d.get("max_combo", 0)
        bucket = size_bucket(total_players)
        best_by = self._best_by_size(d)
        records = []                                       # 이번 경기가 이전 최고 기록을 넘은 항목 (첫 경기는 비교할 기록이 없어 제외)
        if prev_games > 0:
            if bucket in best_by and rank < best_by[bucket]:      # 순위는 같은 규모의 경기끼리만 비교
                records.append("rank")
            if kos > prev_ko and kos > 0:
                records.append("ko")
            if max_combo > prev_combo and max_combo > 0:
                records.append("combo")
        if bucket not in best_by or rank < best_by[bucket]:
            best_by[bucket] = rank
        if daily:                                          # 오늘의 도전: 날짜별 최고 순위 (최근 30일만 유지)
            dd = d.setdefault("daily", {})
            if daily not in dd or rank < dd[daily]:
                dd[daily] = rank
            for old_key in sorted(dd)[:-30]:
                del dd[old_key]
        self.last_ladder_clear = None                      # 이번 경기로 새로 클리어한 난이도 (없으면 None)
        if (mode == "battle" and difficulty in LADDER and total_players >= LADDER_MIN_PLAYERS and rank <= LADDER_RANK
                and difficulty not in d.setdefault("ladder", [])):
            d["ladder"].append(difficulty)
            self.last_ladder_clear = difficulty
        d["total_games"] = prev_games + 1
        self.last_new_achievements = []                    # 이번 경기로 새로 달성한 업적 id
        if mode == "battle":
            ctx = {"rank": rank, "total": total_players, "kos": kos, "lines": lines, "combo": max_combo, "secs": survival_sec,
                   "ladder_n": len(d.get("ladder", [])), "daily_n": len(d.get("daily", {}))}
            have = d.setdefault("achievements", [])
            for aid, _title, _desc, ok in ACHIEVEMENTS:
                if aid not in have and ok(ctx):
                    have.append(aid)
                    self.last_new_achievements.append(aid)
            d["achievements"] = [x for x in ACHIEVEMENT_IDS if x in have]
        
        is_victory = (rank == 1)
        if is_victory:
            d["victories"] = d.get("victories", 0) + 1
            
        if rank <= 5:
            d["top_5"] = d.get("top_5", 0) + 1
        if rank <= 10:
            d["top_10"] = d.get("top_10", 0) + 1
            
        cur_best = d.get("best_rank", 0)
        if cur_best == 0 or rank < cur_best:
            d["best_rank"] = rank
            
        d["total_kos"] = d.get("total_kos", 0) + kos
        d["max_ko"] = max(d.get("max_ko", 0), kos)
        d["max_combo"] = max(d.get("max_combo", 0), max_combo)
        d["total_lines"] = d.get("total_lines", 0) + lines
        d["total_play_time_sec"] = d.get("total_play_time_sec", 0) + int(survival_sec)
        
        # 최근 경기 목록 기록 (최대 100경기)
        match_entry = {
            "date": datetime.datetime.now().strftime("%m-%d %H:%M"),
            "rank": rank,
            "total_players": total_players,
            "kos": kos,
            "lines": lines,
            "max_combo": max_combo,
            "survival_sec": int(survival_sec),
            "won": is_victory,
            "difficulty": difficulty
        }
        
        rec = d.get("recent_matches", [])
        rec.append(match_entry)
        if len(rec) > 100:
            rec = rec[-100:]
        d["recent_matches"] = rec
        
        self.save()
        return records

    def reset_stats(self):
        """전적 초기화"""
        self.data = copy.deepcopy(DEFAULT_STATS)
        self.data["survival"] = copy.deepcopy(DEFAULT_STATS)
        self.save()

    def get_summary(self, mode="battle", size=None, difficulty=None):
        """화면 표시용 요약 통계 문자열 및 계산값 반환.
        size(규모 이름)나 difficulty(난이도 이름)를 주면 전체 누적이 아니라 '최근 100경기' 중 그 조건에 맞는 경기만으로 다시 계산 (filtered=True)"""
        d = self._bucket(mode)
        if size is not None or difficulty is not None:
            ms = [m for m in d.get("recent_matches", [])
                  if (size is None or size_bucket(m.get("total_players", 100)) == size)
                  and (difficulty is None or m.get("difficulty") == difficulty)]
            ranks = [m.get("rank", 0) for m in ms if m.get("rank", 0) > 0]
            best = min(ranks) if ranks else 0
            wins = sum(1 for m in ms if m.get("won"))
            return {
                "filtered": True,
                "total_games": len(ms),
                "victories": wins,
                "win_rate": (wins / len(ms) * 100.0) if ms else 0.0,
                "best_rank": best,
                "best_rank_str": f"#{best}위" if best > 0 else "-",
                "top_5": sum(1 for r in ranks if r <= 5),
                "top_10": sum(1 for r in ranks if r <= 10),
                "total_kos": sum(m.get("kos", 0) for m in ms),
                "max_ko": max([m.get("kos", 0) for m in ms] or [0]),
                "max_combo": max([m.get("max_combo", 0) for m in ms] or [0]),
                "total_lines": sum(m.get("lines", 0) for m in ms),
                "play_time_sec": sum(int(m.get("survival_sec", 0)) for m in ms),
                "recent_matches": ms,
            }
        total = d.get("total_games", 0)
        vic = d.get("victories", 0)
        win_rate = (vic / total * 100.0) if total > 0 else 0.0
        best_rank = d.get("best_rank", 0)
        best_str = f"#{best_rank}위" if best_rank > 0 else "-"
        
        return {
            "filtered": False,
            "total_games": total,
            "victories": vic,
            "win_rate": win_rate,
            "best_rank": best_rank,
            "best_rank_str": best_str,
            "top_5": d.get("top_5", 0),
            "top_10": d.get("top_10", 0),
            "total_kos": d.get("total_kos", 0),
            "max_ko": d.get("max_ko", 0),
            "max_combo": d.get("max_combo", 0),
            "total_lines": d.get("total_lines", 0),
            "play_time_sec": d.get("total_play_time_sec", 0),
            "recent_matches": d.get("recent_matches", [])
        }

"""
Block Royale 100 - Stats & Records Manager
플레이어의 역대 경기 전적(우승 횟수, 최고 순위, 누적 KO, 최대 콤보, 최근 경기 목록)을 stats.json에 영구 저장 및 관리합니다.
"""

import os
import copy
import json
import datetime
import challenges as _ch

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


# ---- 경험치와 레벨 (v1.1.6): 져도 매 판 조금씩 오르는 숫자. 레벨은 해금 스킨(불씨 Lv.5, 프리즘 Lv.10)으로 이어짐
HIGHLIGHT_IDS = ("perfect", "comeback", "chain_ko", "combo10", "b2b5", "wall", "bounty", "revenge")      # 명장면 id (battle_royale.HIGHLIGHT_LABELS와 같아야 함)
STAR_XP = 20                                     # 도전 과제 별 하나당 경험치


def xp_for_next(level):
    """level에서 level+1로 오르는 데 필요한 경험치"""
    return int(100 * max(1, int(level)) ** 1.3)


def level_of(xp):
    """경험치 -> (레벨, 이번 레벨에서 쌓은 경험치, 이번 레벨을 채우는 데 필요한 경험치). 레벨 1에서 시작"""
    xp = max(0, int(xp))
    level = 1
    while xp >= xp_for_next(level):
        xp -= xp_for_next(level)
        level += 1
    return level, xp, xp_for_next(level)


def calc_match_xp(rank, total_players, kos, survival_sec, highlights=(), mode="battle"):
    """한 판의 경험치와 내역 [(항목, 경험치)]. 참가 20 + 순위(꼴찌 0 ~ 우승 60) + K.O. 8 + 생존(20초당 1, 최대 30) + 우승 40 + 명장면 15. 서바이벌은 절반"""
    parts = [("참가", 20)]
    if total_players >= 2:
        parts.append(("순위", int(round((total_players - rank) / float(total_players - 1) * 60))))
    if kos > 0:
        parts.append(("K.O.", int(kos) * 8))
    live = min(30, int(survival_sec) // 20)
    if live > 0:
        parts.append(("생존", live))
    if rank == 1 and total_players >= 2:
        parts.append(("우승", 40))
    if highlights:
        parts.append(("명장면", 15 * len(highlights)))
    if mode == "survival":
        parts = [(k, int(v * 0.5)) for k, v in parts]
    parts = [(k, v) for k, v in parts if v > 0]
    return sum(v for _k, v in parts), parts


def size_bucket(total_players):
    for bid, lo, hi, _label in SIZE_BUCKETS:
        if lo <= int(total_players) <= hi:
            return bid
    return "large" if int(total_players) > 100 else "small"

STATS_FILE = data_path("stats.json")

# 업적 (배틀로얄 전적에만 기록, 한 번 달성하면 유지). (id, 제목, 설명, 달성 조건 ctx -> bool)
# ctx: rank, total, kos, lines, combo, secs, ladder_n(클리어한 난이도 수), daily_n(오늘의 도전을 한 날 수), revenge_n,
#      games/victories/top5/total_kos/total_lines(배틀로얄 누적), 도전 과제 쪽 daily_stars/weekly_stars/weekly_rules_n/practice_n/practice_done/ta/streak_best/daily_full
# 카테고리(ACH_CATEGORY)별로 한 페이지에 최대 10개씩 기록실에서 보여 줌
ACHIEVEMENTS = (
    # ---- 대전
    ("first_ko", "첫 K.O.", "한 판에서 상대를 1명 처치", lambda c: c["kos"] >= 1),
    ("ko5", "사냥꾼", "한 판에서 5명 처치", lambda c: c["kos"] >= 5),
    ("ko10", "학살자", "한 판에서 10명 처치", lambda c: c["kos"] >= 10),
    ("ko15", "전장의 지배자", "한 판에서 15명 처치", lambda c: c["kos"] >= 15),
    ("top10", "TOP 10 진입", "30인 이상 대전에서 10위 안", lambda c: c["total"] >= 30 and c["rank"] <= 10),
    ("victory", "로열 빅토리", "10인 이상 대전에서 우승", lambda c: c["total"] >= 10 and c["rank"] == 1),
    ("century", "백인의 왕", "100인 대전에서 우승", lambda c: c["total"] >= 100 and c["rank"] == 1),
    ("marathon", "마라토너", "한 판에서 7분 이상 생존", lambda c: c["secs"] >= 420),      # 8~9분에 끝나는 경기라 10분은 사실상 우승권만 가능했음 -> 7분
    ("ironman", "철인", "한 판에서 9분 이상 생존", lambda c: c["secs"] >= 540),
    ("revenge", "복수의 화신", "나를 자주 탈락시킨 라이벌 봇을 처치", lambda c: c.get("revenge_n", 0) >= 1),
    # ---- 누적
    ("games10", "신입 대원", "배틀로얄 10판 플레이", lambda c: c.get("games", 0) >= 10),
    ("games100", "백전노장", "배틀로얄 100판 플레이", lambda c: c.get("games", 0) >= 100),
    ("win3", "삼연의 왕관", "배틀로얄에서 우승 3번", lambda c: c.get("victories", 0) >= 3),
    ("win10", "챔피언", "배틀로얄에서 우승 10번", lambda c: c.get("victories", 0) >= 10),
    ("top5_10", "상위권 단골", "5위 안에 10번 들기", lambda c: c.get("top5", 0) >= 10),
    ("kos100", "백 명 사냥", "누적 K.O. 100명", lambda c: c.get("total_kos", 0) >= 100),
    ("lines1000", "천 줄의 길", "누적 1,000줄 지우기", lambda c: c.get("total_lines", 0) >= 1000),
    ("lines5000", "오천 줄의 길", "누적 5,000줄 지우기", lambda c: c.get("total_lines", 0) >= 5000),
    ("ladder_all", "사다리 정복", "난이도 사다리 4단계 모두 클리어", lambda c: c["ladder_n"] >= 4),
    ("playtime", "시간 부자", "배틀로얄 누적 플레이 10시간", lambda c: c.get("play_min", 0) >= 600),
    # ---- 도전
    ("daily3", "꾸준한 도전자", "오늘의 도전을 3일 이상 플레이", lambda c: c["daily_n"] >= 3),
    ("streak3", "사흘 연속", "오늘의 도전 별을 3일 연속으로 받기", lambda c: c.get("streak_best", 0) >= 3),
    ("streak7", "일주일 개근", "오늘의 도전 별을 7일 연속으로 받기", lambda c: c.get("streak_best", 0) >= 7),
    ("streak14", "보름 개근", "오늘의 도전 별을 14일 연속으로 받기", lambda c: c.get("streak_best", 0) >= 14),
    ("daily_perfect", "완벽한 하루", "하루에 오늘의 도전 별 3개를 모두 받기", lambda c: c.get("daily_full", 0) >= 1),
    ("star_collector", "별 수집가", "오늘의 도전 별(★) 누적 30개", lambda c: c.get("daily_stars", 0) >= 30),
    ("star_100", "별의 지배자", "오늘의 도전 + 주간 변형 별 누적 100개", lambda c: c.get("daily_stars", 0) + c.get("weekly_stars", 0) >= 100),
    ("variant_master", "변형 정복자", "주간 변형 규칙 네 가지 모두에서 별 1개 이상", lambda c: c.get("weekly_rules_n", 0) >= 4),
    ("weekly_stars", "주간 단골", "주간 변형 별 누적 10개", lambda c: c.get("weekly_stars", 0) >= 10),
    ("weekly_perfect", "완벽한 한 주", "한 주에 주간 변형 별 3개를 모두 받기", lambda c: c.get("weekly_full", 0) >= 1),
    # ---- 연습·기술
    ("combo8", "콤보 장인", "한 판에서 8연속 콤보", lambda c: c["combo"] >= 8),
    ("combo12", "콤보 전설", "한 판에서 12연속 콤보", lambda c: c["combo"] >= 12),
    ("practice_half", "수련생", f"연습 과제 {len(_ch.PRACTICE_IDS) // 2}개 완료", lambda c: c.get("practice_n", 0) >= len(_ch.PRACTICE_IDS) // 2),
    ("practice_all", "수련 완료", f"연습 과제 {len(_ch.PRACTICE_IDS)}개를 모두 완료", lambda c: c.get("practice_n", 0) >= len(_ch.PRACTICE_IDS)),
    ("tspin_master", "T-스핀 마스터", "연습에서 T-스핀 트리플 달성", lambda c: "p_tst" in c.get("practice_done", ())),
    ("perfect_clear", "퍼펙트 클리어", "연습에서 퍼펙트 클리어 달성", lambda c: "p_pc" in c.get("practice_done", ())),
    ("drill_survivor", "압박을 견딘 자", "압박 드릴에서 3분 버티기", lambda c: "p_drill180" in c.get("practice_done", ())),
    ("sprinter", "스프린터", "타임어택 쿼드 5번을 60초 안에", lambda c: 0 < c.get("ta", {}).get("quad", 0) <= 60),
    ("ta_all", "타임어택 완주", f"타임어택 {len(_ch.TA_MODES)}종 모두 기록 남기기", lambda c: len(c.get("ta", {})) >= len(_ch.TA_MODES)),
    ("pps", "속도광", "연습에서 60초 안에 블록 90개 놓기", lambda c: "p_pps" in c.get("practice_done", ())),
    # ---- 마스터
    ("master_5", "마스터 입문", "마스터 연습 과제 5개 완료", lambda c: c.get("master_n", 0) >= 5),
    ("master_all", "마스터 수료", f"마스터 연습 과제 {len(_ch.MASTER_IDS)}개를 모두 완료", lambda c: c.get("master_n", 0) >= len(_ch.MASTER_IDS)),
    ("pc2", "퍼펙트 두 번", "연습에서 퍼펙트 클리어 2회", lambda c: "p_pc2" in c.get("practice_done", ())),
    ("combo10", "연속의 달인", "연습에서 10연속 콤보", lambda c: "p_combo10" in c.get("practice_done", ())),
    ("b2b7", "B2B 마스터", "연습에서 B2B 7연속", lambda c: "p_b2b7" in c.get("practice_done", ())),
    ("drill300", "철벽", "압박 드릴에서 5분 버티기", lambda c: "p_drill300" in c.get("practice_done", ())),
    ("sprint90", "질주", "타임어택 40줄 스프린트를 90초 안에", lambda c: 0 < c.get("ta", {}).get("sprint", 0) <= 90),
    ("tst3", "트리플의 지배자", "연습에서 T-스핀 트리플 3번", lambda c: "p_tst3" in c.get("practice_done", ())),
    ("ach25", "수집가", "업적 25개 달성", lambda c: c.get("ach_n", 0) >= 25),
    ("ach40", "명예의 전당", "업적 40개 달성", lambda c: c.get("ach_n", 0) >= 40),
)
# 기록실 업적 페이지 (카테고리 id, 이름)와 업적별 카테고리
ACH_CATEGORIES = (("battle", "대전"), ("career", "누적"), ("challenge", "도전"), ("skill", "연습·기술"), ("master", "마스터"))
ACH_CATEGORY = {}
for _cat, _ids in (("battle", ("first_ko", "ko5", "ko10", "ko15", "top10", "victory", "century", "marathon", "ironman", "revenge")),
                   ("career", ("games10", "games100", "win3", "win10", "top5_10", "kos100", "lines1000", "lines5000", "ladder_all", "playtime")),
                   ("challenge", ("daily3", "streak3", "streak7", "streak14", "daily_perfect", "star_collector", "star_100", "variant_master", "weekly_stars", "weekly_perfect")),
                   ("skill", ("combo8", "combo12", "practice_half", "practice_all", "tspin_master", "perfect_clear", "drill_survivor", "sprinter", "ta_all", "pps")),
                   ("master", ("master_5", "master_all", "pc2", "combo10", "b2b7", "drill300", "sprint90", "tst3", "ach25", "ach40"))):
    for _aid in _ids:
        ACH_CATEGORY[_aid] = _cat
CHALLENGE_ACHIEVEMENTS = ("streak3", "streak7", "streak14", "daily_perfect", "star_collector", "star_100", "variant_master", "weekly_stars", "weekly_perfect",
                          "practice_half", "practice_all", "tspin_master", "perfect_clear", "drill_survivor", "sprinter", "ta_all", "pps",
                          "master_5", "master_all", "pc2", "combo10", "b2b7", "drill300", "sprint90", "tst3", "ach25", "ach40")      # 도전 과제를 저장할 때 따로 판정하는 업적 (경기 기록 없이도 달성)
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
    "best_by_size": {},               # 규모별 최고 순위 {"small": 3, "mid": 8, "large": 28} (플레이한 규모만)
    "daily_meta": {},                 # 오늘의 도전 날짜별 {"rank": 최고 순위, "secs": 그때 버틴 시간, "tries": 시도 횟수} (고스트 비교용, 최근 30일)
    "weekly": {},                     # 주간 변형 규칙 주별 최고 순위 {"2026W40": 7} (최근 20주)
    "rivals": {},                     # 라이벌 봇: {"losses": {봇 id: 나를 탈락시킨 횟수}, "revenges": 라이벌을 처치한 횟수}
    "xp": 0,                          # 누적 경험치 (배틀로얄 버킷(최상위)에만 쌓음. 서바이벌/연습/도전 별도 여기로 합산)
    "highlights": {}                  # 명장면 횟수 {HIGHLIGHT_IDS 중 하나: 횟수}
}

def _backup_corrupt(path):
    """읽을 수 없는 전적 파일은 덮어쓰기 전에 옆에 백업해 둠 (전적 영구 손실 방지)"""
    try:
        import shutil
        shutil.copy2(path, f"{path}.corrupt-{int(datetime.datetime.now().timestamp())}")
    except Exception:
        pass


def next_goal_text(rank, kos, total_players, best_in_size, difficulty=None, cleared=(), ladder_clear=None, max_ko=0):
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
    if max_ko > kos and max_ko - kos <= 2 and total_players > 2:          # 근접 실패: K.O. 개인 최고 기록이 코앞
        return f"K.O. 최고 기록({max_ko}명)까지 {max_ko - kos}명"
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


def _clean_challenges(v):
    """저장된 challenges를 검증해 알려진 id와 올바른 형식만 남김 (날짜 30일, 주 20주까지)"""
    def ids(lst, valid):
        return [x for x in (lst if isinstance(lst, list) else []) if isinstance(x, str) and x in valid]

    def nn(x):
        return int(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and x >= 0 else 0
    out = {"v": 1, "practice": {"done": [], "ta": {}}, "daily": {}, "weekly": {},
           "daily_streak": {"cur": 0, "best": 0, "last": ""}, "stars": {"daily": 0, "weekly": 0, "practice": 0}, "weekly_rules": []}
    p = v.get("practice")
    if isinstance(p, dict):
        out["practice"]["done"] = [g for g in _ch.PRACTICE_IDS if g in ids(p.get("done"), set(_ch.PRACTICE_IDS))]
        ta = p.get("ta") if isinstance(p.get("ta"), dict) else {}
        out["practice"]["ta"] = {m: nn(ta.get(m)) for m in _ch.TA_BY_ID if nn(ta.get(m)) > 0}
        if "quad" not in out["practice"]["ta"] and nn(p.get("ta_best")) > 0:         # v1.1.4 이전 저장 형식 (쿼드 5번 최고 기록 하나)
            out["practice"]["ta"]["quad"] = nn(p.get("ta_best"))
    dd = v.get("daily")
    if isinstance(dd, dict):
        for k, rec in dd.items():
            if isinstance(k, str) and len(k) == 8 and k.isdigit() and isinstance(rec, dict):
                out["daily"][k] = {"ids": ids(rec.get("ids"), set(_ch.DAILY_BY_ID))[:3], "done": ids(rec.get("done"), set(_ch.DAILY_BY_ID)), "tries": nn(rec.get("tries"))}
        for old in sorted(out["daily"])[:-30]:
            del out["daily"][old]
    wk = v.get("weekly")
    if isinstance(wk, dict):
        for k, rec in wk.items():
            if isinstance(k, str) and len(k) == 7 and k[4] == "W" and isinstance(rec, dict):
                rule = rec.get("rule") if rec.get("rule") in _ch.WEEKLY_GOALS else ""
                out["weekly"][k] = {"rule": rule, "done": ids(rec.get("done"), set(_ch.WEEKLY_BY_ID))}
        for old in sorted(out["weekly"])[:-20]:
            del out["weekly"][old]
    st = v.get("daily_streak")
    if isinstance(st, dict):
        last = st.get("last")
        out["daily_streak"] = {"cur": nn(st.get("cur")), "best": nn(st.get("best")),
                               "last": last if isinstance(last, str) and len(last) == 8 and last.isdigit() else ""}
    sr = v.get("stars")
    if isinstance(sr, dict):
        out["stars"] = {k: nn(sr.get(k)) for k in ("daily", "weekly", "practice")}
    out["weekly_rules"] = [r for r in (v.get("weekly_rules") if isinstance(v.get("weekly_rules"), list) else []) if r in _ch.WEEKLY_GOALS]
    return out


def _stars_of(d):
    s = d.get("challenges", {}).get("stars", {}) if isinstance(d.get("challenges"), dict) else {}
    return sum(int(s.get(k, 0)) for k in ("daily", "weekly", "practice"))


class StatsManager:
    def __init__(self, filepath=STATS_FILE):
        self.filepath = filepath
        self.data = copy.deepcopy(DEFAULT_STATS)          # 배틀로얄(공격 있음) 전적. 예전 파일과 호환되도록 최상위에 유지
        self.data["survival"] = copy.deepcopy(DEFAULT_STATS)   # 서바이벌(공격 없음) 전적: 같은 구조를 따로 보관
        self.last_ladder_clear = None
        self.last_new_achievements = []
        self.last_xp = None                               # 방금 끝난 경기의 경험치 정산 {"gain","parts","before","after","lv_before","lv_after"}
        self.last_level_up = None                         # (이전 레벨, 새 레벨): 도전 과제 별로 레벨이 오른 직후 앱이 알림을 띄우고 비움
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
            elif k == "challenges":
                if isinstance(v, dict):
                    target[k] = _clean_challenges(v)
            elif k == "daily_meta":
                if isinstance(v, dict):
                    clean = {}
                    for kk, vv in v.items():
                        if (isinstance(kk, str) and len(kk) == 8 and kk.isdigit() and isinstance(vv, dict)
                                and all(isinstance(vv.get(f), int) and not isinstance(vv.get(f), bool) and vv.get(f) >= 0 for f in ("rank", "secs", "tries"))):
                            clean[kk] = {f: int(vv[f]) for f in ("rank", "secs", "tries")}
                    target[k] = clean
            elif k == "weekly":
                if isinstance(v, dict):
                    target[k] = {kk: int(vv) for kk, vv in v.items()
                                 if isinstance(kk, str) and len(kk) == 7 and kk[4] == "W" and isinstance(vv, (int, float)) and not isinstance(vv, bool) and vv >= 1}
            elif k == "rivals":
                if isinstance(v, dict):
                    losses = v.get("losses", {})
                    rev = v.get("revenges", 0)
                    target[k] = {"losses": {kk: int(vv) for kk, vv in (losses.items() if isinstance(losses, dict) else [])
                                            if isinstance(kk, str) and kk.startswith("BOT_") and isinstance(vv, (int, float)) and not isinstance(vv, bool) and vv >= 1},
                                 "revenges": int(rev) if isinstance(rev, (int, float)) and not isinstance(rev, bool) and rev >= 0 else 0}
            elif k == "highlights":                        # 명장면: 알려진 id + 양의 정수만
                if isinstance(v, dict):
                    target[k] = {kk: int(vv) for kk, vv in v.items()
                                 if kk in HIGHLIGHT_IDS and isinstance(vv, (int, float)) and not isinstance(vv, bool) and vv >= 1}
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
        cc = self._challenge_ctx()
        n_pr = len(_ch.PRACTICE_IDS)

        def cap(v, goal):
            return (min(int(v), goal), goal)
        return {"first_ko": cap(mk, 1), "ko5": cap(mk, 5), "ko10": cap(mk, 10), "ko15": cap(mk, 15), "combo8": cap(cb, 8), "combo12": cap(cb, 12),
                "marathon": cap(best_secs, 420), "ironman": cap(best_secs, 540), "ladder_all": (len(d.get("ladder", [])), 4), "daily3": (min(len(d.get("daily", {})), 3), 3),
                "games10": cap(d.get("total_games", 0), 10), "games100": cap(d.get("total_games", 0), 100),
                "win3": cap(d.get("victories", 0), 3), "win10": cap(d.get("victories", 0), 10), "top5_10": cap(d.get("top_5", 0), 10),
                "kos100": cap(d.get("total_kos", 0), 100), "lines1000": cap(d.get("total_lines", 0), 1000), "lines5000": cap(d.get("total_lines", 0), 5000),
                "streak3": cap(cc["streak_best"], 3), "streak7": cap(cc["streak_best"], 7),
                "star_collector": cap(cc["daily_stars"], 30), "star_100": cap(cc["daily_stars"] + cc["weekly_stars"], 100),
                "variant_master": cap(cc["weekly_rules_n"], 4), "weekly_stars": cap(cc["weekly_stars"], 10),
                "practice_half": cap(cc["practice_n"], n_pr // 2), "practice_all": cap(cc["practice_n"], n_pr), "ta_all": cap(len(cc["ta"]), len(_ch.TA_MODES)),
                "playtime": cap(d.get("total_play_time_sec", 0) // 60, 600), "streak14": cap(cc["streak_best"], 14),
                "master_5": cap(cc["master_n"], 5), "master_all": cap(cc["master_n"], len(_ch.MASTER_IDS)),
                "ach25": cap(len(d.get("achievements", [])), 25), "ach40": cap(len(d.get("achievements", [])), 40)}

    # ------------------------------------------------------------------ 도전 과제 (연습 / 오늘의 도전 / 주간 변형)
    def ch(self):
        """도전 과제 저장 영역 (없으면 기본값으로 만들어 둠). 배틀로얄 버킷(최상위)에만 있음"""
        d = self.data
        c = d.get("challenges")
        if not isinstance(c, dict):
            c = d["challenges"] = _clean_challenges({})
        return c

    def challenge_done(self, kind, key=None):
        """이미 달성해 저장된 과제 id 집합. kind: practice / daily(key=날짜) / weekly(key=주 키)"""
        c = self.ch()
        if kind == "practice":
            return set(c["practice"]["done"])
        return set(c[kind].get(key, {}).get("done", []))

    def daily_goal_ids(self, date_key):
        """오늘의 목표 id 3개. 그날 한 번 정해지면 저장해 두고 그 뒤로는 풀이 바뀌어도 같은 목표를 씀"""
        c = self.ch()
        rec = c["daily"].get(date_key)
        if rec and rec.get("ids"):
            return list(rec["ids"])
        ids = _ch.pick_daily(date_key)
        c["daily"][date_key] = {"ids": ids, "done": [], "tries": 0}
        for old in sorted(c["daily"])[:-30]:
            del c["daily"][old]
        return ids

    def weekly_goal_state(self, week_key, rule_id):
        c = self.ch()
        rec = c["weekly"].setdefault(week_key, {"rule": rule_id, "done": []})
        for old in sorted(c["weekly"])[:-20]:
            del c["weekly"][old]
        return rec

    def level(self):
        """(레벨, 이번 레벨에서 쌓은 경험치, 필요 경험치)"""
        return level_of(self.data.get("xp", 0))

    def add_xp(self, n):
        """경험치 추가 (레벨이 오르면 last_level_up에 기록). 새 경험치 합계를 돌려줌"""
        n = int(n)
        if n <= 0:
            return self.data.get("xp", 0)
        before = level_of(self.data.get("xp", 0))[0]
        self.data["xp"] = int(self.data.get("xp", 0)) + n
        after = level_of(self.data["xp"])[0]
        if after > before:
            self.last_level_up = (before, after)
        return self.data["xp"]

    def stars_total(self):
        s = self.ch()["stars"]
        return int(s["daily"]) + int(s["weekly"]) + int(s["practice"])

    def mark_challenges(self, kind, key, ids):
        """새로 달성한 과제 id들을 저장하고 별/스트릭/업적을 갱신. 이미 저장된 id는 무시. 새로 반영된 id 목록을 돌려줌"""
        c = self.ch()
        new = []
        if kind == "practice":
            done = c["practice"]["done"]
            for gid in ids:
                if gid in _ch.PRACTICE_IDS and gid not in done:
                    done.append(gid)
                    new.append(gid)
            c["stars"]["practice"] = len(done)
        elif kind == "daily":
            rec = c["daily"].setdefault(key, {"ids": [], "done": [], "tries": 0})
            for gid in ids:
                if gid in _ch.DAILY_BY_ID and gid not in rec["done"]:
                    rec["done"].append(gid)
                    new.append(gid)
            if new:
                c["stars"]["daily"] += len(new)
                st = c["daily_streak"]
                if st["last"] != key:                                   # 그날 첫 별 = 출석: 어제까지 이어졌으면 +1, 아니면 1부터
                    yesterday = (datetime.datetime.strptime(key, "%Y%m%d") - datetime.timedelta(days=1)).strftime("%Y%m%d")
                    st["cur"] = st["cur"] + 1 if st["last"] == yesterday else 1
                    st["best"] = max(st["best"], st["cur"])
                    st["last"] = key
        elif kind == "weekly":
            rec = c["weekly"].setdefault(key, {"rule": "", "done": []})
            for gid in ids:
                if gid in _ch.WEEKLY_BY_ID and gid not in rec["done"]:
                    rec["done"].append(gid)
                    new.append(gid)
            if new:
                c["stars"]["weekly"] += len(new)
                rule = next((r for r, gl in _ch.WEEKLY_GOALS.items() if any(g["id"] == new[0] for g in gl)), "")
                rec["rule"] = rule or rec.get("rule", "")
                if rule and rule not in c["weekly_rules"]:
                    c["weekly_rules"].append(rule)
        if new:
            self.add_xp(STAR_XP * len(new))
            self.grant_challenge_achievements()
            self.save()
        return new

    def daily_stars_today(self, date_key):
        return len(self.ch()["daily"].get(date_key, {}).get("done", []))

    def streak(self):
        """(현재 연속 일수, 최고 연속 일수). 어제도 오늘도 별이 없으면 현재는 0으로 봄"""
        st = self.ch()["daily_streak"]
        today = datetime.date.today().strftime("%Y%m%d")
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")
        return (st["cur"] if st["last"] in (today, yesterday) else 0), st["best"]

    def _challenge_ctx(self):
        """업적 판정에 쓰는 도전 과제 쪽 값 (경기 기록과 상관없이 연습/도전/주간 기록에서 나옴)"""
        c = self.ch()
        return {"daily_stars": c["stars"]["daily"], "weekly_stars": c["stars"]["weekly"], "weekly_rules_n": len(c["weekly_rules"]),
                "practice_n": len(c["practice"]["done"]), "practice_done": set(c["practice"]["done"]), "ta": dict(c["practice"]["ta"]),
                "streak_best": c["daily_streak"]["best"], "daily_full": sum(1 for r in c["daily"].values() if len(r.get("done", [])) >= 3),
                "weekly_full": sum(1 for r in c["weekly"].values() if len(r.get("done", [])) >= 3),
                "master_n": sum(1 for x in c["practice"]["done"] if x in _ch.MASTER_IDS)}

    def save_time_attack(self, bests):
        """타임어택 종류별 최고 기록(초)을 저장된 것과 비교해 더 빠른 것만 반영하고, 그 덕에 달성한 업적까지 판정. 바뀐 것이 있으면 True"""
        ta = self.ch()["practice"]["ta"]
        changed = False
        for mode, secs in bests.items():
            if mode in _ch.TA_BY_ID and int(secs) > 0 and (mode not in ta or int(secs) < ta[mode]):
                ta[mode] = int(secs)
                changed = True
        if changed:
            self.grant_challenge_achievements()
            self.save()
        return changed

    def grant_challenge_achievements(self):
        """도전 과제 저장 직후 업적 판정 (경기 기록 없이도 연습/도전으로 달성 가능). 새로 달성한 id 목록"""
        ctx = self._challenge_ctx()
        have = self.data.setdefault("achievements", [])
        got = []
        for aid, _t, _d, ok in ACHIEVEMENTS:
            ctx["ach_n"] = len(have)                                          # 업적 개수 업적은 이번에 얻은 것까지 센다 (목록 맨 뒤에 둠)
            if aid in CHALLENGE_ACHIEVEMENTS and aid not in have and ok(ctx):
                have.append(aid)
                got.append(aid)
        if got:
            self.data["achievements"] = [x for x in ACHIEVEMENT_IDS if x in have]
            self.last_new_achievements = list(getattr(self, "last_new_achievements", [])) + got
        return got

    def rival_id(self):
        """나를 가장 많이 탈락시킨 봇 id (2번 이상일 때만 라이벌로 인정). 없으면 None"""
        losses = self.data.get("rivals", {}).get("losses", {})
        if not losses:
            return None
        bid = max(sorted(losses), key=lambda b: losses[b])
        return bid if losses[bid] >= 2 else None

    def daily_ghost(self, date_key):
        """오늘의 도전의 지난 최고 기록 {"rank","secs","tries"} (처음이면 None)"""
        return self.data.get("daily_meta", {}).get(date_key)

    def weekly_best(self, week_key):
        return self.data.get("weekly", {}).get(week_key, 0)

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

    def record_match(self, rank, total_players, kos, lines, max_combo, survival_sec, mode="battle", difficulty="mixed", daily=None,
                     weekly=None, killer=None, revenge=False, highlights=()):
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
            meta = d.setdefault("daily_meta", {})          # 고스트 비교용: 최고 순위(같으면 더 오래 버틴 기록)와 시도 횟수
            cur = meta.get(daily, {"rank": 10 ** 6, "secs": 0, "tries": 0})
            better = rank < cur["rank"] or (rank == cur["rank"] and int(survival_sec) > cur["secs"])
            meta[daily] = {"rank": rank if better else cur["rank"], "secs": int(survival_sec) if better else cur["secs"], "tries": cur["tries"] + 1}
            for old_key in sorted(meta)[:-30]:
                del meta[old_key]
        if weekly:                                         # 주간 변형 규칙: 주별 최고 순위 (최근 20주)
            wk = d.setdefault("weekly", {})
            if weekly not in wk or rank < wk[weekly]:
                wk[weekly] = rank
            for old_key in sorted(wk)[:-20]:
                del wk[old_key]
        if mode == "battle" and killer and isinstance(killer, str) and killer.startswith("BOT_") and rank > 1:   # 라이벌 집계: 나를 탈락시킨 봇
            rv = d.setdefault("rivals", {})
            losses = rv.setdefault("losses", {})
            losses[killer] = losses.get(killer, 0) + 1
            if len(losses) > 30:                           # 오래된 기록이 쌓이지 않게 횟수가 적은 것부터 정리
                for k_ in sorted(losses, key=lambda x: losses[x])[:len(losses) - 30]:
                    del losses[k_]
        if mode == "battle" and revenge:
            rv = d.setdefault("rivals", {})
            rv["revenges"] = rv.get("revenges", 0) + 1
            rv.setdefault("losses", {}).clear()            # 복수에 성공하면 라이벌 관계를 새로 시작

        self.last_ladder_clear = None                      # 이번 경기로 새로 클리어한 난이도 (없으면 None)
        if (mode == "battle" and difficulty in LADDER and total_players >= LADDER_MIN_PLAYERS and rank <= LADDER_RANK
                and difficulty not in d.setdefault("ladder", [])):
            d["ladder"].append(difficulty)
            self.last_ladder_clear = difficulty
        d["total_games"] = prev_games + 1
        self.last_new_achievements = []                    # 이번 경기로 새로 달성한 업적 id
        
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

        hl = [h for h in highlights if h in HIGHLIGHT_IDS]                 # 명장면 집계 + 경험치 정산 (서바이벌도 경험치는 쌓이지만 절반)
        if hl and mode == "battle":
            hc = self.data.setdefault("highlights", {})
            for h in hl:
                hc[h] = hc.get(h, 0) + 1
        xp_before = int(self.data.get("xp", 0))
        gain, parts = calc_match_xp(rank, total_players, kos, survival_sec, hl if mode == "battle" else (), mode)
        self.data["xp"] = xp_before + gain
        lv_b, lv_a = level_of(xp_before)[0], level_of(self.data["xp"])[0]
        self.last_xp = {"gain": gain, "parts": parts, "before": xp_before, "after": self.data["xp"], "lv_before": lv_b, "lv_after": lv_a}

        if mode == "battle":                               # 업적은 누적 값을 모두 갱신한 뒤에 판정
            ctx = {"rank": rank, "total": total_players, "kos": kos, "lines": lines, "combo": max_combo, "secs": survival_sec,
                   "ladder_n": len(d.get("ladder", [])), "daily_n": len(d.get("daily", {})),
                   "revenge_n": d.get("rivals", {}).get("revenges", 0),
                   "games": d.get("total_games", 0), "victories": d.get("victories", 0), "top5": d.get("top_5", 0),
                   "total_kos": d.get("total_kos", 0), "total_lines": d.get("total_lines", 0), "play_min": d.get("total_play_time_sec", 0) // 60}
            ctx.update(self._challenge_ctx())
            have = d.setdefault("achievements", [])
            for aid, _title, _desc, ok in ACHIEVEMENTS:
                ctx["ach_n"] = len(have)
                if aid not in have and ok(ctx):
                    have.append(aid)
                    self.last_new_achievements.append(aid)
            d["achievements"] = [x for x in ACHIEVEMENT_IDS if x in have]

        
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


# 해금 꾸밈: 업적/기록으로 열리는 블록 스킨. id -> (조건 설명, 조건 함수(전적 dict) -> bool). 기존 4종(classic/neon/flat/jelly)은 처음부터 사용 가능
SKIN_UNLOCKS = {
    "pixel": ("업적 3개 달성", lambda d: len(d.get("achievements", [])) >= 3),
    "glass": ("로열 빅토리(우승) 1회", lambda d: d.get("victories", 0) >= 1),
    "starlight": ("도전 과제 별(★) 누적 90개", lambda d: _stars_of(d) >= 90),
    "ember": ("레벨 5 달성", lambda d: level_of(d.get("xp", 0))[0] >= 5),
    "prism": ("레벨 10 달성", lambda d: level_of(d.get("xp", 0))[0] >= 10),
}


def unlocked_skin_ids(stats_data):
    """지금 쓸 수 있는 스킨 id 목록 (기본 4종 + 조건을 채운 해금 스킨)"""
    out = ["classic", "neon", "flat", "jelly"]
    out += [sid for sid, (_d, ok) in SKIN_UNLOCKS.items() if ok(stats_data)]
    return out


def locked_skin_hints(stats_data):
    """아직 잠긴 스킨의 [(id, 조건 설명)]"""
    return [(sid, desc) for sid, (desc, ok) in SKIN_UNLOCKS.items() if not ok(stats_data)]

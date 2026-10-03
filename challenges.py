"""
Block Royale 100 - 도전 과제 시스템 (연습 / 오늘의 도전 / 주간 변형 공용)
pygame을 쓰지 않는 순수 파이썬 모듈이라 단위 테스트가 쉽다.

 - 과제 정의: dict(id, text, short, metric, goal, op, tier, cat)
     metric: 추적기가 모으는 지표 이름, op: ">=" (기본) 또는 "<=" (순위처럼 작을수록 좋은 지표)
     tier: 별 등급 1~3, cat: 같은 날 겹치지 않게 하려는 범주, short: HUD용 짧은 문구(7자 안팎)
 - ChallengeTracker: 매치가 이벤트(줄 지우기/K.O./공격/...)를 알려 주면 지표를 갱신하고 새로 달성한 과제를 newly_done에 쌓는다.
   엔진의 누적 카운터에 기대지 않으므로 연습 모드에서 보드가 리셋돼도 진행도가 유지된다.
 - pick_daily(날짜 키): 날짜로 결정되는 하루 목표 3개 (별도 Random 인스턴스를 써서 전역 난수/봇 구성을 건드리지 않음)
"""

import random

POOL_VERSION = 1
TOP_INIT = 10 ** 6           # "top" 지표의 초기값 (내가 살아 있는 동안 본 가장 적은 생존자 수)


def _g(gid, text, short, metric, goal, tier, cat, op=">="):
    return {"id": gid, "text": text, "short": short, "metric": metric, "goal": goal, "tier": tier, "cat": cat, "op": op}


# ------------------------------------------------------------------ 연습 과제 (쉬운 순서)
PRACTICE_GOALS = [
    _g("p_cancel2", "G로 받은 줄 2줄 상쇄하기", "상쇄 2줄", "canceled_total", 2, 1, "defense"),
    _g("p_quad", "4줄 한 번에 지우기(쿼드)", "쿼드", "quads", 1, 1, "tech"),
    _g("p_combo3", "3연속 콤보 만들기", "콤보 3", "combo_max", 3, 1, "tech"),
    _g("p_tspin", "T-스핀으로 줄 지우기", "T-스핀", "tspins", 1, 1, "tech"),
    _g("p_cancel_big", "Shift+G로 8줄을 받고 한 번에 4줄 이상 막기", "한번에 4막기", "canceled_max", 4, 2, "defense"),
    _g("p_drill60", "압박 드릴(V)에서 60초 버티기", "드릴 60초", "drill_secs", 60, 2, "survival"),
    _g("p_b2bquad", "B2B 쿼드 (쿼드를 연달아)", "B2B 쿼드", "b2b_quads", 1, 2, "tech"),
    _g("p_combo5", "5연속 콤보 만들기", "콤보 5", "combo_max", 5, 2, "tech"),
    _g("p_tsd", "T-스핀 더블 (2줄)", "T-스핀 더블", "tspin_doubles", 1, 3, "tech"),
    _g("p_b2b3", "B2B를 3번 이어가기", "B2B 3연속", "b2b_chain_max", 3, 3, "tech"),
    _g("p_drill_lv5", "압박 드릴 Lv.5까지 버티기 (2분)", "드릴 Lv.5", "drill_level", 5, 3, "survival"),
    _g("p_pc", "퍼펙트 클리어 1회", "퍼펙트", "pcs", 1, 3, "tech"),
]
PRACTICE_IDS = [g["id"] for g in PRACTICE_GOALS]
TA_QUADS = 5                  # 타임어택: 쿼드 5번을 가장 빨리

# ------------------------------------------------------------------ 오늘의 도전 후보 풀
DAILY_POOL = [
    # ★1: 쉬움 대역 봇 수준에서도 가능한 목표
    _g("d_life90", "1분 30초 생존", "생존 1:30", "survive", 90, 1, "survival"),
    _g("d_lines20", "줄 20개 지우기", "20줄 삭제", "lines", 20, 1, "tech"),
    _g("d_cancel2", "받은 공격 2줄 막기", "상쇄 2줄", "canceled_total", 2, 1, "defense"),
    _g("d_ko1", "K.O. 1명", "K.O. 1", "kos", 1, 1, "combat"),
    _g("d_combo2", "2연속 콤보", "콤보 2", "combo_max", 2, 1, "tech"),
    # ★2
    _g("d_quad2", "쿼드 2회", "쿼드 2회", "quads", 2, 2, "tech"),
    _g("d_life300", "5분 생존", "생존 5:00", "survive", 300, 2, "survival"),
    _g("d_ko4", "K.O. 4명", "K.O. 4", "kos", 4, 2, "combat"),
    _g("d_cancel8", "받은 공격 8줄 막기", "상쇄 8줄", "canceled_total", 8, 2, "defense"),
    _g("d_top30", "30위 안에 들기", "30위 안", "top", 30, 2, "rank", "<="),
    _g("d_sent30", "보낸 줄 30줄", "공격 30줄", "sent_total", 30, 2, "combat"),
    # ★3
    _g("d_top20", "20위 안에 들기", "20위 안", "top", 20, 3, "rank", "<="),
    _g("d_quad4", "쿼드 4회", "쿼드 4회", "quads", 4, 3, "tech"),
    _g("d_ko5", "K.O. 5명", "K.O. 5", "kos", 5, 3, "combat"),
    _g("d_cancel5x", "한 번에 5줄 이상 막기", "한번에 5막기", "canceled_max", 5, 3, "defense"),
    _g("d_clutch1", "위기 탈출 1회", "위기 탈출", "clutch", 1, 3, "defense"),
    _g("d_tsd", "T-스핀 더블", "T-스핀 더블", "tspin_doubles", 1, 3, "tech"),
    _g("d_b2bquad", "B2B 쿼드", "B2B 쿼드", "b2b_quads", 1, 3, "tech"),
]
DAILY_BY_ID = {g["id"]: g for g in DAILY_POOL}

# ------------------------------------------------------------------ 주간 변형 규칙 전용 목표 (규칙 id -> 목표 3개, ★1~3)
WEEKLY_GOALS = {
    "elite": [_g("w_el_1", "1분 생존 (모두 어려움 봇)", "생존 1:00", "survive", 60, 1, "survival"),
              _g("w_el_2", "어려움 봇 K.O. 1명", "K.O. 1", "kos", 1, 2, "combat"),
              _g("w_el_3", "30인 중 15위 안 (절반 안)", "15위 안", "top", 15, 3, "rank", "<=")],
    "perfect": [_g("w_pf_1", "받은 공격 5줄 막기 (폭격 대비)", "상쇄 5줄", "canceled_total", 5, 1, "defense"),
                _g("w_pf_2", "한 번에 4줄 이상 막기", "한번에 4막기", "canceled_max", 4, 2, "defense"),
                _g("w_pf_3", "퍼펙트 클리어 1회 (20줄!)", "퍼펙트", "pcs", 1, 3, "tech")],
    "fog": [_g("w_fg_1", "NEXT 1개만 보고 줄 30개 지우기", "30줄 삭제", "lines", 30, 1, "tech"),
            _g("w_fg_2", "NEXT 1개만 보고 쿼드 2회", "쿼드 2회", "quads", 2, 2, "tech"),
            _g("w_fg_3", "7분 생존", "생존 7:00", "survive", 420, 3, "survival")],
    "rush": [_g("w_rs_1", "공격력 증폭(×1.2↑) 상태로 30초 생존", "증폭 30초", "esc_survive", 30, 1, "survival"),
             _g("w_rs_2", "K.O. 5명", "K.O. 5", "kos", 5, 2, "combat"),
             _g("w_rs_3", "10위 안에 들기", "10위 안", "top", 10, 3, "rank", "<=")],
}
WEEKLY_BY_ID = {g["id"]: g for rule in WEEKLY_GOALS.values() for g in rule}

ALL_GOALS = {g["id"]: g for g in PRACTICE_GOALS + DAILY_POOL + list(WEEKLY_BY_ID.values())}


def known_ids():
    return set(ALL_GOALS)


def pick_daily(date_key):
    """날짜 키('YYYYMMDD')로 정해지는 오늘의 목표 id 3개 [★1, ★2, ★3]. 같은 날은 항상 같은 결과.
    범주(cat)가 겹치지 않게 뽑고 순위 목표는 하루 최대 1개. 전용 Random 인스턴스를 쓰므로 전역 random(봇 구성)은 건드리지 않는다."""
    rng = random.Random(int(date_key) * 1009 + 7)
    by_tier = {t: [g for g in DAILY_POOL if g["tier"] == t] for t in (1, 2, 3)}
    for _ in range(200):
        picks = [rng.choice(by_tier[t]) for t in (1, 2, 3)]
        cats = [p["cat"] for p in picks]
        if len(set(cats)) == 3:
            return [p["id"] for p in picks]
    return [by_tier[t][0]["id"] for t in (1, 2, 3)]      # (사실상 도달하지 않음) 안전한 기본값


def weekly_goal_ids(rule_id):
    return [g["id"] for g in WEEKLY_GOALS.get(rule_id, [])]


class ChallengeTracker:
    """한 경기 동안의 지표를 모아 목표 달성을 판정한다. goals: 과제 dict 목록, done: 이미 달성해 저장돼 있는 id들"""

    def __init__(self, goals, done=()):
        self.goals = [dict(g) for g in goals]
        self.order = [g["id"] for g in self.goals]
        self.by_id = {g["id"]: g for g in self.goals}
        self.done = set(x for x in done if x in self.by_id)
        self.newly_done = []                       # 이번 경기에서 새로 달성한 id (앱이 꺼내 가며 저장/알림)
        self.m = {"lines": 0, "quads": 0, "tspins": 0, "tspin_doubles": 0, "b2b_quads": 0, "b2b_chain_max": 0, "pcs": 0,
                  "combo_max": 0, "canceled_total": 0, "canceled_max": 0, "kos": 0, "sent_total": 0, "sent_max": 0,
                  "multi": 0, "clutch": 0, "survive": 0.0, "esc_survive": 0.0, "top": TOP_INIT,
                  "drill_secs": 0, "drill_level": 0}
        self._last_survive = 0.0
        self._last_esc = 0.0

    # ---- 판정
    def _value(self, g):
        return self.m.get(g["metric"], 0)

    def reached(self, g):
        v = self._value(g)
        return v <= g["goal"] if g.get("op") == "<=" else v >= g["goal"]

    def _check(self):
        for g in self.goals:
            if g["id"] not in self.done and self.reached(g):
                self.done.add(g["id"])
                self.newly_done.append(g["id"])

    def pop_new(self):
        out, self.newly_done = self.newly_done, []
        return out

    def progress(self, gid):
        """HUD 표시용 (현재값, 목표). 순위 목표는 현재 생존자 수가 아니라 '지금까지 본 가장 적은 생존자 수'라 표시하지 않음(None)"""
        g = self.by_id[gid]
        if g.get("op") == "<=":
            return None
        cur = self._value(g)
        return (int(min(cur, g["goal"])), int(g["goal"]))

    # ---- 이벤트 (매치가 호출)
    def on_clear(self, info):
        """라인 클리어 한 번. info: block_engine.last_clear_info (+ cleared)"""
        cleared = int(info.get("cleared", 0))
        if cleared <= 0:
            return
        m = self.m
        m["lines"] += cleared
        quad = cleared >= 4
        if quad:
            m["quads"] += 1
            if info.get("is_b2b"):
                m["b2b_quads"] += 1
        if info.get("is_tspin"):
            m["tspins"] += 1
            if cleared == 2 and not info.get("is_mini"):
                m["tspin_doubles"] += 1
        m["b2b_chain_max"] = max(m["b2b_chain_max"], int(info.get("b2b_chain", 0)))
        if info.get("is_pc"):
            m["pcs"] += 1
        m["combo_max"] = max(m["combo_max"], int(info.get("combo", 0)))
        c = int(info.get("canceled", 0))
        if c > 0:
            m["canceled_total"] += c
            m["canceled_max"] = max(m["canceled_max"], c)
        self._check()

    def on_ko(self):
        self.m["kos"] += 1
        self._check()

    def on_attack(self, lines, n_targets=1):
        """내 공격이 실제로 나간 한 번 (lines: 보낸 줄 수, n_targets: 동시에 노린 상대 수)"""
        total = int(lines) * max(1, int(n_targets))
        self.m["sent_total"] += total
        self.m["sent_max"] = max(self.m["sent_max"], int(lines))
        if n_targets >= 2:
            self.m["multi"] += 1
        self._check()

    def on_clutch(self):
        self.m["clutch"] += 1
        self._check()

    def on_drill(self, secs, level):
        """압박 드릴 진행 (secs: 이번 드릴에서 버틴 초, level: 1부터 시작하는 단계)"""
        self.m["drill_secs"] = max(self.m["drill_secs"], int(secs))
        self.m["drill_level"] = max(self.m["drill_level"], int(level))
        self._check()

    def tick(self, elapsed, alive, alive_count, multiplier=1.0):
        """매 프레임(또는 1초마다): 생존 시간, 증폭 상태 생존 시간, 가장 적은 생존자 수"""
        if alive:
            self.m["survive"] = max(self.m["survive"], float(elapsed))
            self.m["top"] = min(self.m["top"], int(alive_count))
            dt = max(0.0, float(elapsed) - self._last_esc)
            if multiplier >= 1.2 and self._last_esc > 0.0:
                self.m["esc_survive"] += min(dt, 1.0)
            self._last_esc = float(elapsed)
        self._check()

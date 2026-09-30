"""
Block Royale 100 - Stats & Records Manager
플레이어의 역대 경기 전적(우승 횟수, 최고 순위, 누적 KO, 최대 콤보, 최근 경기 목록)을 stats.json에 영구 저장 및 관리합니다.
"""

import os
import copy
import json
import datetime

from app_paths import data_path

STATS_FILE = data_path("stats.json")

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
    "recent_matches": []
}

def _backup_corrupt(path):
    """읽을 수 없는 전적 파일은 덮어쓰기 전에 옆에 백업해 둠 (전적 영구 손실 방지)"""
    try:
        import shutil
        shutil.copy2(path, f"{path}.corrupt-{int(datetime.datetime.now().timestamp())}")
    except Exception:
        pass


class StatsManager:
    def __init__(self, filepath=STATS_FILE):
        self.filepath = filepath
        self.data = copy.deepcopy(DEFAULT_STATS)          # 배틀로얄(공격 있음) 전적. 예전 파일과 호환되도록 최상위에 유지
        self.data["survival"] = copy.deepcopy(DEFAULT_STATS)   # 서바이벌(공격 없음) 전적: 같은 구조를 따로 보관
        self.load()

    def _bucket(self, mode):
        return self.data["survival"] if mode == "survival" else self.data

    @staticmethod
    def _merge_saved(target, saved):
        """저장된 값 중 형식이 맞는 것만 target에 반영"""
        for k, v in saved.items():
            d = DEFAULT_STATS.get(k)
            if isinstance(d, list):                        # 최근 경기 목록: 리스트이고 각 항목이 dict일 때만
                if isinstance(v, list):
                    target[k] = [m for m in v if isinstance(m, dict)][-100:]
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

    def record_match(self, rank, total_players, kos, lines, max_combo, survival_sec, mode="battle", difficulty="mixed"):
        """경기 완료 시 전적 기록 및 통계 갱신 (mode: "battle" 배틀로얄 / "survival" 서바이벌)"""
        d = self._bucket(mode)
        prev_games = d.get("total_games", 0)
        prev_best, prev_ko, prev_combo = d.get("best_rank", 0), d.get("max_ko", 0), d.get("max_combo", 0)
        records = []                                       # 이번 경기가 이전 최고 기록을 넘은 항목 (첫 경기는 비교할 기록이 없어 제외)
        if prev_games > 0:
            if prev_best > 0 and rank < prev_best:
                records.append("rank")
            if kos > prev_ko and kos > 0:
                records.append("ko")
            if max_combo > prev_combo and max_combo > 0:
                records.append("combo")
        d["total_games"] = prev_games + 1
        
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
        
        # 최근 경기 목록 기록 (최대 15경기)
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

    def get_summary(self, mode="battle"):
        """화면 표시용 요약 통계 문자열 및 계산값 반환"""
        d = self._bucket(mode)
        total = d.get("total_games", 0)
        vic = d.get("victories", 0)
        win_rate = (vic / total * 100.0) if total > 0 else 0.0
        best_rank = d.get("best_rank", 0)
        best_str = f"#{best_rank}위" if best_rank > 0 else "-"
        
        return {
            "total_games": total,
            "victories": vic,
            "win_rate": win_rate,
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

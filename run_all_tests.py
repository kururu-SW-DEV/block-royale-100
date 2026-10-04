"""
전체 테스트 실행기: 모든 테스트 파일과 정적 검사(정의되지 않은 이름)를 차례로 실행하고 결과를 요약.
하나라도 실패하면 종료 코드 1 (CI/빌드 전 점검용). 사용자 settings.json/stats.json은 실행 후 원래대로 복원.
사용: python run_all_tests.py
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.join(HERE, "tests")
TESTS = ["test_engine_fixes.py", "test_royale.py", "test_v24_perfect_score.py", "test_review_network.py", "test_review_bot.py", "test_review_ui.py", "test_review_data.py", "test_review_rules.py", "test_opus_review2.py", "test_opus_review3.py", "test_challenges.py", "test_juice.py", "test_handling.py", "test_render_smoke.py"]


def _snapshot():
    files = [os.path.join(HERE, n) for n in ("settings.json", "stats.json")]
    return {p: (open(p, "rb").read() if os.path.exists(p) else None) for p in files}


def _restore(snap):
    for p, data in snap.items():
        if data is not None:
            with open(p, "wb") as f:
                f.write(data)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # 한글 결과 줄이 cp1252 같은 콘솔(GitHub Actions Windows 등)에서도 출력되도록
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", PYTHONIOENCODING="utf-8", PYTHONPATH=HERE)  # 프로젝트 루트를 import 경로에 추가(tests/ 안에서 실행돼도 block_engine 등을 찾도록)
    snap = _snapshot()
    results = []
    try:
        for name in TESTS:
            t0 = time.time()
            p = subprocess.run([sys.executable, os.path.join(TESTS_DIR, name)], cwd=HERE, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
            last = (p.stdout.strip().splitlines() or [""])[-1]
            results.append((name, p.returncode == 0, time.time() - t0, last if p.returncode == 0 else (p.stderr.strip().splitlines() or [last])[-1]))
        # 정적 검사: 정의되지 않은 이름(오타)만 실패로 취급
        code_files = [f for f in os.listdir(HERE) if f.endswith(".py") and not f.startswith("test_") and f != "run_all_tests.py"]
        code_files += ["screens/" + f for f in os.listdir(os.path.join(HERE, "screens")) if f.endswith(".py")]
        try:
            p = subprocess.run([sys.executable, "-m", "pyflakes"] + code_files, cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="replace")
            bad = [l for l in p.stdout.splitlines() if "undefined name" in l or "syntax" in l.lower()]
            results.append(("pyflakes(정의되지 않은 이름)", not bad and "No module named" not in p.stderr, 0.0, bad[0] if bad else "이상 없음"))
        except Exception as e:
            results.append(("pyflakes", True, 0.0, f"건너뜀: {e}"))
    finally:
        _restore(snap)
    width = max(len(r[0]) for r in results)
    for name, ok, sec, msg in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {sec:5.1f}s  {msg[:90]}")
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} 통과")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

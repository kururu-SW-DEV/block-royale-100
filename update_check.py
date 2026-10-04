"""
Block Royale 100 - 업데이트 확인 (옵트인)
설정에서 켠 경우에만, 게임을 시작할 때 GitHub Releases의 최신 버전을 한 번 조회해 메인 화면에 "새 버전" 알림을 띄움.
자동으로 내려받거나 설치하지 않으며, 응답이 없거나 오프라인이면 아무 일도 없었던 것처럼 조용히 끝남 (최대 대기 시간 제한).
보내는 정보: 일반적인 HTTPS 요청(IP 주소, 'BlockRoyale100/<버전>' 사용자 에이전트)뿐이며 전적/설정 등 개인 정보는 보내지 않음.
"""

import json
import threading
import urllib.request

from config import APP_VERSION

REPO = "kururu-SW-DEV/block-royale-100"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"
TIMEOUT_SECS = 2.5


def parse_version(text):
    """'v1.1.13' / '1.1.13' -> (1, 1, 13). 숫자가 아닌 조각이 있으면 거기까지만 (예: '1.2.0-beta' -> (1, 2, 0))"""
    nums = []
    for part in str(text).strip().lstrip("vV").split("."):
        digits = ""
        for ch in part:
            if ch.isdigit():
                digits += ch
            else:
                break
        if not digits:
            break
        nums.append(int(digits))
    return tuple(nums)


def is_newer(latest, current=APP_VERSION):
    a, b = parse_version(latest), parse_version(current)
    return bool(a) and a > b


def fetch_latest(opener=None, timeout=TIMEOUT_SECS):
    """최신 릴리스 {"tag", "url"}을 돌려줌. 실패/형식 이상이면 None. opener(url, timeout) -> bytes 는 테스트에서 네트워크를 대신함"""
    try:
        if opener is None:
            req = urllib.request.Request(API_URL, headers={"User-Agent": f"BlockRoyale100/{APP_VERSION}", "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read(200_000)
        else:
            raw = opener(API_URL, timeout)
        data = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
        tag = data.get("tag_name")
        if not isinstance(tag, str) or not parse_version(tag):
            return None
        url = data.get("html_url") if isinstance(data.get("html_url"), str) and data["html_url"].startswith("https://github.com/") else RELEASES_URL
        return {"tag": tag, "url": url}
    except Exception:
        return None


class UpdateChecker:
    """백그라운드 스레드로 한 번만 조회. result: 새 버전이 있을 때만 {"tag", "url"}, 아니면 None. done: 조회가 끝났는지"""

    def __init__(self, opener=None):
        self.opener = opener
        self.result = None
        self.done = False
        self._started = False

    def start(self):
        if self._started:
            return
        self._started = True
        threading.Thread(target=self._run, name="update-check", daemon=True).start()

    def _run(self):
        info = fetch_latest(self.opener)
        if info and is_newer(info["tag"]):
            self.result = info
        self.done = True

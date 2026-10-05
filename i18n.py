"""
Block Royale 100 - 화면 글자 번역 (v1.1.14, 영어 UI 1단계)
게임의 글자는 모두 gfx.HiFont를 거쳐 그려지므로, 거기서 한 번만 가로채 번역함 (코드 곳곳의 문자열을 고치지 않음).
- 정확히 같은 한국어 문구 -> 영어 문구 (i18n_en.EXACT)
- 숫자/이름이 끼는 문구는 '{}' 자리표시자가 있는 틀 -> 영어 틀 (i18n_en.TEMPLATES)
- 둘 다 없으면 ' · ' 같은 구분자로 잘라 조각별로 번역해 보고, 하나도 못 옮기면 한국어 그대로 (번역이 없어도 깨지지 않음)
1단계는 메인 메뉴 / 설정 / 경기 화면 HUD / 결과 창 / 일시정지와 안내 창 위주이고, 기록실·도전 과제 이름·업적 설명 같은 긴 글은 한국어로 남아 있다.
언어는 설정의 '언어 / Language'로 바꾸며 "ko"가 기본이다 (한국어일 때는 번역 함수가 곧바로 원문을 돌려줘 비용이 없다).
"""

import re

LANGS = ("ko", "en")
_lang = "ko"
_cache = {}
_exact = {}
_templates = []                 # [(컴파일된 정규식, 영어 틀, 고정 글자 수, 자리표시자 수)]
_loaded = False

_SEPARATORS = ("  ·  ", " · ", "  /  ", " / ", ", ")


def _load():
    global _loaded
    if _loaded:
        return
    _loaded = True
    exact, templates = {}, {}
    # 번역표 묶음은 반드시 '정적 import'로 읽음: importlib.import_module(이름)으로 읽으면 PyInstaller가 묶음을 exe에 넣지 않아
    # 빌드된 exe에서는 영어 표가 통째로 빠지고 조용히 한국어로 남았음 (v1.2.0 ~ v1.4.3). 새 묶음을 만들면 여기에 import를 추가할 것
    import i18n_en, i18n_en2, i18n_en3, i18n_en4, i18n_en5
    for mod in (i18n_en, i18n_en2, i18n_en3, i18n_en4, i18n_en5):
        exact.update(mod.EXACT)
        templates.update(mod.TEMPLATES)
    _exact.update(exact)
    for ko, en in templates.items():                                    # '{}' = 아무 글자, '{#}' = 숫자(쉼표 포함)만
        rx = "".join("(.+?)" if tok == "{}" else (r"(\d[\d,]*)" if tok == "{#}" else re.escape(tok)) for tok in re.split(r"(\{\}|\{#\})", ko))
        literal = len(re.sub(r"\{\}|\{#\}", "", ko))                     # 틀 안의 고정 글자 수
        _templates.append((re.compile("^" + rx + "$", re.S), en, literal, ko.count("{")))
    # 더 구체적인 틀을 먼저: 고정 글자가 많은 순 (정규식 문자열 길이로 정하면 '{#}'가 길게 변환돼 "{} {#}초"가 "최고 {}초"보다 앞서 "최고 120초"가 "최고 120s"로 반쯤만 번역됨),
    # 같으면 자리표시자가 적은 순
    _templates.sort(key=lambda t: (-t[2], t[3]))


def set_language(lang):
    global _lang
    _lang = lang if lang in LANGS else "ko"
    _cache.clear()
    if _lang != "ko":
        _load()


def language():
    return _lang


def _translate(text):
    hit = _exact.get(text)
    if hit is not None:
        return hit
    stripped = text.strip()
    if stripped != text and stripped in _exact:                      # 앞뒤 공백만 다른 경우
        lead = text[:len(text) - len(text.lstrip())]
        tail = text[len(text.rstrip()):]
        return lead + _exact[stripped] + tail
    for rx, en, _lit, _n in _templates:
        m = rx.match(text)
        if m:
            groups = [translate_piece(g) for g in m.groups()]
            try:
                return en.format(*groups)
            except (IndexError, KeyError, ValueError):                 # 틀이 잘못돼도 화면이 깨지지 않게 원문을 돌려줌
                return text
    if stripped != text and stripped:                                # 틀 앞뒤에 공백이 더 붙은 조각 ("a   ·   b"를 "  ·  "로 나눈 뒤 남는 공백 등)
        done = _translate(stripped)
        if done != stripped:
            return text[:len(text) - len(text.lstrip())] + done + text[len(text.rstrip()):]
    for sep in _SEPARATORS:                                          # 조각으로 나눠 번역 (하나라도 옮겨지면 사용)
        if sep in text:
            pieces = text.split(sep)
            done = [translate_piece(p) for p in pieces]
            if done != pieces:
                return sep.join(done)
    return text


def translate_piece(text):
    """조각 번역 (숫자/이름처럼 번역이 없는 조각은 그대로)"""
    if not text or not re.search(r"[가-힣]", text):
        return text
    hit = _exact.get(text)
    return hit if hit is not None else _translate(text)


def tr(text):
    """화면에 그리기 직전의 글자를 현재 언어로 바꿈 (한국어면 그대로)"""
    if _lang == "ko" or not text or not isinstance(text, str):
        return text
    out = _cache.get(text)
    if out is None:
        out = _translate(text) if re.search(r"[가-힣]", text) else text
        if len(_cache) > 8000:
            _cache.clear()
        _cache[text] = out
    return out

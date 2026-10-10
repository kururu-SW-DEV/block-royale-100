"""레벨 보상(보드 테두리 장식)과 조준 모드/열기 이름 변경 테스트. 실행: python tests/test_levelperks.py"""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import stats_manager as sm


def test_border_perks_follow_level():
    assert sm.border_perk_for_level(7) is None
    assert sm.border_perk_for_level(8)[1] is False
    assert sm.border_perk_for_level(20)[0] != sm.border_perk_for_level(8)[0]
    assert sm.border_perk_for_level(35)[1] is True and sm.border_perk_for_level(50)[1] is True
    got = sm.perks_unlocked_between(7, 8)
    assert got == ["내 보드에 은빛 테두리 장식이 붙습니다"], got
    assert len(sm.perks_unlocked_between(0, 50)) == len(sm.LEVEL_PERKS) + len(sm.BORDER_PERKS)


def test_heat_tiers_are_ascending_and_renamed():
    needs = [n for n, _ in config.BADGE_TIERS]
    rates = [r for _, r in config.BADGE_TIERS]
    assert needs == sorted(needs) and rates == sorted(rates) and needs[1] == 3
    import ui_renderer
    assert ui_renderer.TARGET_MODE_LABELS == {"AUTO": "자동", "KO": "추격", "ATTACKERS": "응수", "BADGES": "거물", "RANDOM": "운명"}
    for k, v in ui_renderer.TARGET_MODE_HELP.items():
        assert v.startswith(ui_renderer.TARGET_MODE_LABELS[k] + ":"), (k, v)


def test_new_mode_names_are_translated():
    import i18n
    i18n.set_language("en")
    try:
        for ko in ("추격", "응수", "거물", "운명", "열기"):
            assert i18n.tr(ko) != ko, ko
    finally:
        i18n.set_language("ko")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print("[ALL LEVEL PERK TESTS PASSED]")

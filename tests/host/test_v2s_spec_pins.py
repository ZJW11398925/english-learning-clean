"""v2-s spec 重写刀的处置钉（评审 F-7）——spec ↔ tokens.css 值等值与
关键注记护栏。

评审仓外变异 m1/m3 NOT-RED 实证：spec ② 表色值与 #23 退役注记此前
无机检护栏（「三方对照回执」只是过程声称，不承重）。本文件补三条：
① 15 色（简报 §2 14 色 + --ink-ghost 扩展位）spec ② 表 ↔ tokens.css
逐值相等；② #23 partner-card 退役注记在场（含 rd-4 增/cs-2 退役因果）；
③ F-1 真值句（v2-1 起判分行不盖章）防回退。改 ② 表任一色值、删退役
注记、或让旧判分戳假句回归，本文件即红。
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
WEBUI = _ROOT / "src" / "elc" / "webui"
SPEC = _ROOT / "docs" / "FRONTEND_SPEC.md"

#: spec ② 表与 tokens.css 双侧在场的 15 色名单。
COLOR_TOKENS = (
    "--paper",
    "--paper-high",
    "--paper-2",
    "--desk",
    "--ink",
    "--ink-soft",
    "--ink-faint",
    "--ink-ghost",
    "--rule",
    "--rule-soft",
    "--accent",
    "--accent-deep",
    "--accent-soft",
    "--seal",
    "--touch",
)


def _token_css_values() -> dict[str, str]:
    text = (WEBUI / "tokens.css").read_text(encoding="utf-8")
    found = dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})\s*;", text))
    return {name: found[name].lower() for name in COLOR_TOKENS}


def _spec_table_values() -> dict[str, str]:
    text = SPEC.read_text(encoding="utf-8")
    values: dict[str, str] = {}
    for name in COLOR_TOKENS:
        m = re.search(
            rf"^\|\s*`?{re.escape(name)}`?\s*\|\s*`?(#[0-9a-fA-F]{{6}})`?",
            text,
            re.M,
        )
        if m:
            values[name] = m.group(1).lower()
    return values


def test_spec_color_table_matches_tokens_css() -> None:
    """spec ② 表的 15 色与 tokens.css 逐值相等（评审 m1 形态转 RED）。"""
    css = _token_css_values()
    spec = _spec_table_values()
    missing = [n for n in COLOR_TOKENS if n not in css or n not in spec]
    assert not missing, f"token 缺席（双侧须在场）: {missing}"
    mismatch = {
        n: (spec[n], css[n]) for n in COLOR_TOKENS if spec[n] != css[n]
    }
    assert not mismatch, f"spec ② 表与 tokens.css 色值不一致: {mismatch}"


def test_partner_card_23_retirement_note_present() -> None:
    """#23 partner-card 退役注记在场（评审 m3 形态转 RED）。

    退役事实两处承载（③ 表行的注册表句 + 独立退役注记块），两处都
    必须在场——删任一处即红（单处存活会让「退役」只在一张脸出现，
    ③ 表的查库入口会再次说谎）。
    """
    text = SPEC.read_text(encoding="utf-8")
    assert "#23" in text
    assert "partner-card" in text
    # 因果句防孤立词凑数：rd-4 曾增 ↔ cs-2 退役必须同场
    assert re.search(r"rd-4[^。]*#23|#23[^。]*rd-4", text), (
        "#23 退役注记缺 rd-4 因果"
    )
    assert re.search(r"cs-2[^。]*退役|退役[^。]*cs-2", text), (
        "#23 退役注记缺 cs-2 退役事实"
    )
    # 独立退役注记块标题必须在场（③ 表行不替代它）
    assert "**#23 退役注记" in text, "独立 #23 退役注记块缺席"
    # ③ 表行的注册表句必须在场（退役注记块不替代它）
    assert re.search(r"rd-4 曾增 #23", text), "③ 表行的 #23 注册表句缺席"


def test_verdict_rows_no_stamp_v2_truth() -> None:
    """F-1 真值句防回退：v2-1 起判分行不盖章，旧假句不得回归。"""
    text = SPEC.read_text(encoding="utf-8")
    assert "判分行不盖章" in text, "v2-1 判分行不盖章真值句缺席"
    assert "成功族（SUCCESS / ALTERNATIVE_SUCCESS）的明细行落" not in text, (
        "rd-4 旧假句（判分盖章）回归"
    )

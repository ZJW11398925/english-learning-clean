"""v3-2S 滚动条纪律钉（spec ⑨-9.6a）——三件：全局纸墨细条在场、滚动
井 gutter 在场、滚动容器清单防复发。

用户实测（2026-10-02）：扇叠/全览/编辑/写信面的桌面滚动条（15–17px）
直接压卡。纪律 = 全局 6px 细条（占位从源头缩）+ 滚动井 scrollbar-gutter:
stable（内容零跳动）+ 本钉的清单（新增滚动容器必须同刀进清单并带
gutter——清单外的新滚动容器即红，强制登记面）。
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_CSS = (_ROOT / "src" / "elc" / "webui").glob("*.css")

#: 纪律清单：仓内全部容器内滚动面（新增滚动容器 = 同刀进此清单 + gutter）。
SCROLL_CONTAINERS = (
    ".envsel-stack",   # 沓扇叠态
    ".envpage",        # 全览窗口页卡
    ".envsel-editor",  # 编辑面（唯一滚动井）
    ".envsel-compose", # 写信工作区面
)


def _css(name: str) -> str:
    return (_ROOT / "src" / "elc" / "webui" / name).read_text(encoding="utf-8")


def test_global_thin_ink_scrollbar_is_defined_once() -> None:
    """全局纸墨细条：thin + 6px + 轨道透明 + 拇指发丝线（地基块唯一定义）。"""
    css = _css("components.css")
    # 非注释体的规则形恰一处（地基注释里也提到该词——以规则形计数）
    rule = css[css.index("* { scrollbar-width: thin;"):]
    assert rule[:64].startswith("* { scrollbar-width: thin;")
    assert css.count("* { scrollbar-width: thin;") == 1
    assert css.count("::-webkit-scrollbar { width: 6px; height: 6px; }") == 1
    assert css.count("::-webkit-scrollbar-thumb { background: var(--rule); }") == 1
    assert css.count("::-webkit-scrollbar-thumb:hover") == 1
    assert css.count("scrollbar-color: var(--rule) transparent") == 1
    # 细条只许全局定义一处——组件面不得自造第二套滚动条语汇
    assert _css("screens.css").count("scrollbar-width") == 0
    assert _css("screens.css").count("::-webkit-scrollbar") == 0


def test_every_scroll_container_is_in_the_discipline_list() -> None:
    """清单防复发：解析两份 CSS 抓全部容器内滚动面的选择器，必须 ⊆ 纪律
    清言且该块必须带 scrollbar-gutter: stable——新增滚动容器不进清单
    即红（强制同刀登记 + 加槽）。"""
    container_pat = re.compile(
        r"([^{}]+)\{[^{}]*?overflow(?:-y|-x)?\s*:\s*(auto|scroll)[^{}]*?\}",
        re.S,
    )
    # 块内注释可能含花括号字符破坏块边界——先剥注释再解析（注释不
    # 参与规则语义）；元素级豁免：.pen（textarea 自身滚动，全局细条
    # 覆盖）与 pre（横向滚，gutter 只作用于块轴）。
    element_exempt = {"*", ".pen", "pre"}
    offenders: list[str] = []
    for name in ("components.css", "screens.css"):
        css = re.sub(r"/\*.*?\*/", "", _css(name), flags=re.S)
        for m in container_pat.finditer(css):
            selectors = " ".join(m.group(1).split())
            body = m.group(0)
            if "::" in selectors or selectors.strip() in element_exempt:
                continue
            listed = any(sel in selectors for sel in SCROLL_CONTAINERS)
            if not listed:
                offenders.append(f"{name}: {selectors}")
                continue
            if "scrollbar-gutter: stable" not in body:
                offenders.append(f"{name}: {selectors}（缺 gutter）")
    assert not offenders, (
        "滚动容器越出纪律清单或缺 gutter（spec ⑨-9.6a：新增滚动容器"
        "必须同刀进 SCROLL_CONTAINERS 清单并带 scrollbar-gutter: "
        f"stable）: {offenders}"
    )


def test_spec_scroll_discipline_clause_present() -> None:
    """spec ⑨-9.6a 纪律条在场（三件全钉，防被误删）。"""
    spec = (_ROOT / "docs" / "FRONTEND_SPEC.md").read_text(encoding="utf-8")
    assert "### 9.6a 滚动条纪律" in spec
    assert "scrollbar-gutter: stable" in spec
    assert "test_v32s_scroll_discipline" in spec

"""Ensure detailed website scores equal the one authoritative V1 engine formula."""
import json
import math
import re
import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from radar.catalog import build_catalog
from radar.dashboard import render_dashboard
from radar.engine import SCORE_RULES, indicators, screen
from radar.main import export
from radar.storage import connect, store


def synthetic_prices(trend=0.08, days=95):
    dates = pd.bdate_range("2026-05-01", periods=days)
    rows = []
    for i, day in enumerate(dates):
        close = 70 + trend*i + 2.1 * math.sin(i/4)
        rows.append({
            "date": day.strftime("%Y-%m-%d"), "market": "TPEX",
            "code": "4939", "name": "亞電",
            "open": close-0.5, "high": close+1.3,
            "low": close-1.5, "close": close,
            "volume": 200000 + int(19000 * (1+math.sin(i/3))),
            "turnover": close * 200000,
            "source_url": "synthetic-test-fixture",
        })
    return pd.DataFrame(rows)


@pytest.mark.parametrize("trend", [0.08, -0.12])
def test_ten_scoring_rules_match_independent_original_formula(trend):
    df = indicators(synthetic_prices(trend=trend))
    assert len(SCORE_RULES) == 10
    assert sum(rule["weight"] for rule in SCORE_RULES) == 100
    x = df.iloc[-1]
    values = [x["score_"+rule["key"]] for rule in SCORE_RULES]
    assert all(v in (0, rule["weight"]) for v,rule in zip(values,SCORE_RULES))
    assert int(sum(values)) == int(x.tech_score)
    expected = (
        int(x.close>x.ma20)*15
        + int(x.ma20>x.ma60)*10
        + int(x.slope20>0)*10
        + int(-2 <= x.bias20 <= 8)*15
        + int(1.2 <= x.volume_ratio <= 3.5)*10
        + int(48 <= x.rsi14 <= 70)*10
        + int(x.macd_hist>0)*10
        + int(x.adx14>17 and x.plus_di>x.minus_di)*10
        + int(x.higher_low)*5
        + int(x.range_contraction)*5
    )
    assert int(x.tech_score) == expected
    assert all(pd.isna(df.iloc[i]["score_"+SCORE_RULES[0]["key"]]) for i in range(79))


def test_all_stocks_catalog_exports_detailed_points():
    prices=synthetic_prices()
    ranked=screen(prices)
    cat=build_catalog(prices,ranked,prices.date.max())
    assert len(cat["score_rules"]) == 10
    assert len(cat["stocks"]) == 1
    rec=cat["stocks"][0]
    assert round(sum(rec["score_"+r["key"]] for r in cat["score_rules"])) == round(rec["tech_score"])
    assert rec["code"] == "4939"


def test_nightly_export_includes_rules_in_both_json_reports(tmp_path, monkeypatch):
    import radar.main as main
    monkeypatch.setattr(main, "ROOT", tmp_path)
    (tmp_path/"data").mkdir()
    conn=connect(tmp_path/"data"/"radar.sqlite")
    prices=synthetic_prices()
    for row in prices.itertuples(index=False):
        fields = (row.date,row.market,row.code,row.name,row.open,row.high,row.low,
                  row.close,row.volume,row.turnover,row.source_url)
        store(conn,row.date,row.market,[fields],"ok")
    export(conn,tmp_path/"output",tmp_path/"docs",prices.date.max())
    conn.close()
    for name in ("report.json","radar_all.json"):
        data=json.loads((tmp_path/"docs"/name).read_text("utf-8"))
        assert len(data["score_rules"])==10
        stock=data["top"][0] if name=="report.json" else data["stocks"][0]
        assert sum(stock["score_"+r["key"]] for r in data["score_rules"]) == stock["tech_score"]


def test_dashboard_renders_click_target_and_score_breakdown_js():
    html=render_dashboard()
    assert "技術分數細項分析" in html
    assert "score-trigger" in html
    assert "scoreRules" in html
    assert "renderBreakdown(x)" in html
    assert "score_'+rule.key" in html
    # GitHub hosted Linux runners include Node.js; check JS syntax when available.
    if shutil.which("node"):
        parts=re.findall(r"<script>([\s\S]*?)</script>",html)
        assert len(parts)==1
        proc=subprocess.run(["node","--check"],input=parts[0],text=True,capture_output=True)
        assert proc.returncode==0,proc.stderr

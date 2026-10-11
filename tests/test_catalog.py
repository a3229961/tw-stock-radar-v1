import json
import pandas as pd

from radar.catalog import build_catalog
from radar.main import export
from radar.storage import connect, store


def make_row(day, code, name, close=80):
    return (day, "TWSE", code, name,
            close - 1, close + 2, close - 2, close, 200000, close * 200000, "test-source")


def test_catalog_sees_stock_outside_top50_and_records_short_history():
    day = "2026-10-08"
    ranking = pd.DataFrame([
        {"date": day, "market": "TWSE", "code": f"{i:04d}", "name": f"測試{i}",
         "tech_score": 100 - i / 100, "close": 80.0}
        for i in range(1000, 1050)
    ] + [{"date": day, "market": "TWSE", "code": "4939", "name": "亞電",
          "tech_score": 10, "close": 78.3}])
    prices = ranking[["date", "market", "code", "name", "close"]].copy()
    prices = pd.concat([prices, pd.DataFrame([{
        "date": day, "market": "TWSE", "code": "9999",
        "name": "不足K線測試", "close": 11
    }])], ignore_index=True)
    catalog = build_catalog(prices, ranking, day)
    assert len(catalog["stocks"]) == 51
    assert any(item["code"] == "4939" for item in catalog["stocks"])
    assert catalog["unranked"] == [{
        "market": "TWSE", "code": "9999", "name": "不足K線測試",
        "last_data_date": day, "close": 11.0, "bars": 1, "status": "INSUFFICIENT_HISTORY"
    }]


def test_full_export_generates_all_stock_json(tmp_path, monkeypatch):
    import radar.main as main
    monkeypatch.setattr(main, "ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    conn = connect(tmp_path / "data" / "radar.sqlite")
    days = pd.bdate_range("2026-05-01", periods=85)
    for i, day in enumerate(days):
        d = day.strftime("%Y-%m-%d")
        store(conn, d, "TWSE", [make_row(d, "4939", "亞電", 70 + i / 10)], "ok")
    store(conn, days[-1].strftime("%Y-%m-%d"), "TWSE",
          [make_row(days[-1].strftime("%Y-%m-%d"), "9999", "短歷史", 11)], "ok")
    export(conn, tmp_path / "output", tmp_path / "docs", days[-1].date())
    conn.close()
    cat = json.loads((tmp_path / "docs" / "radar_all.json").read_text("utf-8"))
    assert cat["ranked_count"] == 1
    assert cat["stocks"][0]["code"] == "4939"
    assert cat["unranked"][0]["code"] == "9999"
    assert cat["unranked"][0]["status"] == "INSUFFICIENT_HISTORY"
    report = json.loads((tmp_path / "docs" / "report.json").read_text("utf-8"))
    assert len(report["top"]) == 1
    page = (tmp_path / "docs" / "index.html").read_text("utf-8")
    assert "radar_all.json" in page
    assert "完整技術排名" in page

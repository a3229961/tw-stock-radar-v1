import json
import sqlite3

from radar.main import export
from radar.storage import connect


def test_export_generates_v2_dashboard_with_no_branch_source(tmp_path, monkeypatch):
    import radar.main as main
    monkeypatch.setattr(main, "ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    con = connect(tmp_path / "data" / "radar.sqlite")
    export(con, tmp_path / "output", tmp_path / "docs", "2026-10-08")
    con.close()
    report = json.loads((tmp_path / "docs" / "report.json").read_text(encoding="utf-8"))
    assert report["summary"]["branch_coverage"] == "NOT_AVAILABLE"
    assert report["summary"]["branch_data_status"]["source_status"] == "MISSING_SOURCE"
    assert len(report["branch_profiles"]) == 18
    assert report["top"] == []
    html = (tmp_path / "docs" / "index.html").read_text(encoding="utf-8")
    assert "台股全市場起漲雷達" in html
    assert "report.json" in html
    assert (tmp_path / "output" / "radar_latest.xlsx").exists()

import pandas as pd
import pytest

from radar.branch_signals import (
    COLS, TRACKED_BRANCHES, enrich_ranking, load_branch_trades,
    normalize_branch, profiles, reference_labels, score_branches,
)


def test_reference_groups_are_multilabel_and_not_numeric_evidence():
    assert "隔日沖" in reference_labels("富邦－建國")
    assert "短線" in reference_labels("富邦-建國")
    assert normalize_branch("凱基－三多") == "凱基-三多"
    assert len(TRACKED_BRANCHES) == 18
    assert len(profiles()) == 18


def test_missing_data_never_creates_chip_score(tmp_path):
    missing = tmp_path / "no_such_file.csv"
    trades, status = load_branch_trades(missing)
    assert status == "MISSING_SOURCE"
    result = score_branches(trades, "TWSE", "4939", "2026-10-08")
    assert result["branch_score"] is None
    ranking = pd.DataFrame([{
        "market": "TWSE", "code": "4939", "name": "亞電",
        "date": "2026-10-08", "close": 80, "ma20": 75,
        "volume_ratio": 1.5, "tech_score": 80,
    }])
    output = enrich_ranking(ranking, trades, "2026-10-08")
    assert output.iloc[0]["branch_score"] is None
    assert output.iloc[0]["tech_score"] == 80


def test_incomplete_days_do_not_get_scores(tmp_path):
    path = tmp_path / "trades.csv"
    pd.DataFrame([{
        "date": "2026-10-08", "market": "TWSE", "code": "4939",
        "branch": "富邦-建國", "buy": 100, "sell": 10,
        "source": "test fixture", "coverage_verified": False,
    }], columns=COLS).to_csv(path, index=False)
    data, status = load_branch_trades(path)
    assert status == "LOADED"
    result = score_branches(data, "TWSE", "4939", "2026-10-08")
    assert result["branch_score"] is None


def test_duplicate_rows_rejected(tmp_path):
    path = tmp_path / "trades.csv"
    row = {
        "date": "2026-10-08", "market": "TWSE", "code": "4939",
        "branch": "元大-土城永寧", "buy": 100, "sell": 30,
        "source": "fixture", "coverage_verified": True,
    }
    pd.DataFrame([row, row], columns=COLS).to_csv(path, index=False)
    with pytest.raises(ValueError, match="重複"):
        load_branch_trades(path)


def test_ten_verified_dates_generate_provisional_score():
    rows = []
    for day in pd.bdate_range("2026-09-25", periods=10):
        rows.append({
            "date": day.strftime("%Y-%m-%d"), "market": "TWSE", "code": "4939",
            "branch": "國票-和平", "buy": 80, "sell": 20,
            "source": "synthetic-test", "coverage_verified": True,
        })
    data = pd.DataFrame(rows, columns=COLS)
    result = score_branches(data, "TWSE", "4939", rows[-1]["date"],
                            close=80, ma20=75, volume_ratio=1.5)
    assert result["branch_status"] == "PROVISIONAL_VERIFIED"
    assert 0 <= result["branch_score"] <= 100
    assert result["branch_wave_branches"] == 1
    assert result["branch_overnight_risk"] == 0.0

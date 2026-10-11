import datetime as dt

from radar.main import days_to_fetch
from radar.data_quality import make_quality_report
from radar.market_holidays import (
    confirmed_closure, is_equity_session_candidate, label_past_empty_holidays,
    CALENDAR_VERSION, EQUITY_CLOSED_2026,
)
from radar.storage import connect, store, read_prices


def test_exchange_confirmed_2026_closures_and_unknown_years():
    for day in ["2026-09-25","2026-09-28","2026-10-09","2026-10-26"]:
        assert confirmed_closure(day)
        assert not is_equity_session_candidate(day)
    for day in ["2026-09-24","2026-09-29","2026-10-08","2026-10-12"]:
        assert confirmed_closure(day) is None
        assert is_equity_session_candidate(day)
    # No speculative closure classification for 2027.
    assert confirmed_closure("2027-10-09") is None
    assert not is_equity_session_candidate("2027-10-09")  # Saturday, independently from official closure list
    assert "2026-02-12" in EQUITY_CLOSED_2026
    assert CALENDAR_VERSION.startswith("2026-official-")


def test_empty_market_snapshots_migrate_without_changing_valid_data(tmp_path):
    conn=connect(tmp_path/"calendar.sqlite")
    for day in ["2026-09-25","2026-09-28","2026-10-09"]:
        for market in ("TWSE","TPEX"):
            store(conn,day,market,[],"empty_unverified","unsure if holiday")
    store(conn,"2026-10-08","TWSE",[
        ("2026-10-08","TWSE","2330","台積電",1100,1120,1090,1110,1000,1_110_000,"https://www.twse.com.tw")
    ],"ok")
    store(conn,"2026-10-08","TPEX",[
        ("2026-10-08","TPEX","4939","亞電",75,80,74,78,1000,78_000,"https://www.tpex.org.tw")
    ],"ok")
    assert label_past_empty_holidays(conn)==6
    assert label_past_empty_holidays(conn)==0
    assert conn.execute("SELECT COUNT(*) FROM fetch_log WHERE status='holiday'").fetchone()[0]==6
    assert conn.execute("SELECT COUNT(*) FROM fetch_log WHERE status='ok'").fetchone()[0]==2
    assert conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]==2
    fetch=days_to_fetch(conn,dt.date(2026,10,12),30,30)
    assert not any(d.isoformat() in ["2026-09-25","2026-09-28","2026-10-09"] for d in fetch)
    assert dt.date(2026,10,12) in fetch
    quality=make_quality_report(conn,read_prices(conn),dt.date(2026,10,11))
    assert quality["last_45d_problem_snapshots"]==0
    assert [x["date"] for x in quality["confirmed_official_closures_last_45d"]]==[
        "2026-09-25","2026-09-28","2026-10-09"
    ]
    assert not any(d in quality["recent_weekdays_without_verified_market_pairs"]
                   for d in ("2026-09-25","2026-09-28","2026-10-09"))
    assert quality["official_calendar"]["covered_years"]==[2026]
    conn.close()

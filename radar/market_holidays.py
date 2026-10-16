"""Official 2026 (ROC 115) equity market non-trading weekdays.

Static, source-attributed snapshot for 2026 only. Unknown years never get
invented holidays; must be separately verified from exchange calendars.
Sources:
TWSE https://accessibility.twse.com.tw/zh/trading/holiday.html
TPEx https://www.tpex.org.tw/storage/eb_data/11411/114007545811-1.pdf
These are equity trading sessions, not bond/depository settlement schedules.
"""
import datetime as dt

CALENDAR_VERSION = "2026-official-equity-calendar-v1"
SOURCES = {
    "TWSE": "https://accessibility.twse.com.tw/zh/trading/holiday.html",
    "TPEX": "https://www.tpex.org.tw/storage/eb_data/11411/114007545811-1.pdf",
}

EQUITY_CLOSED_2026 = {
    "2026-01-01": "元旦",
    "2026-02-12": "春節前僅辦理結算交割，股票市場無交易",
    "2026-02-13": "春節前僅辦理結算交割，股票市場無交易",
    "2026-02-16": "農曆春節",
    "2026-02-17": "農曆春節",
    "2026-02-18": "農曆春節",
    "2026-02-19": "農曆春節",
    "2026-02-20": "春節補假",
    "2026-02-27": "和平紀念日補假",
    "2026-04-03": "兒童節補假",
    "2026-04-06": "清明節補假",
    "2026-05-01": "勞動節",
    "2026-06-19": "端午節",
    "2026-09-25": "中秋節",
    "2026-09-28": "教師節",
    "2026-10-09": "國慶日補假",
    "2026-10-26": "光復節補假",
    "2026-12-25": "行憲紀念日",
}


def confirmed_closure(day):
    """Name of official 2026 weekday equity closure, or None for unknown."""
    if isinstance(day, dt.datetime):
        day=day.date()
    if isinstance(day, dt.date):
        day=day.isoformat()
    return EQUITY_CLOSED_2026.get(str(day))


def is_equity_session_candidate(day):
    if isinstance(day,str):
        day=dt.date.fromisoformat(day)
    return day.weekday()<5 and confirmed_closure(day) is None


def label_past_empty_holidays(conn):
    """Migrate only recorded empty market snapshots to official holiday status.

    Never rewrite a row that was successfully downloaded or that has stock
    prices; historically recorded attempts remain available for audit.
    """
    changed=0
    with conn:
        for date,reason in EQUITY_CLOSED_2026.items():
            cur=conn.execute(
                """UPDATE fetch_log SET status='holiday', detail=?
                   WHERE date=? AND market IN ('TWSE','TPEX')
                     AND status='empty_unverified' AND rows=0""",
                (CALENDAR_VERSION+": "+reason,date)
            )
            changed+=cur.rowcount
    return changed

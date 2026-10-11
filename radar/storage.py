import sqlite3
import pandas as pd

DDL='''
CREATE TABLE IF NOT EXISTS prices (date TEXT NOT NULL,market TEXT NOT NULL,code TEXT NOT NULL,name TEXT,open REAL,high REAL,low REAL,close REAL,volume INTEGER,turnover REAL,source_url TEXT,PRIMARY KEY(date,market,code));
CREATE TABLE IF NOT EXISTS fetch_log (date TEXT NOT NULL,market TEXT NOT NULL,status TEXT NOT NULL,rows INTEGER NOT NULL,detail TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(date,market));
CREATE TABLE IF NOT EXISTS radar_scores (date TEXT NOT NULL,market TEXT NOT NULL,code TEXT NOT NULL,tech_score REAL,PRIMARY KEY(date,market,code));
CREATE TABLE IF NOT EXISTS fetch_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, market TEXT NOT NULL, status TEXT NOT NULL, rows INTEGER NOT NULL, detail TEXT, checked_at TEXT DEFAULT CURRENT_TIMESTAMP);
'''

def connect(path):
    c=sqlite3.connect(path,timeout=30);c.executescript(DDL);return c

def store(c,day,market,rows,status,detail=''):
    with c:
        if rows:c.executemany('INSERT OR REPLACE INTO prices VALUES (?,?,?,?,?,?,?,?,?,?,?)',rows)
        c.execute('INSERT OR REPLACE INTO fetch_log(date,market,status,rows,detail) VALUES(?,?,?,?,?)',(day,market,status,len(rows),detail[:500]))

def read_prices(c):
    return pd.read_sql_query('SELECT * FROM prices ORDER BY date,market,code',c)

def record_attempt(c, day, market, status, rows=0, detail='', preserve_good=True):
    """Record every fetch. An unsuccessful refresh cannot revoke a good snapshot."""
    old=c.execute('SELECT status FROM fetch_log WHERE date=? AND market=?',(day,market)).fetchone()
    with c:
        c.execute(
            'INSERT INTO fetch_attempts(date,market,status,rows,detail) VALUES(?,?,?,?,?)',
            (day,market,status,int(rows),str(detail)[:500])
        )
        if not (preserve_good and old and old[0]=='ok' and status!='ok'):
            c.execute('INSERT OR REPLACE INTO fetch_log(date,market,status,rows,detail) VALUES(?,?,?,?,?)',
                (day,market,status,int(rows),str(detail)[:500]))


def replace_market_snapshot(c, day, market, rows, detail=''):
    """Atomically replace one verified market/day snapshot.

    Re-fetch can remove stale codes and revise official values. Rejection must
    happen *before* this method; an invalid refresh must not delete history.
    """
    if not rows:
        raise ValueError('Cannot replace market snapshot with empty rows')
    with c:
        old=c.execute('SELECT code,close,volume FROM prices WHERE date=? AND market=?',(day,market)).fetchall()
        old_index={str(code):(float(close),int(vol)) for code,close,vol in old}
        new_index={str(r[2]):(float(r[7]),int(r[8])) for r in rows}
        changed=sum(1 for code,pair in new_index.items() if code in old_index and pair != old_index[code])
        removed=len(set(old_index)-set(new_index))
        added=len(set(new_index)-set(old_index))
        c.execute('DELETE FROM prices WHERE date=? AND market=?',(day,market))
        c.executemany('INSERT INTO prices VALUES (?,?,?,?,?,?,?,?,?,?,?)',rows)
        detail_text=f'{detail}; revised={changed}; added={added}; removed={removed}'
        c.execute(
            'INSERT OR REPLACE INTO fetch_log(date,market,status,rows,detail) VALUES(?,?,?,?,?)',
            (day,market,'ok',len(rows),detail_text[:500])
        )
        c.execute(
            'INSERT INTO fetch_attempts(date,market,status,rows,detail) VALUES(?,?,?,?,?)',
            (day,market,'ok',len(rows),detail_text[:500])
        )
    return {'changed':changed,'added':added,'removed':removed,'rows':len(rows)}

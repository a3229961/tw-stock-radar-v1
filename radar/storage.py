import sqlite3
import pandas as pd

DDL='''
CREATE TABLE IF NOT EXISTS prices (date TEXT NOT NULL,market TEXT NOT NULL,code TEXT NOT NULL,name TEXT,open REAL,high REAL,low REAL,close REAL,volume INTEGER,turnover REAL,source_url TEXT,PRIMARY KEY(date,market,code));
CREATE TABLE IF NOT EXISTS fetch_log (date TEXT NOT NULL,market TEXT NOT NULL,status TEXT NOT NULL,rows INTEGER NOT NULL,detail TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(date,market));
CREATE TABLE IF NOT EXISTS radar_scores (date TEXT NOT NULL,market TEXT NOT NULL,code TEXT NOT NULL,tech_score REAL,PRIMARY KEY(date,market,code));
'''

def connect(path):
    c=sqlite3.connect(path,timeout=30);c.executescript(DDL);return c

def store(c,day,market,rows,status,detail=''):
    with c:
        if rows:c.executemany('INSERT OR REPLACE INTO prices VALUES (?,?,?,?,?,?,?,?,?,?,?)',rows)
        c.execute('INSERT OR REPLACE INTO fetch_log(date,market,status,rows,detail) VALUES(?,?,?,?,?)',(day,market,status,len(rows),detail[:500]))

def read_prices(c):
    return pd.read_sql_query('SELECT * FROM prices ORDER BY date,market,code',c)

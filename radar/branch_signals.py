"""分點交易行為與籌碼品質評分。資料未經完整驗證時不產生分數。

CSV schema: date,market,code,branch,buy,sell,source,coverage_verified.
coverage_verified=true 表示該日期/市場的資料來源已涵蓋全部目標分點，
非單一股票/分點的零星紀錄。資料不完整時必須填 false。
"""
from __future__ import annotations

import datetime as dt
import math
from pathlib import Path

import pandas as pd


# 使用者提供的網路分類圖，僅作「待驗證觀察標籤」，不是交易事實。
REFERENCE_GROUPS = {
    "當沖": """新加坡瑞銀、摩根大通、美林、元大、元富、台新、亞東、新光、群益、元大-中壢、永全-八德、兆豐-南門、凱基-大里、凱基-台北、凱基-屏東、凱基-員林、凱基-站前、富邦-嘉義、華南-中正、聯邦-富強""",
    "隔日沖": """美商高盛、港商野村、新加坡瑞銀、摩根大通、元大、元富、元大-土城永寧、元大-太平、元大-成功、元大-竹科、元大-虎尾、元大-鹿港、元大-新竹、元大-彰化、日盛-忠孝、永豐金-虎尾、永豐金-桃園、兆豐-中港、兆豐-北高雄、兆豐-虎尾、兆豐-南京、兆豐-復興、凱基-士林、凱基-台北、凱基-市政、凱基-板橋、凱基-屏東、富邦-台中、富邦-台南、富邦-虎尾、富邦-建國、統一-仁愛、統一-松江、統一-南京、華南-竹北、華南-長虹、華南-嘉義、群益-內湖、群益-海山、群益-館前""",
    "短線": """新加坡瑞銀瑞銀、新加坡大通、玉山、康和、台企銀-嘉義、台新-台中、台新-建北、台新-高雄、玉山-台南、兆豐-大安、兆豐-忠孝、合庫-台中、國泰-博愛、國票-長城、凱基-市政、凱基-桃園、富邦-建國、富邦-員林、統一-敦南""",
    "波段": """台灣匯立、台灣摩根、港商野村、瑞士信貸、摩根大通、元富、台新、宏遠、國泰綜合、富邦、華南永昌、新光、群益、福邦、中國信託、元大-敦化、日盛-龍潭、台企銀-桃園、台新-高雄、兆豐-忠孝、兆豐-復興、國票-和平、國票-長城、凱基-大安、凱基-中港、富邦-南屯、統一-敦南""",
}
TRACKED_BRANCHES = """凱基-虎尾、富邦-虎尾、凱基-台北、元大-土城永寧、康和-永和、康和-板橋、凱基-松山、凱基-信義、永豐金-市政、富邦-建國、永豐金-板新、玉山-嘉義、統一-嘉義、兆豐-中壢、國票-和平、凱基-城中、元大-館前、凱基-三多""".split("、")
COLS = ["date", "market", "code", "branch", "buy", "sell", "source", "coverage_verified"]


def normalize_branch(name):
    return str(name).strip().replace("－", "-").replace("–", "-").replace("—", "-").replace(" ", "").replace("臺", "台")


def reference_labels(name):
    key = normalize_branch(name)
    return [label for label, names in REFERENCE_GROUPS.items()
            if key in {normalize_branch(n) for n in names.split("、")}]


def profiles():
    return [{"branch": name, "reference_labels": reference_labels(name),
             "source": "使用者提供之網路分點分類圖；未獨立驗證"}
            for name in TRACKED_BRANCHES]


def load_branch_trades(path):
    path = Path(path)
    if not path.is_file():
        return pd.DataFrame(columns=COLS), "MISSING_SOURCE"
    data = pd.read_csv(path, dtype={"date": str, "market": str, "code": str, "branch": str,
                                    "source": str, "coverage_verified": str})
    missing = sorted(set(COLS) - set(data.columns))
    if missing:
        raise ValueError("branch CSV 缺少欄位: " + ", ".join(missing))
    data = data[COLS].copy()
    data["date"] = pd.to_datetime(data["date"], format="%Y-%m-%d", errors="raise").dt.strftime("%Y-%m-%d")
    data["market"] = data["market"].str.strip().str.upper()
    if not data["market"].isin(["TWSE", "TPEX"]).all():
        raise ValueError("market 必須是 TWSE 或 TPEX")
    data["code"] = data["code"].str.strip()
    if not data["code"].str.fullmatch(r"\d{4}").all():
        raise ValueError("股票代號必須為4位數（V1限制）")
    data["branch"] = data["branch"].map(normalize_branch)
    if data["branch"].eq("").any() or data["source"].isna().any() or data["source"].eq("").any():
        raise ValueError("分點與來源不可空白")
    for key in ["buy", "sell"]:
        data[key] = pd.to_numeric(data[key], errors="raise")
        if data[key].isna().any() or (~data[key].map(math.isfinite)).any() or (data[key] < 0).any():
            raise ValueError(key + " 必須是有限且非負數字")
    value = data["coverage_verified"].str.strip().str.lower()
    if not value.isin(["true", "false"]).all():
        raise ValueError("coverage_verified 必須是 true/false")
    data["coverage_verified"] = value.eq("true")
    if data.duplicated(["date", "market", "code", "branch"]).any():
        raise ValueError("同一天/市場/股票/分點有重複紀錄")
    return data, "LOADED"


def _clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(value)))


def score_branches(frame, market, code, latest_date, close=None, ma20=None, volume_ratio=None):
    """僅在有至少10個完整市場快照且最新日完整時評分。

    沒有列出的分點視作零交易，前提是來源已保證該市場當日全分點完整快照。
    此處推論的是「交易通路行為」，不是單一機構或實際持有人。
    """
    unavailable = {"branch_score": None, "branch_status": "INSUFFICIENT_VERIFIED_DATA",
                   "branch_net5": None, "branch_net20": None,
                   "branch_wave_branches": None, "branch_overnight_risk": None,
                   "branch_source": None}
    if frame.empty:
        return unavailable
    market_frame = frame.loc[(frame.market == market) & (frame.coverage_verified)].copy()
    days = sorted(market_frame.date.unique())
    if latest_date not in days or len(days) < 10:
        return unavailable
    days = [d for d in days if d <= latest_date][-20:]
    if len(days) < 10:
        return unavailable
    part = market_frame[(market_frame.code == str(code)) & (market_frame.date.isin(days))].copy()
    if part.empty:
        return {**unavailable, "branch_status": "VERIFIED_NO_TRADES"}
    part["net"] = part.buy - part.sell
    tail5 = days[-5:]
    net5 = float(part.loc[part.date.isin(tail5), "net"].sum())
    net20 = float(part.net.sum())
    buy5 = float(part.loc[part.date.isin(tail5), "buy"].sum())
    sell5 = float(part.loc[part.date.isin(tail5), "sell"].sum())
    by_branch = part.groupby("branch").agg(net=("net", "sum"), buy=("buy", "sum"), sell=("sell", "sum"))
    wave = [b for b in by_branch.index if "波段" in reference_labels(b) and by_branch.loc[b, "net"] > 0]
    wave_net = float(by_branch.loc[wave, "net"].sum()) if wave else 0.
    total_positive = float(by_branch.net.clip(lower=0).sum())
    wave_score = 30 * _clamp(wave_net / max(total_positive, 1))
    trend_score = 25 * _clamp((net5 / max(buy5 + sell5, 1) + 1) / 2)
    positive = by_branch[by_branch.net > 0]
    co_score = 20 * _clamp(len(positive) / 4)
    hot = [b for b in by_branch.index if "隔日沖" in reference_labels(b)]
    lastday = part[part.date == latest_date]
    hot_buy = float(lastday.loc[lastday.branch.isin(hot), "buy"].sum())
    all_buy = float(lastday.buy.sum())
    risk = _clamp(hot_buy / max(all_buy, 1))
    risk_score = 15 * (1 - risk)
    aligned = bool(close is not None and ma20 is not None and pd.notna(close)
                   and pd.notna(ma20) and close > ma20)
    active = bool(volume_ratio is not None and pd.notna(volume_ratio) and volume_ratio >= 1.2)
    alignment_score = (5 if aligned else 0) + (5 if active else 0)
    points = wave_score + trend_score + co_score + risk_score + alignment_score
    return {"branch_score": round(points, 1), "branch_status": "PROVISIONAL_VERIFIED",
            "branch_net5": round(net5, 1), "branch_net20": round(net20, 1),
            "branch_wave_branches": len(wave), "branch_overnight_risk": round(risk * 100, 1),
            "branch_source": "、".join(sorted(part.source.unique())[:3])}


def enrich_ranking(ranking, frame, latest_date):
    if ranking.empty:
        return ranking
    df = ranking.copy()
    records = [score_branches(frame, row.market, str(row.code), latest_date,
                              close=row.close, ma20=row.ma20, volume_ratio=row.volume_ratio)
               for row in df.itertuples()]
    extra = pd.DataFrame(records, index=df.index)
    for col in extra.columns:
        df[col] = extra[col]
    # 沒有來源時不改動原有技術排名，也不杜撰籌碼分數。
    return df


def branch_summary(frame, status):
    return {"source_status": status,
            "verified_dates": int(frame.loc[frame.coverage_verified, ["date", "market"]]
                                  .drop_duplicates().shape[0]) if not frame.empty else 0,
            "tracked_branches": len(TRACKED_BRANCHES),
            "reference_only": True,
            "notes": "券商分點不等於單一主力；風格標籤出自網路圖片，需由歷史交易驗證。"}

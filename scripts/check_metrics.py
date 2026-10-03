"""
חישוב המדדים של הדשבורד בפייתון, מתוך קבצי ה-CSV.
משמש לבדיקה: בהמשך נשווה אליו את המספרים שהדף מחשב בדפדפן.

הרצה:  python scripts/check_metrics.py
פלט:   הדפסה למסך + data/expected_metrics.json
"""
import csv
import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def read(name):
    with open(DATA / name, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def metrics(lines, start, end):
    """מדדים לתקופה [start, end] כולל. כל הסכומים בשלמים (ש"ח)."""
    rows = [r for r in lines if start <= date.fromisoformat(r["תאריך"]) <= end]
    gross = sum(int(r["כמות"]) * int(r["מחיר ליחידה"]) for r in rows)
    returns = sum(int(r["כמות"]) * int(r["מחיר ליחידה"]) for r in rows if r["סטטוס"] == "הוחזר")
    net = gross - returns
    orders = len({r["מזהה הזמנה"] for r in rows})
    return {
        "הכנסות": gross,
        "החזרים": returns,
        "הכנסה לאחר החזרים": net,
        "אחוז החזרים": round(100 * returns / gross, 1) if gross else 0.0,
        "הזמנות": orders,
        "ערך הזמנה ממוצע": round(net / orders, 1) if orders else 0.0,
    }


def pct_change(new, old):
    return round(100 * (new - old) / old, 1) if old else None


def main():
    products = {p["מזהה מוצר"]: p for p in read("products.csv")}
    sales = read("sales.csv")
    end = max(date.fromisoformat(r["תאריך"]) for r in sales)
    start = min(date.fromisoformat(r["תאריך"]) for r in sales)

    out = {"תאריך אחרון בנתונים": end.isoformat(), "תאריך ראשון בנתונים": start.isoformat()}
    out["כל התקופה"] = metrics(sales, start, end)

    for days in (7, 30, 90):
        cur_s, cur_e = end - timedelta(days=days - 1), end
        prev_s, prev_e = cur_s - timedelta(days=days), cur_s - timedelta(days=1)
        cur, prev = metrics(sales, cur_s, cur_e), metrics(sales, prev_s, prev_e)
        out[f"{days} ימים"] = {
            "תקופה": f"{cur_s} עד {cur_e}",
            "תקופה קודמת": f"{prev_s} עד {prev_e}",
            "נוכחית": cur,
            "קודמת": prev,
            "שינוי בהכנסה לאחר החזרים באחוזים": pct_change(
                cur["הכנסה לאחר החזרים"], prev["הכנסה לאחר החזרים"]),
        }

    # לפי קטגוריה (כל התקופה)
    by_cat = defaultdict(list)
    for r in sales:
        by_cat[products[r["מוצר"]]["קטגוריה"]].append(r)
    out["לפי קטגוריה"] = {c: metrics(rs, start, end) for c, rs in by_cat.items()}

    # מוצרים מובילים לפי הכנסה לאחר החזרים (הגדרה זמנית, לאישור)
    rev = defaultdict(int)
    for r in sales:
        if r["סטטוס"] != "הוחזר":
            rev[r["מוצר"]] += int(r["כמות"]) * int(r["מחיר ליחידה"])
    top = sorted(rev.items(), key=lambda kv: -kv[1])[:5]
    out["חמשת המוצרים המובילים (הכנסה לאחר החזרים)"] = [
        {"מוצר": pid, "שם": products[pid]["שם"], "הכנסה": v} for pid, v in top]

    # סטטוסים (שורות)
    status = defaultdict(int)
    for r in sales:
        status[r["סטטוס"]] += 1
    out["שורות לפי סטטוס"] = dict(status)

    # בדיקות שלמות
    ids = [r["מזהה שורה"] for r in sales]
    checks = {
        "מזהי שורה ייחודיים": len(ids) == len(set(ids)),
        "כל מוצר במכירות קיים בטבלת מוצרים": all(r["מוצר"] in products for r in sales),
        "הכנסות פחות החזרים שווה להכנסה לאחר החזרים":
            out["כל התקופה"]["הכנסות"] - out["כל התקופה"]["החזרים"]
            == out["כל התקופה"]["הכנסה לאחר החזרים"],
        "סכום הקטגוריות שווה לסך הכול":
            sum(v["הכנסות"] for v in out["לפי קטגוריה"].values()) == out["כל התקופה"]["הכנסות"],
        "לא נמצאו כמויות או מחירים לא חיוביים":
            all(int(r["כמות"]) > 0 and int(r["מחיר ליחידה"]) > 0 for r in sales),
    }
    out["בדיקות שלמות"] = checks

    with open(DATA / "expected_metrics.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()

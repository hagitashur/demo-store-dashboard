"""
יצירת data.json מקובצי ה-CSV (data/products.csv, data/sales.csv).

data.json הוא הקובץ היחיד שהדשבורד קורא. המבנה שלו הוא "חוזה": גם הסקריפט
שימשוך מ-Airtable (בהמשך) חייב ליצור בדיוק אותו מבנה.

הרצה:  python scripts/build_data_json.py
פלט:   data.json (בשורש הפרויקט)
"""
import csv
import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

CATEGORIES = {"ספרים", "משחקים", "ציוד לבית ספר"}
STATUSES = {"ממתין", "נשלח", "נמסר", "הוחזר"}


def read(name):
    with open(DATA / name, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build():
    products = []
    for r in read("products.csv"):
        if r["קטגוריה"] not in CATEGORIES:
            raise ValueError(f"קטגוריה לא מוכרת: {r['קטגוריה']} במוצר {r['מזהה מוצר']}")
        products.append({
            "id": r["מזהה מוצר"],
            "name": r["שם"],
            "category": r["קטגוריה"],
            "price": int(r["מחיר"]),
        })
    product_ids = {p["id"] for p in products}

    sales = []
    for r in read("sales.csv"):
        if r["סטטוס"] not in STATUSES:
            raise ValueError(f"סטטוס לא מוכר: {r['סטטוס']} בשורה {r['מזהה שורה']}")
        if r["מוצר"] not in product_ids:
            raise ValueError(f"מוצר לא קיים: {r['מוצר']} בשורה {r['מזהה שורה']}")
        date.fromisoformat(r["תאריך"])  # נכשל אם התאריך לא תקין
        sales.append({
            "lineId": r["מזהה שורה"],
            "orderId": r["מזהה הזמנה"],
            "date": r["תאריך"],
            "productId": r["מוצר"],
            "quantity": int(r["כמות"]),
            "unitPrice": int(r["מחיר ליחידה"]),
            "status": r["סטטוס"],
            "customer": r["לקוחה"],
        })

    dates = sorted(s["date"] for s in sales)
    return {
        "meta": {
            "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
            "source": "csv",
            "currency": "₪",
            "firstDate": dates[0],
            "lastDate": dates[-1],
        },
        "products": products,
        "sales": sales,
    }


def verify(doc):
    """משווה את הסכומים ב-data.json לחישוב שנעשה ב-check_metrics.py."""
    with open(DATA / "expected_metrics.json", encoding="utf-8") as f:
        expected = json.load(f)["כל התקופה"]
    gross = sum(s["quantity"] * s["unitPrice"] for s in doc["sales"])
    returns = sum(s["quantity"] * s["unitPrice"] for s in doc["sales"] if s["status"] == "הוחזר")
    orders = len({s["orderId"] for s in doc["sales"]})
    got = {"הכנסות": gross, "החזרים": returns, "הכנסה לאחר החזרים": gross - returns, "הזמנות": orders}
    ok = True
    for key, value in got.items():
        match = value == expected[key]
        ok = ok and match
        print(f"  {key}: {value} (צפוי {expected[key]}) {'✓' if match else '✗ לא תואם'}")
    return ok


def main():
    doc = build()
    with open(ROOT / "data.json", "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"data.json נכתב: {len(doc['products'])} מוצרים, {len(doc['sales'])} שורות מכירה, "
          f"מקור: {doc['meta']['source']}, תקופה: {doc['meta']['firstDate']} עד {doc['meta']['lastDate']}")
    print("השוואה ל-expected_metrics.json:")
    if not verify(doc):
        sys.exit("נמצאה אי־התאמה בין data.json לחישוב הצפוי")
    print("הכול תואם.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()

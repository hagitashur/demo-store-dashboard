"""
סנכרון מ-Airtable אל data.json.

מושך את הטבלאות "מוצרים" ו"מכירות", בודק אותן, ויוצר data.json באותו מבנה בדיוק
שיוצר build_data_json.py (המבנה הוא ה"חוזה" שהדשבורד קורא). בלי ספריות חיצוניות.

הגדרות: קובץ .env בשורש הפרויקט (ראו .env.example). הקובץ הזה לא עולה לריפו.
    AIRTABLE_TOKEN     אסימון גישה אישי (Personal Access Token), קריאה בלבד, לבסיס הזה בלבד
    AIRTABLE_BASE_ID   מזהה הבסיס (מתחיל ב-app)

הרצה:
    python scripts/sync_airtable.py              סנכרון רגיל
    python scripts/sync_airtable.py --dry-run    בדיקה בלי לכתוב קובץ
    python scripts/sync_airtable.py --no-verify  בלי השוואה ל-expected_metrics.json (אחרי שינוי מכוון בנתונים)
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

from build_data_json import CATEGORIES, STATUSES, verify

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.airtable.com/v0"


class SyncError(Exception):
    """שגיאה עם הודעה ברורה למשתמשת (בלי פרטים סודיים)."""


# ---------- הגדרות ----------
def load_env(path=ROOT / ".env"):
    """קורא קובץ .env פשוט (שורות KEY=VALUE). משתני סביבה קיימים קודמים לקובץ."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# ---------- משיכה מ-Airtable ----------
def fetch_all(base_id, table, token):
    """מחזיר את כל הרשומות של טבלה (עם דפדוף). האסימון לא מודפס בשום מקום."""
    url_base = f"{API}/{base_id}/{urllib.parse.quote(table)}"
    records, offset = [], None
    while True:
        query = {"pageSize": "100"}
        if offset:
            query["offset"] = offset
        req = urllib.request.Request(url_base + "?" + urllib.parse.urlencode(query),
                                     headers={"Authorization": f"Bearer {token}"})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    page = json.load(resp)
                break
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 2:
                    time.sleep(30)  # Airtable מגבילה קצב: מחכים ומנסים שוב
                    continue
                hints = {
                    401: "האסימון לא תקין או שפג תוקפו. יוצרים אסימון חדש.",
                    403: "לאסימון אין הרשאה לבסיס או לטבלה הזו (data.records:read, והבסיס צריך להיות ברשימת הבסיסים של האסימון).",
                    404: f"הבסיס או הטבלה '{table}' לא נמצאו. בודקים את AIRTABLE_BASE_ID ואת שם הטבלה.",
                    422: "בקשה לא תקינה (בדקי את שם הטבלה).",
                }
                raise SyncError(f"Airtable החזירה שגיאה {e.code} בטבלה '{table}'. {hints.get(e.code, '')}") from None
            except urllib.error.URLError as e:
                raise SyncError(f"אין חיבור ל-Airtable ({e.reason}). בודקים אינטרנט.") from None
        records += page.get("records", [])
        offset = page.get("offset")
        if not offset:
            return records


# ---------- המרה למבנה של data.json ----------
def clean_key(k):
    """מוריד תו BOM נסתר ורווחים משם עמודה (נשאר לפעמים מייבוא קובץ CSV)."""
    return k.lstrip("﻿").strip()


def text(value):
    """ערך טקסט, גם כשהוא מגיע כבחירה (dict עם name) או כרשימה."""
    if isinstance(value, dict):
        value = value.get("name", "")
    if isinstance(value, list):
        value = value[0] if value else ""
    return "" if value is None else str(value).strip().lstrip("﻿")


def whole_number(value, what):
    """מספר שלם, אחרת שגיאה ברורה (כדי לא להסתיר נתון שבור)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise SyncError(f"{what}: הערך '{value}' אינו מספר") from None
    if number != int(number) or number < 0:
        raise SyncError(f"{what}: הערך {value} אינו מספר שלם וחיובי")
    return int(number)


def fields_of(record):
    return {clean_key(k): v for k, v in record.get("fields", {}).items()}


def is_record_id(value):
    return isinstance(value, str) and value.startswith("rec") and len(value) == 17


def transform(product_records, sales_records, source="airtable"):
    products, product_by_record = [], {}
    for rec in product_records:
        f = fields_of(rec)
        pid = text(f.get("מזהה מוצר"))
        if not pid:
            raise SyncError(f"מוצר ללא 'מזהה מוצר' (רשומה {rec.get('id')})")
        category = text(f.get("קטגוריה"))
        if category not in CATEGORIES:
            raise SyncError(f"קטגוריה לא מוכרת '{category}' במוצר {pid}")
        products.append({"id": pid, "name": text(f.get("שם")), "category": category,
                         "price": whole_number(f.get("מחיר"), f"מחיר של {pid}")})
        product_by_record[rec["id"]] = pid
    product_ids = set(product_by_record.values())
    if len(product_ids) != len(products):
        raise SyncError("יש 'מזהה מוצר' כפול בטבלת המוצרים")

    sales = []
    for rec in sales_records:
        f = fields_of(rec)
        line_id = text(f.get("מזהה שורה"))
        if not line_id:
            raise SyncError(f"שורת מכירה ללא 'מזהה שורה' (רשומה {rec.get('id')})")
        raw = f.get("מוצר")
        first = raw[0] if isinstance(raw, list) and raw else raw
        if is_record_id(first):  # שדה מסוג קישור: מחזיר מזהה רשומה, מתרגמים אותו ל-"מזהה מוצר"
            if first not in product_by_record:
                raise SyncError(f"{line_id}: הקישור למוצר מצביע על רשומה שאינה בטבלת המוצרים")
            pid = product_by_record[first]
        else:  # עדיין טקסט או בחירה: משתמשים בערך עצמו
            pid = text(raw)
        if pid not in product_ids:
            raise SyncError(f"{line_id}: המוצר '{pid}' לא קיים בטבלת המוצרים")
        status = text(f.get("סטטוס"))
        if status not in STATUSES:
            raise SyncError(f"{line_id}: סטטוס לא מוכר '{status}'")
        day = text(f.get("תאריך"))[:10]
        try:
            date.fromisoformat(day)
        except ValueError:
            raise SyncError(f"{line_id}: תאריך לא תקין '{day}'") from None
        order_id = text(f.get("מזהה הזמנה"))
        if not order_id:
            raise SyncError(f"{line_id}: חסר 'מזהה הזמנה'")
        sales.append({
            "lineId": line_id, "orderId": order_id, "date": day, "productId": pid,
            "quantity": whole_number(f.get("כמות"), f"כמות ב-{line_id}"),
            "unitPrice": whole_number(f.get("מחיר ליחידה"), f"מחיר ליחידה ב-{line_id}"),
            "status": status, "customer": text(f.get("לקוחה")),
        })
    if len({s["lineId"] for s in sales}) != len(sales):
        raise SyncError("יש 'מזהה שורה' כפול בטבלת המכירות")
    if not sales:
        raise SyncError("טבלת המכירות ריקה")

    products.sort(key=lambda p: p["id"])
    sales.sort(key=lambda s: s["lineId"])
    dates = sorted(s["date"] for s in sales)
    return {
        "meta": {"generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
                 "source": source, "currency": "₪", "firstDate": dates[0], "lastDate": dates[-1]},
        "products": products, "sales": sales,
    }


# ---------- הרצה ----------
def main(argv):
    dry_run, no_verify = "--dry-run" in argv, "--no-verify" in argv
    load_env()
    token = os.environ.get("AIRTABLE_TOKEN", "").strip()
    base_id = os.environ.get("AIRTABLE_BASE_ID", "").strip()
    if not token or not base_id:
        raise SyncError("חסרים AIRTABLE_TOKEN או AIRTABLE_BASE_ID. ממלאים אותם בקובץ .env (ראו .env.example).")
    if not base_id.startswith("app"):
        raise SyncError("AIRTABLE_BASE_ID צריך להתחיל ב-app")
    products_table = os.environ.get("AIRTABLE_PRODUCTS_TABLE", "מוצרים")
    sales_table = os.environ.get("AIRTABLE_SALES_TABLE", "מכירות")

    print("מושך נתונים מ-Airtable...")
    product_records = fetch_all(base_id, products_table, token)
    sales_records = fetch_all(base_id, sales_table, token)
    print(f"נמשכו {len(product_records)} מוצרים ו-{len(sales_records)} שורות מכירה.")
    doc = transform(product_records, sales_records)

    if not no_verify:
        print("השוואה ל-expected_metrics.json:")
        if not verify(doc):
            raise SyncError("הנתונים ב-Airtable שונים מהצפוי, ולכן לא נכתב קובץ. אם שינית נתונים בכוונה, הריצי עם --no-verify.")
    if dry_run:
        print("בדיקה בלבד (--dry-run): לא נכתב קובץ.")
        return
    tmp = ROOT / "data.json.tmp"
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ROOT / "data.json")
    print(f"data.json עודכן (מקור: airtable, {len(doc['products'])} מוצרים, {len(doc['sales'])} שורות).")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        main(sys.argv[1:])
    except SyncError as err:
        sys.exit(f"שגיאה: {err}")

"""
בדיקה אוטומטית ללוגיקת ההמרה של sync_airtable.py, בלי חיבור לרשת ובלי אסימון.

בונה "תשובות מדומות" של Airtable מקובצי ה-CSV, בכמה צורות שונות שהבסיס האמיתי עלול להחזיר
(עמודה ראשונה עם תו BOM, בחירה כטקסט או כאובייקט, מוצר כטקסט או כקישור), ומוודאת שהתוצאה
זהה לחלוטין ל-data.json שנוצר מה-CSV.

הרצה:  python scripts/test_sync_transform.py
"""
import sys

from build_data_json import build
from sync_airtable import SyncError, transform


def fake_airtable(reference, link_mode, select_as_dict):
    """בונה רשומות בצורה של תשובת Airtable מתוך הנתונים המקוריים."""
    sel = (lambda v: {"id": "sel" + "x" * 14, "name": v, "color": "blue"}) if select_as_dict else (lambda v: v)
    rec_of = {p["id"]: f"recP{i:013d}" for i, p in enumerate(reference["products"])}
    products = [{"id": rec_of[p["id"]], "createdTime": "2026-10-03T00:00:00.000Z",
                 "fields": {"﻿מזהה מוצר": p["id"], "שם": p["name"],
                            "קטגוריה": sel(p["category"]), "מחיר": float(p["price"])}}
                for p in reference["products"]]
    sales = []
    for i, s in enumerate(reference["sales"]):
        product = [rec_of[s["productId"]]] if link_mode else sel(s["productId"])
        sales.append({"id": f"recS{i:013d}", "createdTime": "2026-10-03T00:00:00.000Z",
                      "fields": {"﻿מזהה שורה": s["lineId"], "מזהה הזמנה": sel(s["orderId"]),
                                 "תאריך": s["date"], "מוצר": product, "כמות": s["quantity"],
                                 "מחיר ליחידה": s["unitPrice"], "סטטוס": sel(s["status"]),
                                 "לקוחה": sel(s["customer"])}})
    # Airtable לא מבטיחה סדר: מערבבים כדי לוודא שהסקריפט ממיין
    products.reverse()
    sales.reverse()
    return products, sales


def same(a, b):
    return a["products"] == b["products"] and a["sales"] == b["sales"]


def expect_error(label, products, sales):
    try:
        transform(products, sales)
    except SyncError as e:
        print(f"  תקין: {label} -> נעצר עם הודעה: {e}")
        return True
    print(f"  !!! {label} היה צריך להיכשל")
    return False


def main():
    ref = build()
    ok = True
    for link_mode in (False, True):
        for as_dict in (False, True):
            p, s = fake_airtable(ref, link_mode, as_dict)
            got = transform(p, s)
            good = same(got, ref) and got["meta"]["source"] == "airtable" \
                and got["meta"]["firstDate"] == ref["meta"]["firstDate"] \
                and got["meta"]["lastDate"] == ref["meta"]["lastDate"]
            ok &= good
            print(f"{'עבר' if good else 'נכשל'}: מוצר={'קישור' if link_mode else 'טקסט/בחירה'}, "
                  f"בחירות={'אובייקט' if as_dict else 'מחרוזת'}")

    print("מקרי שגיאה (חייבים להיעצר עם הודעה ברורה):")
    p, s = fake_airtable(ref, True, False)
    bad = [dict(r, fields=dict(r["fields"])) for r in s]
    bad[0]["fields"]["סטטוס"] = "מבוטל"
    ok &= expect_error("סטטוס לא מוכר", p, bad)
    bad = [dict(r, fields=dict(r["fields"])) for r in s]
    bad[0]["fields"]["מוצר"] = ["recZZZZZZZZZZZZZZ"]
    ok &= expect_error("קישור לרשומה שלא קיימת", p, bad)
    bad = [dict(r, fields=dict(r["fields"])) for r in s]
    bad[0]["fields"]["כמות"] = 1.5
    ok &= expect_error("כמות לא שלמה", p, bad)
    bad = [dict(r, fields=dict(r["fields"])) for r in s]
    bad[0]["fields"]["תאריך"] = "03/04/2026"
    ok &= expect_error("תאריך בפורמט שגוי", p, bad)
    ok &= expect_error("טבלת מכירות ריקה", p, [])

    print("\nכל הבדיקות עברו." if ok else "\nיש בדיקות שנכשלו.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()

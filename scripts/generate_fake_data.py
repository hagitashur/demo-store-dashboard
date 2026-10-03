"""
יצירת נתוני דמה לחנות אונליין (ספרים, משחקים, ציוד לבית ספר).

כל הנתונים בדויים: שמות מוצרים מורכבים ממילים כלליות, לקוחות הן קודים אנונימיים.
הזרע (SEED) קבוע, ולכן הרצה חוזרת נותנת בדיוק אותם קבצים.

הרצה:  python scripts/generate_fake_data.py
פלט:   data/products.csv, data/sales.csv, data/נתוני-דמה-לצפייה.xlsx
"""
import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

# ---------- הנחות (אפשר לשנות כאן) ----------
SEED = 2026
START = date(2026, 4, 3)
END = date(2026, 10, 2)          # התאריך האחרון בנתונים
N_BOOKS, N_GAMES, N_SCHOOL = 40, 30, 30
N_CUSTOMERS = 160
BASE_ORDERS_PER_DAY = 1.5        # ממוצע הזמנות ביום מחוץ לעונה
LINES_PER_ORDER = ([1, 2, 3], [0.60, 0.28, 0.12])
# הסתברות החזר לשורה שנמסרה, לפי קטגוריה
RETURN_PROB = {"ספרים": 0.03, "משחקים": 0.07, "ציוד לבית ספר": 0.04}

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
rng = random.Random(SEED)


# ---------- מוצרים ----------
def build_books():
    places = ["האי הנעלם", "עמק הכוכבים", "יער הערפל", "העיר הצפה", "הר הסודות",
              "ממלכת הענן", "הים הכחול", "גן הפלאות", "המגדלור הישן", "הכפר הנסתר"]
    heroes = ["נועם", "מאיה", "אורי", "תמר", "יובל", "שירה", "דניאל", "רוני", "ליאור", "גל"]
    animals = [("הדוב", "הארנבת"), ("השועל", "הצב"), ("הינשוף", "החתולה"), ("הפיל", "העכבר"),
               ("הדולפין", "הסרטן"), ("הצפרדע", "הברווז"), ("הכלב", "הציפור"), ("האריה", "הגמד")]
    topics = ["החלל", "הדינוזאורים", "הבישול", "הציפורים", "הרובוטים", "המדע בכיף", "הצבעים", "הים"]
    cand = [f"מסע אל {p}" for p in places]
    cand += [f"הסוד של {h}" for h in heroes]
    cand += [f"{a} ו{b} בעיר" for a, b in animals]
    cand += [f"מדריך לילדים: {t}" for t in topics]
    cand += [f"אגדות {p}" for p in places]
    rng.shuffle(cand)
    return [(name, "ספרים", rng.randint(3, 10) * 10 - 1) for name in cand[:N_BOOKS]]


def build_games():
    themes = ["החלל", "הג'ונגל", "הים העמוק", "המדע", "הצבעים", "הדינוזאורים",
              "האותיות", "המספרים", "הממלכה", "הרכבות", "החווה", "הבלשים"]
    cand = [f"משחק קלפים: {t}" for t in themes]
    cand += [f"פאזל {t} {n} חלקים" for t in themes[:6] for n in (100, 500)]
    cand += [f"משחק קופסה: {t}" for t in themes]
    cand += [f"לוטו {t}" for t in themes[:5]]
    rng.shuffle(cand)
    return [(name, "משחקים", rng.randint(4, 25) * 10 - 1) for name in cand[:N_GAMES]]


def build_school():
    items = [
        ("מחברת", ["A4 משבצות", "A5 שורות", "A4 חלקה"], (9, 29)),
        ("עט", ["כחול", "שחור", "ג'ל"], (5, 19)),
        ("קלמר", ["כחול", "ורוד", "ירוק", "אפור"], (19, 59)),
        ("תיק גב", ["קטן", "גדול", "עם גלגלים"], (89, 249)),
        ("עפרונות", ["סט 12", "סט 24"], (15, 39)),
        ("צבעי עץ", ["12 צבעים", "24 צבעים", "36 צבעים"], (19, 69)),
        ("מחשבון", ["בסיסי", "מדעי"], (29, 99)),
        ("דבק סטיק", ["קטן", "גדול"], (5, 15)),
        ("מספריים", ["לילדים", "למבוגרים"], (9, 29)),
        ("סרגל", ["30 ס״מ", "15 ס״מ"], (5, 15)),
        ("טוש", ["סט 10", "סט 20"], (19, 49)),
    ]
    cand = [(f"{item} {v}", rng.randint(lo, hi)) for item, variants, (lo, hi) in items for v in variants]
    rng.shuffle(cand)
    return [(name, "ציוד לבית ספר", price) for name, price in cand[:N_SCHOOL]]


def build_products():
    products = []
    for group in (build_books(), build_games(), build_school()):
        for name, cat, price in group:
            products.append({"שם": name, "קטגוריה": cat, "מחיר": price})
    for i, p in enumerate(products, start=1):
        p["מזהה מוצר"] = f"P-{i:03d}"
    return products


# ---------- מכירות ----------
def season_multiplier(d):
    """עונת חזרה ללימודים: עלייה מאמצע יולי, שיא 10 באוגוסט עד 10 בספטמבר."""
    if d < date(2026, 7, 15):
        return 1.0
    if d < date(2026, 8, 10):
        return 1.0 + 1.6 * (d - date(2026, 7, 15)).days / 26
    if d <= date(2026, 9, 10):
        return 2.6
    return 1.3


def poisson(lam):
    limit, k, p = pow(2.718281828, -lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def category_weights(mult):
    s = min(1.0, max(0.0, (mult - 1.0) / 1.6))
    school = 0.25 + 0.35 * s
    rest = 1 - school
    return {"ספרים": rest * 0.60, "משחקים": rest * 0.40, "ציוד לבית ספר": school}


def build_sales(products):
    by_cat = {}
    for p in products:
        by_cat.setdefault(p["קטגוריה"], []).append(p)
    # פופולריות קבועה לכל מוצר: מעטים נמכרים הרבה, רבים נמכרים מעט
    pop = {}
    for cat, plist in by_cat.items():
        for rank, p in enumerate(plist, start=1):
            pop[p["מזהה מוצר"]] = 1 / (rank ** 0.8)

    customers = [f"לקוחה-{i:03d}" for i in range(1, N_CUSTOMERS + 1)]
    cust_w = [1 / (i ** 0.5) for i in range(1, N_CUSTOMERS + 1)]

    sales, order_n, line_n = [], 0, 0
    d = START
    while d <= END:
        mult = season_multiplier(d)
        for _ in range(poisson(BASE_ORDERS_PER_DAY * mult)):
            order_n += 1
            order_id = f"O-{order_n:04d}"
            customer = rng.choices(customers, cust_w)[0]
            age = (END - d).days
            if age <= 3:
                ship = rng.choices(["ממתין", "נשלח"], [0.6, 0.4])[0]
            elif age <= 10:
                ship = rng.choices(["נשלח", "נמסר"], [0.45, 0.55])[0]
            else:
                ship = "נמסר"
            n_lines = rng.choices(*LINES_PER_ORDER)[0]
            chosen = []
            cw = category_weights(mult)
            while len(chosen) < n_lines:
                cat = rng.choices(list(cw), list(cw.values()))[0]
                plist = by_cat[cat]
                prod = rng.choices(plist, [pop[p["מזהה מוצר"]] for p in plist])[0]
                if prod not in chosen:
                    chosen.append(prod)
            for prod in chosen:
                line_n += 1
                cat = prod["קטגוריה"]
                if cat == "ציוד לבית ספר":
                    qty = rng.choices([1, 2, 3, 4], [0.5, 0.25, 0.15, 0.10])[0]
                else:
                    qty = rng.choices([1, 2, 3], [0.80, 0.15, 0.05])[0]
                status = ship
                if ship == "נמסר" and rng.random() < RETURN_PROB[cat]:
                    status = "הוחזר"
                sales.append({
                    "מזהה שורה": f"S-{line_n:04d}",
                    "מזהה הזמנה": order_id,
                    "תאריך": d.isoformat(),
                    "מוצר": prod["מזהה מוצר"],
                    "כמות": qty,
                    "מחיר ליחידה": prod["מחיר"],
                    "סטטוס": status,
                    "לקוחה": customer,
                })
        d += timedelta(days=1)
    return sales


# ---------- כתיבה ----------
def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig כדי שאקסל יקרא עברית
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def write_xlsx(path, products, sales, pfields, sfields):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = Workbook()
    for title, rows, fields in (("מוצרים", products, pfields), ("מכירות", sales, sfields)):
        ws = wb.active if title == "מוצרים" else wb.create_sheet()
        ws.title = title
        ws.sheet_view.rightToLeft = True  # אקסל מימין לשמאל
        ws.append(fields)
        for r in rows:
            row = [r[k] for k in fields]
            if "תאריך" in fields:
                row[fields.index("תאריך")] = date.fromisoformat(r["תאריך"])
            ws.append(row)
        for c in ws[1]:
            c.font = Font(bold=True)
            c.fill = PatternFill("solid", fgColor="E8EEF7")
            c.alignment = Alignment(horizontal="right")
        for col in ws.columns:
            width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
            ws.column_dimensions[col[0].column_letter].width = min(max(width + 3, 10), 34)
        ws.freeze_panes = "A2"
        if "תאריך" in fields:
            col = fields.index("תאריך") + 1
            for cell in ws.iter_rows(min_row=2, min_col=col, max_col=col):
                cell[0].number_format = "DD/MM/YYYY"
    wb.save(path)


def main():
    DATA.mkdir(exist_ok=True)
    products = build_products()
    sales = build_sales(products)
    pfields = ["מזהה מוצר", "שם", "קטגוריה", "מחיר"]
    sfields = ["מזהה שורה", "מזהה הזמנה", "תאריך", "מוצר", "כמות", "מחיר ליחידה", "סטטוס", "לקוחה"]
    write_csv(DATA / "products.csv", products, pfields)
    write_csv(DATA / "sales.csv", sales, sfields)
    write_xlsx(DATA / "נתוני-דמה-לצפייה.xlsx", products, sales, pfields, sfields)
    orders = {s["מזהה הזמנה"] for s in sales}
    print(f"מוצרים: {len(products)} | שורות מכירה: {len(sales)} | הזמנות: {len(orders)}")
    print(f"נכתב אל: {DATA}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()

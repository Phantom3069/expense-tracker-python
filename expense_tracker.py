"""
╔══════════════════════════════════════════════╗
║           EXPENSE TRACKER                    ║
╚══════════════════════════════════════════════╝

Features  : Add / View / Filter / Delete expenses
            Monthly & category reports with bar charts
Storage   : SQLite  (expenses.db — auto-created on first run)
Concepts  : SQLite (sqlite3), datetime, file I/O (CSV export),
            modular functions, exception handling, data analytics
"""

import sqlite3
import os
import csv
from datetime import datetime, date, timedelta

# ── Database file ──────────────────────────────────────────────────────────────
DB_FILE = "expenses.db"

# ── Terminal colours ───────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
MAGENTA= "\033[95m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✔  {msg}{RESET}")
def err(msg):  print(f"  {RED}✘  {msg}{RESET}")
def info(msg): print(f"  {CYAN}ℹ  {msg}{RESET}")
def warn(msg): print(f"  {YELLOW}⚠  {msg}{RESET}")

# ── Predefined categories ──────────────────────────────────────────────────────
CATEGORIES = [
    "Food", "Transport", "Shopping", "Health",
    "Entertainment", "Education", "Utilities", "Other"
]

# ══════════════════════════════════════════════════════════════════════════════
#  DATABASE SETUP & HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def get_connection() -> sqlite3.Connection:
    """Open (or create) the SQLite database and return a connection."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row   # lets us access columns by name
    return conn


def init_db() -> None:
    """Create the expenses table if it doesn't already exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT    NOT NULL,
                category    TEXT    NOT NULL,
                description TEXT    NOT NULL,
                amount      REAL    NOT NULL
            )
        """)
    info(f"Database ready: {os.path.abspath(DB_FILE)}")


# ══════════════════════════════════════════════════════════════════════════════
#  INPUT HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def prompt(label: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    try:
        val = input(f"  {label}{hint}: ").strip()
        return val if val else default
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit("\n  Exiting. Goodbye!")


def get_valid_date(label: str, default: str = "") -> str:
    """Prompt until a valid YYYY-MM-DD date string is entered."""
    while True:
        raw = prompt(label, default)
        try:
            datetime.strptime(raw, "%Y-%m-%d")
            return raw
        except ValueError:
            warn("Invalid date. Use YYYY-MM-DD format (e.g. 2025-06-15).")


def get_positive_float(label: str) -> float:
    """Prompt until a positive number is entered."""
    while True:
        raw = prompt(label)
        try:
            val = float(raw)
            if val > 0:
                return round(val, 2)
            warn("Amount must be greater than 0.")
        except ValueError:
            warn("Please enter a valid number.")


def get_category() -> str:
    """Show category menu and return the chosen category string."""
    print("\n  Categories:")
    for i, cat in enumerate(CATEGORIES, 1):
        print(f"    {i}) {cat}")
    while True:
        raw = prompt("Choose category number", "8")
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(CATEGORIES):
                return CATEGORIES[idx]
            warn(f"Enter a number between 1 and {len(CATEGORIES)}.")
        except ValueError:
            warn("Please enter a number.")


# ══════════════════════════════════════════════════════════════════════════════
#  DISPLAY HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def print_banner() -> None:
    print(f"\n{BOLD}{'═'*50}")
    print("        💸  EXPENSE TRACKER")
    print(f"{'═'*50}{RESET}")


def print_menu() -> None:
    print(f"""\n{BOLD}  ┌──────────────────────────────────┐
  │            MAIN MENU             │
  ├──────────────────────────────────┤
  │  1 │ Add Expense                 │
  │  2 │ View All Expenses           │
  │  3 │ Filter by Date Range        │
  │  4 │ Filter by Category          │
  │  5 │ Monthly Report              │
  │  6 │ Category Report             │
  │  7 │ Delete Expense              │
  │  8 │ Export to CSV               │
  │  0 │ Exit                        │
  └──────────────────────────────────┘{RESET}""")


def print_expense_table(rows, title: str = "Expenses") -> None:
    """Render a formatted table from a list of sqlite3.Row objects."""
    if not rows:
        warn("No expenses found.")
        return

    total = sum(r["amount"] for r in rows)
    print(f"\n  {BOLD}{title}{RESET}")
    print(f"  {'─'*68}")
    print(f"  {'ID':>4}  {'Date':<12}  {'Category':<14}  {'Description':<20}  {'Amount':>8}")
    print(f"  {'─'*68}")
    for r in rows:
        print(
            f"  {r['id']:>4}  {r['date']:<12}  {r['category']:<14}  "
            f"{r['description'][:20]:<20}  {GREEN}₹{r['amount']:>7.2f}{RESET}"
        )
    print(f"  {'─'*68}")
    print(f"  {'Total':>53}  {BOLD}{GREEN}₹{total:>7.2f}{RESET}")
    print(f"  {len(rows)} record(s)\n")


def bar_chart(label: str, value: float, max_value: float, width: int = 25) -> str:
    """Return a single coloured bar-chart row string."""
    filled = int((value / max_value) * width) if max_value else 0
    bar    = "█" * filled + "░" * (width - filled)
    return f"  {label:<18} {CYAN}{bar}{RESET}  ₹{value:>8.2f}"


# ══════════════════════════════════════════════════════════════════════════════
#  CRUD OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

# ── 1. ADD ─────────────────────────────────────────────────────────────────────
def add_expense() -> None:
    print(f"\n{BOLD}  ── Add New Expense ──{RESET}")
    today    = date.today().strftime("%Y-%m-%d")
    exp_date = get_valid_date("Date (YYYY-MM-DD)", today)
    category = get_category()
    desc     = prompt("Description") or "No description"
    amount   = get_positive_float("Amount (₹)")

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO expenses (date, category, description, amount) VALUES (?,?,?,?)",
            (exp_date, category, desc, amount)
        )
    ok(f"Expense added — ₹{amount:.2f} for {category} on {exp_date}.")


# ── 2. VIEW ALL ────────────────────────────────────────────────────────────────
def view_all() -> None:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM expenses ORDER BY date DESC"
        ).fetchall()
    print_expense_table(rows, "All Expenses")


# ── 3. FILTER BY DATE RANGE ────────────────────────────────────────────────────
def filter_by_date() -> None:
    print(f"\n{BOLD}  ── Filter by Date Range ──{RESET}")
    today = date.today().strftime("%Y-%m-%d")
    start = get_valid_date("Start date (YYYY-MM-DD)", today)
    end   = get_valid_date("End date   (YYYY-MM-DD)", today)

    if start > end:
        warn("Start date is after end date — swapping them.")
        start, end = end, start

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM expenses WHERE date BETWEEN ? AND ? ORDER BY date",
            (start, end)
        ).fetchall()
    print_expense_table(rows, f"Expenses from {start} to {end}")


# ── 4. FILTER BY CATEGORY ──────────────────────────────────────────────────────
def filter_by_category() -> None:
    print(f"\n{BOLD}  ── Filter by Category ──{RESET}")
    category = get_category()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM expenses WHERE category = ? ORDER BY date DESC",
            (category,)
        ).fetchall()
    print_expense_table(rows, f"Expenses — {category}")


# ── 5. MONTHLY REPORT ─────────────────────────────────────────────────────────
def monthly_report() -> None:
    print(f"\n{BOLD}  ── Monthly Report ──{RESET}")
    year = prompt("Year (YYYY)", str(date.today().year))

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT strftime('%m', date) AS month,
                   SUM(amount)          AS total,
                   COUNT(*)             AS count
            FROM   expenses
            WHERE  strftime('%Y', date) = ?
            GROUP  BY month
            ORDER  BY month
        """, (year,)).fetchall()

    if not rows:
        warn(f"No expenses found for {year}.")
        return

    MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]
    max_total = max(r["total"] for r in rows)
    grand_total = sum(r["total"] for r in rows)

    print(f"\n  {BOLD}Year: {year}   Grand Total: ₹{grand_total:.2f}{RESET}\n")
    for r in rows:
        name = MONTH_NAMES[int(r["month"]) - 1]
        print(bar_chart(f"{name} ({r['count']} items)", r["total"], max_total))
    print()


# ── 6. CATEGORY REPORT ────────────────────────────────────────────────────────
def category_report() -> None:
    print(f"\n{BOLD}  ── Category Report ──{RESET}")

    # Optional month filter
    filter_month = prompt("Filter by month? (YYYY-MM or Enter to skip)", "")
    if filter_month:
        try:
            datetime.strptime(filter_month, "%Y-%m")
            date_filter = f"AND strftime('%Y-%m', date) = '{filter_month}'"
            title_suffix = f"for {filter_month}"
        except ValueError:
            warn("Invalid format — showing all-time report.")
            date_filter  = ""
            title_suffix = "(all time)"
    else:
        date_filter  = ""
        title_suffix = "(all time)"

    with get_connection() as conn:
        rows = conn.execute(f"""
            SELECT category,
                   SUM(amount) AS total,
                   COUNT(*)    AS count,
                   AVG(amount) AS avg
            FROM   expenses
            WHERE  1=1 {date_filter}
            GROUP  BY category
            ORDER  BY total DESC
        """).fetchall()

    if not rows:
        warn("No expenses found.")
        return

    max_total   = rows[0]["total"]
    grand_total = sum(r["total"] for r in rows)

    print(f"\n  {BOLD}Category Breakdown {title_suffix}   Total: ₹{grand_total:.2f}{RESET}\n")
    for r in rows:
        pct = (r["total"] / grand_total) * 100
        print(bar_chart(r["category"], r["total"], max_total))
        print(f"  {'':18}   {r['count']} transactions · avg ₹{r['avg']:.2f} · {pct:.1f}% of total")
    print()


# ── 7. DELETE ─────────────────────────────────────────────────────────────────
def delete_expense() -> None:
    print(f"\n{BOLD}  ── Delete Expense ──{RESET}")
    raw = prompt("Enter Expense ID to delete")
    try:
        eid = int(raw)
    except ValueError:
        err("Invalid ID.")
        return

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (eid,)
        ).fetchone()

        if not row:
            err(f"No expense found with ID {eid}.")
            return

        print_expense_table([row], "Expense to Delete")
        confirm = prompt("Confirm delete? (y/n)", "n").lower()
        if confirm == "y":
            conn.execute("DELETE FROM expenses WHERE id = ?", (eid,))
            ok(f"Expense ID {eid} deleted.")
        else:
            info("Delete cancelled.")


# ── 8. EXPORT TO CSV ──────────────────────────────────────────────────────────
def export_csv() -> None:
    print(f"\n{BOLD}  ── Export to CSV ──{RESET}")
    filename = prompt("Output filename", "expenses_export.csv")
    if not filename.endswith(".csv"):
        filename += ".csv"

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, date, category, description, amount FROM expenses ORDER BY date"
        ).fetchall()

    if not rows:
        warn("Nothing to export.")
        return

    try:
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Date", "Category", "Description", "Amount"])
            for r in rows:
                writer.writerow([r["id"], r["date"], r["category"], r["description"], r["amount"]])
        ok(f"Exported {len(rows)} record(s) to '{filename}'.")
    except IOError as e:
        err(f"Could not write file: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  QUICK SUMMARY shown on startup
# ══════════════════════════════════════════════════════════════════════════════

def startup_summary() -> None:
    """Show this month's total and last 3 expenses on launch."""
    this_month = date.today().strftime("%Y-%m")
    with get_connection() as conn:
        month_total = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE strftime('%Y-%m',date)=?",
            (this_month,)
        ).fetchone()[0]
        total_all = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM expenses"
        ).fetchone()[0]
        recent = conn.execute(
            "SELECT * FROM expenses ORDER BY date DESC, id DESC LIMIT 3"
        ).fetchall()

    print(f"\n  {BOLD}📅 This month ({this_month}):{RESET}  ₹{month_total:.2f}")
    print(f"  {BOLD}📊 All-time total:{RESET}           ₹{total_all:.2f}")
    if recent:
        print(f"\n  {BOLD}Recent entries:{RESET}")
        for r in recent:
            print(f"    #{r['id']}  {r['date']}  {r['category']:<14}  ₹{r['amount']:.2f}  – {r['description'][:30]}")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN LOOP
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print_banner()
    init_db()
    startup_summary()

    ACTIONS = {
        "1": add_expense,
        "2": view_all,
        "3": filter_by_date,
        "4": filter_by_category,
        "5": monthly_report,
        "6": category_report,
        "7": delete_expense,
        "8": export_csv,
    }

    while True:
        print_menu()
        choice = prompt("Select option", "0")

        if choice == "0":
            print(f"\n  {BOLD}Goodbye! Your data is saved in {DB_FILE}.{RESET}\n")
            break
        elif choice in ACTIONS:
            ACTIONS[choice]()
        else:
            warn("Invalid option. Please choose 0–8.")


if __name__ == "__main__":
    main()

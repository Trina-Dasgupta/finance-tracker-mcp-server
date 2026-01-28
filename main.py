from fastmcp import FastMCP
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "expenses.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

mcp = FastMCP("ExpenseTracker")

def init_db():
    with sqlite3.connect(DB_PATH) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS expenses(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                note TEXT DEFAULT ''
            )
        """)

init_db()

@mcp.tool()
def add_expense(date, amount, category, subcategory="", note=""):
    '''Add a new expense entry to the database.'''
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            "INSERT INTO expenses(date, amount, category, subcategory, note) VALUES (?,?,?,?,?)",
            (date, amount, category, subcategory, note)
        )
        return {"status": "ok", "id": cur.lastrowid}
    
@mcp.tool()
def list_expenses(start_date, end_date):
    '''List expense entries within an inclusive date range.'''
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            """
            SELECT id, date, amount, category, subcategory, note
            FROM expenses
            WHERE date BETWEEN ? AND ?
            ORDER BY id ASC
            """,
            (start_date, end_date)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

@mcp.tool()
def delete_expense(expense_id):
    '''Delete an expense entry by id.'''
    try:
        expense_id = int(expense_id)
    except (TypeError, ValueError):
        return {"status": "error", "message": "expense_id must be an integer"}

    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            "DELETE FROM expenses WHERE id = ?",
            (expense_id,)
        )
        if cur.rowcount == 0:
            return {"status": "not_found", "deleted": 0}
        return {"status": "ok", "deleted": cur.rowcount}

@mcp.tool()
def delete_expenses(expense_ids=None, delete_all=False):
    '''Delete all expenses or multiple expenses by id.'''
    if delete_all:
        with sqlite3.connect(DB_PATH) as c:
            cur = c.execute("DELETE FROM expenses")
            return {"status": "ok", "deleted": cur.rowcount}

    if expense_ids is None:
        return {"status": "error", "message": "provide expense_ids or set delete_all=true"}

    if isinstance(expense_ids, str):
        raw_ids = [p for p in expense_ids.replace(",", " ").split() if p]
    elif isinstance(expense_ids, (list, tuple)):
        raw_ids = expense_ids
    else:
        raw_ids = [expense_ids]

    ids = []
    invalid = []
    for item in raw_ids:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            invalid.append(item)

    if invalid:
        return {"status": "error", "message": "expense_ids must be integers", "invalid": invalid}
    if not ids:
        return {"status": "error", "message": "no valid expense_ids provided"}

    placeholders = ",".join(["?"] * len(ids))
    with sqlite3.connect(DB_PATH) as c:
        existing = {
            row[0]
            for row in c.execute(
                f"SELECT id FROM expenses WHERE id IN ({placeholders})",
                ids
            ).fetchall()
        }
        cur = c.execute(
            f"DELETE FROM expenses WHERE id IN ({placeholders})",
            ids
        )
        missing = sorted(set(ids) - existing)
        status = "ok" if cur.rowcount > 0 else "not_found"
        return {"status": status, "deleted": cur.rowcount, "missing": missing}

@mcp.tool()
def update_expense(expense_id, date=None, amount=None, category=None, subcategory=None, note=None):
    '''Update one or more fields on an expense entry by id.'''
    try:
        expense_id = int(expense_id)
    except (TypeError, ValueError):
        return {"status": "error", "message": "expense_id must be an integer"}

    fields = []
    params = []

    if date is not None:
        fields.append("date = ?")
        params.append(date)
    if amount is not None:
        fields.append("amount = ?")
        params.append(amount)
    if category is not None:
        fields.append("category = ?")
        params.append(category)
    if subcategory is not None:
        fields.append("subcategory = ?")
        params.append(subcategory)
    if note is not None:
        fields.append("note = ?")
        params.append(note)

    if not fields:
        return {"status": "error", "message": "provide at least one field to update"}

    params.append(expense_id)

    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            f"UPDATE expenses SET {', '.join(fields)} WHERE id = ?",
            params
        )
        if cur.rowcount == 0:
            exists = c.execute(
                "SELECT 1 FROM expenses WHERE id = ?",
                (expense_id,)
            ).fetchone()
            if exists:
                return {"status": "no_change", "updated": 0}
            return {"status": "not_found", "updated": 0}
        return {"status": "ok", "updated": cur.rowcount}

@mcp.tool()
def summarize(start_date, end_date, category=None):
    '''Summarize expenses by category within an inclusive date range.'''
    with sqlite3.connect(DB_PATH) as c:
        query = (
            """
            SELECT category, SUM(amount) AS total_amount
            FROM expenses
            WHERE date BETWEEN ? AND ?
            """
        )
        params = [start_date, end_date]

        if category:
            query += " AND category = ?"
            params.append(category)

        query += " GROUP BY category ORDER BY category ASC"

        cur = c.execute(query, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

@mcp.resource("expense://categories", mime_type="application/json")
def categories():
    # Read fresh each time so you can edit the file without restarting
    with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    mcp.run()

# Budgeting App v2 (Flask + Bootstrap + Plotly)

Polished UI, dark mode, richer dashboard:
- Income vs Expense, Net Cashflow, Monthly category donut
- Cumulative Spend vs Budget line
- Budget progress bars per category
- Auth, Transactions CRUD, CSV import/export, Budgets, Reports (PDF)
- SQLite by default; MySQL via `DATABASE_URL`

## Quickstart
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```
Login: `admin@gmail.com` / `admin123`

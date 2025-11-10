import io, csv, json, calendar
from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_login import login_required, current_user
from sqlalchemy import extract
import pandas as pd
from ..models import db, Category, Transaction, Budget, Report

bp = Blueprint("core", __name__)

@bp.route("/")
@login_required
def dashboard():
    txns = Transaction.query.filter_by(user_id=current_user.id, is_deleted=False).all()
    df = pd.DataFrame([{
        "date": t.date, "amount": float(t.amount), "type": Category.query.get(t.category_id).type,
        "category": Category.query.get(t.category_id).name
    } for t in txns]) if txns else pd.DataFrame(columns=["date","amount","type","category"])

    total_income = float(df[df["type"]=="income"]["amount"].sum()) if not df.empty else 0.0
    total_expense = float(df[df["type"]=="expense"]["amount"].sum()) if not df.empty else 0.0
    balance = total_income - total_expense

    # Alerts vs budget (current month)
    today = date.today()
    period = today.strftime("%Y-%m")
    alerts = []
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        month_df = df[(df["date"].dt.strftime("%Y-%m")==period) & (df["type"]=="expense")]
        spent_by_cat = month_df.groupby("category")["amount"].sum().to_dict()
        budgets = Budget.query.filter_by(user_id=current_user.id, period=period).all()
        for b in budgets:
            cat = Category.query.get(b.category_id).name
            spent = spent_by_cat.get(cat, 0.0)
            if float(b.target_amount) > 0 and spent >= 0.9*float(b.target_amount):
                alerts.append({"category": cat, "spent": round(spent,2), "budget": float(b.target_amount)})

    return render_template("index.html",
                           total_income=round(total_income,2),
                           total_expense=round(total_expense,2),
                           balance=round(balance,2),
                           alerts=alerts)

@bp.route("/data/summary.json")
@login_required
def data_summary():
    txns = Transaction.query.filter_by(user_id=current_user.id, is_deleted=False).all()
    if not txns:
        return jsonify({"timeseries": [], "categories": [], "income_ts": [], "expense_ts": [],
                        "cm_categories": [], "daily_cum": [], "budget_total": 0, "spent_total": 0,
                        "budget_progress": []})
    rows = []
    for t in txns:
        cat = Category.query.get(t.category_id)
        rows.append({"date": t.date.isoformat(), "amount": float(t.amount), "ctype": cat.type, "category": cat.name})
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()

    inc = df[df["ctype"]=="income"].groupby("month")["amount"].sum().reset_index()
    exp = df[df["ctype"]=="expense"].groupby("month")["amount"].sum().reset_index()
    net = pd.merge(inc, exp, on="month", how="outer", suffixes=("_inc","_exp")).fillna(0)
    net["net"] = net["amount_inc"] - net["amount_exp"]
    net = net.sort_values("month")

    cat_split = df[df["ctype"]=="expense"].groupby("category")["amount"].sum().reset_index().sort_values("amount", ascending=False)

    today = date.today()
    period = today.strftime("%Y-%m")
    cm = df[df["date"].dt.strftime("%Y-%m")==period]
    cm_exp = cm[cm["ctype"]=="expense"]
    cm_cat = cm_exp.groupby("category")["amount"].sum().reset_index().sort_values("amount", ascending=False)

    if not cm_exp.empty:
        cm_exp = cm_exp.copy()
        cm_exp["day"] = cm_exp["date"].dt.day
        daily = cm_exp.groupby("day")["amount"].sum().sort_index().cumsum().reset_index()
        days_in_month = calendar.monthrange(today.year, today.month)[1]
        budgets = Budget.query.filter_by(user_id=current_user.id, period=period).all()
        budget_total = float(sum([b.target_amount for b in budgets])) if budgets else 0.0
        spent_total = float(cm_exp["amount"].sum())
        daily["budget_line"] = [(budget_total/days_in_month)*int(d) for d in daily["day"]]
        daily_cum = [{"day": int(r["day"]), "spent_cum": round(float(r["amount"]),2), "budget_line": round(float(r["budget_line"]),2)} for _, r in daily.iterrows()]
    else:
        daily_cum = []
        budgets = Budget.query.filter_by(user_id=current_user.id, period=period).all()
        budget_total = float(sum([b.target_amount for b in budgets])) if budgets else 0.0
        spent_total = 0.0

    budget_progress = []
    if budgets:
        by_cat = cm_exp.groupby("category")["amount"].sum().to_dict() if not cm_exp.empty else {}
        for b in budgets:
            cat_name = Category.query.get(b.category_id).name
            spent = float(by_cat.get(cat_name, 0.0))
            bud = float(b.target_amount)
            pct = (spent / bud * 100.0) if bud > 0 else 0.0
            budget_progress.append({"category": cat_name, "spent": round(spent,2), "budget": bud, "pct": round(pct,1)})
        budget_progress.sort(key=lambda x: x["pct"], reverse=True)

    return jsonify({
        "timeseries": [{"month": m.strftime("%Y-%m"), "net": round(v,2)} for m, v in zip(net["month"], net["net"])],
        "income_ts": [{"month": m.strftime("%Y-%m"), "income": round(v,2)} for m, v in zip(inc["month"], inc["amount"])],
        "expense_ts": [{"month": m.strftime("%Y-%m"), "expense": round(v,2)} for m, v in zip(exp["month"], exp["amount"])],
        "categories": [{"category": r["category"], "amount": round(r["amount"],2)} for _, r in cat_split.iterrows()],
        "cm_categories": [{"category": r["category"], "amount": round(r["amount"],2)} for _, r in cm_cat.iterrows()],
        "daily_cum": daily_cum,
        "budget_total": round(budget_total,2),
        "spent_total": round(spent_total,2),
        "budget_progress": budget_progress
    })

@bp.route("/transactions")
@login_required
def transactions_list():
    q = Transaction.query.filter_by(user_id=current_user.id, is_deleted=False).order_by(Transaction.date.desc(), Transaction.id.desc())
    return render_template("transactions_list.html", txns=q.all(), categories=Category.query.all())

@bp.route("/transactions/add", methods=["GET","POST"])
@login_required
def transactions_add():
    if request.method == "POST":
        d = datetime.fromisoformat(request.form.get("date")).date()
        amount = float(request.form.get("amount", "0"))
        category_id = int(request.form.get("category_id"))
        desc = request.form.get("description","")
        tags = request.form.get("tags","")
        t = Transaction(user_id=current_user.id, category_id=category_id, date=d, amount=amount, description=desc, tags=tags)
        t.dup_hash = t.compute_dup_hash()
        db.session.add(t); db.session.commit()
        flash("Transaction added.", "success")
        return redirect(url_for("core.transactions_list"))
    return render_template("transaction_form.html", categories=Category.query.all(), txn=None)

@bp.route("/transactions/<int:txn_id>/edit", methods=["GET","POST"])
@login_required
def transactions_edit(txn_id):
    t = Transaction.query.get_or_404(txn_id)
    if t.user_id != current_user.id:
        flash("Not allowed.", "danger"); return redirect(url_for("core.transactions_list"))
    if request.method == "POST":
        t.date = datetime.fromisoformat(request.form.get("date")).date()
        t.amount = float(request.form.get("amount","0"))
        t.category_id = int(request.form.get("category_id"))
        t.description = request.form.get("description","")
        t.tags = request.form.get("tags","")
        t.dup_hash = t.compute_dup_hash()
        db.session.commit()
        flash("Transaction updated.", "success")
        return redirect(url_for("core.transactions_list"))
    return render_template("transaction_form.html", categories=Category.query.all(), txn=t)

@bp.route("/transactions/<int:txn_id>/delete")
@login_required
def transactions_delete(txn_id):
    t = Transaction.query.get_or_404(txn_id)
    if t.user_id != current_user.id:
        flash("Not allowed.", "danger"); return redirect(url_for("core.transactions_list"))
    t.is_deleted = True; db.session.commit()
    flash("Transaction deleted (soft).", "info")
    return redirect(url_for("core.transactions_list"))

@bp.route("/transactions/import", methods=["POST"])
@login_required
def transactions_import():
    f = request.files.get("csvfile")
    if not f:
        flash("No file uploaded.", "warning"); return redirect(url_for("core.transactions_list"))
    df = pd.read_csv(f)
    df.columns = [c.lower() for c in df.columns]
    required = {"date","description","amount","type","category"}
    if not required.issubset(set(df.columns)):
        flash("CSV must include columns: date, description, amount, type, category.", "danger")
        return redirect(url_for("core.transactions_list"))
    cats = { (c.name.lower(), c.type): c for c in Category.query.all() }
    for _, row in df.iterrows():
        cname = str(row["category"]).strip()
        ctype = str(row["type"]).strip().lower()
        if (cname.lower(), ctype) not in cats:
            c = Category(name=cname, type=ctype); db.session.add(c); db.session.flush()
            cats[(cname.lower(), ctype)] = c
        d = pd.to_datetime(row["date"]).date()
        amount = float(row["amount"]); desc = str(row.get("description",""))
        cat_id = cats[(cname.lower(), ctype)].id
        t = Transaction(user_id=current_user.id, category_id=cat_id, date=d, amount=amount, description=desc)
        t.dup_hash = t.compute_dup_hash(); db.session.add(t)
    db.session.commit(); flash("CSV imported.", "success")
    return redirect(url_for("core.transactions_list"))

@bp.route("/transactions/export.csv")
@login_required
def transactions_export_csv():
    txns = Transaction.query.filter_by(user_id=current_user.id, is_deleted=False).all()
    out = io.StringIO(); writer = csv.writer(out)
    writer.writerow(["date","description","amount","category","type","tags"])
    for t in txns:
        c = Category.query.get(t.category_id)
        writer.writerow([t.date.isoformat(), t.description, float(t.amount), c.name, c.type, t.tags or ""])
    mem = io.BytesIO(out.getvalue().encode())
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name="transactions.csv")

@bp.route("/categories", methods=["GET","POST"])
@login_required
def categories():
    if request.method == "POST":
        name = request.form.get("name","").strip(); ctype = request.form.get("type","expense")
        if not name: flash("Name required.", "warning")
        else:
            db.session.add(Category(name=name, type=ctype)); db.session.commit()
            flash("Category added.", "success")
        return redirect(url_for("core.categories"))
    return render_template("categories.html", categories=Category.query.order_by(Category.type, Category.name).all())

@bp.route("/categories/<int:cid>/delete")
@login_required
def categories_delete(cid):
    c = Category.query.get_or_404(cid); db.session.delete(c); db.session.commit()
    flash("Category deleted.", "info"); return redirect(url_for("core.categories"))

@bp.route("/budgets", methods=["GET","POST"])
@login_required
def budgets():
    if request.method == "POST":
        category_id = int(request.form.get("category_id"))
        period = request.form.get("period")
        target = float(request.form.get("target_amount","0"))
        b = Budget.query.filter_by(user_id=current_user.id, category_id=category_id, period=period).first()
        if not b: b = Budget(user_id=current_user.id, category_id=category_id, period=period, target_amount=target); db.session.add(b)
        else: b.target_amount = target
        db.session.commit(); flash("Budget saved.", "success")
        return redirect(url_for("core.budgets"))
    items = db.session.query(Budget, Category).join(Category, Budget.category_id==Category.id).filter(Budget.user_id==current_user.id).all()
    return render_template("budgets.html", categories=Category.query.filter_by(type="expense").all(), items=items)

@bp.route("/budgets/<int:bid>/delete")
@login_required
def budgets_delete(bid):
    b = Budget.query.get_or_404(bid)
    if b.user_id != current_user.id: 
        flash("Not allowed.", "danger"); return redirect(url_for("core.budgets"))
    db.session.delete(b); db.session.commit(); flash("Budget deleted.", "info")
    return redirect(url_for("core.budgets"))

@bp.route("/reports")
@login_required
def reports():
    months = db.session.query(extract("year", Transaction.date).label("y"), extract("month", Transaction.date).label("m"))            .filter_by(user_id=current_user.id, is_deleted=False).distinct().order_by("y","m").all()
    periods = [f"{int(y):04d}-{int(m):02d}" for y,m in months]
    return render_template("reports.html", periods=periods)

@bp.route("/reports/<period>")
@login_required
def report_view(period):
    y, m = map(int, period.split("-"))
    start = date(y,m,1)
    end = date(y + (m==12), (m % 12)+1, 1)
    txns = Transaction.query.filter(Transaction.user_id==current_user.id, Transaction.is_deleted==False, Transaction.date>=start, Transaction.date<end).all()
    rows = []
    for t in txns:
        c = Category.query.get(t.category_id)
        rows.append({"date": t.date.isoformat(), "amount": float(t.amount), "type": c.type, "category": c.name, "desc": t.description})
    df = pd.DataFrame(rows)
    income = round(float(df[df["type"]=="income"]["amount"].sum()) if not df.empty else 0.0, 2)
    expense = round(float(df[df["type"]=="expense"]["amount"].sum()) if not df.empty else 0.0, 2)
    by_cat = df[df["type"]=="expense"].groupby("category")["amount"].sum().sort_values(ascending=False) if not df.empty else pd.Series(dtype=float)
    top3 = by_cat.head(3).round(2).to_dict()
    variance = []
    budgets = Budget.query.filter_by(user_id=current_user.id, period=period).all()
    for b in budgets:
        cat = Category.query.get(b.category_id).name
        spent = float(by_cat.get(cat, 0.0))
        variance.append({"category": cat, "spent": round(spent,2), "budget": float(b.target_amount), "delta": round(spent-float(b.target_amount),2)})
    summary = {"income": income, "expense": expense, "balance": round(income-expense,2), "top3": top3, "variance": variance}
    rep = Report.query.filter_by(user_id=current_user.id, period=period).first()
    if not rep: rep = Report(user_id=current_user.id, period=period, summary_json=json.dumps(summary)); db.session.add(rep)
    else: rep.summary_json = json.dumps(summary)
    db.session.commit()
    return render_template("report_view.html", period=period, summary=summary, rows=rows)

@bp.route("/reports/<period>/export.pdf")
@login_required
def report_pdf(period):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm
    rep = Report.query.filter_by(user_id=current_user.id, period=period).first()
    if not rep:
        flash("Generate the report first by viewing it.", "warning")
        return redirect(url_for("core.reports"))
    summary = json.loads(rep.summary_json)
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4; y = height - 2*cm
    c.setFont("Helvetica-Bold", 16); c.drawString(2*cm, y, f"Monthly Report - {period}"); y -= 1*cm
    c.setFont("Helvetica", 12)
    c.drawString(2*cm, y, f"Income: {summary['income']}"); y -= 0.6*cm
    c.drawString(2*cm, y, f"Expense: {summary['expense']}"); y -= 0.6*cm
    c.drawString(2*cm, y, f"Balance: {summary['balance']}"); y -= 1*cm
    c.setFont("Helvetica-Bold", 12); c.drawString(2*cm, y, "Top 3 Expenses:"); y -= 0.6*cm
    c.setFont("Helvetica", 12)
    for k,v in summary.get("top3",{}).items():
        c.drawString(2.5*cm, y, f"- {k}: {v}"); y -= 0.5*cm
    y -= 0.4*cm
    c.setFont("Helvetica-Bold", 12); c.drawString(2*cm, y, "Budget Variance:"); y -= 0.6*cm
    c.setFont("Helvetica", 12)
    for v in summary.get("variance", []):
        c.drawString(2.5*cm, y, f"- {v['category']}: Spent {v['spent']} vs Budget {v['budget']} (Δ {v['delta']})"); y -= 0.5*cm
        if y < 2*cm: c.showPage(); y = height - 2*cm
    c.showPage(); c.save(); buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f"report_{period}.pdf", mimetype="application/pdf")

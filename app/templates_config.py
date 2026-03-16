"""
app/templates_config.py
Single shared Jinja2Templates instance used by ALL routers.
Filters are registered here once, available everywhere.
"""
from datetime import datetime
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")


# ── Filters ───────────────────────────────────────────────────

def _dtformat(value, fmt="%d %b %Y, %H:%M"):
    if not value:
        return "—"
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.strftime(fmt)

def _dateonly(value):
    return _dtformat(value, "%d %b %Y")

def _currency(value, currency="GBP"):
    if value is None:
        return "N/A"
    sym = {"GBP": "£", "USD": "$", "EUR": "€", "INR": "₹"}.get(currency, currency + " ")
    return f"{sym}{value:,.2f}"

templates.env.filters["dtformat"]  = _dtformat
templates.env.filters["dateonly"]  = _dateonly
templates.env.filters["currency"]  = _currency

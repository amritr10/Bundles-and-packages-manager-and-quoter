import streamlit as st
from addlify import Addlify
import json

COMPANY_LIST_URL = (
    "https://store.omron.com.au/backend-portal/customers/all-customer-data?cached=true"
)
MODELS_JSON_PATH = "model-list-reduced-250904.json"

def login_to_addlify(email, password):
    """Attempts to log into Addlify and returns an Addlify object."""
    try:
        adder = Addlify(email, password)
        if not getattr(adder, "logged_in", False):
            return None, "Login failed. Check credentials."
        return adder, "✅ Logged in"
    except Exception as e:
        return None, f"Login error: {e}"

def fetch_all_companies(adder):
    """Fetch all customers via the authenticated Addlify session."""
    resp = adder.get(COMPANY_LIST_URL, headers={"Accept": "application/json"})
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch companies ({resp.status_code}): {resp.text[:200]!r}")
    try:
        payload = resp.json()
        return payload["customerData"]["allCustomers"]["dataSource"]
    except (ValueError, KeyError) as e:
        raise RuntimeError(f"Unexpected JSON structure in companies response: {e}")

def load_models():
    """Load and flatten your local models JSON file."""
    try:
        with open(MODELS_JSON_PATH, "r") as f:
            data = json.load(f)
    except Exception as e:
        raise FileNotFoundError(f"Could not open models JSON: {e}")
    models = []
    for bucket in data.values():
        models.extend(bucket)
    return models

def get_contacts_for(adder, company_id):
    """Retrieve contacts for a company via Addlify."""
    co_info = adder.get_company_info(company_id)
    return co_info.get("contacts", [])

def create_new_quote(adder, company_id, title, expiry_date, contact_id):
    """Create a new quote, return the quoteId."""
    resp = adder.new_quote(company_id, title, expiry_date, contact_id, True, "")
    resp.raise_for_status()
    return resp.json().get("quoteId")

def get_quote_info(adder, company_id, quote_id):
    """Fetch quote info (with sections)."""
    return adder.get_quote_info(company_id, quote_id)

def add_line_item_to_quote(
    adder, company_id, quote_id, section_id,
    product_id, price, quantity, min_quantity
):
    """Add a single line item to a quote."""
    return adder.add_item_to_quote(
        company_id, quote_id, section_id,
        product_id, price, quantity, min_quantity
    )

def fetch_quote_url(adder, company_id, quote_id):
    """Get the public URL for a quote."""
    return adder.get_quote_url(company_id, quote_id)

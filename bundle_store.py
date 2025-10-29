import streamlit as st
import pandas as pd
import uuid
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- Google Sheets Connection ---

def get_connection():
    """Creates and returns a connection to Google Sheets."""
    return st.connection("gsheets", type=GSheetsConnection)

# --- Data Loading and Schema ---

def get_worksheet(conn, worksheet_name):
    """Retrieves a worksheet, creating it with headers if it doesn't exist."""
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        return df
    except Exception as e:
        # A more robust way to check if the sheet or worksheet exists is needed.
        # For now, we assume an error means it needs creation.
        st.warning(f"Could not read worksheet {worksheet_name}. It might be created. Error: {e}")
        # This part of the code is tricky because streamlit_gsheets doesn't
        # directly support creating a worksheet. This has to be done manually in Google Sheets first.
        # We will assume the worksheets 'bundles', 'user_stats', and 'quote_log' exist.
        return pd.DataFrame()


def get_bundle_definitions_df():
    """Loads the bundle definitions from the 'bundles' worksheet."""
    conn = get_connection()
    return get_worksheet(conn, "bundles")

def get_user_stats_df():
    """Loads user login stats from the 'user_stats' worksheet."""
    conn = get_connection()
    return get_worksheet(conn, "user_stats")

def get_quote_log_df():
    """Loads the quote log from the 'quote_log' worksheet."""
    conn = get_connection()
    return get_worksheet(conn, "quote_log")

# --- Bundle Management ---

def save_bundle(
    bundle_name, bundle_items, user_id,
    description="", tags="", source_model_json="", bundle_type="Standard"
):
    """
    Saves a new bundle or a new version of an existing bundle to the 'bundles' worksheet.
    """
    conn = get_connection()
    df = get_bundle_definitions_df()

    new_version = 1
    if not df.empty:
        existing_bundles = df[df["bundle_name"] == bundle_name]
        if not existing_bundles.empty:
            new_version = existing_bundles["bundle_version"].max() + 1

    bundle_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    
    new_rows = []
    for item in bundle_items:
        new_row = {
            "bundle_id": bundle_id,
            "bundle_name": bundle_name,
            "bundle_version": new_version,
            "status": "active",
            "bundle_type": bundle_type,
            "parent_model_id": item.get("parent_model_id"),
            "parent_group_name": item.get("parent_group_name"),
            "dependent_model_id": item.get("dependent_model_id"),
            "dependent_group_name": item.get("dependent_group_name"),
            "mapping_type": item.get("mapping_type"),
            "multiple": item.get("multiple"),
            "quantity": item.get("quantity"),
            "min_quantity": item.get("min_quantity"),
            "price_override": item.get("price_override"),
            "notes": description,
            "created_by": user_id, # Changed from user_email
            "created_at": created_at,
            "source_model_json": source_model_json,
            "user_id": user_id
        }
        new_rows.append(new_row)

    new_df = pd.DataFrame(new_rows)
    updated_df = pd.concat([df, new_df], ignore_index=True)
    conn.update(worksheet="bundles", data=updated_df)
    return bundle_id, new_version

def load_bundles(user_id=None, active_only=True):
    """
    Loads the latest version of each bundle.
    If user_id is provided, it filters for that user's bundles.
    """
    df = get_bundle_definitions_df()
    if df.empty:
        return pd.DataFrame()

    if user_id:
        df = df[df["user_id"] == user_id]

    latest_versions = df.loc[df.groupby("bundle_name")["bundle_version"].idxmax()]
    
    if active_only:
        return latest_versions[latest_versions["status"] == "active"]
    return latest_versions

def get_bundle_details(bundle_name, version=None):
    """
    Retrieves all items for a specific bundle name and version.
    If version is None, it fetches the latest version.
    """
    df = get_bundle_definitions_df()
    bundle_df = df[df["bundle_name"] == bundle_name]

    if bundle_df.empty:
        return None

    if version is None:
        version = bundle_df["bundle_version"].max()
        
    return bundle_df[bundle_df["bundle_version"] == version]

def delete_bundle(bundle_name, user_id):
    """
    Deletes all versions of a bundle if the user is the owner.
    """
    conn = get_connection()
    df = get_bundle_definitions_df()
    
    bundle_to_delete = df[(df["bundle_name"] == bundle_name) & (df["user_id"] == user_id)]
    
    if bundle_to_delete.empty:
        return False, "Bundle not found or you do not have permission to delete it."

    df = df.drop(bundle_to_delete.index)
    conn.update(worksheet="bundles", data=df)
    return True, f"Bundle '{bundle_name}' has been deleted."


def deprecate_bundle(bundle_name, user_id):
    """
    Marks all versions of a bundle as 'deprecated'.
    This is done by creating a new version with the status 'deprecated'.
    """
    conn = get_connection()
    df = get_bundle_definitions_df()
    
    latest_bundle_items = get_bundle_details(bundle_name)
    if latest_bundle_items is None or latest_bundle_items.iloc[0]["user_id"] != user_id:
        return False, "Bundle not found or you do not have permission to deprecate it."

    new_version = latest_bundle_items["bundle_version"].iloc[0] + 1
    
    deprecated_rows = latest_bundle_items.copy()
    deprecated_rows["bundle_version"] = new_version
    deprecated_rows["status"] = "deprecated"
    deprecated_rows["created_by"] = user_id
    deprecated_rows["created_at"] = datetime.now().isoformat()
    
    updated_df = pd.concat([df, deprecated_rows], ignore_index=True)
    conn.update(worksheet="bundles", data=updated_df)
    
    return True, f"Bundle '{bundle_name}' marked as deprecated (Version {new_version})."

# --- Logging ---

def log_user_login(user_id):
    """Logs a user login event to the 'user_stats' worksheet."""
    if not user_id:
        return

    conn = get_connection()
    df = get_user_stats_df()
    
    now = datetime.now().isoformat()

    if df.empty:
        # If the dataframe is empty, create it with the first user
        df = pd.DataFrame([{"user_id": user_id, "last_login": now, "login_count": 1}])
    elif user_id in df["user_id"].values:
        user_row = df[df["user_id"] == user_id]
        df.loc[user_row.index, "last_login"] = now
        df.loc[user_row.index, "login_count"] += 1
    else:
        new_row = pd.DataFrame([{
            "user_id": user_id,
            "last_login": now,
            "login_count": 1
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        
    conn.update(worksheet="user_stats", data=df)

def log_quote(user_id, bundle_name, total_value, quote_url):
    """Logs a created quote to the 'quote_log' worksheet."""
    conn = get_connection()
    df = get_quote_log_df()
    
    new_row = pd.DataFrame([{
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "bundle_name": bundle_name,
        "total_value": total_value,
        "quote_url": quote_url
    }])
    
    updated_df = pd.concat([df, new_row], ignore_index=True)
    conn.update(worksheet="quote_log", data=updated_df)
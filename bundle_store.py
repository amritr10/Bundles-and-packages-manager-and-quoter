import pandas as pd
import uuid
from datetime import datetime
import os

BUNDLE_DEFS_PATH = "bundle_definitions.csv"

def get_bundle_definitions_df():
    """Loads the bundle definitions CSV, creating it if it doesn't exist."""
    if not os.path.exists(BUNDLE_DEFS_PATH):
        df = pd.DataFrame(columns=[
            "bundle_id", "bundle_name", "bundle_version", "status",
            "parent_model_id", "parent_group_name", "dependent_model_id",
            "dependent_group_name", "mapping_type", "multiple", "quantity",
            "min_quantity", "price_override", "notes", "created_by",
            "created_at", "source_model_json"
        ])
        df.to_csv(BUNDLE_DEFS_PATH, index=False)
        return df
    return pd.read_csv(BUNDLE_DEFS_PATH)

def save_bundle(
    bundle_name, bundle_items, user_email,
    description="", tags="", source_model_json=""
):
    """
    Saves a new bundle or a new version of an existing bundle to the CSV.
    Each item in the bundle is saved as a separate row.
    """
    df = get_bundle_definitions_df()

    # Check if a bundle with this name already exists to increment version
    existing_bundles = df[df["bundle_name"] == bundle_name]
    new_version = 1
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
            "parent_model_id": item.get("parent_model_id"),
            "parent_group_name": item.get("parent_group_name"),
            "dependent_model_id": item.get("dependent_model_id"),
            "dependent_group_name": item.get("dependent_group_name"),
            "mapping_type": item.get("mapping_type"),
            "multiple": item.get("multiple"),
            "quantity": item.get("quantity"),
            "min_quantity": item.get("min_quantity"),
            "price_override": item.get("price_override"),
            "notes": description, # Notes are at bundle level
            "created_by": user_email,
            "created_at": created_at,
            "source_model_json": source_model_json
        }
        new_rows.append(new_row)

    new_df = pd.DataFrame(new_rows)
    updated_df = pd.concat([df, new_df], ignore_index=True)
    updated_df.to_csv(BUNDLE_DEFS_PATH, index=False)
    return bundle_id, new_version

def load_bundles(active_only=True):
    """
    Loads the latest version of each bundle.
    If active_only is True, it only returns bundles with status 'active'.
    """
    df = get_bundle_definitions_df()
    if df.empty:
        return pd.DataFrame()

    # Get the latest version for each bundle name
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

def deprecate_bundle(bundle_name, user_email):
    """
    Marks all versions of a bundle as 'deprecated'.
    This is done by creating a new version with the status 'deprecated'.
    """
    df = get_bundle_definitions_df()
    
    # Find the latest version of the bundle
    latest_bundle_items = get_bundle_details(bundle_name)
    if latest_bundle_items is None:
        return False, "Bundle not found."

    # Create a new version that is identical but for status and version number
    new_version = latest_bundle_items["bundle_version"].iloc[0] + 1
    
    deprecated_rows = latest_bundle_items.copy()
    deprecated_rows["bundle_version"] = new_version
    deprecated_rows["status"] = "deprecated"
    deprecated_rows["created_by"] = user_email
    deprecated_rows["created_at"] = datetime.now().isoformat()
    
    updated_df = pd.concat([df, deprecated_rows], ignore_index=True)
    updated_df.to_csv(BUNDLE_DEFS_PATH, index=False)
    
    return True, f"Bundle '{bundle_name}' marked as deprecated (Version {new_version})."

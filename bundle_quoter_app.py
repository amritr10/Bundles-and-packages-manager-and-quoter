import streamlit as st
import pandas as pd
import datetime
import io
from streamlit_gsheets import GSheetsConnection
import re

# Internal imports
import bundle_store
import quoting_utils
import association_utils

st.set_page_config(page_title="Bundle Quoter", layout="wide")

SPECIAL_USERS = ["amrit.ramadugu@omron.com", "arvey.e@ssa.omron.com", "chandan.khanal@omron.com"]

# --- Helper Functions ---

def is_special_user():
    """Checks if the current user is a special user."""
    return st.session_state.get("user_id") in SPECIAL_USERS

def initialize_session_state():
    """Initialize session state variables."""
    if "adder" not in st.session_state:
        st.session_state.adder = None
    if "companies" not in st.session_state:
        st.session_state.companies = []
    if "models" not in st.session_state:
        st.session_state.models = []
    if "user_id" not in st.session_state:
        st.session_state.user_id = ""
    if "bundle_builder_items" not in st.session_state:
        st.session_state.bundle_builder_items = [{"parent_model_id": None, "dependents": []}]

# --- Sidebar (Login & Navigation) ---

def render_sidebar():
    """Render the sidebar for login and navigation."""
    st.sidebar.title("Bundle Quoter")

    # --- Login Section ---
    st.sidebar.header("🔑 Login to Addlify")
    if st.session_state.adder:
        st.sidebar.success(f"Logged in as {st.session_state.user_id}")
        if st.sidebar.button("Logout"):
            st.session_state.adder = None
            st.session_state.user_id = ""
            st.session_state.companies = []
            st.session_state.models = []
            st.rerun()
    else:
        email = st.sidebar.text_input("Email", key="login_email")
        password = st.sidebar.text_input("Password", type="password", key="login_password")
        if st.sidebar.button("Login"):
            if not email:
                st.sidebar.error("Please enter your email address to log in.")
            else:
                with st.spinner("Logging in..."):
                    adder, message = quoting_utils.login_to_addlify(email, password)
                    if adder:
                        st.session_state.adder = adder
                        st.session_state.user_id = email  # Set user_id to Addlify email
                        st.sidebar.success(message)
                        bundle_store.log_user_login(st.session_state.user_id)
                        # Preload data on login
                        with st.spinner("Loading companies and models..."):
                            st.session_state.companies = quoting_utils.fetch_all_companies(adder)
                            st.session_state.models = pd.DataFrame(quoting_utils.load_models())
                        st.rerun()
                    else:
                        st.sidebar.error(message)

    st.sidebar.markdown("---")
    
    # --- Navigation ---
    navigation_options = ["Bundle Builder", "My Bundles", "All Bundles", "Promotion Bundles", "Quote Page"]
    if is_special_user():
        navigation_options.extend(["User Login Log", "Quote Log"])

    page = st.sidebar.radio(
        "Navigation",
        navigation_options,
        key="page_selection"
    )
    return page

# --- Page Implementations ---

def page_bundle_builder():
    """Page for creating and editing bundles."""
    st.header("📦 Bundle Builder")

    if 'bundle_saved_success' in st.session_state:
        st.success(st.session_state.bundle_saved_success)
        del st.session_state.bundle_saved_success
        # Clear form for the next entry
        st.session_state.bundle_name = ""
        st.session_state.bundle_desc = ""
        st.session_state.bundle_builder_items = [{"parent_model_id": None, "dependents": []}]

    if not st.session_state.get("adder"):
        st.warning("Please log in to Addlify via the sidebar to create bundles.")
        return

    models_df = st.session_state.get("models", pd.DataFrame())
    if models_df.empty:
        st.warning("Models not loaded. Please log in to load model data.")
        return

    bundle_name = st.text_input("Bundle Name", key="bundle_name")
    bundle_desc = st.text_area("Bundle Description", key="bundle_desc")
    
    bundle_type = "Standard"
    if is_special_user():
        if st.checkbox("Mark as Promotion Bundle"):
            bundle_type = "Promotion"

    st.subheader("Bundle Items")

    items = st.session_state.bundle_builder_items
    
    # --- Parent Selection ---
    parent_item = items[0]
    st.markdown("**Parent Product**")
    parent_cols = st.columns([4, 1])
    parent_model = parent_cols[0].selectbox(
        "Select Parent Model",
        options=models_df.to_dict('records'),
        format_func=lambda m: f"{m['modelNumber']} (SKU: {m['skuCode']})",
        key="parent_model_select"
    )
    parent_item['price_override'] = parent_cols[1].number_input(
        "Price Override", min_value=0.0, value=parent_item.get('price_override', 0.0), 
        step=0.01, key="parent_price_override"
    )
    parent_item['parent_model_id'] = parent_model['id'] if parent_model else None
    parent_item['parent_group_name'] = parent_model['modelNumber'] if parent_model else ""


    # --- Dependent Selection ---
    st.markdown("**Dependent Products**")
    
    for i, dep in enumerate(parent_item.get('dependents', [])):
        st.markdown(f"---")
        cols = st.columns([4, 2, 2, 1])
        dep_model = cols[0].selectbox(
            f"Dependent Model #{i+1}",
            options=models_df.to_dict('records'),
            format_func=lambda m: f"{m['modelNumber']} (SKU: {m['skuCode']})",
            key=f"dep_model_{i}",
            index=dep.get('model_index', 0)
        )
        
        dep['dependent_model_id'] = dep_model['id'] if dep_model else None
        dep['dependent_group_name'] = dep_model['modelNumber'] if dep_model else ""
        dep['model_index'] = models_df.to_dict('records').index(dep_model) if dep_model else 0

        if is_special_user():
            dep['mapping_type'] = cols[1].selectbox(
                "Mapping", ["Objective", "Subjective"], key=f"map_type_{i}",
                index=["Objective", "Subjective"].index(dep.get('mapping_type', 'Objective'))
            )
            dep['multiple'] = cols[2].number_input("Multiple", min_value=0.1, value=dep.get('multiple', 1.0), step=0.1, key=f"multiple_{i}")
        else:
            dep['mapping_type'] = "Objective"
            dep['multiple'] = 1.0

        dep['quantity'] = cols[2].number_input("Default Qty", min_value=1, value=dep.get('quantity', 1), step=1, key=f"qty_{i}")
        dep['price_override'] = cols[3].number_input("Price Override", min_value=0.0, value=dep.get('price_override', 0.0), step=0.01, key=f"price_{i}")

        if cols[3].button("❌", key=f"remove_dep_{i}"):
            parent_item['dependents'].pop(i)
            st.rerun()

    if st.button("➕ Add Dependent"):
        parent_item.setdefault('dependents', []).append({})
        st.rerun()

    # --- Save Bundle ---
    st.markdown("---")
    if st.button("💾 Save Bundle", type="primary"):
        if not bundle_name:
            st.error("Bundle Name is required.")
        elif not parent_item['parent_model_id']:
            st.error("A parent model must be selected.")
        else:
            bundle_items_to_save = []
            # Parent is an item too
            bundle_items_to_save.append({
                "parent_model_id": None,
                "parent_group_name": "root",
                "dependent_model_id": parent_item['parent_model_id'],
                "dependent_group_name": parent_item['parent_group_name'],
                "mapping_type": "root",
                "multiple": 1,
                "quantity": 1,
                "min_quantity": 1,
                "price_override": parent_item.get('price_override', 0.0)
            })
            # Add dependents
            for dep in parent_item.get('dependents', []):
                bundle_items_to_save.append({
                    "parent_model_id": parent_item['parent_model_id'],
                    "parent_group_name": parent_item['parent_group_name'],
                    "dependent_model_id": dep['dependent_model_id'],
                    "dependent_group_name": dep['dependent_group_name'],
                    "mapping_type": dep['mapping_type'],
                    "multiple": dep['multiple'],
                    "quantity": dep['quantity'],
                    "min_quantity": dep.get('min_quantity', 1),
                    "price_override": dep.get('price_override', 0.0)
                })

            bundle_id, version = bundle_store.save_bundle(
                bundle_name, bundle_items_to_save, st.session_state.user_id,
                description=bundle_desc, bundle_type=bundle_type
            )
            st.session_state.bundle_saved_success = f"✅ Bundle '{bundle_name}' saved as Version {version} (ID: {bundle_id})"
            st.rerun()

def page_my_bundles():
    """Page for viewing and managing the user's own bundles."""
    st.header("📚 My Bundles")

    if not st.session_state.adder:
        st.warning("Please log in to see your bundles.")
        return

    bundles_df = bundle_store.load_bundles(user_id=st.session_state.user_id)
    
    if bundles_df.empty:
        st.info("No bundles found for your user. Create one in the Bundle Builder.")
        return

    st.dataframe(bundles_df[['bundle_name', 'bundle_version', 'status', 'created_at', 'notes']].rename(columns={'notes': 'Description'}), use_container_width=True)

    selected_bundle_name = st.selectbox("Select a bundle to view, edit, or delete", options=bundles_df['bundle_name'].unique())

    if selected_bundle_name:
        bundle_details = bundle_store.get_bundle_details(selected_bundle_name)
        st.subheader(f"Details for: {selected_bundle_name} (v{bundle_details['bundle_version'].iloc[0]}) ")
        
        total_cost = (bundle_details['price_override'] * bundle_details['quantity']).sum()
        st.metric("Total Bundle Cost", f"${total_cost:,.2f}")

        display_df = bundle_details.copy()
        display_df['Role'] = display_df['mapping_type'].apply(lambda x: 'Parent' if x == 'root' else 'Dependent')
        
        columns_to_show = ['Role', 'dependent_group_name', 'quantity', 'price_override']
        if is_special_user():
            columns_to_show.extend(['mapping_type', 'multiple'])
            
        st.dataframe(display_df[columns_to_show].rename(columns={'dependent_group_name': 'Product', 'price_override': 'Price'}), use_container_width=True)

        col1, col2, col3 = st.columns(3)
        if col1.button("📝 Edit this Bundle"):
            st.warning("Edit functionality not yet implemented.")
        
        if col2.button("🗑️ Delete this Bundle", type="secondary"):
            success, message = bundle_store.delete_bundle(selected_bundle_name, st.session_state.user_id)
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

        if col3.button("➡️ Go to Quote Page with this Bundle", type="primary"):
            st.session_state.quote_page_preselected_bundles = [selected_bundle_name]
            st.session_state.page_selection = "Quote Page"
            st.rerun()

def page_all_bundles():
    """Page for viewing all bundles from all users."""
    st.header("🌐 All Bundles")
    
    bundles_df = bundle_store.load_bundles() # No user_id filter
    
    if bundles_df.empty:
        st.info("No bundles found.")
        return

    st.dataframe(bundles_df[['bundle_name', 'bundle_version', 'status', 'created_by', 'created_at', 'notes']].rename(columns={'notes': 'Description'}), use_container_width=True)

    selected_bundle_name = st.selectbox("Select a bundle to view details", options=bundles_df['bundle_name'].unique())

    if selected_bundle_name:
        bundle_details = bundle_store.get_bundle_details(selected_bundle_name)
        st.subheader(f"Details for: {selected_bundle_name} (v{bundle_details['bundle_version'].iloc[0]}) by {bundle_details['created_by'].iloc[0]}")
        
        total_cost = (bundle_details['price_override'] * bundle_details['quantity']).sum()
        st.metric("Total Bundle Cost", f"${total_cost:,.2f}")

        display_df = bundle_details.copy()
        display_df['Role'] = display_df['mapping_type'].apply(lambda x: 'Parent' if x == 'root' else 'Dependent')
        
        columns_to_show = ['Role', 'dependent_group_name', 'quantity', 'price_override']
        if is_special_user():
            columns_to_show.extend(['mapping_type', 'multiple'])
            
        st.dataframe(display_df[columns_to_show].rename(columns={'dependent_group_name': 'Product', 'price_override': 'Price'}), use_container_width=True)

        if st.button("➡️ Go to Quote Page with this Bundle", type="primary"):
            st.session_state.quote_page_preselected_bundles = [selected_bundle_name]
            st.session_state.page_selection = "Quote Page"
            st.rerun()

def page_promotion_bundles():
    """Page for viewing promotion bundles."""
    st.header("🌟 Promotion Bundles")
    
    bundles_df = bundle_store.load_bundles()
    if bundles_df.empty:
        st.info("No bundles found.")
        return

    promotion_bundles = bundles_df[bundles_df['bundle_type'] == 'Promotion']

    if promotion_bundles.empty:
        st.info("No promotion bundles found.")
        return

    st.dataframe(promotion_bundles[['bundle_name', 'bundle_version', 'status', 'created_by', 'created_at', 'notes']].rename(columns={'notes': 'Description'}), use_container_width=True)

    selected_bundle_name = st.selectbox("Select a bundle to view details", options=promotion_bundles['bundle_name'].unique())

    if selected_bundle_name:
        bundle_details = bundle_store.get_bundle_details(selected_bundle_name)
        st.subheader(f"Details for: {selected_bundle_name} (v{bundle_details['bundle_version'].iloc[0]}) by {bundle_details['created_by'].iloc[0]}")
        
        total_cost = (bundle_details['price_override'] * bundle_details['quantity']).sum()
        st.metric("Total Bundle Cost", f"${total_cost:,.2f}")

        display_df = bundle_details.copy()
        display_df['Role'] = display_df['mapping_type'].apply(lambda x: 'Parent' if x == 'root' else 'Dependent')
        
        columns_to_show = ['Role', 'dependent_group_name', 'quantity', 'price_override']
        if is_special_user():
            columns_to_show.extend(['mapping_type', 'multiple'])
            
        st.dataframe(display_df[columns_to_show].rename(columns={'dependent_group_name': 'Product', 'price_override': 'Price'}), use_container_width=True)

        if st.button("➡️ Go to Quote Page with this Bundle", type="primary"):
            st.session_state.quote_page_preselected_bundles = [selected_bundle_name]
            st.session_state.page_selection = "Quote Page"
            st.rerun()

def page_quote():
    """Page for creating a quote from bundles."""
    st.header("💵 Quote Page")

    if not st.session_state.adder:
        st.warning("Please log in to Addlify via the sidebar to create quotes.")
        st.stop()

    # --- Company and Contact Selection ---
    companies = st.session_state.get("companies", [])
    if not companies:
        st.error("Company list not loaded.")
        st.stop()

    selected_company = st.selectbox(
        "Select Company",
        options=companies,
        format_func=lambda c: f"{c['displayName']} ({c['amplifyId']})",
        key="quote_company"
    )
    company_id = selected_company["customerId"]

    contacts = quoting_utils.get_contacts_for(st.session_state.adder, company_id)
    selected_contact = st.selectbox(
        "Select Contact",
        options=contacts,
        format_func=lambda c: f"{c.get('displayName','')} <{c.get('emailAddress','')}>",
        key="quote_contact"
    )
    contact_id = selected_contact["id"]

    # --- Quote Metadata ---
    quote_title = st.text_input("Quote Title", key="quote_title_main")
    expiry_date = st.date_input("Expiry Date", datetime.date.today() + datetime.timedelta(days=30))

    # --- Bundle Selection ---
    st.subheader("Select Bundles")
    all_bundles = bundle_store.load_bundles()
    selected_bundles = st.multiselect(
        "Choose bundles to add to the quote",
        options=all_bundles['bundle_name'].tolist(),
        default=st.session_state.get('quote_page_preselected_bundles', [])
    )

    # --- Line Item Preview and Overrides ---
    st.subheader("Quote Line Items")
    if not selected_bundles:
        st.info("Select one or more bundles to see the line items.")
    else:
        line_items = []
        for bundle_name in selected_bundles:
            bundle_details = bundle_store.get_bundle_details(bundle_name)
            if bundle_details is not None:
                line_items.extend(bundle_details.to_dict('records'))
        
        if 'quote_line_items' not in st.session_state or st.session_state.get('last_selected_bundles') != selected_bundles:
            st.session_state.quote_line_items = line_items
            st.session_state.last_selected_bundles = selected_bundles

        items_df = pd.DataFrame(st.session_state.quote_line_items)
        
        edited_items = st.data_editor(
            items_df[['dependent_group_name', 'quantity', 'price_override']],
            num_rows="dynamic",
            key="quote_items_editor"
        )
        st.session_state.quote_line_items_edited = edited_items

    # --- Create Quote Button ---
    if st.button("🚀 Create Quote in Addlify", type="primary"):
        if not quote_title:
            st.error("Quote Title is required.")
        elif 'quote_line_items_edited' not in st.session_state or st.session_state.quote_line_items_edited.empty:
            st.error("No line items to quote.")
        else:
            with st.spinner("Creating quote..."):
                try:
                    expiry_str = expiry_date.strftime("%Y-%m-%d")
                    quote_id, quote_url = quoting_utils.create_new_quote(
                        st.session_state.adder, company_id, quote_title, expiry_str, contact_id
                    )
                    
                    info = quoting_utils.get_quote_info(st.session_state.adder, company_id, quote_id)
                    section_id = info.get("sections", [])[-1]["id"]

                    errors = []
                    final_items = pd.merge(
                        pd.DataFrame(st.session_state.quote_line_items),
                        st.session_state.quote_line_items_edited,
                        on='dependent_group_name',
                        suffixes=('', '_edited')
                    )

                    for _, item in final_items.iterrows():
                        try:
                            quoting_utils.add_line_item_to_quote(
                                st.session_state.adder, company_id, quote_id, section_id,
                                product_id=item['dependent_model_id'],
                                price=item['price_override_edited'],
                                quantity=item['quantity_edited'],
                                min_quantity=item.get('min_quantity', 1)
                            )
                        except Exception as e:
                            errors.append({'item': item['dependent_group_name'], 'error': str(e)})
                    
                    total_value = quoting_utils.calculate_total_value(final_items.to_dict('records'))
                    bundle_store.log_quote(st.session_state.user_id, ", ".join(selected_bundles), total_value, quote_url)

                    st.success(f"Quote created successfully! [View on Addlify]({quote_url})")
                    if errors:
                        st.error("Some line items failed to add:")
                        st.json(errors)

                except Exception as e:
                    st.error(f"Failed to create quote: {e}")

def page_user_login_log():
    """Page for viewing user login activity."""
    st.header("📈 User Login Log")
    user_stats_df = bundle_store.get_user_stats_df()
    if user_stats_df.empty:
        st.info("No user login data found.")
    else:
        st.dataframe(user_stats_df, use_container_width=True)

def page_quote_log():
    """Page for viewing the quote history."""
    st.header("📜 Quote Log")
    quote_log_df = bundle_store.get_quote_log_df()
    if quote_log_df.empty:
        st.info("No quote data found.")
    else:
        st.dataframe(quote_log_df, use_container_width=True)

# --- Main App Logic ---

def main():
    """Main function to run the Streamlit app."""
    initialize_session_state()
    page = render_sidebar()

    if page == "Bundle Builder":
        page_bundle_builder()
    elif page == "My Bundles":
        page_my_bundles()
    elif page == "All Bundles":
        page_all_bundles()
    elif page == "Promotion Bundles":
        page_promotion_bundles()
    elif page == "Quote Page":
        page_quote()
    elif page == "User Login Log":
        page_user_login_log()
    elif page == "Quote Log":
        page_quote_log()

if __name__ == "__main__":
    main()
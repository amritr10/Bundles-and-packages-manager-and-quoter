
import streamlit as st
import pandas as pd
import datetime
import io

# Internal imports
import bundle_store
import quoting_utils
import association_utils

st.set_page_config(page_title="Bundle Quoter", layout="wide")

# --- Helper Functions ---

def initialize_session_state():
    """Initialize session state variables."""
    if "adder" not in st.session_state:
        st.session_state.adder = None
    if "companies" not in st.session_state:
        st.session_state.companies = []
    if "models" not in st.session_state:
        st.session_state.models = []
    if "user_email" not in st.session_state:
        st.session_state.user_email = ""
    if "bundle_builder_items" not in st.session_state:
        st.session_state.bundle_builder_items = [{"parent_model_id": None, "dependents": []}]

# --- Sidebar (Login & Navigation) ---

def render_sidebar():
    """Render the sidebar for login and navigation."""
    st.sidebar.title("Bundle Quoter")
    
    # --- Login Section ---
    st.sidebar.header("🔑 Login to Addlify")
    if st.session_state.adder:
        st.sidebar.success(f"Logged in as {st.session_state.user_email}")
        if st.sidebar.button("Logout"):
            st.session_state.adder = None
            st.session_state.user_email = ""
            st.session_state.companies = []
            st.session_state.models = []
            st.rerun()
    else:
        email = st.sidebar.text_input("Email", key="login_email")
        password = st.sidebar.text_input("Password", type="password", key="login_password")
        if st.sidebar.button("Login"):
            with st.spinner("Logging in..."):
                adder, message = quoting_utils.login_to_addlify(email, password)
                if adder:
                    st.session_state.adder = adder
                    st.session_state.user_email = email
                    st.sidebar.success(message)
                    # Preload data on login
                    with st.spinner("Loading companies and models..."):
                        st.session_state.companies = quoting_utils.fetch_all_companies(adder)
                        st.session_state.models = pd.DataFrame(quoting_utils.load_models())
                    st.rerun()
                else:
                    st.sidebar.error(message)

    st.sidebar.markdown("---")
    
    # --- Navigation ---
    page = st.sidebar.radio(
        "Navigation",
        ["Bundle Builder", "Bundle Library", "Quote Page"],
        key="page_selection"
    )
    return page

# --- Page Implementations ---

def page_bundle_builder():
    """Page for creating and editing bundles."""
    st.header("📦 Bundle Builder")
    
    if not st.session_state.get("adder"):
        st.warning("Please log in to Addlify via the sidebar to create bundles.")
        return

    models_df = st.session_state.get("models", pd.DataFrame())
    if models_df.empty:
        st.warning("Models not loaded. Please log in to load model data.")
        return

    bundle_name = st.text_input("Bundle Name", key="bundle_name")
    bundle_desc = st.text_area("Bundle Description", key="bundle_desc")

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

        dep['mapping_type'] = cols[1].selectbox(
            "Mapping", ["Objective", "Subjective"], key=f"map_type_{i}",
            index=["Objective", "Subjective"].index(dep.get('mapping_type', 'Objective'))
        )
        dep['multiple'] = cols[2].number_input("Multiple", min_value=0.1, value=dep.get('multiple', 1.0), step=0.1, key=f"multiple_{i}")
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
                bundle_name, bundle_items_to_save, st.session_state.user_email,
                description=bundle_desc
            )
            st.success(f"✅ Bundle '{bundle_name}' saved as Version {version} (ID: {bundle_id})")
            # Clear form
            st.session_state.bundle_builder_items = [{"parent_model_id": None, "dependents": []}]
            st.session_state.bundle_name = ""
            st.session_state.bundle_desc = ""


def page_bundle_library():
    """Page for viewing and managing existing bundles."""
    st.header("📚 Bundle Library")
    
    bundles_df = bundle_store.load_bundles()
    
    if bundles_df.empty:
        st.info("No bundles found. Create one in the Bundle Builder.")
        return

    st.dataframe(bundles_df[['bundle_name', 'bundle_version', 'status', 'created_by', 'created_at']], use_container_width=True)

    selected_bundle_name = st.selectbox("Select a bundle to view details or quote", options=bundles_df['bundle_name'].unique())

    if selected_bundle_name:
        bundle_details = bundle_store.get_bundle_details(selected_bundle_name)
        st.subheader(f"Details for: {selected_bundle_name} (v{bundle_details['bundle_version'].iloc[0]})")
        
        # Reconstruct for display
        parent_item = bundle_details[bundle_details['mapping_type'] == 'root']
        if not parent_item.empty:
            st.write(f"**Parent:** {parent_item['dependent_group_name'].iloc[0]}")
        
        dependents = bundle_details[bundle_details['mapping_type'] != 'root']
        if not dependents.empty:
            st.write("**Dependents:**")
            st.dataframe(dependents[[
                'dependent_group_name', 'mapping_type', 'multiple', 'quantity'
            ]], use_container_width=True)

        col1, col2 = st.columns(2)
        if col1.button("📝 Edit this Bundle"):
            # Pre-fill the builder page
            st.warning("Edit functionality not yet implemented.") # Placeholder
        
        if col2.button("➡️ Go to Quote Page with this Bundle", type="primary"):
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
        
        # Use st.data_editor to allow overrides
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
                    quote_id = quoting_utils.create_new_quote(
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
                    
                    quote_url = quoting_utils.fetch_quote_url(st.session_state.adder, company_id, quote_id)
                    st.success(f"Quote created successfully! [View on Addlify]({quote_url})")
                    if errors:
                        st.error("Some line items failed to add:")
                        st.json(errors)

                except Exception as e:
                    st.error(f"Failed to create quote: {e}")


# --- Main App Logic ---

def main():
    """Main function to run the Streamlit app."""
    initialize_session_state()
    page = render_sidebar()

    if page == "Bundle Builder":
        page_bundle_builder()
    elif page == "Bundle Library":
        page_bundle_library()
    elif page == "Quote Page":
        page_quote()

if __name__ == "__main__":
    main()

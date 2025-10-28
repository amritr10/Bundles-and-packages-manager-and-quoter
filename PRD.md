# Product Requirements Document (PRD): Bundle Quoter App

## 1. Background & Rationale

Sales frequently needs to quote **composite packages** (bundles) of Omron products. Currently, bundle logic is fragmented across two Streamlit apps:
- **Product Association App**: Defines parent and dependent product groupings with mapping types (“Objective/Subjective”) and multiples, plus analytics and exports.
- **Quote Automater App**: Authenticates to Addlify, selects company/contact, sets quote metadata, chooses models, and pushes line items into a quote.

**Bundle Quoter** unifies these: define bundles once, store them in a single CSV, and generate quotes directly from bundle selections.

---

## 2. Goals & Non‑Goals
**Goals**
- Rapid creation of **bundles** comprising selected models with parent–dependent associations.
- Persist all **new** bundles into **one CSV file**; support loading and editing existing bundles.
- **Quote** generation in Addlify from selected bundles (company/contact selection; line items created automatically).
- Reuse existing **grouping, mapping, and calculation** capabilities and existing **quote pipeline**.
- Provide **auditable** bundle definitions (created by, timestamps) and simple versioning.

**Non‑Goals**
- Replace Addlify’s end-to-end quoting experience.
- Complex pricing rules (beyond per-line item price & quantity).
- Real-time multiuser concurrency management (basic file locking is sufficient for v1).

---

## 3. Users & Use Cases

**Primary users**: Sales engineers, BDMs, PMMs, and inside sales.

**Key use cases**
1. **Create bundle**: Choose parent group, add dependents, set multiples/quantities; save bundle to CSV.
2. **Manage bundles**: Search/load existing bundles, modify, and re-save; deprecate with a flag.
3. **Generate quote from bundle(s)**: Pick company/contact, title, expiry; select bundles; optionally override price/qty; push to Addlify; get public quote link.
4. **Export/inspect**: Download bundle definitions and analytics.

---

## 4. Product Scope & Features

### 4.1 Bundle Builder (Streamlit page/tab)
- **Model/Group selection**: Parent and dependent group inputs, mapping type (Objective/Subjective), multiple, quantity per dependent.
- **Bundle details**: Name, description, tags, created_by, created_at.
- **Add/remove items**: Unlimited dependents; parent may be one or many models.
- **Validation**: Ensure model IDs exist in the models list loaded by quoting code.
- **Persist**: Save as a row-per-line-item in a single CSV. Append only for new bundles; edits create a new revision row.

### 4.2 Bundle Library (Streamlit page/tab)
- Filter/search by bundle_name, creator, tag, active/deprecated.
- Load existing bundle → prefill the Builder controls for editing (creates a new revision).

### 4.3 Quote Page
- **Login** to Addlify (sidebar) using existing login flow and session state.
- **Company & contact selection**: Reuse company/contact selection logic.
- **Quote metadata**: Title, expiry date, optional notes.
- **Choose bundles**: Multiselect bundles, show their items; allow per-item overrides (price, qty, min_qty).
- **Create quote**: Reuse quote creation pipeline; add each bundle line and display public URL.
- **Error summary**: Provide a downloadable Excel log for failed line items.

---

## 5. Data Model & Single-CSV Schema

**File**: `bundle_definitions.csv`

**Row granularity**: one line item per bundle component.

| Column               | Type      | Notes                                                      |
|----------------------|-----------|------------------------------------------------------------|
| bundle_id            | string    | UUIDv4 for the bundle revision                             |
| bundle_name          | string    | Human-friendly name                                        |
| bundle_version       | int       | Incremented per edit (start at 1)                          |
| status               | enum      | `active` / `deprecated`                                    |
| parent_model_id      | string    | Optional: parent model’s ID; or use group name             |
| parent_group_name    | string    | If using groups from association UI                        |
| dependent_model_id   | string    | Model ID for dependent line                                |
| dependent_group_name | string    | Optional grouping label                                    |
| mapping_type         | enum      | `Objective` / `Subjective`                                 |
| multiple             | float     | Multiplier from association UI                             |
| quantity             | int       | Default quantity for this dependent in the bundle          |
| min_quantity         | int       | Minimum allowed quantity                                   |
| price_override       | float     | Optional default price override                            |
| notes                | string    | Free text                                                  |
| created_by           | string    | e.g., user email                                           |
| created_at           | ISO datetime |                                                          |
| source_model_json    | string    | Path/hash of models JSON used                              |

---

## 6. Architecture & Integration

**Pages**
1. **Bundle Builder** (build/edit; saves to CSV)
2. **Bundle Library** (search/load bundles)
3. **Quote** (select company/contact, generate quote)

**Modules**
- `association_utils.py`: Extract reusable helpers from product association app.
- `quoting_utils.py`: Extract Addlify-facing helpers from quote automater app.
- `bundle_store.py`: Read/write single CSV, dedupe, fetch latest version per bundle_name.

**Flow**
- Builder uses association utils to create logical parent–dependent mappings and validate multiples.
- Builder writes the final normalized bundle rows via bundle_store.
- Quote page:
  1. Login & preload companies/models.
  2. Load selected bundle(s) from CSV.
  3. Transform to Addlify line-item payloads.
  4. Create quote → add items → display URL.

---

## 7. UI/UX Requirements

- **Consistent Streamlit nav**: Sidebar radio with three pages; reuse login section from quoting app.
- **Builder controls**: Parent group expanders, dependent group expanders with Objective/Subjective checkboxes and Multiple numeric inputs.
- **Quote page**: Company and contact select boxes, bundle multiselect, items preview table with editable price/qty/min_qty per line.

---

## 8. Functional Requirements

1. **Create bundles**  
   - Input: parent(s), dependent(s), mapping_type, multiple, default quantity & min_quantity, optional price_override.  
   - Output: append rows to `bundle_definitions.csv` with bundle_version incremented if name matches an existing bundle.

2. **Load bundles**  
   - Show latest bundle_version per bundle_name; allow selecting older versions.

3. **Quote generation**  
   - Require Addlify login; choose company & contact; set title and expiry; push line items generated from the bundle(s).

4. **Error handling**  
   - Display failed line items and offer an Excel download of errors.

5. **Model validation**  
   - Bundle Builder must validate selected model IDs exist in the flattened models list.

---


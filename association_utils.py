import re
import pandas as pd

def filter_and_sum(df, search_terms, exclusion_terms=None,
                   column_name='Description', sum_columns=None):
    """Filter by wildcard search_terms (+ exclusions), optionally sum columns."""
    if sum_columns is None:
        sum_columns = ['IA', 'FA']
        
    def pattern(t):
        return '^' + re.escape(t.strip()).replace(r'\*','.*') + '$'
        
    pats = [pattern(t) for t in search_terms if t.strip()]
    if not pats:
        return pd.DataFrame(), {c: 0.0 for c in sum_columns}
        
    rx = re.compile("|".join(pats), flags=re.IGNORECASE)
    mask = df[column_name].astype(str).str.match(rx)
    
    if exclusion_terms:
        ex_pats = [pattern(t) for t in exclusion_terms if t.strip()]
        if ex_pats:
            ex_rx = re.compile("|".join(ex_pats), flags=re.IGNORECASE)
            mask &= ~df[column_name].astype(str).str.match(ex_rx)
            
    sub = df[mask].copy()
    sums = {c: float(sub[c].sum()) if c in sub and pd.api.types.is_numeric_dtype(sub[c]) else 0.0 for c in sum_columns}
    return sub, sums

def validate_model_ids(model_ids, available_models_df):
    """Checks if all provided model IDs exist in the list of available models."""
    if available_models_df.empty:
        return False, ["Model list is empty."]
        
    available_ids = set(available_models_df['id'])
    invalid_ids = [mid for mid in model_ids if mid not in available_ids]
    
    if invalid_ids:
        return False, invalid_ids
    return True, []

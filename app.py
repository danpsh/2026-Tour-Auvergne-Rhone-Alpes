import streamlit as st
import pandas as pd
import unicodedata

# --- 1. SETTINGS & SCORING ---
st.set_page_config(
    page_title="2026 Tour Auvergne - Rhône-Alpes Fantasy", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

SCORING = {
    "GC Standing": {1: 40, 2: 35, 3: 30, 4: 25, 5: 20, 6: 18, 7: 16, 8: 14, 9: 12, 10: 10},
    "Stage Result": {1: 12, 2: 10, 3: 8, 4: 6, 5: 5, 6: 4, 7: 3, 8: 2, 9: 1, 10: 1},
    "Jersey": {1: 12, 2: 8, 3: 4} 
}

REPLACEMENT_MAP = {
    1: 1.0, 2: 1.0, 3: 1.0, 4: 0.9, 5: 0.9, 6: 0.8,
    7: 0.8, 8: 0.7, 9: 0.7, 10: 0.6, 11: 0.6, 12: 0.6,
    13: 0.5, 14: 0.5, 15: 0.5, 16: 0.5, 17: 0.5, 18: 0.5, 19: 0.5, 20: 0.5 
}

# June 2026 Schedule
STAGE_DATES = {
    1: '2026-06-07',
    2: '2026-06-08',
    3: '2026-06-09',
    4: '2026-06-10',
    5: '2026-06-11',
    6: '2026-06-12',
    7: '2026-06-13',
    8: '2026-06-14'
}

# --- 2. HELPERS ---
def normalize_name(name):
    if not isinstance(name, str): return ""
    name = "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    return name.lower().replace('-', ' ').strip()

def group_cat(cat):
    if "Jersey" in cat: return "Jerseys"
    return cat

def format_name(name, drop_date):
    if pd.isna(drop_date):
        return name
    sd = str(drop_date).lower().strip()
    if sd in ["", "nan", "none", "nat", "0", "false"] or len(sd) < 7:
        return name
    return "".join(f"{char}\u0336" for char in name)

@st.cache_data(ttl=300)
def load_data():
    empty_riders = pd.DataFrame(columns=['rider_name', 'match_name', 'owner', 'team_pick', 'is_replacement', 'add_date', 'drop_date', 'replaces_rider'])
    empty_proc = pd.DataFrame(columns=['Stage', 'Category', 'rank', 'res_rider', 'match_name', 'owner', 'rider_name', 'team_pick', 'is_replacement', 'add_date', 'drop_date', 'replaces_rider', 'pts', 'Display Category'])
    empty_fa = pd.DataFrame(columns=['res_rider', 'pts'])

    try:
        # Load local rosters file dynamically
        try:
            r_df = pd.read_csv('riders.csv', encoding='utf-8', engine='python', on_bad_lines='skip')
        except (UnicodeDecodeError, FileNotFoundError):
            try:
                r_df = pd.read_csv('riders.csv', encoding='cp1252', engine='python', on_bad_lines='skip')
            except:
                return empty_proc, empty_riders, 0, empty_fa

        r_df['match_name'] = r_df['rider_name'].apply(normalize_name)
        
        if 'drop_date' in r_df.columns:
            r_df['drop_date'] = r_df['drop_date'].astype(str).replace(r'^\s*$', pd.NA, regex=True)
            r_df['drop_date'] = r_df['drop_date'].replace(['nan', 'NaN', 'None', 'nan ', 'nan'], pd.NA)
        else:
            r_df['drop_date'] = pd.NA
            
        if 'is_replacement' in r_df.columns:
            r_df['is_replacement'] = r_df['is_replacement'].astype(str).str.strip().str.lower().isin(['true', '1', 'yes'])
        else:
            r_df['is_replacement'] = False
            
        if 'add_date' not in r_df.columns: r_df['add_date'] = '2026-06-05'
        if 'replaces_rider' not in r_df.columns: r_df['replaces_rider'] = pd.NA

        r_df = r_df.sort_values('add_date', ascending=True).reset_index(drop=True)

        base_mask = r_df['is_replacement'] != True
        r_df.loc[base_mask, 'team_pick'] = r_df[base_mask].groupby('owner').cumcount() + 1
        
        pick_map = {}
        team_picks = []
        for idx, row in r_df.iterrows():
            owner = str(row['owner']).lower().strip()
            rider = str(row['rider_name']).lower().strip()
            if not row['is_replacement']:
                p_num = int(row['team_pick'])
                pick_map[(owner, rider)] = p_num
                team_picks.append(p_num)
            else:
                replaced = str(row['replaces_rider']).lower().strip() if pd.notna(row['replaces_rider']) else ""
                p_num = pick_map.get((owner, replaced), 99)
                team_picks.append(p_num)
        r_df['team_pick'] = team_picks

        # Target results.xlsx instead of a CSV
        try:
            res = pd.read_excel('results.xlsx', engine='openpyxl')
        except Exception:
            res = pd.DataFrame()

        if res.empty or 'Stage' not in res.columns:
            return empty_proc, r_df, 0, empty_fa
        
        has_data = res.copy()
        if '1st' in has_data.columns:
            has_data = has_data[has_data['1st'].notna() & (has_data['1st'].astype(str).str.strip() != "")]
        elif 'GC #1' in has_data.columns:
            has_data = has_data[has_data['GC #1'].notna() & (has_data['GC #1'].astype(str).str.strip() != "")]
            
        all_stages = sorted(has_data['Stage'].unique()) if not has_data.empty else []
        latest_stage = max(all_stages) if len(all_stages) > 0 else 0
        
        if latest_stage == 0:
            return empty_proc, r_df, 0, empty_fa

        raw_results_list = []
        for s in all_stages:
            stage_data = res[res['Stage'] == s]
            stage_cols = ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th']
            for i, col in enumerate(stage_cols, 1):
                if col in stage_data.columns and not pd.isna(stage_data[col].iloc[0]):
                    raw_results_list.append({'Stage': s, 'res_rider': stage_data[col].iloc[0], 'rank': i, 'Category': 'Stage Result'})
            for i in range(1, 11):
                col = f'GC #{i}'
                if col in stage_data.columns and not pd.isna(stage_data[col].iloc[0]):
                    raw_results_list.append({'Stage': s, 'res_rider': stage_data[col].iloc[0], 'rank': i, 'Category': 'GC Standing'})
            
            for prefix, cat_name in [('Points #', 'Points Jersey'), ('Mountain #', 'Mountain Jersey'), ('Youth #', 'Youth Jersey')]:
                for i in range(1, 4):
                    col = f'{prefix}{i}'
                    if col in stage_data.columns and not pd.isna(stage_data[col].iloc[0]):
                        raw_results_list.append({'Stage': s, 'res_rider': stage_data[col].iloc[0], 'rank': i, 'Category': cat_name})

        df_all_raw = pd.DataFrame(raw_results_list)
        if df_all_raw.empty: return empty_proc, r_df, latest_stage, empty_fa

        df_all_raw['match_name'] = df_all_raw['res_rider'].apply(normalize_name)
        proc = df_all_raw.merge(r_df[['match_name', 'owner', 'rider_name', 'team_pick', 'is_replacement', 'add_date', 'drop_date', 'replaces_rider']], on='match_name', how='inner')

        proc['stage_date'] = pd.to_datetime(proc['Stage'].map(STAGE_DATES))
        proc['add_dt'] = pd.to_datetime(proc['add_date'])
        
        is_dropped_null = proc['drop_date'].isnull() | proc['drop_date'].astype(str).str.strip().isin(["", "nan", "<NA>", "NaT", "None"])
        proc['drop_dt'] = pd.to_datetime(proc['drop_date'], errors='coerce')
        
        valid_mask = (proc['stage_date'] >= proc['add_dt']) & (is_dropped_null | (proc['stage_date'] <= proc['drop_dt']))
        proc = proc[valid_mask].copy()

        def calc_pts(row):
            cat, rank = row['Category'], row['rank']
            base = SCORING.get(cat, SCORING.get("Jersey", {}).get(rank, 0))
            if isinstance(base, dict):
                base = base.get(rank, 0)
            add_date = pd.to_datetime(row['add_date'])
            if row.get('is_replacement', False) and add_date >= pd.Timestamp('2026-06-10'):
                if cat == "Stage Result": return base * 1.0  
                elif "Jersey" in cat: return 0.0         
                elif cat == "GC Standing": return base * REPLACEMENT_MAP.get(row['team_pick'], 0.5) 
            return base

        proc['pts'] = proc.apply(calc_pts, axis=1)
        proc['Display Category'] = proc['Category'].apply(group_cat)
        
        is_stage_result = proc['Category'] == 'Stage Result'
        is_latest_snapshot = proc['Stage'] == latest_stage
        proc = proc[is_stage_result | is_latest_snapshot].copy()

        unpicked = df_all_raw[~df_all_raw['match_name'].isin(r_df['match_name'].tolist())].copy()
        
        def calc_unpicked_pts(x):
            cat_score = SCORING.get(x['Category'])
            if cat_score is None:
                cat_score = SCORING.get("Jersey", {})
            return cat_score.get(x['rank'], 0)
            
        unpicked['pts'] = unpicked.apply(calc_unpicked_pts, axis=1)
        unpicked = unpicked[(unpicked['Category'] == 'Stage Result') | (unpicked['Stage'] == latest_stage)]
        best_unpicked = unpicked.groupby('res_rider')['pts'].sum().reset_index().sort_values('pts', ascending=False)
        
        return proc, r_df, latest_stage, best_unpicked

    except Exception as e:
        st.error(f"⚠️ App Data Processing Error: {e}")
        return empty_proc, empty_riders, 0, empty_fa

proc_data, riders, current_stage, best_unpicked = load_data()

# --- 3. VIEWS ---
def show_dashboard():
    st.title("🏆 Tour Auvergne - Rhône-Alpes Fantasy")
    
    if riders.empty:
        st.warning("Roster dataset is completely empty.")
        return

    owners = sorted(riders['owner'].unique())
    m_cols = st.columns(max(len(owners), 1))
    for idx, owner in enumerate(owners):
        if not proc_data.empty and 'owner' in proc_data.columns:
            owner_pts = proc_data[proc_data['owner'] == owner]['pts'].sum()
        else:
            owner_pts = 0.0
        m_cols[idx].metric(str(owner), f"{owner_pts:,.1f}")

    st.divider()

    if not proc_data.empty and current_stage > 0:
        all_stages = list(range(1, current_stage + 1))
        stage_res_data = proc_data[proc_data['Category'] == 'Stage Result']
        
        try:
            res = pd.read_excel('results.xlsx', engine='openpyxl')
            raw_list = []
            for s in all_stages:
                stage_data = res[res['Stage'] == s]
                for i in range(1, 11):
                    col = f'GC #{i}'
                    if col in stage_data.columns and not pd.isna(stage_data[col].iloc[0]):
                        raw_list.append({'Stage': s, 'res_rider': stage_data[col].iloc[0], 'rank': i, 'Category': 'GC Standing'})
                
                for prefix, cat_name in [('Points #', 'Points Jersey'), ('Mountain #', 'Mountain Jersey'), ('Youth #', 'Youth Jersey')]:
                    for i in range(1, 4):
                        col = f'{prefix}{i}'
                        if col in stage_data.columns and not pd.isna(stage_data[col].iloc[0]):
                            raw_list.append({'Stage': s, 'res_rider': stage_data[col].iloc[0], 'rank': i, 'Category': cat_name})
            df_hist_snaps = pd.DataFrame(raw_list)
            if not df_hist_snaps.empty:
                df_hist_snaps['match_name'] = df_hist_snaps['res_rider'].apply(normalize_name)
                df_hist_

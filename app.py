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
        # Load local rosters file dynamically as seen in image_8928c9.png
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

        # Safely try opening results.csv
        try:
            res = pd.read_csv('results.csv', encoding='utf-8', engine='python', on_bad_lines='skip')
        except (UnicodeDecodeError, FileNotFoundError):
            try:
                res = pd.read_csv('results.csv', encoding='cp1252', engine='python', on_bad_lines='skip')
            except:
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
        proc['drop_dt'] = pd.to_datetime(proc['drop_date'])
        valid_mask = (proc['stage_date'] >= proc['add_dt']) & (proc['drop_dt'].isna() | (proc['stage_date'] <= proc['drop_dt']))
        proc = proc[valid_mask].copy()

        def calc_pts(row):
            cat, rank = row['Category'], row['rank']
            base = SCORING.get(cat, SCORING.get("Jersey", {})).get(rank, 0)
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
        unpicked['pts'] = unpicked.apply(lambda x: SCORING.get(x['Category'], SCORING.get("Jersey", {})).get(x['rank'], 0), axis=1)
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
            res = pd.read_csv('results.csv', engine='python', on_bad_lines='skip')
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
                df_hist_snaps = df_hist_snaps.merge(riders[['match_name', 'owner', 'add_date', 'drop_date', 'is_replacement', 'team_pick']], on='match_name', how='inner')
                df_hist_snaps['stage_date'] = pd.to_datetime(df_hist_snaps['Stage'].map(STAGE_DATES))
                df_hist_snaps['add_dt'] = pd.to_datetime(df_hist_snaps['add_date'])
                df_hist_snaps['drop_dt'] = pd.to_datetime(df_hist_snaps['drop_date'])
                df_hist_snaps = df_hist_snaps[(df_hist_snaps['stage_date'] >= df_hist_snaps['add_dt']) & (df_hist_snaps['drop_dt'].isna() | (df_hist_snaps['stage_date'] <= df_hist_snaps['drop_dt']))]
                
                def calc_pts_hist(row):
                    cat, rank = row['Category'], row['rank']
                    base = SCORING.get(cat, SCORING.get("Jersey", {})).get(rank, 0)
                    if row.get('is_replacement', False) and pd.to_datetime(row['add_date']) >= pd.Timestamp('2026-06-10'):
                        if cat == "Stage Result": return base * 1.0
                        elif "Jersey" in cat: return 0.0
                        elif "GC Standing" in cat: return base * REPLACEMENT_MAP.get(row['team_pick'], 0.5)
                    return base
                df_hist_snaps['pts'] = df_hist_snaps.apply(calc_pts_hist, axis=1)
        except:
            df_hist_snaps = pd.DataFrame()

        df_stage_res = stage_res_data.groupby(['Stage', 'owner'])['pts'].sum().unstack(fill_value=0.0)
        df_snapshots = df_hist_snaps.groupby(['Stage', 'owner'])['pts'].sum().unstack(fill_value=0.0) if not df_hist_snaps.empty else pd.DataFrame()
        
        for o_name in owners:
            if o_name not in df_stage_res.columns: df_stage_res[o_name] = 0.0
            if df_snapshots.empty or o_name not in df_snapshots.columns: df_snapshots[o_name] = 0.0
            
        chart_rows, matrix_rows = [], []
        for s in all_stages: 
            dan_accum = df_stage_res.loc[df_stage_res.index <= s, 'Daniel'].sum() if 'Daniel' in df_stage_res.columns else 0
            tan_accum = df_stage_res.loc[df_stage_res.index <= s, 'Tanner'].sum() if 'Tanner' in df_stage_res.columns else 0
            dan_snap = df_snapshots.loc[s, 'Daniel'] if ('Daniel' in df_snapshots.columns and s in df_snapshots.index) else 0
            tan_snap = df_snapshots.loc[s, 'Tanner'] if ('Tanner' in df_snapshots.columns and s in df_snapshots.index) else 0
            
            dan_total, tan_total = round(dan_accum + dan_snap, 1), round(tan_accum + tan_snap, 1)
            chart_rows.append({"Stage": s, "Daniel": dan_total, "Tanner": tan_total})
            diff_str = f"Daniel +{round(dan_total - tan_total, 1)}" if dan_total > tan_total else (f"Tanner +{round(tan_total - dan_total, 1)}" if tan_total > dan_total else "Tie")
            matrix_rows.append({"Stage": f"Stage {s}", "Daniel": dan_total, "Tanner": tan_total, "Difference": diff_str})
                
        g_col1, g_col2 = st.columns([3, 2])
        with g_col1:
            st.subheader("📈 Points Trajectory Progression")
            st.line_chart(pd.DataFrame(chart_rows).set_index("Stage"), height=350)
        with g_col2:
            st.subheader("📊 Head-to-Head Standings")
            st.dataframe(pd.DataFrame(reversed(matrix_rows)), use_container_width=True, hide_index=True, height=350)
    else:
        st.info("🕒 The race hasn't started yet! Head over to 'Team Rosters' to view active lineups. Charts and standings will unlock as soon as Stage 1 results are published.")

    st.divider()
    
    st.subheader("🔥 Top 10 Performers per Team")
    t_cols = st.columns(max(len(owners), 1))
    for idx, owner in enumerate(owners):
        with t_cols[idx]:
            st.markdown(f"#### {owner}")
            if not proc_data.empty and owner in proc_data['owner'].values:
                owner_df = proc_data[proc_data['owner'] == owner]
                team_points = owner_df.groupby('rider_name')['pts'].sum().reset_index().sort_values('pts', ascending=False).head(10)
                for _, r in team_points.iterrows():
                    r_sub = riders[(riders['owner'] == owner) & (riders['rider_name'] == r['rider_name'])]
                    display_drop = pd.NA if r_sub.empty else r_sub['drop_date'].iloc[-1]
                    st.markdown(f"**{r['pts']:.1f}** — {format_name(r['rider_name'], display_drop)}")
            else: 
                owner_riders = riders[riders['owner'] == owner].head(10)
                for _, r in owner_riders.iterrows():
                    st.markdown(f"**0.0** — {r['rider_name']}")

def show_leaderboard():
    st.title("🏆 Full Rider Leaderboard")
    if riders.empty:
        st.warning("Roster metrics are empty.")
        return
        
    if not proc_data.empty:
        df = proc_data.groupby(['rider_name', 'owner', 'drop_date', 'Display Category'], dropna=False)['pts'].sum().unstack(fill_value=0.0).reset_index()
        for col in ['Stage Result', 'GC Standing', 'Jerseys']:
            if col not in df.columns: df[col] = 0.0
        df['Total'] = df[['Stage Result', 'GC Standing', 'Jerseys']].sum(axis=1)
        df['Rider'] = df.apply(lambda x: format_name(x['rider_name'], x['drop_date']), axis=1)
        df = df.sort_values('Total', ascending=False)
    else:
        df = riders.copy()
        df['Stage Result'], df['GC Standing'], df['Jerseys'], df['Total'] = 0.0, 0.0, 0.0, 0.0
        df['Rider'] = df['rider_name']

    st.dataframe(
        df[['Rider', 'owner', 'Stage Result', 'GC Standing', 'Jerseys', 'Total']], 
        use_container_width=True, hide_index=True, height=600,
        column_config={
            "owner": st.column_config.TextColumn("Owner"),
            "Stage Result": st.column_config.NumberColumn("Stage Result", format="%.1f"),
            "GC Standing": st.column_config.NumberColumn("GC Standing", format="%.1f"),
            "Jerseys": st.column_config.NumberColumn("Jerseys", format="%.1f"),
            "Total": st.column_config.NumberColumn("Total", format="%.1f")
        }
    )

def show_team_rosters():
    st.title("👥 Team Rosters")
    st.markdown("Current active lineups and live scoring potential.")
    
    if riders.empty:
        st.warning("No roster metadata found.")
        return

    owners = sorted(riders['owner'].unique())
    r_pts = proc_data.groupby(['match_name', 'owner', 'team_pick'])['pts'].sum().reset_index() if not proc_data.empty else pd.DataFrame(columns=['match_name', 'owner', 'team_pick', 'pts'])
        
    cols = st.columns(max(len(owners), 1))
    for idx, owner in enumerate(owners):
        with cols[idx]:
            owner_df = riders[riders['owner'] == owner].merge(r_pts[['match_name', 'team_pick', 'pts']], on=['match_name', 'team_pick'], how='left').fillna(0)
            owner_df['is_active'] = owner_df['drop_date'].apply(lambda d: pd.isna(d) or str(d).lower().strip() in ["", "nan", "none", "nat"])
            st.markdown(f"### Team {owner}")
            
            active_current = owner_df[owner_df['is_active'] == True].sort_values('team_pick', ascending=True)
            if not active_current.empty:
                st.dataframe(
                    active_current[['team_pick', 'rider_name', 'pts', 'add_date']].rename(columns={'team_pick': 'Slot', 'rider_name': 'Rider', 'pts': 'Pts', 'add_date': 'Date Added'}),
                    use_container_width=True, hide_index=True, height=735,
                    column_config={"Slot": st.column_config.NumberColumn("Slot", format="%d"), "Pts": st.column_config.NumberColumn("Total Pts", format="%.1f")}
                )

def show_analytics():
    st.title(" 🚀 Draft Pick Efficiency")
    if riders.empty:
        st.warning("Data arrays unavailable.")
        return

    owners = sorted(riders['owner'].unique())
    cols = st.columns(max(len(owners), 1))
    for idx, owner in enumerate(owners):
        with cols[idx]:
            st.subheader(f"Team {owner}")
            r_pts = proc_data[proc_data['owner'] == owner].groupby(['match_name', 'team_pick'])['pts'].sum().reset_index() if not proc_data.empty else pd.DataFrame(columns=['match_name', 'team_pick', 'pts'])
            df = riders[riders['owner'] == owner].merge(r_pts, on=['match_name', 'team_pick'], how='left').fillna(0)
            
            for pick in sorted(df['team_pick'].unique()):
                pick_df = df[df['team_pick'] == pick].sort_values('is_replacement', ascending=True)
                with st.expander(f"Pick {pick} — {pick_df['pts'].sum():.1f} pts"):
                    pick_df['Rider'] = pick_df.apply(lambda r: f"↳ Sub: {r['rider_name']}" if r['is_replacement'] else r['rider_name'], axis=1)
                    st.dataframe(pick_df[['Rider', 'pts']].rename(columns={'pts': 'Pts'}), use_container_width=True, hide_index=True)
                                             
    st.divider()
    st.subheader("Free Agents")
    if not best_unpicked.empty:
        st.dataframe(best_unpicked[best_unpicked['pts'] > 0].head(25), use_container_width=True, hide_index=True)
    else:
        st.info("No unpicked alternative riders have accrued points yet.")

def show_rider_breakdowns():
    st.title("🔍 Detailed Rider Breakdowns")
    if riders.empty:
        st.warning("Roster metrics missing.")
        return

    owners = sorted(riders['owner'].unique())
    owner_cols = st.columns(max(len(owners), 1))
    for idx, owner in enumerate(owners):
        with owner_cols[idx]:
            st.header(f"Team {owner}")
            r_totals = proc_data[proc_data['owner'] == owner].groupby(['match_name', 'team_pick'])['pts'].sum().reset_index() if not proc_data.empty else pd.DataFrame(columns=['match_name', 'team_pick', 'pts'])
            team_riders = riders[riders['owner'] == owner].merge(r_totals, on=['match_name', 'team_pick'], how='left').fillna(0).sort_values('pts', ascending=False)
            
            for _, r in team_riders.iterrows():
                display = f"{r['rider_name']} (Sub)" if r['is_replacement'] else r['rider_name']
                with st.expander(f"Pick {r['team_pick']} | {format_name(display, r['drop_date'])} — {r['pts']:.1f} pts"):
                    if r['pts'] > 0 and not proc_data.empty:
                        st.dataframe(proc_data[(proc_data['match_name'] == r['match_name']) & (proc_data['team_pick'] == r['team_pick'])][['Stage', 'Category', 'rank', 'pts']], use_container_width=True, hide_index=True)
                    else: 
                        st.write("No points scored yet.")

# --- 4. NAVIGATION ---
pg = st.navigation([
    st.Page(show_dashboard, title="Home", icon="🏠"), 
    st.Page(show_leaderboard, title="Leaderboard", icon="🏆"), 
    st.Page(show_team_rosters, title="Team Rosters", icon="👥"), 
    st.Page(show_analytics, title="Draft Analytics", icon="📈"), 
    st.Page(show_rider_breakdowns, title="Rider Breakdowns", icon="🔍")
])
pg.run()

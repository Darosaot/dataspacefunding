"""
EU Data Spaces Funding – Project Search Tool  (v3)
==================================================
Run with:
    pip install streamlit pandas
    streamlit run dashboard.py
"""

import re
import pandas as pd
import streamlit as st
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EU Data Spaces – Project Search",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .stApp { background-color: #F2F6FC; }

  [data-testid="stSidebar"] { background-color: #1F4E79; }
  [data-testid="stSidebar"] *         { color: #FFFFFF !important; }
  [data-testid="stSidebar"] input     { color: #000 !important; }
  [data-testid="stSidebar"] .stMarkdown p { font-size: 0.82rem; opacity: 0.8; }

  .kpi { background:white; border-radius:12px; padding:16px 20px;
         border-top:4px solid #1F4E79; box-shadow:0 2px 10px rgba(0,0,0,.07);
         text-align:center; }
  .kpi.green  { border-top-color:#375623; }
  .kpi.teal   { border-top-color:#1a7a6e; }
  .kpi.orange { border-top-color:#C55A11; }
  .kpi-val  { font-size:1.8rem; font-weight:800; color:#1F4E79; margin:0; line-height:1.1; }
  .kpi-val.green  { color:#375623; }
  .kpi-val.teal   { color:#1a7a6e; }
  .kpi-val.orange { color:#C55A11; }
  .kpi-lbl  { font-size:0.75rem; text-transform:uppercase; letter-spacing:.06em;
               color:#888; margin:4px 0 0; }
  .kpi-sub  { font-size:0.78rem; color:#aaa; margin:2px 0 0; }

  .sec { font-size:1.05rem; font-weight:700; color:#1F4E79;
         border-bottom:2px solid #BDD7EE; padding-bottom:5px; margin:22px 0 14px; }

  .stDownloadButton > button { background:#375623; color:white;
                                border:none; border-radius:6px;
                                font-size:0.82rem; padding:6px 14px; }
  .stDownloadButton > button:hover { background:#2E4A1C; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Reference data
# ─────────────────────────────────────────────────────────────────────────────
COUNTRY_NAMES = {
    'AT':'Austria','BE':'Belgium','BG':'Bulgaria','HR':'Croatia','CY':'Cyprus',
    'CZ':'Czechia','DK':'Denmark','EE':'Estonia','FI':'Finland','FR':'France',
    'DE':'Germany','GR':'Greece','EL':'Greece','HU':'Hungary','IE':'Ireland',
    'IT':'Italy','LV':'Latvia','LT':'Lithuania','LU':'Luxembourg','MT':'Malta',
    'NL':'Netherlands','PL':'Poland','PT':'Portugal','RO':'Romania','SK':'Slovakia',
    'SI':'Slovenia','ES':'Spain','SE':'Sweden','IS':'Iceland','NO':'Norway',
    'CH':'Switzerland','TR':'Turkey','UK':'United Kingdom','GB':'United Kingdom',
    'RS':'Serbia','AL':'Albania','ME':'Montenegro','MK':'North Macedonia',
    'IL':'Israel','MA':'Morocco','ZA':'South Africa','US':'United States',
    'CA':'Canada','AU':'Australia','JP':'Japan','KR':'South Korea','CN':'China',
    'IN':'India','BR':'Brazil','UA':'Ukraine','SG':'Singapore',
}
PROG_LABELS = {
    'HE':'Horizon Europe','H2020':'Horizon 2020',
    'DIGITAL':'Digital Europe','FP7':'FP7','Unknown':'Unknown / Other',
}
ACTIVITY_LABELS = {
    'PRC':'Private Company','REC':'Research Centre',
    'HES':'Higher Education','PUB':'Public Body','OTH':'Other',
}

def flag_emoji(code):
    code = str(code).upper().strip()
    if code == 'EL': code = 'GR'
    if code == 'UK': code = 'GB'
    if len(code) == 2 and code.isalpha():
        return chr(0x1F1E0+ord(code[0])-65) + chr(0x1F1E0+ord(code[1])-65)
    return ''

# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent

@st.cache_data
def load_data():
    proj = pd.read_csv(DATA_DIR / 'eu_projects_data_spaces.csv', dtype=str)
    ben  = pd.read_csv(DATA_DIR / 'eu_beneficiaries_data_spaces.csv', dtype=str)

    for col in ['total_cost_eur','ec_contribution_eur']:
        proj[col] = pd.to_numeric(proj[col], errors='coerce').fillna(0)
    proj['start_date']       = pd.to_datetime(proj['start_date'], errors='coerce')
    proj['end_date']         = pd.to_datetime(proj['end_date'],   errors='coerce')
    proj['start_year']       = proj['start_date'].dt.year.astype('Int64')
    proj['duration_months']  = pd.to_numeric(proj.get('duration_months', pd.Series()), errors='coerce')
    proj['programme']        = proj['programme'].fillna('').replace('', 'Unknown')
    proj['prog_label']       = proj['programme'].map(lambda x: PROG_LABELS.get(x, x))
    proj['status']           = proj.get('status', pd.Series(dtype=str)).fillna('Unknown')

    for col in ['ecContribution','netEcContribution','totalCost']:
        if col in ben.columns:
            ben[col] = pd.to_numeric(ben[col], errors='coerce').fillna(0)
    ben['country_name']   = ben['country'].map(lambda x: COUNTRY_NAMES.get(str(x).upper(), str(x)))
    ben['activity_label'] = ben['activityType'].map(lambda x: ACTIVITY_LABELS.get(str(x), str(x)))
    ben['flag']           = ben['country'].map(flag_emoji)
    ben['IsSME']          = ben.get('SME', pd.Series(dtype=str)).str.lower() == 'true'

    return proj, ben

proj_raw, ben_raw = load_data()

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar – filters
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🇪🇺 EU Data Spaces")
    st.markdown("---")

    all_progs = sorted(proj_raw['programme'].unique())
    sel_prog  = st.multiselect("Programme", all_progs, default=all_progs,
                                format_func=lambda x: PROG_LABELS.get(x, x))

    years  = proj_raw['start_year'].dropna().astype(int)
    y_min, y_max = int(years.min()), int(years.max())
    sel_years = st.slider("Start Year", y_min, y_max, (y_min, y_max))

    all_actions = sorted(proj_raw['action_type'].dropna().unique())
    sel_action  = st.multiselect("Action Type", all_actions, default=[])

    all_status = sorted(proj_raw['status'].dropna().unique())
    sel_status = st.multiselect("Project Status", all_status, default=[])

    all_countries = sorted(ben_raw['country_name'].dropna().unique())
    sel_country   = st.multiselect("Beneficiary Country", all_countries, default=[])

    all_acts = sorted(ben_raw['activityType'].dropna().unique())
    sel_act  = st.multiselect("Organisation Type", all_acts, default=[],
                               format_func=lambda x: ACTIVITY_LABELS.get(x, x))

    st.markdown("---")
    st.markdown("**🏢 Organisation search**")
    org_query = st.text_input("Type name…", "", key="org_q")
    sel_org   = None
    if org_query.strip():
        matches = sorted(
            ben_raw[ben_raw['name'].str.contains(org_query.strip(), case=False, na=False)]
            ['name'].unique()
        )
        if matches:
            pick = st.selectbox(f"{len(matches)} match(es)", ["— all —"] + matches)
            if pick != "— all —":
                sel_org = pick
        else:
            st.caption("No match found.")

    st.markdown("---")
    st.caption("OpenAIRE API + CORDIS bulk data  \nRun `eu_funding_scraper.py` to refresh")

# ─────────────────────────────────────────────────────────────────────────────
# Header & search bar
# ─────────────────────────────────────────────────────────────────────────────
st.title("🔍 EU Data Spaces – Project Search")
st.markdown(
    "Find EU-funded projects on **data spaces**, GAIA-X, federated data, "
    "data governance and the broader data economy."
)

search_query = st.text_input(
    "search_bar",
    placeholder="Search by title, acronym, summary, keywords, grant ID, topic…",
    label_visibility="collapsed",
    key="main_search",
)
st.caption(
    "Searches across: title · acronym · summary · objective · keywords · "
    "subjects · topics · grant ID · call ID"
)

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# Apply filters
# ─────────────────────────────────────────────────────────────────────────────

# Organisation filter (sidebar)
if sel_org:
    org_pids = set(ben_raw[ben_raw['name'] == sel_org]['projectID'].astype(str))
    proj = proj_raw[proj_raw['grant_id'].isin(org_pids)].copy()
else:
    proj = proj_raw[
        proj_raw['programme'].isin(sel_prog if sel_prog else all_progs) &
        (proj_raw['start_year'].between(sel_years[0], sel_years[1]) | proj_raw['start_year'].isna())
    ].copy()
    if sel_action:
        proj = proj[proj['action_type'].isin(sel_action)]
    if sel_status:
        proj = proj[proj['status'].isin(sel_status)]

# Country / org-type: filter via beneficiaries
if sel_country or sel_act:
    ben_f = ben_raw.copy()
    if sel_country:
        ben_f = ben_f[ben_f['country_name'].isin(sel_country)]
    if sel_act:
        ben_f = ben_f[ben_f['activityType'].isin(sel_act)]
    valid_pids = set(ben_f['projectID'].astype(str))
    proj = proj[proj['grant_id'].isin(valid_pids)]

# Free-text search across project fields
if search_query.strip():
    q = search_query.strip()
    text_cols = [
        'title', 'acronym', 'summary', 'objective', 'keywords',
        'subjects', 'topics', 'grant_id', 'call_id', 'action_type_desc',
        'masterCall', 'frameworkProgramme',
    ]
    mask = pd.Series(False, index=proj.index)
    for col in text_cols:
        if col in proj.columns:
            mask |= proj[col].fillna('').str.contains(q, case=False, na=False)
    proj = proj[mask]

ben = ben_raw[ben_raw['projectID'].isin(proj['grant_id'])].copy()
if sel_country:
    ben = ben[ben['country_name'].isin(sel_country)]
if sel_act:
    ben = ben[ben['activityType'].isin(sel_act)]

# ─────────────────────────────────────────────────────────────────────────────
# KPI summary row
# ─────────────────────────────────────────────────────────────────────────────
n_proj   = len(proj)
ec_total = proj['ec_contribution_eur'].sum() / 1e6
n_orgs   = ben['name'].nunique()
n_ctry   = ben['country'].nunique()

c1, c2, c3, c4 = st.columns(4)
for col, val, lbl, sub, klass in [
    (c1, n_proj,               "Projects Found",     "matching your search",    ""),
    (c2, f"€{ec_total:.1f}M",  "Total EC Funding",   "across matched projects", "green"),
    (c3, n_orgs,               "Organisations",      "unique beneficiaries",    "teal"),
    (c4, n_ctry,               "Countries",          "represented",             "orange"),
]:
    col.markdown(f"""<div class="kpi {klass}">
      <p class="kpi-val {klass}">{val}</p>
      <p class="kpi-lbl">{lbl}</p>
      <p class="kpi-sub">{sub}</p>
    </div>""", unsafe_allow_html=True)

st.markdown("")

# ─────────────────────────────────────────────────────────────────────────────
# Results table
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="sec">Search Results</div>', unsafe_allow_html=True)

sort_options = {
    "EC Contribution (high → low)": ("ec_contribution_eur", False),
    "Start Date (newest first)":    ("start_date",          False),
    "Start Date (oldest first)":    ("start_date",          True),
    "Title (A → Z)":                ("title",               True),
    "Duration (longest first)":     ("duration_months",     False),
}

r1, r2, r3 = st.columns([3, 1, 1])
with r1:
    sort_choice = st.selectbox("Sort by", list(sort_options.keys()))
with r3:
    dl = proj.copy()
    dl['start_date'] = dl['start_date'].dt.strftime('%Y-%m-%d').fillna('')
    dl['end_date']   = dl['end_date'].dt.strftime('%Y-%m-%d').fillna('')
    st.download_button(
        "⬇ Download CSV",
        dl.to_csv(index=False).encode(),
        "eu_projects_results.csv",
        "text/csv",
    )

sort_col_name, sort_asc = sort_options[sort_choice]
proj_sorted = proj.sort_values(sort_col_name, ascending=sort_asc, na_position='last') \
    if sort_col_name in proj.columns else proj

display_cols = [c for c in [
    'grant_id', 'acronym', 'title', 'prog_label', 'action_type',
    'status', 'start_date', 'end_date', 'duration_months',
    'ec_contribution_eur', 'cordis_url',
] if c in proj_sorted.columns]

pt = proj_sorted[display_cols].copy().rename(columns={
    'grant_id':           'Grant ID',
    'acronym':            'Acronym',
    'title':              'Title',
    'prog_label':         'Programme',
    'action_type':        'Action',
    'status':             'Status',
    'start_date':         'Start',
    'end_date':           'End',
    'duration_months':    'Duration (mo)',
    'ec_contribution_eur':'EC (€)',
    'cordis_url':         'CORDIS',
})

if 'Start' in pt.columns:
    pt['Start'] = pd.to_datetime(pt['Start']).dt.strftime('%Y-%m-%d')
if 'End' in pt.columns:
    pt['End'] = pd.to_datetime(pt['End']).dt.strftime('%Y-%m-%d')

col_cfg = {
    'Title':   st.column_config.TextColumn(width='large'),
    'EC (€)':  st.column_config.NumberColumn(format='€%.0f'),
}
if 'CORDIS' in pt.columns:
    col_cfg['CORDIS'] = st.column_config.LinkColumn('CORDIS', width='small')

st.dataframe(pt.reset_index(drop=True), use_container_width=True, height=450, column_config=col_cfg)
st.caption(f"{n_proj} project(s) found")

# ─────────────────────────────────────────────────────────────────────────────
# Project detail viewer
# ─────────────────────────────────────────────────────────────────────────────
if n_proj > 0:
    st.markdown('<div class="sec">Project Details</div>', unsafe_allow_html=True)

    proj_labels = (
        proj_sorted['acronym'].fillna('') + ' – ' +
        proj_sorted['title'].fillna('').str[:80]
    ).tolist()
    proj_ids = proj_sorted['grant_id'].tolist()
    label_to_id = dict(zip(proj_labels, proj_ids))

    sel_label = st.selectbox("Select a project to view details", proj_labels, index=0)
    sel_id    = label_to_id[sel_label]
    row       = proj_sorted[proj_sorted['grant_id'] == sel_id].iloc[0]

    ec_m  = row['ec_contribution_eur'] / 1e6
    start = row['start_date'].strftime('%Y-%m-%d') if pd.notna(row['start_date']) else '—'
    end   = row['end_date'].strftime('%Y-%m-%d')   if pd.notna(row['end_date'])   else '—'
    dur   = f"{int(row['duration_months'])} months" if pd.notna(row.get('duration_months')) and row.get('duration_months', 0) > 0 else '—'

    da, db = st.columns([3, 1])
    with da:
        st.markdown(f"### {row.get('acronym', '—')}  ·  {row.get('title', '—')}")
        st.markdown(
            f"**Programme:** {row.get('prog_label','—')}  ·  "
            f"**Action:** {row.get('action_type','—')}  ·  "
            f"**Status:** {row.get('status','—')}"
        )
        st.markdown(
            f"**Period:** {start} → {end}  ·  **Duration:** {dur}  ·  "
            f"**EC Contribution:** €{ec_m:.2f}M  ·  **Grant ID:** {row.get('grant_id','—')}"
        )
    with db:
        cordis = row.get('cordis_url', '')
        if pd.notna(cordis) and str(cordis).startswith('http'):
            st.link_button("🔗 View on CORDIS", str(cordis))

    # Summary / objective
    with st.expander("📄 Summary & Objective", expanded=True):
        summary   = str(row.get('summary',   '') or '').strip()
        objective = str(row.get('objective', '') or '').strip()
        if summary:
            st.markdown("**Summary**")
            st.write(summary)
        if objective:
            st.markdown("**Objective**")
            st.write(objective)
        if not summary and not objective:
            st.info("No description available for this project.")

    # Keywords / tags
    all_kw = []
    for kw_col in ['keywords', 'subjects', 'topics']:
        val = row.get(kw_col, '')
        if pd.notna(val) and str(val).strip():
            for kw in re.split(r'[;,\|/\n]+', str(val)):
                kw = kw.strip()
                if kw:
                    all_kw.append(kw)
    if all_kw:
        st.markdown("**Keywords:** " + "  ".join(f"`{kw}`" for kw in all_kw[:25]))

    # Beneficiaries
    with st.expander("🏢 Participating Organisations", expanded=True):
        proj_ben = ben_raw[ben_raw['projectID'].astype(str) == str(sel_id)].copy()
        if not proj_ben.empty:
            proj_ben['country_name']   = proj_ben['country'].map(lambda x: COUNTRY_NAMES.get(str(x).upper(), str(x)))
            proj_ben['activity_label'] = proj_ben['activityType'].map(lambda x: ACTIVITY_LABELS.get(str(x), str(x)))
            proj_ben['Flag']           = proj_ben['country'].map(flag_emoji)
            proj_ben['Country']        = proj_ben['Flag'] + ' ' + proj_ben['country_name']
            proj_ben['IsSME']          = proj_ben.get('SME', pd.Series(dtype=str)).str.lower() == 'true'

            role_order = {'coordinator':0,'participant':1,'thirdParty':2,'associatedPartner':3}
            proj_ben['_ord'] = proj_ben['role'].map(lambda x: role_order.get(x, 99))
            proj_ben = proj_ben.sort_values('_ord')

            ben_disp = proj_ben[['name','role','Country','city','activity_label','IsSME','ecContribution']].copy()
            ben_disp.columns = ['Organisation','Role','Country','City','Type','SME','EC (€)']
            ben_disp['EC (€)'] = pd.to_numeric(ben_disp['EC (€)'], errors='coerce').fillna(0)

            st.dataframe(
                ben_disp.reset_index(drop=True),
                use_container_width=True,
                column_config={
                    'Organisation': st.column_config.TextColumn(width='large'),
                    'EC (€)':       st.column_config.NumberColumn(format='€%.0f'),
                },
            )
            st.download_button(
                "⬇ Download Organisations (CSV)",
                ben_disp.to_csv(index=False).encode(),
                f"beneficiaries_{row.get('acronym','project')}.csv",
                "text/csv",
            )
        else:
            st.info("No beneficiary data available for this project.")

# ─────────────────────────────────────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<small>Sources: <a href='https://api.openaire.eu'>OpenAIRE</a> · "
    "<a href='https://cordis.europa.eu'>CORDIS</a> · "
    "<a href='https://ec.europa.eu/info/funding-tenders/opportunities/portal'>EU F&T Portal</a>"
    " &nbsp;|&nbsp; Refresh: run <code>eu_funding_scraper.py</code></small>",
    unsafe_allow_html=True,
)

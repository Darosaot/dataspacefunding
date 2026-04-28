"""
EU Data Spaces Funding – Project Search Tool  (v4)
==================================================
Run with:
    pip install streamlit pandas requests
    streamlit run dashboard.py
"""

import re
import requests
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
# Local data (beneficiaries + enrichment fields from CORDIS)
# ─────────────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent

@st.cache_data
def load_local_data():
    """Load the pre-scraped CSVs for beneficiary lookups and browse mode."""
    proj = pd.read_csv(DATA_DIR / 'eu_projects_data_spaces.csv', dtype=str)
    ben  = pd.read_csv(DATA_DIR / 'eu_beneficiaries_data_spaces.csv', dtype=str)

    for col in ['total_cost_eur', 'ec_contribution_eur']:
        proj[col] = pd.to_numeric(proj[col], errors='coerce').fillna(0)
    proj['start_date']      = pd.to_datetime(proj['start_date'], errors='coerce')
    proj['end_date']        = pd.to_datetime(proj['end_date'],   errors='coerce')
    proj['start_year']      = proj['start_date'].dt.year.astype('Int64')
    proj['duration_months'] = pd.to_numeric(proj.get('duration_months', pd.Series()), errors='coerce')
    proj['programme']       = proj['programme'].fillna('').replace('', 'Unknown')
    proj['prog_label']      = proj['programme'].map(lambda x: PROG_LABELS.get(x, x))
    proj['status']          = proj.get('status', pd.Series(dtype=str)).fillna('Unknown')

    for col in ['ecContribution', 'netEcContribution', 'totalCost']:
        if col in ben.columns:
            ben[col] = pd.to_numeric(ben[col], errors='coerce').fillna(0)
    ben['country_name']   = ben['country'].map(lambda x: COUNTRY_NAMES.get(str(x).upper(), str(x)))
    ben['activity_label'] = ben['activityType'].map(lambda x: ACTIVITY_LABELS.get(str(x), str(x)))
    ben['flag']           = ben['country'].map(flag_emoji)
    ben['IsSME']          = ben.get('SME', pd.Series(dtype=str)).str.lower() == 'true'
    return proj, ben

local_proj, local_ben = load_local_data()

# ─────────────────────────────────────────────────────────────────────────────
# OpenAIRE API helpers  (adapted from eu_funding_scraper.py)
# ─────────────────────────────────────────────────────────────────────────────
OPENAIRE_URL = "https://api.openaire.eu/search/projects"

def _leaf(obj, default=""):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get("$", default)
    if isinstance(obj, list):
        return obj[0].get("$", default) if obj and isinstance(obj[0], dict) else default
    return str(obj)

def _first(obj):
    return (obj[0] if obj else None) if isinstance(obj, list) else obj

def _parse_funding(ft_raw):
    ft = _first(ft_raw)
    if not isinstance(ft, dict):
        return ("", "", "", "")
    fl1     = ft.get("funding_level_1", {})
    action  = _leaf(fl1.get("name"))
    fl0     = fl1.get("parent", {}).get("funding_level_0", {})
    prog    = _leaf(fl0.get("name"))
    prog_desc = _leaf(fl0.get("description"))
    if not prog:
        fl0b      = ft.get("funding_level_0", {})
        prog      = _leaf(fl0b.get("name"))
        prog_desc = _leaf(fl0b.get("description"))
    return prog, prog_desc, action, _leaf(fl1.get("description"))

def _parse_result(result: dict) -> dict | None:
    try:
        proj = (result
                .get("metadata", {})
                .get("oaf:entity", {})
                .get("oaf:project", {}))
        if not proj:
            return None
        grant_id = _leaf(proj.get("code"))
        if not grant_id:
            return None
        prog, prog_desc, action, action_desc = _parse_funding(proj.get("fundingtree", {}))
        subjects_raw = proj.get("subject", [])
        if isinstance(subjects_raw, dict):
            subjects_raw = [subjects_raw]
        subjects = "; ".join(
            s.get("$", "") for s in (subjects_raw or [])
            if isinstance(s, dict) and s.get("$")
        )
        return {
            "grant_id":            grant_id,
            "acronym":             _leaf(proj.get("acronym")),
            "title":               _leaf(proj.get("title")),
            "start_date":          _leaf(proj.get("startdate")),
            "end_date":            _leaf(proj.get("enddate")),
            "duration_months":     _leaf(proj.get("duration")),
            "total_cost_eur":      _leaf(proj.get("totalcost")),
            "ec_contribution_eur": _leaf(proj.get("fundedamount")),
            "call_id":             _leaf(proj.get("callidentifier")),
            "programme":           prog,
            "programme_desc":      prog_desc,
            "prog_label":          PROG_LABELS.get(prog, prog) if prog else "Unknown",
            "action_type":         action,
            "action_type_desc":    action_desc,
            "subjects":            subjects,
            "summary":             str(_leaf(proj.get("summary")))[:3000],
            "cordis_url":          f"https://cordis.europa.eu/project/id/{grant_id}",
        }
    except Exception:
        return None

@st.cache_data(ttl=300, show_spinner=False)
def api_search(query: str, year_from: int, year_to: int, page_size: int = 100) -> tuple[list, int, str]:
    """Query OpenAIRE and return (projects_list, total_count, error_msg)."""
    params = {
        "keywords":      query,
        "funder":        "EC",
        "format":        "json",
        "size":          page_size,
        "page":          1,
        "fromStartDate": f"{year_from}-01-01",
        "toStartDate":   f"{year_to}-12-31",
    }
    try:
        resp = requests.get(OPENAIRE_URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        return [], 0, "Request timed out. Please try again."
    except requests.exceptions.ConnectionError:
        return [], 0, "Could not reach OpenAIRE API. Check your connection."
    except Exception as e:
        return [], 0, f"API error: {e}"

    header  = data.get("response", {}).get("header", {})
    total   = int(header.get("total", {}).get("$", 0))
    results = data.get("response", {}).get("results", {}).get("result", []) or []
    projects = [p for r in results if (p := _parse_result(r))]
    return projects, total, ""

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar – filters
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🇪🇺 EU Data Spaces")
    st.markdown("---")

    y_min_all = int(local_proj['start_year'].dropna().min())
    y_max_all = int(local_proj['start_year'].dropna().max())
    sel_years = st.slider("Start Year", y_min_all, y_max_all, (y_min_all, y_max_all))

    st.markdown("**Refine results**")
    sel_prog   = st.multiselect("Programme",    list(PROG_LABELS.keys()), default=[],
                                 format_func=lambda x: PROG_LABELS.get(x, x))
    sel_action = st.multiselect("Action Type",  [], default=[])   # populated after search
    sel_status = st.multiselect("Project Status", [], default=[]) # populated after search

    st.markdown("---")
    st.caption("Live search via **OpenAIRE API** · EC-funded projects only  \n"
               "Beneficiary data from local CORDIS export")

# ─────────────────────────────────────────────────────────────────────────────
# Header + search bar
# ─────────────────────────────────────────────────────────────────────────────
st.title("🔍 EU Funded Projects – Search")
st.markdown(
    "Search **any topic** across all European Commission-funded research projects "
    "via the OpenAIRE API — data spaces, GAIA-X, climate, AI, health, and more."
)

sq_col, btn_col = st.columns([6, 1])
with sq_col:
    search_input = st.text_input(
        "query",
        placeholder="e.g.  data spaces   ·   GAIA-X   ·   federated learning   ·   quantum computing …",
        label_visibility="collapsed",
        key="search_input",
    )
with btn_col:
    search_clicked = st.button("🔍 Search", use_container_width=True)

st.caption("Searches title · acronym · summary · keywords · subjects across all EC-funded projects on OpenAIRE")
st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# Trigger / manage search state
# ─────────────────────────────────────────────────────────────────────────────
if "active_query"  not in st.session_state: st.session_state.active_query  = ""
if "active_years"  not in st.session_state: st.session_state.active_years  = (y_min_all, y_max_all)
if "search_mode"   not in st.session_state: st.session_state.search_mode   = "browse"

if search_clicked and search_input.strip():
    st.session_state.active_query = search_input.strip()
    st.session_state.active_years = sel_years
    st.session_state.search_mode  = "api"
elif search_clicked and not search_input.strip():
    st.session_state.search_mode  = "browse"
    st.session_state.active_query = ""

# ─────────────────────────────────────────────────────────────────────────────
# Fetch / select project set
# ─────────────────────────────────────────────────────────────────────────────
api_error   = ""
api_total   = 0
source_note = ""

if st.session_state.search_mode == "api" and st.session_state.active_query:
    with st.spinner(f"Searching OpenAIRE for **{st.session_state.active_query}** …"):
        raw, api_total, api_error = api_search(
            st.session_state.active_query,
            st.session_state.active_years[0],
            st.session_state.active_years[1],
        )
    if api_error:
        st.error(api_error)
        proj = local_proj.copy()
        source_note = "⚠️ API unavailable — showing locally cached data."
    else:
        proj = pd.DataFrame(raw) if raw else pd.DataFrame()
        if not proj.empty:
            for col in ['ec_contribution_eur', 'total_cost_eur', 'duration_months']:
                proj[col] = pd.to_numeric(proj.get(col, pd.Series()), errors='coerce').fillna(0)
            proj['start_date'] = pd.to_datetime(proj['start_date'], errors='coerce')
            proj['end_date']   = pd.to_datetime(proj['end_date'],   errors='coerce')
            proj['start_year'] = proj['start_date'].dt.year.astype('Int64')
            proj['prog_label'] = proj['programme'].map(lambda x: PROG_LABELS.get(x, x) if pd.notna(x) else 'Unknown')
            proj['status']     = proj.get('status', pd.Series(dtype=str)).fillna('Unknown')
        shown = min(len(raw), 100)
        source_note = (
            f"🌐 OpenAIRE live results — showing {shown} of {api_total:,} total matches. "
            "Refine your query or use filters to narrow down."
        )
else:
    # Browse mode: show local pre-scraped data
    proj = local_proj[
        local_proj['start_year'].between(sel_years[0], sel_years[1]) | local_proj['start_year'].isna()
    ].copy()
    source_note = f"📂 Browsing {len(proj)} locally cached data-spaces projects. Enter a search term to query all EC projects."

# ─────────────────────────────────────────────────────────────────────────────
# Client-side filters (programme / action type / status)
# ─────────────────────────────────────────────────────────────────────────────
if not proj.empty:
    if sel_prog:
        proj = proj[proj['programme'].isin(sel_prog)]
    if sel_action and 'action_type' in proj.columns:
        proj = proj[proj['action_type'].isin(sel_action)]
    if sel_status and 'status' in proj.columns:
        proj = proj[proj['status'].isin(sel_status)]

# ─────────────────────────────────────────────────────────────────────────────
# KPIs
# ─────────────────────────────────────────────────────────────────────────────
n_proj   = len(proj)
ec_total = proj['ec_contribution_eur'].sum() / 1e6 if n_proj else 0
n_progs  = proj['programme'].nunique()         if n_proj else 0

c1, c2, c3, c4 = st.columns(4)
for col, val, lbl, sub, klass in [
    (c1, n_proj,               "Projects Found",   "in results",             ""),
    (c2, f"€{ec_total:.1f}M",  "Total EC Funding", "across results",         "green"),
    (c3, n_progs,              "Programmes",       "represented",            "teal"),
    (c4, f"{sel_years[0]}–{sel_years[1]}", "Year Range", "filter applied",   "orange"),
]:
    col.markdown(f"""<div class="kpi {klass}">
      <p class="kpi-val {klass}">{val}</p>
      <p class="kpi-lbl">{lbl}</p>
      <p class="kpi-sub">{sub}</p>
    </div>""", unsafe_allow_html=True)

st.markdown("")
st.caption(source_note)

# ─────────────────────────────────────────────────────────────────────────────
# Results table
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="sec">Results</div>', unsafe_allow_html=True)

sort_options = {
    "EC Contribution (high → low)": ("ec_contribution_eur", False),
    "Start Date (newest first)":    ("start_date",          False),
    "Start Date (oldest first)":    ("start_date",          True),
    "Title (A → Z)":                ("title",               True),
    "Duration (longest first)":     ("duration_months",     False),
}

r1, _, r3 = st.columns([3, 1, 1])
with r1:
    sort_choice = st.selectbox("Sort by", list(sort_options.keys()))
with r3:
    if not proj.empty:
        dl = proj.copy()
        for c in ['start_date', 'end_date']:
            if c in dl.columns:
                dl[c] = pd.to_datetime(dl[c], errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
        st.download_button("⬇ Download CSV", dl.to_csv(index=False).encode(),
                           "eu_projects_results.csv", "text/csv")

if not proj.empty:
    sort_col_name, sort_asc = sort_options[sort_choice]
    proj_sorted = proj.sort_values(sort_col_name, ascending=sort_asc, na_position='last') \
        if sort_col_name in proj.columns else proj

    display_cols = [c for c in [
        'grant_id', 'acronym', 'title', 'prog_label', 'action_type',
        'status', 'start_date', 'end_date', 'duration_months',
        'ec_contribution_eur', 'cordis_url',
    ] if c in proj_sorted.columns]

    pt = proj_sorted[display_cols].copy().rename(columns={
        'grant_id':            'Grant ID',
        'acronym':             'Acronym',
        'title':               'Title',
        'prog_label':          'Programme',
        'action_type':         'Action',
        'status':              'Status',
        'start_date':          'Start',
        'end_date':            'End',
        'duration_months':     'Duration (mo)',
        'ec_contribution_eur': 'EC (€)',
        'cordis_url':          'CORDIS',
    })
    if 'Start' in pt.columns:
        pt['Start'] = pd.to_datetime(pt['Start'], errors='coerce').dt.strftime('%Y-%m-%d')
    if 'End' in pt.columns:
        pt['End']   = pd.to_datetime(pt['End'],   errors='coerce').dt.strftime('%Y-%m-%d')

    col_cfg = {
        'Title':  st.column_config.TextColumn(width='large'),
        'EC (€)': st.column_config.NumberColumn(format='€%.0f'),
    }
    if 'CORDIS' in pt.columns:
        col_cfg['CORDIS'] = st.column_config.LinkColumn('CORDIS', width='small')

    st.dataframe(pt.reset_index(drop=True), use_container_width=True,
                 height=450, column_config=col_cfg)
    st.caption(f"{n_proj} project(s) shown")
else:
    st.info("No projects match your search. Try different keywords or adjust the filters.")

# ─────────────────────────────────────────────────────────────────────────────
# Project detail viewer
# ─────────────────────────────────────────────────────────────────────────────
if n_proj > 0:
    st.markdown('<div class="sec">Project Details</div>', unsafe_allow_html=True)

    proj_labels = (
        proj_sorted['acronym'].fillna('') + ' – ' +
        proj_sorted['title'].fillna('').str[:80]
    ).tolist()
    proj_ids   = proj_sorted['grant_id'].tolist()
    label_map  = dict(zip(proj_labels, proj_ids))

    sel_label = st.selectbox("Select a project to view details", proj_labels, index=0)
    sel_id    = label_map[sel_label]
    row       = proj_sorted[proj_sorted['grant_id'] == sel_id].iloc[0]

    # Try to enrich from local CORDIS data
    local_row = local_proj[local_proj['grant_id'].astype(str) == str(sel_id)]
    enriched  = local_row.iloc[0] if not local_row.empty else None

    ec_m  = row['ec_contribution_eur'] / 1e6
    start = row['start_date'].strftime('%Y-%m-%d') if pd.notna(row.get('start_date')) else '—'
    end   = row['end_date'].strftime('%Y-%m-%d')   if pd.notna(row.get('end_date'))   else '—'
    dur_v = row.get('duration_months')
    dur   = f"{int(float(dur_v))} months" if pd.notna(dur_v) and float(dur_v) > 0 else '—'

    da, db = st.columns([3, 1])
    with da:
        st.markdown(f"### {row.get('acronym', '—')}  ·  {row.get('title', '—')}")
        prog_lbl = row.get('prog_label') or PROG_LABELS.get(row.get('programme',''), row.get('programme','—'))
        st.markdown(
            f"**Programme:** {prog_lbl}  ·  "
            f"**Action:** {row.get('action_type','—')}  ·  "
            f"**Status:** {(enriched['status'] if enriched is not None else row.get('status','—'))}"
        )
        st.markdown(
            f"**Period:** {start} → {end}  ·  **Duration:** {dur}  ·  "
            f"**EC Contribution:** €{ec_m:.2f}M  ·  **Grant ID:** {sel_id}"
        )
    with db:
        cordis = row.get('cordis_url', '')
        if pd.notna(cordis) and str(cordis).startswith('http'):
            st.link_button("🔗 View on CORDIS", str(cordis))

    # Summary / objective
    with st.expander("📄 Summary & Objective", expanded=True):
        summary   = str(row.get('summary', '') or '').strip()
        objective = str((enriched['objective'] if enriched is not None and pd.notna(enriched.get('objective')) else '') or '').strip()
        if summary:
            st.markdown("**Summary**")
            st.write(summary)
        if objective:
            st.markdown("**Objective** *(from CORDIS)*")
            st.write(objective)
        if not summary and not objective:
            st.info("No description available. Visit CORDIS for full project details.")

    # Keywords
    all_kw = []
    kw_sources = [row.get('subjects', '')]
    if enriched is not None:
        kw_sources += [enriched.get('keywords',''), enriched.get('topics','')]
    for val in kw_sources:
        if pd.notna(val) and str(val).strip():
            for kw in re.split(r'[;,\|/\n]+', str(val)):
                kw = kw.strip()
                if kw:
                    all_kw.append(kw)
    if all_kw:
        st.markdown("**Keywords:** " + "  ".join(f"`{kw}`" for kw in all_kw[:25]))

    # Beneficiaries
    with st.expander("🏢 Participating Organisations", expanded=True):
        proj_ben = local_ben[local_ben['projectID'].astype(str) == str(sel_id)].copy()
        if not proj_ben.empty:
            role_order = {'coordinator':0,'participant':1,'thirdParty':2,'associatedPartner':3}
            proj_ben['_ord'] = proj_ben['role'].map(lambda x: role_order.get(x, 99))
            proj_ben = proj_ben.sort_values('_ord')

            ben_disp = proj_ben[['name','role','country_name','city','activity_label','IsSME','ecContribution']].copy()
            ben_disp.columns = ['Organisation','Role','Country','City','Type','SME','EC (€)']
            ben_disp['EC (€)'] = pd.to_numeric(ben_disp['EC (€)'], errors='coerce').fillna(0)

            st.dataframe(ben_disp.reset_index(drop=True), use_container_width=True,
                         column_config={
                             'Organisation': st.column_config.TextColumn(width='large'),
                             'EC (€)':       st.column_config.NumberColumn(format='€%.0f'),
                         })
            st.download_button(
                "⬇ Download Organisations (CSV)",
                ben_disp.to_csv(index=False).encode(),
                f"beneficiaries_{row.get('acronym','project')}.csv",
                "text/csv",
            )
        else:
            st.info(
                "Beneficiary data not available for this project in the local cache. "
                "Run `eu_funding_scraper.py` to fetch it, or visit CORDIS directly."
            )

# ─────────────────────────────────────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<small>Live search: <a href='https://api.openaire.eu'>OpenAIRE API</a> · "
    "Beneficiary data: <a href='https://cordis.europa.eu'>CORDIS</a> · "
    "<a href='https://ec.europa.eu/info/funding-tenders/opportunities/portal'>EU F&T Portal</a>"
    " &nbsp;|&nbsp; Refresh local cache: run <code>eu_funding_scraper.py</code></small>",
    unsafe_allow_html=True,
)

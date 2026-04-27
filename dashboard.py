"""
EU Data Spaces Funding – Interactive Dashboard  (v2)
=====================================================
Run with:
    pip install streamlit plotly pandas
    streamlit run dashboard.py
"""

import re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path
from itertools import combinations
from collections import Counter

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EU Data Spaces Dashboard",
    page_icon="🇪🇺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .stApp { background-color: #F2F6FC; }

  /* Sidebar */
  [data-testid="stSidebar"] { background-color: #1F4E79; }
  [data-testid="stSidebar"] *         { color: #FFFFFF !important; }
  [data-testid="stSidebar"] input     { color: #000 !important; }
  [data-testid="stSidebar"] .stMarkdown p { font-size: 0.82rem; opacity: 0.8; }

  /* KPI cards */
  .kpi { background:white; border-radius:12px; padding:18px 22px;
         border-top:4px solid #1F4E79; box-shadow:0 2px 10px rgba(0,0,0,.07);
         text-align:center; }
  .kpi.green  { border-top-color:#375623; }
  .kpi.teal   { border-top-color:#1a7a6e; }
  .kpi.orange { border-top-color:#C55A11; }
  .kpi.purple { border-top-color:#7030A0; }
  .kpi-val  { font-size:2rem; font-weight:800; color:#1F4E79; margin:0; line-height:1.1; }
  .kpi-val.green  { color:#375623; }
  .kpi-val.teal   { color:#1a7a6e; }
  .kpi-val.orange { color:#C55A11; }
  .kpi-val.purple { color:#7030A0; }
  .kpi-lbl  { font-size:0.75rem; text-transform:uppercase; letter-spacing:.06em;
               color:#888; margin:4px 0 0; }
  .kpi-sub  { font-size:0.78rem; color:#aaa; margin:2px 0 0; }

  /* Section header */
  .sec { font-size:1.05rem; font-weight:700; color:#1F4E79;
         border-bottom:2px solid #BDD7EE; padding-bottom:5px; margin:22px 0 14px; }

  /* Org profile banner */
  .org-banner { background:linear-gradient(135deg,#1F4E79 0%,#2E75B6 100%);
                border-radius:14px; padding:22px 28px; color:white;
                box-shadow:0 4px 14px rgba(0,0,0,.18); margin-bottom:18px; }

  /* Download button */
  .stDownloadButton > button { background:#375623; color:white;
                                border:none; border-radius:6px;
                                font-size:0.82rem; padding:6px 14px; }
  .stDownloadButton > button:hover { background:#2E4A1C; }

  /* Tab styling */
  .stTabs [data-baseweb="tab-list"] { gap:6px; }
  .stTabs [data-baseweb="tab"] { background:#e8eef6; border-radius:8px 8px 0 0;
                                   padding:8px 20px; font-weight:600; }
  .stTabs [aria-selected="true"] { background:#1F4E79 !important; color:white !important; }
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
EU_ISO3 = {
    'AT':'AUT','BE':'BEL','BG':'BGR','HR':'HRV','CY':'CYP','CZ':'CZE',
    'DK':'DNK','EE':'EST','FI':'FIN','FR':'FRA','DE':'DEU','EL':'GRC',
    'GR':'GRC','HU':'HUN','IE':'IRL','IT':'ITA','LV':'LVA','LT':'LTU',
    'LU':'LUX','MT':'MLT','NL':'NLD','PL':'POL','PT':'PRT','RO':'ROU',
    'SK':'SVK','SI':'SVN','ES':'ESP','SE':'SWE','IS':'ISL','NO':'NOR',
    'CH':'CHE','TR':'TUR','UK':'GBR','GB':'GBR','RS':'SRB','IL':'ISR',
    'US':'USA','CA':'CAN','AU':'AUS','JP':'JPN','KR':'KOR','CN':'CHN',
    'IN':'IND','BR':'BRA','UA':'UKR','SG':'SGP','AL':'ALB','ME':'MNE',
    'MK':'MKD','MA':'MAR','ZA':'ZAF',
}

def flag_emoji(code):
    code = str(code).upper().strip()
    # Handle EL→GR for flags
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
    proj['start_date']  = pd.to_datetime(proj['start_date'], errors='coerce')
    proj['end_date']    = pd.to_datetime(proj['end_date'],   errors='coerce')
    proj['start_year']  = proj['start_date'].dt.year.astype('Int64')
    proj['duration_months'] = pd.to_numeric(proj.get('duration_months', pd.Series()), errors='coerce')
    proj['programme']   = proj['programme'].fillna('').replace('', 'Unknown')
    proj['prog_label']  = proj['programme'].map(lambda x: PROG_LABELS.get(x, x))
    proj['status']      = proj.get('status', pd.Series(dtype=str)).fillna('Unknown')

    for col in ['ecContribution','netEcContribution','totalCost']:
        if col in ben.columns:
            ben[col] = pd.to_numeric(ben[col], errors='coerce').fillna(0)
    ben['country_name']   = ben['country'].map(lambda x: COUNTRY_NAMES.get(str(x).upper(), str(x)))
    ben['activity_label'] = ben['activityType'].map(lambda x: ACTIVITY_LABELS.get(str(x), str(x)))
    ben['iso3']           = ben['country'].map(lambda x: EU_ISO3.get(str(x).upper(), None))
    ben['flag']           = ben['country'].map(flag_emoji)
    ben['IsSME']          = ben.get('SME', pd.Series(dtype=str)).str.lower() == 'true'

    return proj, ben

proj_raw, ben_raw = load_data()

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🇪🇺 EU Data Spaces")
    st.markdown("---")

    all_progs = sorted(proj_raw['programme'].unique())
    sel_prog  = st.multiselect("Programme", all_progs, default=all_progs,
                                format_func=lambda x: PROG_LABELS.get(x, x))

    years = proj_raw['start_year'].dropna().astype(int)
    y_min, y_max = int(years.min()), int(years.max())
    sel_years = st.slider("Start year", y_min, y_max, (y_min, y_max))

    all_countries = sorted(ben_raw['country_name'].dropna().unique())
    sel_country   = st.multiselect("Beneficiary country", all_countries, default=[])

    all_acts  = sorted(ben_raw['activityType'].dropna().unique())
    sel_act   = st.multiselect("Organisation type", all_acts, default=[],
                                format_func=lambda x: ACTIVITY_LABELS.get(x, x))

    all_roles = sorted(ben_raw['role'].dropna().unique())
    sel_role  = st.multiselect("Role", all_roles, default=[])

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
# Apply filters
# ─────────────────────────────────────────────────────────────────────────────
if sel_org:
    org_pids = set(ben_raw[ben_raw['name'] == sel_org]['projectID'].astype(str))
    proj = proj_raw[proj_raw['grant_id'].isin(org_pids)].copy()
else:
    proj = proj_raw[
        proj_raw['programme'].isin(sel_prog if sel_prog else all_progs) &
        (proj_raw['start_year'].between(sel_years[0], sel_years[1]) | proj_raw['start_year'].isna())
    ].copy()

ben = ben_raw[ben_raw['projectID'].isin(proj['grant_id'])].copy()
if sel_country: ben = ben[ben['country_name'].isin(sel_country)]
if sel_act:     ben = ben[ben['activityType'].isin(sel_act)]
if sel_role:    ben = ben[ben['role'].isin(sel_role)]

# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────
st.title("🇪🇺 EU Data Spaces Funding Dashboard")
st.markdown(
    "EU-funded projects on **data spaces**, GAIA-X, federated data, data governance "
    "and the broader data economy — OpenAIRE + CORDIS."
)

# ─────────────────────────────────────────────────────────────────────────────
# Org profile banner
# ─────────────────────────────────────────────────────────────────────────────
if sel_org:
    or_rows     = ben_raw[ben_raw['name'] == sel_org]
    or_info     = or_rows.iloc[0]
    or_type     = ACTIVITY_LABELS.get(str(or_info.get('activityType','')), '—')
    or_country  = COUNTRY_NAMES.get(str(or_info.get('country','')).upper(), '—')
    or_flag     = flag_emoji(str(or_info.get('country','')))
    or_sme      = str(or_info.get('SME','')).lower() == 'true'
    or_projects = or_rows['projectID'].nunique()
    or_coord    = (or_rows['role'] == 'coordinator').sum()
    or_ec       = or_rows['ecContribution'].sum() / 1e6
    or_roles    = " · ".join(f"{v}× {k}" for k, v in or_rows['role'].value_counts().items())

    st.markdown(f"""
    <div class="org-banner">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;">
        <div>
          <div style="font-size:1.35rem;font-weight:800;">{or_flag} {sel_org}</div>
          <div style="opacity:.85;margin-top:4px;font-size:.9rem;">
            {or_type} &nbsp;·&nbsp; {or_country}{"&nbsp;·&nbsp; 🏭 SME" if or_sme else ""}
          </div>
          <div style="margin-top:10px;opacity:.75;font-size:.82rem;">{or_roles}</div>
        </div>
        <div style="display:flex;gap:28px;text-align:center;">
          <div><div style="font-size:1.8rem;font-weight:800;">{or_projects}</div>
               <div style="font-size:.75rem;opacity:.8;">projects</div></div>
          <div><div style="font-size:1.8rem;font-weight:800;">{or_coord}</div>
               <div style="font-size:.75rem;opacity:.8;">as coordinator</div></div>
          <div><div style="font-size:1.8rem;font-weight:800;">€{or_ec:.1f}M</div>
               <div style="font-size:.75rem;opacity:.8;">EC contribution</div></div>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    or_detail = (
        or_rows[['projectID','projectAcronym','role','ecContribution']]
        .merge(proj_raw[['grant_id','title','prog_label','start_date','end_date']],
               left_on='projectID', right_on='grant_id', how='left')
        .drop(columns='grant_id')
    )
    with st.expander(f"📋 {sel_org} — participation detail", expanded=True):
        d = or_detail[['projectAcronym','title','role','ecContribution','prog_label','start_date','end_date']].copy()
        d.columns = ['Acronym','Title','Role','EC Contribution (€)','Programme','Start','End']
        d['EC Contribution (€)'] = pd.to_numeric(d['EC Contribution (€)'], errors='coerce').fillna(0)
        st.dataframe(d.reset_index(drop=True), use_container_width=True,
                     column_config={'EC Contribution (€)': st.column_config.NumberColumn(format='€%.0f'),
                                    'Title': st.column_config.TextColumn(width='large')})
    st.info(f"Dashboard filtered to {or_projects} project(s) involving **{sel_org}**. Clear the search to return to full view.")

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# KPIs
# ─────────────────────────────────────────────────────────────────────────────
n_proj   = len(proj)
ec_total = proj['ec_contribution_eur'].sum() / 1e6
n_orgs   = ben['name'].nunique()
n_ctry   = ben['country'].nunique()
n_coord  = (ben['role'] == 'coordinator').sum()
sme_pct  = ben['IsSME'].mean() * 100 if not ben.empty else 0
avg_ec   = proj['ec_contribution_eur'].mean() / 1e6 if n_proj else 0

c1,c2,c3,c4,c5,c6 = st.columns(6)
for col, val, lbl, sub, klass in [
    (c1, n_proj,         "Projects",            "EU-funded grants",      ""),
    (c2, f"€{ec_total:.1f}M", "EC Contribution",  f"avg €{avg_ec:.1f}M / project", "green"),
    (c3, n_orgs,         "Organisations",       "unique beneficiaries",  "teal"),
    (c4, n_ctry,         "Countries",           "represented",           "orange"),
    (c5, n_coord,        "Coordinators",        "project leads",         "purple"),
    (c6, f"{sme_pct:.0f}%", "SME Share",        "of participations",     ""),
]:
    col.markdown(f"""<div class="kpi {klass}">
      <p class="kpi-val {klass}">{val}</p>
      <p class="kpi-lbl">{lbl}</p>
      <p class="kpi-sub">{sub}</p>
    </div>""", unsafe_allow_html=True)

st.markdown("")

# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Overview",
    "🔬 Projects",
    "🏢 Organisations",
    "🌍 Geography",
    "📈 Trends & Themes",
])

EU_BLUE  = [[0,'#D6E4F7'],[0.5,'#2E75B6'],[1,'#1F4E79']]
PLT_OPTS = dict(plot_bgcolor='white', paper_bgcolor='white',
                margin=dict(l=0,r=10,t=38,b=0))

# ═══════════════════════════════════════════════════════════════════════════
# TAB 1 – OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════
with tab1:
    ca, cb = st.columns(2)

    with ca:
        st.markdown('<div class="sec">Funding by Programme</div>', unsafe_allow_html=True)
        pg = (proj.groupby('prog_label')
              .agg(Projects=('grant_id','count'),
                   EC_M=('ec_contribution_eur', lambda x: x.sum()/1e6))
              .reset_index().sort_values('EC_M'))
        fig = px.bar(pg, x='EC_M', y='prog_label', orientation='h',
                     text='Projects', color='EC_M',
                     color_continuous_scale=EU_BLUE,
                     labels={'EC_M':'EC (M€)','prog_label':'Programme'})
        fig.update_traces(texttemplate='%{text} projects', textposition='outside')
        fig.update_layout(**PLT_OPTS, coloraxis_showscale=False, height=260)
        st.plotly_chart(fig, use_container_width=True)

    with cb:
        st.markdown('<div class="sec">Funding by Action Type</div>', unsafe_allow_html=True)
        at = (proj.groupby('action_type')
              .agg(Projects=('grant_id','count'),
                   EC_M=('ec_contribution_eur', lambda x: x.sum()/1e6))
              .reset_index().sort_values('EC_M').tail(12))
        fig2 = px.bar(at, x='EC_M', y='action_type', orientation='h',
                      text='Projects', color='EC_M',
                      color_continuous_scale=[[0,'#D5E8D4'],[1,'#375623']],
                      labels={'EC_M':'EC (M€)','action_type':'Action Type'})
        fig2.update_traces(texttemplate='%{text}', textposition='outside')
        fig2.update_layout(**PLT_OPTS, coloraxis_showscale=False, height=260)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown('<div class="sec">Project Timeline</div>', unsafe_allow_html=True)
    tl = proj.dropna(subset=['start_date']).copy()
    tl['ec_m'] = tl['ec_contribution_eur'] / 1e6
    fig3 = px.scatter(
        tl, x='start_date', y='acronym',
        size='ec_m', color='prog_label',
        size_max=40,
        color_discrete_sequence=px.colors.qualitative.Bold,
        hover_data={'title':True,'ec_m':':.2f','end_date':True,'action_type':True,'acronym':False},
        labels={'start_date':'Start','acronym':'','ec_m':'EC (M€)','prog_label':'Programme'},
        title=None,
    )
    fig3.update_layout(**PLT_OPTS, height=max(300, n_proj*16),
                       showlegend=True,
                       legend=dict(orientation='h',yanchor='bottom',y=1.01,x=0))
    fig3.update_yaxes(tickfont=dict(size=8))
    st.plotly_chart(fig3, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════
# TAB 2 – PROJECTS
# ═══════════════════════════════════════════════════════════════════════════
with tab2:
    # Budget vs Duration scatter
    cc, cd = st.columns(2)
    with cc:
        st.markdown('<div class="sec">EC Contribution vs Duration</div>', unsafe_allow_html=True)
        sc = proj.dropna(subset=['duration_months','ec_contribution_eur']).copy()
        sc = sc[sc['duration_months'] > 0]
        sc['ec_m'] = sc['ec_contribution_eur'] / 1e6
        fig4 = px.scatter(
            sc, x='duration_months', y='ec_m',
            color='prog_label', size='ec_m', size_max=35,
            hover_data={'acronym':True,'title':True,'duration_months':True,'ec_m':':.2f'},
            color_discrete_sequence=px.colors.qualitative.Bold,
            labels={'duration_months':'Duration (months)','ec_m':'EC (M€)','prog_label':'Programme'},
        )
        fig4.update_layout(**PLT_OPTS, height=300)
        st.plotly_chart(fig4, use_container_width=True)

    with cd:
        st.markdown('<div class="sec">Project Status</div>', unsafe_allow_html=True)
        if 'status' in proj.columns and proj['status'].ne('Unknown').any():
            st_grp = proj['status'].value_counts().reset_index()
            st_grp.columns = ['Status','Count']
            fig5 = px.pie(st_grp, names='Status', values='Count', hole=0.5,
                          color_discrete_sequence=['#1F4E79','#2E75B6','#9DC3E6','#BDD7EE'])
            fig5.update_traces(textinfo='percent+label')
            fig5.update_layout(paper_bgcolor='white', margin=dict(l=0,r=0,t=10,b=0),
                                height=300, showlegend=False)
            st.plotly_chart(fig5, use_container_width=True)
        else:
            # Fallback: projects per programme pie
            pp = proj['prog_label'].value_counts().reset_index()
            pp.columns = ['Programme','Count']
            fig5b = px.pie(pp, names='Programme', values='Count', hole=0.5,
                           color_discrete_sequence=px.colors.qualitative.Bold)
            fig5b.update_traces(textinfo='percent+label')
            fig5b.update_layout(paper_bgcolor='white', margin=dict(l=0,r=0,t=10,b=0),
                                 height=300, showlegend=False)
            st.plotly_chart(fig5b, use_container_width=True)

    # Searchable project table
    st.markdown('<div class="sec">Project List</div>', unsafe_allow_html=True)
    ce, cf = st.columns([4,1])
    with ce:
        search_p = st.text_input("🔍 Search by title, acronym, grant ID or call…", "")
    with cf:
        st.markdown("<br>", unsafe_allow_html=True)
        dl_proj = proj.copy()
        dl_proj['start_date'] = dl_proj['start_date'].dt.strftime('%Y-%m-%d').fillna('')
        dl_proj['end_date']   = dl_proj['end_date'].dt.strftime('%Y-%m-%d').fillna('')
        st.download_button("⬇ Download CSV", dl_proj.to_csv(index=False).encode(),
                           "projects.csv","text/csv")

    pt = proj.copy()
    if search_p:
        m = (pt['title'].str.contains(search_p, case=False, na=False) |
             pt['acronym'].str.contains(search_p, case=False, na=False) |
             pt['grant_id'].str.contains(search_p, case=False, na=False) |
             pt['call_id'].fillna('').str.contains(search_p, case=False, na=False))
        pt = pt[m]

    cols_show = [c for c in ['grant_id','acronym','title','prog_label',
                              'action_type','start_date','end_date',
                              'ec_contribution_eur','cordis_url'] if c in pt.columns]
    pt_d = pt[cols_show].copy()
    pt_d.columns = ['Grant ID','Acronym','Title','Programme','Action','Start',
                    'End','EC (€)','CORDIS'][:len(cols_show)]
    if 'Start' in pt_d: pt_d['Start'] = pd.to_datetime(pt_d['Start']).dt.strftime('%Y-%m-%d')
    if 'End'   in pt_d: pt_d['End']   = pd.to_datetime(pt_d['End']).dt.strftime('%Y-%m-%d')

    st.dataframe(pt_d.reset_index(drop=True), use_container_width=True, height=400,
                 column_config={
                     'Title':  st.column_config.TextColumn(width='large'),
                     'EC (€)': st.column_config.NumberColumn(format='€%.0f'),
                     'CORDIS': st.column_config.LinkColumn('CORDIS', width='small'),
                 })
    st.caption(f"{len(pt_d)} of {n_proj} projects")

# ═══════════════════════════════════════════════════════════════════════════
# TAB 3 – ORGANISATIONS
# ═══════════════════════════════════════════════════════════════════════════
with tab3:
    cg, ch = st.columns(2)

    with cg:
        st.markdown('<div class="sec">Top 15 Coordinators</div>', unsafe_allow_html=True)
        top_c = (ben[ben['role']=='coordinator']
                 .groupby(['name','country_name','activity_label','flag'])
                 .agg(Led=('projectID','nunique'),
                      EC_M=('ecContribution', lambda x: x.sum()/1e6))
                 .reset_index().sort_values('Led').tail(15))
        top_c['label'] = top_c['flag'] + ' ' + top_c['name'].str[:35]
        fig6 = px.bar(top_c, x='Led', y='label', orientation='h',
                      color='activity_label',
                      color_discrete_sequence=px.colors.qualitative.Set2,
                      hover_data={'country_name':True,'EC_M':':.2f','activity_label':True,'flag':False,'label':False},
                      labels={'Led':'Projects coordinated','label':''},
                      text='Led')
        fig6.update_traces(textposition='outside')
        fig6.update_layout(**PLT_OPTS, height=420, showlegend=True,
                           legend=dict(title='Type',orientation='h',y=1.05))
        fig6.update_yaxes(tickfont=dict(size=8))
        st.plotly_chart(fig6, use_container_width=True)

    with ch:
        st.markdown('<div class="sec">Top 15 Beneficiaries by EC Contribution</div>', unsafe_allow_html=True)
        top_b = (ben.groupby(['name','activity_label','flag'])
                 .agg(EC_M=('ecContribution', lambda x: x.sum()/1e6),
                      Projects=('projectID','nunique'))
                 .reset_index().sort_values('EC_M').tail(15))
        top_b['label'] = top_b['flag'] + ' ' + top_b['name'].str[:35]
        fig7 = px.bar(top_b, x='EC_M', y='label', orientation='h',
                      color='activity_label',
                      color_discrete_sequence=px.colors.qualitative.Set2,
                      hover_data={'Projects':True,'activity_label':True,'flag':False,'label':False},
                      labels={'EC_M':'EC Contribution (M€)','label':''},
                      text='EC_M')
        fig7.update_traces(texttemplate='€%{text:.1f}M', textposition='outside')
        fig7.update_layout(**PLT_OPTS, height=420, showlegend=False)
        fig7.update_yaxes(tickfont=dict(size=8))
        st.plotly_chart(fig7, use_container_width=True)

    # SME + Activity type row
    ci, cj, ck = st.columns(3)
    with ci:
        st.markdown('<div class="sec">Organisation Types</div>', unsafe_allow_html=True)
        act_c = ben.groupby('activity_label').size().reset_index(name='Count')
        fig8 = px.pie(act_c, names='activity_label', values='Count', hole=0.45,
                      color_discrete_sequence=px.colors.sequential.Blues_r)
        fig8.update_traces(textinfo='percent+label')
        fig8.update_layout(paper_bgcolor='white', margin=dict(l=0,r=0,t=10,b=0),
                            height=260, showlegend=False)
        st.plotly_chart(fig8, use_container_width=True)

    with cj:
        st.markdown('<div class="sec">SME vs Non-SME</div>', unsafe_allow_html=True)
        sme_c = ben['IsSME'].map({True:'SME ✅',False:'Non-SME'}).value_counts()
        fig9 = px.pie(values=sme_c.values, names=sme_c.index, hole=0.45,
                      color_discrete_sequence=['#375623','#A9D18E'])
        fig9.update_traces(textinfo='percent+label')
        fig9.update_layout(paper_bgcolor='white', margin=dict(l=0,r=0,t=10,b=0),
                            height=260, showlegend=False)
        st.plotly_chart(fig9, use_container_width=True)

    with ck:
        st.markdown('<div class="sec">Roles Breakdown</div>', unsafe_allow_html=True)
        role_c = ben['role'].value_counts().reset_index()
        role_c.columns = ['Role','Count']
        role_labels = {'coordinator':'Coordinator','participant':'Participant',
                       'thirdParty':'Third Party','associatedPartner':'Associated Partner'}
        role_c['Role'] = role_c['Role'].map(lambda x: role_labels.get(x,x))
        fig10 = px.bar(role_c, x='Role', y='Count',
                       color='Role', text='Count',
                       color_discrete_sequence=['#1F4E79','#2E75B6','#9DC3E6','#BDD7EE'])
        fig10.update_traces(textposition='outside')
        fig10.update_layout(**PLT_OPTS, height=260, showlegend=False,
                            xaxis_tickangle=-20)
        st.plotly_chart(fig10, use_container_width=True)

    # Co-participation heatmap
    st.markdown('<div class="sec">Co-participation Heatmap (top organisations that share projects)</div>',
                unsafe_allow_html=True)
    top_n = 12
    top_orgs_list = (ben.groupby('name')['projectID'].nunique()
                     .sort_values(ascending=False).head(top_n).index.tolist())
    ben_top = ben[ben['name'].isin(top_orgs_list)]
    co_matrix = pd.DataFrame(0, index=top_orgs_list, columns=top_orgs_list)
    for pid, grp in ben_top.groupby('projectID'):
        orgs_in_proj = grp['name'].unique()
        for a, b in combinations(orgs_in_proj, 2):
            if a in co_matrix.index and b in co_matrix.columns:
                co_matrix.loc[a, b] += 1
                co_matrix.loc[b, a] += 1

    short = {o: o[:28]+'…' if len(o)>28 else o for o in top_orgs_list}
    co_short = co_matrix.rename(index=short, columns=short)
    fig11 = px.imshow(co_short, color_continuous_scale='Blues',
                      labels=dict(color='Shared projects'),
                      aspect='auto')
    fig11.update_layout(paper_bgcolor='white', margin=dict(l=0,r=0,t=10,b=0), height=380)
    fig11.update_xaxes(tickangle=-35, tickfont=dict(size=9))
    fig11.update_yaxes(tickfont=dict(size=9))
    st.plotly_chart(fig11, use_container_width=True)
    st.caption("Cell value = number of projects both organisations appear in together.")

    # Beneficiary table with download
    st.markdown('<div class="sec">Full Beneficiary List</div>', unsafe_allow_html=True)
    cl, cm = st.columns([4,1])
    with cl:
        search_b = st.text_input("🔍 Search organisation…", "", key="ben_search2")
    with cm:
        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button("⬇ Download CSV", ben.to_csv(index=False).encode(),
                           "beneficiaries.csv","text/csv")
    bt = ben.copy()
    if search_b:
        bt = bt[bt['name'].str.contains(search_b, case=False, na=False) |
                bt['country_name'].str.contains(search_b, case=False, na=False) |
                bt['projectAcronym'].str.contains(search_b, case=False, na=False)]
    bc = [c for c in ['projectAcronym','name','role','country_name','city',
                       'activity_label','IsSME','ecContribution'] if c in bt.columns]
    bd = bt[bc].copy()
    bd.columns = ['Project','Organisation','Role','Country','City','Type','SME','EC (€)'][:len(bc)]
    st.dataframe(bd.reset_index(drop=True), use_container_width=True, height=360,
                 column_config={'EC (€)': st.column_config.NumberColumn(format='€%.0f')})
    st.caption(f"{len(bd)} records")

# ═══════════════════════════════════════════════════════════════════════════
# TAB 4 – GEOGRAPHY
# ═══════════════════════════════════════════════════════════════════════════
with tab4:
    # Choropleth
    st.markdown('<div class="sec">World Map — Beneficiary Participations</div>', unsafe_allow_html=True)
    geo = (ben.dropna(subset=['iso3'])
           .groupby(['iso3','country_name'])
           .agg(Participations=('name','count'),
                Organisations=('name','nunique'),
                Projects=('projectID','nunique'),
                EC_M=('ecContribution', lambda x: x.sum()/1e6))
           .reset_index())
    fig12 = px.choropleth(
        geo, locations='iso3', color='Participations',
        hover_name='country_name',
        hover_data={'iso3':False,'Organisations':True,'Projects':True,'EC_M':':.1f'},
        color_continuous_scale=EU_BLUE,
        labels={'EC_M':'EC (M€)'},
    )
    fig12.update_layout(
        geo=dict(showframe=False, showcoastlines=True,
                 projection_type='natural earth',
                 lataxis_range=[20,75], lonaxis_range=[-30,50]),
        paper_bgcolor='white', margin=dict(l=0,r=0,t=10,b=0), height=400,
        coloraxis_colorbar=dict(title='Participations',thickness=12)
    )
    st.plotly_chart(fig12, use_container_width=True)

    # Country ranking table + bar
    cn, co = st.columns([3,2])
    with cn:
        st.markdown('<div class="sec">Country Ranking</div>', unsafe_allow_html=True)
        ctbl = (ben.groupby(['country','country_name'])
                .agg(Participations=('name','count'),
                     Organisations=('name','nunique'),
                     Projects=('projectID','nunique'),
                     EC_M=('ecContribution', lambda x: x.sum()/1e6))
                .reset_index()
                .sort_values('Participations', ascending=False))
        ctbl['Flag'] = ctbl['country'].map(flag_emoji)
        ctbl['Country'] = ctbl['Flag'] + ' ' + ctbl['country_name']
        ctbl['EC_M'] = ctbl['EC_M'].round(2)
        ctbl_disp = ctbl[['Country','Participations','Organisations','Projects','EC_M']].copy()
        ctbl_disp.columns = ['Country','Participations','Organisations','Projects','EC (M€)']

        cp, cq = st.columns([3,1])
        with cq:
            st.markdown("<br>", unsafe_allow_html=True)
            st.download_button("⬇ CSV", ctbl_disp.to_csv(index=False).encode(),
                               "countries.csv","text/csv")
        st.dataframe(ctbl_disp.reset_index(drop=True), use_container_width=True, height=420,
                     column_config={
                         'Participations': st.column_config.ProgressColumn(
                             format='%d', min_value=0, max_value=int(ctbl_disp['Participations'].max())),
                         'EC (M€)': st.column_config.NumberColumn(format='€%.2f'),
                     })

    with co:
        st.markdown('<div class="sec">EU vs Non-EU</div>', unsafe_allow_html=True)
        eu_codes = {'AT','BE','BG','HR','CY','CZ','DK','EE','FI','FR','DE','GR','EL',
                    'HU','IE','IT','LV','LT','LU','MT','NL','PL','PT','RO','SK','SI','ES','SE'}
        ben['is_eu'] = ben['country'].str.upper().isin(eu_codes)
        eu_grp = ben.groupby('is_eu').agg(
            Participations=('name','count'),
            EC_M=('ecContribution', lambda x: x.sum()/1e6)
        ).reset_index()
        eu_grp['Group'] = eu_grp['is_eu'].map({True:'🇪🇺 EU Member States', False:'🌍 Non-EU'})
        fig13 = px.pie(eu_grp, names='Group', values='Participations', hole=0.5,
                       color_discrete_sequence=['#1F4E79','#9DC3E6'])
        fig13.update_traces(textinfo='percent+label')
        fig13.update_layout(paper_bgcolor='white', margin=dict(l=0,r=0,t=10,b=0),
                             height=220, showlegend=False)
        st.plotly_chart(fig13, use_container_width=True)

        st.markdown('<div class="sec">Top Countries (bar)</div>', unsafe_allow_html=True)
        top_ctry = ctbl.head(12).copy()
        top_ctry['Short'] = top_ctry['Flag'] + ' ' + top_ctry['country_name'].str[:14]
        fig14 = px.bar(top_ctry.sort_values('Participations'), x='Participations', y='Short',
                       orientation='h', color='Participations',
                       color_continuous_scale=EU_BLUE,
                       text='Participations')
        fig14.update_traces(textposition='outside')
        fig14.update_layout(**PLT_OPTS, coloraxis_showscale=False, height=380)
        fig14.update_yaxes(tickfont=dict(size=9))
        st.plotly_chart(fig14, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════
# TAB 5 – TRENDS & THEMES
# ═══════════════════════════════════════════════════════════════════════════
with tab5:
    # Funding trend by year
    cr, cs = st.columns(2)
    with cr:
        st.markdown('<div class="sec">Projects & Funding by Start Year</div>', unsafe_allow_html=True)
        yr = (proj.dropna(subset=['start_year'])
              .groupby(['start_year','prog_label'])
              .agg(Projects=('grant_id','count'),
                   EC_M=('ec_contribution_eur', lambda x: x.sum()/1e6))
              .reset_index())
        yr['start_year'] = yr['start_year'].astype(int)
        fig15 = px.bar(yr, x='start_year', y='Projects', color='prog_label',
                       color_discrete_sequence=px.colors.qualitative.Bold,
                       labels={'start_year':'Year','prog_label':'Programme'})
        fig15.update_layout(**PLT_OPTS, height=280, barmode='stack',
                            legend=dict(orientation='h',y=1.05))
        st.plotly_chart(fig15, use_container_width=True)

    with cs:
        st.markdown('<div class="sec">EC Contribution Trend (M€ by Year)</div>', unsafe_allow_html=True)
        yr_ec = (proj.dropna(subset=['start_year'])
                 .groupby('start_year')
                 .agg(EC_M=('ec_contribution_eur', lambda x: x.sum()/1e6))
                 .reset_index())
        yr_ec['start_year'] = yr_ec['start_year'].astype(int)
        fig16 = px.area(yr_ec, x='start_year', y='EC_M',
                        labels={'start_year':'Year','EC_M':'EC Contribution (M€)'},
                        color_discrete_sequence=['#1F4E79'])
        fig16.update_traces(fill='tozeroy', fillcolor='rgba(31,78,121,0.15)')
        fig16.update_layout(**PLT_OPTS, height=280)
        st.plotly_chart(fig16, use_container_width=True)

    # Keyword treemap
    st.markdown('<div class="sec">Keyword / Theme Landscape</div>', unsafe_allow_html=True)

    STOP = {'and','the','of','in','for','a','to','with','on','by','an','are','is',
            'from','as','that','this','be','which','at','or','not','have','has',
            'been','will','can','its','their','also','project','data','european',
            'eu','research','innovation','new','system','systems','based','using',
            'through','between','within','across','into','more','such','these'}

    raw_kw = []
    for col in ['keywords','subjects','topics']:
        if col in proj.columns:
            raw_kw += proj[col].dropna().tolist()

    words = []
    for text in raw_kw:
        for w in re.split(r'[;,\|/\n]+', str(text)):
            w = w.strip().lower()
            if len(w) > 3 and w not in STOP:
                words.append(w)

    freq = Counter(words).most_common(60)
    if freq:
        kw_df = pd.DataFrame(freq, columns=['Keyword','Count'])
        kw_df['Keyword'] = kw_df['Keyword'].str.title()
        fig17 = px.treemap(kw_df, path=['Keyword'], values='Count',
                           color='Count', color_continuous_scale=EU_BLUE)
        fig17.update_layout(paper_bgcolor='white', margin=dict(l=0,r=0,t=10,b=0), height=400)
        fig17.update_traces(textinfo='label+value')
        st.plotly_chart(fig17, use_container_width=True)
    else:
        st.info("Keyword data not available — run the full scraper to populate CORDIS keyword fields.")

    # Average project metrics
    st.markdown('<div class="sec">Project Size Analytics</div>', unsafe_allow_html=True)
    ct, cu, cv = st.columns(3)
    avg_dur = proj['duration_months'].dropna()
    avg_dur = avg_dur[avg_dur > 0].mean()
    med_ec  = proj['ec_contribution_eur'].median() / 1e6
    max_ec  = proj['ec_contribution_eur'].max() / 1e6
    max_proj= proj.loc[proj['ec_contribution_eur'].idxmax(), 'acronym'] if n_proj else '—'

    for col, val, lbl, sub in [
        (ct, f"{avg_dur:.0f} months" if not pd.isna(avg_dur) else "—", "Avg Project Duration", "across all projects"),
        (cu, f"€{med_ec:.2f}M",   "Median EC Contribution", "50th percentile"),
        (cv, f"€{max_ec:.1f}M",   f"Largest Grant ({max_proj})", "single project max"),
    ]:
        col.markdown(f"""<div class="kpi">
          <p class="kpi-val">{val}</p>
          <p class="kpi-lbl">{lbl}</p>
          <p class="kpi-sub">{sub}</p>
        </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<small>Sources: <a href='https://api.openaire.eu'>OpenAIRE</a> · "
    "<a href='https://cordis.europa.eu'>CORDIS</a> · "
    "<a href='https://ec.europa.eu/info/funding-tenders/opportunities/portal'>EU F&T Portal</a>"
    " &nbsp;|&nbsp; Refresh: run <code>eu_funding_scraper.py</code></small>",
    unsafe_allow_html=True
)

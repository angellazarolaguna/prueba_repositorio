import streamlit as st
import pandas as pd
import altair as alt
import requests
import re
import unicodedata
from urllib.parse import quote, urljoin
from io import StringIO
from datetime import datetime
from bs4 import BeautifulSoup

# ===================== CONFIG =====================
st.set_page_config(page_title="Observatorio ESG — NFQ", page_icon=None, layout="wide")

SHEET_ID = "1tGyDxmB1TuBFiC8k-j19IoSkJO7gkdFCBIlG_hBPUCw"
WORKSHEET = "BBDD"

FORM_ACTION_URL = "https://docs.google.com/forms/d/e/1FAIpQLScTbCS0DRON_-aVzdA4y65_18cicMQdLy98uiapoXqc5B6xeQ/formResponse"

ENTRY_MAP = {k: "" for k in [
    "Nombre","Documento","Link","Autoridad emisora","Tipo de documento","Ámbito de aplicación",
    "Tema ESG","Temática ESG","Descripción","Aplicación",
    "Fecha de publicación","Fecha de aplicación","Comentarios",
    "UG 01, 02, 03 - bancos","UG04 - Asset management","UG05 - Seguros","UG06 - LATAM","UG07 - Corporates",
    "Estado","Mes publicación","Año publicación"
]}

COLUMNS = list(ENTRY_MAP.keys())

# ===================== THEME =====================
NFQ_RED = "#9e1927"; NFQ_BLUE = "#6fa2d9"; NFQ_ORANGE = "#d4781b"; NFQ_PURPLE = "#5a64a8"; NFQ_GREY = "#5c6773"
BG_GRADIENT = f"linear-gradient(135deg, {NFQ_ORANGE}20, {NFQ_RED}20 33%, {NFQ_PURPLE}20 66%, {NFQ_BLUE}20)"

st.markdown(f"""
<style>
.stApp {{ background: {BG_GRADIENT}; background-attachment: fixed; }}
.portal-wrap{{ background:#f2dbe6; padding:18px 22px; border-radius:18px; margin-top:8px; }}
.portal-card{{ background:#fff; border-radius:24px; box-shadow: 0 10px 24px rgb(0 0 0 / 10%); padding:14px 18px; }}
.portal-title{{ font-size:28px; font-weight:800; color:#6b2242; margin:0 0 12px 2px; }}
.table-header,.table-row{{ display:grid; grid-template-columns:1.6fr 1fr 4fr 1.6fr; gap:12px; align-items:center; }}
.table-header{{ font-weight:700; border-bottom:1px solid #eee; padding:10px 4px; }}
.badge-src{{ padding:4px 8px; border-radius:999px; background:#eef4ff; color:#25467a; font-weight:600; font-size:12px; }}
.desc{{ color:#404040; font-size:14px; }}
.hub-tag{{ font-weight:700; color:#222; }}
</style>
""", unsafe_allow_html=True)

# ===================== HELPERS =====================
def _norm_txt(x: str) -> str:
    if x is None: return ""
    s = unicodedata.normalize("NFD", str(x))
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn").lower()

def ensure_schema(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[COLUMNS]

    # Fechas
    for c in ["Fecha de publicación", "Fecha de aplicación"]:
        df.loc[:, c] = pd.to_datetime(df[c], errors="coerce").dt.date

    # Año / Mes
    df.loc[:, "Año publicación"] = pd.to_numeric(df["Año publicación"], errors="coerce").astype("Int64")
    df.loc[:, "Mes publicación"] = df["Mes publicación"].astype(str).replace({"<NA>": ""})

    # Limpiar links HYPERLINK()
    def clean_link(x):
        s = str(x)
        if s.startswith("=HYPERLINK"):
            m = re.search(r'HYPERLINK\("([^"]+)"', s, flags=re.IGNORECASE)
            return m.group(1) if m else ""
        return s
    if "Link" in df.columns:
        df.loc[:, "Link"] = df["Link"].apply(clean_link)

    return df

@st.cache_data(ttl=30)
def load_sheet(sheet_id: str, worksheet: str) -> pd.DataFrame:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={quote(worksheet)}"
    r = requests.get(url, timeout=20, headers={"User-Agent":"Mozilla/5.0"}); r.raise_for_status()
    return ensure_schema(pd.read_csv(StringIO(r.text)).dropna(how="all"))

# ===================== SCRAPING =====================
DEFAULT_KEYWORDS = ["climate","esg","sustainable","transition","risk","net zero"]

def safe_get(url): 
    return requests.get(url, timeout=20, headers={"User-Agent":"Mozilla/5.0"}).text

def extract_links(html, base):
    soup = BeautifulSoup(html,"html.parser"); out=[]
    for a in soup.find_all("a", href=True):
        href = urljoin(base,a["href"])
        txt = a.get_text(" ", strip=True)
        if len(txt)<5: continue
        out.append({"title":txt,"url":href,"source":base})
    return out

@st.cache_data(ttl=600)
def fetch_all_news(kws):
    rows=[]
    for label,url in [
        ("CAF","https://carbonaccountingfinancials.com/en/news-events"),
        ("NZBA","https://www.unepfi.org/net-zero-banking/"),
        ("PACTA","https://pacta.rmi.org/"),
        ("EBA","https://www.eba.europa.eu/homepage"),
        ("BIS","https://www.bis.org/")]:
        try:
            html=safe_get(url)
            for it in extract_links(html,url):
                if any(_norm_txt(k) in _norm_txt(it["title"]) for k in kws):
                    it["source"]=label; rows.append(it)
        except: continue
    return pd.DataFrame(rows).drop_duplicates("url")

def classify_hub(source,title):
    t=_norm_txt(title)
    if "net zero" in t: return "Net Zero"
    if "data" in t or "analytics" in t or "ai" in t: return "Data, Analytics & AI"
    if "pacta" in _norm_txt(source): return "Corporate"
    return "Sustainable Finance"

# ===================== UI =====================
st.title("Observatorio ESG — NFQ")
tabs = st.tabs(["Repositorio","Alta nuevo documento","Noticias","Resumen"])

# --- REPOSITORIO ---
with tabs[0]:
    try: df_full=load_sheet(SHEET_ID,WORKSHEET)
    except Exception: st.error("Error cargando Google Sheet"); st.stop()
    texto_busqueda=st.text_input("Buscar")
    df=df_full.copy()
    if texto_busqueda:
        q=_norm_txt(texto_busqueda); mask=pd.Series(False,index=df.index)
        for c in ["Nombre","Documento","Descripción","Temática ESG"]:
            mask|=df[c].apply(_norm_txt).str.contains(q,na=False)
        df=df[mask]
    st.metric("Total documentos",len(df))
    st.dataframe(df,width="stretch",
        column_config={"Link":st.column_config.LinkColumn("Link")})

# --- ALTA ---
with tabs[1]:
    st.subheader("Alta de documento")
    st.write("Configura FORM_ACTION_URL y ENTRY_MAP para enviar al Google Form.")

# --- NOTICIAS ---
with tabs[2]:
    st.markdown('<div class="portal-wrap"><div class="portal-title">Portal de noticias y novedades</div>',unsafe_allow_html=True)
    kws=st.text_input("Palabras clave",", ".join(DEFAULT_KEYWORDS)).split(",")
    df_news=fetch_all_news(kws)
    st.markdown('<div class="portal-card">',unsafe_allow_html=True)
    st.markdown('<div class="table-header"><div>Hub</div><div>Fuente</div><div>Descripción</div><div>Acciones</div></div>',unsafe_allow_html=True)
    for _,r in df_news.head(20).iterrows():
        hub=classify_hub(r["source"],r["title"])
        c1,c2,c3,c4=st.columns([1.6,1,4,1.6])
        with c1: st.markdown(f'<div class="hub-tag">{hub}</div>',unsafe_allow_html=True)
        with c2: st.markdown(f'<span class="badge-src">{r["source"]}</span>',unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="desc"><a href="{r["url"]}" target="_blank">{r["title"]}</a></div>',unsafe_allow_html=True)
        with c4:
            a,b=st.columns(2)
            if a.button("Añadir",key="a"+r["url"]): st.success("Añadido (demo)")
            if b.button("Descartar",key="d"+r["url"]): st.warning("Descartado (demo)")
    st.markdown("</div></div>",unsafe_allow_html=True)

# --- RESUMEN ---
with tabs[3]:
    st.subheader("Resumen automático")
    url=st.text_input("Pega URL de noticia")
    if url:
        try:
            html=safe_get(url); soup=BeautifulSoup(html,"html.parser")
            text=" ".join(p.get_text(" ",strip=True) for p in soup.find_all("p"))
            sents=re.split(r"(?<=[.!?]) +",text)[:5]
            for s in sents: st.markdown(f"- {s}")
        except Exception as e: st.error(e)

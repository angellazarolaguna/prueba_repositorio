import streamlit as st
import pandas as pd
import altair as alt
import requests
import re
import unicodedata
from urllib.parse import quote, urljoin
from io import StringIO
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from datetime import datetime

# ===================== CONFIG =====================
st.set_page_config(page_title="Observatorio ESG — NFQ", page_icon=None, layout="wide")

# Tu Google Sheet y pestaña:
SHEET_ID = "1tGyDxmB1TuBFiC8k-j19IoSkJO7gkdFCBIlG_hBPUCw"   # <- tu Sheet ID
WORKSHEET = "BBDD"                                         # <- tu pestaña

# Tu Google Form (URL termina en /formResponse):
FORM_ACTION_URL = "https://docs.google.com/forms/d/e/1FAIpQLScTbCS0DRON_-aVzdA4y65_18cicMQdLy98uiapoXqc5B6xeQ/formResponse"

# Pega aquí tus entry.xxxxxx reales cuando los tengas (si no, la pestaña "Alta" avisará).
ENTRY_MAP = {
    "Nombre": "",
    "Documento": "",
    "Link": "",
    "Autoridad emisora": "",
    "Tipo de documento": "",
    "Ámbito de aplicación": "",
    "Tema ESG": "",
    "Temática ESG": "",
    "Descripción": "",
    "Aplicación": "",
    "Fecha de publicación": "",
    "Fecha de aplicación": "",
    "Comentarios": "",
    "UG 01, 02, 03 - bancos": "",
    "UG04 - Asset management": "",
    "UG05 - Seguros": "",
    "UG06 - LATAM": "",
    "UG07 - Corporates": "",
    "Estado": "",
    "Mes publicación": "",
    "Año publicación": "",
}

COLUMNS = [
    "Nombre","Documento","Link","Autoridad emisora","Tipo de documento",
    "Ámbito de aplicación","Tema ESG","Temática ESG","Descripción","Aplicación",
    "Fecha de publicación","Fecha de aplicación","Comentarios",
    "UG 01, 02, 03 - bancos","UG04 - Asset management","UG05 - Seguros",
    "UG06 - LATAM","UG07 - Corporates","Estado","Mes publicación","Año publicación"
]

# ===================== THEME (NFQ) =====================
NFQ_RED = "#9e1927"
NFQ_BLUE = "#6fa2d9"
NFQ_ORANGE = "#d4781b"
NFQ_PURPLE = "#5a64a8"
NFQ_GREY = "#5c6773"
BG_GRADIENT = f"linear-gradient(135deg, {NFQ_ORANGE}20, {NFQ_RED}20 33%, {NFQ_PURPLE}20 66%, {NFQ_BLUE}20)"

st.markdown(f"""
<style>
:root {{
  --nfq-red: {NFQ_RED};
  --nfq-blue: {NFQ_BLUE};
  --nfq-orange: {NFQ_ORANGE};
  --nfq-purple: {NFQ_PURPLE};
}}
.stApp {{
  background: {BG_GRADIENT};
  background-attachment: fixed;
}}
.block-container {{
  padding-top: 1.2rem;
  padding-bottom: 2.5rem;
}}
h1, h2, h3 {{ letter-spacing: 0.2px; }}
[data-testid="stMetric"] {{
  background: #ffffffcc;
  border: 1px solid #ffffff;
  border-radius: 16px;
  padding: 12px 16px;
  box-shadow: 0 2px 12px rgb(0 0 0 / 6%);
}}
[data-testid="stDataFrame"] {{
  background: #ffffffee;
  border-radius: 16px;
  box-shadow: 0 4px 18px rgb(0 0 0 / 10%);
  border: 1px solid #ffffff;
  overflow: hidden;
}}
section[data-testid="stSidebar"] > div {{
  background: #ffffffd8;
  border-left: 4px solid var(--nfq-purple);
}}
[data-testid="stHorizontalBlock"] [data-baseweb="tab"] {{
  background: transparent;
}}
/* Tarjetas de noticias */
.card {{
  background: #ffffffee;
  border-radius: 16px;
  border: 1px solid #fff;
  box-shadow: 0 6px 18px rgb(0 0 0 / 10%);
  padding: 14px 16px;
  margin-bottom: 12px;
}}
.card h4 {{
  margin: 0 0 6px 0;
}}
.card small {{
  color: {NFQ_GREY};
}}
</style>
""", unsafe_allow_html=True)

# Tema Altair
def nfq_theme():
    return {
        "config": {
            "view": {"stroke": "transparent"},
            "background": None,
            "font": "Inter, Segoe UI, system-ui, sans-serif",
            "axis": {
                "labelColor": NFQ_GREY,
                "titleColor": NFQ_GREY,
                "gridColor": "#e9edf3",
                "tickColor": "#e9edf3"
            },
            "legend": {"labelColor": NFQ_GREY, "titleColor": NFQ_GREY},
            "range": {
                "category": [NFQ_ORANGE, NFQ_RED, NFQ_PURPLE, NFQ_BLUE, "#2e7d32", "#8e24aa"]
            },
            "bar": {"cornerRadiusTopLeft": 8, "cornerRadiusTopRight": 8},
            "area": {"line": True}
        }
    }
alt.themes.register("nfq", nfq_theme)
alt.themes.enable("nfq")

# ===================== HELPERS =====================
def _norm_txt(x: str) -> str:
    """minúsculas + sin acentos (NFD) para búsquedas robustas."""
    if x is None:
        return ""
    s = str(x)
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s.lower()

def ensure_schema(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[COLUMNS]
    # Fechas
    for c in ["Fecha de publicación","Fecha de aplicación"]:
        df[c] = pd.to_datetime(df[c], errors="coerce").dt.date
    # Año / Mes
    df["Año publicación"] = pd.to_numeric(df["Año publicación"], errors="coerce").astype("Int64")
    df["Mes publicación"] = df["Mes publicación"].astype(str).replace({"<NA>": ""})
    # Extraer URL si viene como =HYPERLINK("url","texto")
    def clean_link(x):
        s = str(x)
        if s.startswith("=HYPERLINK"):
            m = re.search(r'HYPERLINK\("([^"]+)"', s, flags=re.IGNORECASE)
            return m.group(1) if m else ""
        return s
    if "Link" in df.columns:
        df["Link"] = df["Link"].apply(clean_link)
    return df

@st.cache_data(show_spinner=False, ttl=30)
def load_sheet(sheet_id: str, worksheet: str) -> pd.DataFrame:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={quote(worksheet)}"
    r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    df = pd.read_csv(StringIO(r.text))
    df = df.dropna(how="all")
    return ensure_schema(df)

# ===================== SCRAPING (Noticias) =====================
DEFAULT_KEYWORDS = ["climate", "climate risk", "esg", "sustainable", "transition risk", "physical risk", "net zero"]

def safe_get(url: str) -> str:
    r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.text

def extract_links(html: str, base_url: str) -> list[dict]:
    """Extrae links con texto; intenta detectar fecha en el texto cercano."""
    soup = BeautifulSoup(html, "lxml")
    items = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("#"):
            continue
        url = urljoin(base_url, href)
        text = " ".join(a.get_text(" ", strip=True).split())
        if not text:
            # intenta con aria-label o title
            text = a.get("title") or a.get("aria-label") or ""
        text = text.strip()
        # fecha (heurística)
        date_str = None
        for parent in [a.parent, a.find_parent("article"), a.find_parent("li"), a.find_parent("div")]:
            if not parent:
                continue
            m = re.search(r"(\d{1,2}\s+[A-Za-z]{3,}\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})", parent.get_text(" ", strip=True))
            if m:
                date_str = m.group(1)
                break
        items.append({"title": text, "url": url, "raw_date": date_str})
    # limpiar duplicados por url
    seen = set()
    dedup = []
    for it in items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        dedup.append(it)
    return dedup

def parse_date(raw):
    if not raw:
        return None
    try:
        return dateparser.parse(raw, dayfirst=True, fuzzy=True)
    except Exception:
        return None

def site_scraper(label: str, base_url: str, list_url: str | None = None, keywords: list[str] | None = None, must_contain: list[str] | None = None) -> pd.DataFrame:
    """
    - label: nombre de la fuente (p.ej. 'EBA')
    - base_url: URL base
    - list_url: URL específica de listados (si existe)
    - keywords: si se pasan, filtramos título por estas palabras (case/acentos insensitive)
    - must_contain: si se pasan, el href debe contener alguna (p.ej. 'news','press')
    """
    urls_to_fetch = [u for u in [list_url or base_url] if u]
    rows = []
    for u in urls_to_fetch:
        try:
            html = safe_get(u)
            links = extract_links(html, base_url)
            for it in links:
                title_norm = _norm_txt(it["title"])
                href_norm = _norm_txt(it["url"])
                keep = True
                if must_contain:
                    keep = any(mc in href_norm for mc in [m.lower() for m in must_contain])
                if keep and keywords:
                    keep = any(k in title_norm for k in [_norm_txt(k) for k in keywords])
                if keep and it["title"] and len(it["title"]) > 4:
                    rows.append({
                        "source": label,
                        "title": it["title"],
                        "url": it["url"],
                        "date": parse_date(it["raw_date"]),
                    })
        except Exception:
            continue
    if not rows:
        return pd.DataFrame(columns=["source","title","url","date"])
    df = pd.DataFrame(rows).drop_duplicates(subset=["url"])
    df["date_str"] = df["date"].dt.strftime("%Y-%m-%d").fillna("")
    return df

@st.cache_data(show_spinner=False, ttl=600)
def fetch_all_news(user_keywords: list[str]) -> pd.DataFrame:
    kws = user_keywords or DEFAULT_KEYWORDS

    # CAF
    df_caf = site_scraper("CAF",
        base_url="https://carbonaccountingfinancials.com/",
        list_url="https://carbonaccountingfinancials.com/en/news-events",
        keywords=None, must_contain=["news", "event"]
    )

    # NZBA (UNEPFI)
    df_nzba = site_scraper("NZBA (UNEPFI)",
        base_url="https://www.unepfi.org/net-zero-banking/",
        list_url="https://www.unepfi.org/net-zero-banking/",
        keywords=["member", "join", "joined", "signatory", "signatories"] + kws,
        must_contain=["news", "announcement", "press", "net-zero-banking"]
    )

    # PACTA (RMI)
    df_pacta = site_scraper("PACTA",
        base_url="https://pacta.rmi.org/",
        list_url="https://pacta.rmi.org/",
        keywords=kws, must_contain=["news", "blog", "updates", "pacta"]
    )

    # EBA (filtrar por keywords ESG)
    df_eba = site_scraper("EBA",
        base_url="https://www.eba.europa.eu/",
        list_url="https://www.eba.europa.eu/homepage",
        keywords=kws, must_contain=["news", "press", "publications", "esg", "sustainable", "risk"]
    )

    # BIS (filtrar por keywords ESG)
    df_bis = site_scraper("BIS",
        base_url="https://www.bis.org/",
        list_url="https://www.bis.org/",
        keywords=kws, must_contain=["press", "speeches", "publications", "research", "green", "climate", "esg", "sustainable"]
    )

    df_all = pd.concat([df_caf, df_nzba, df_pacta, df_eba, df_bis], ignore_index=True)
    # Ordenar por fecha si hay; si no, por fuente y título
    df_all = df_all.sort_values(by=["date","source","title"], ascending=[False, True, True], na_position="last")
    return df_all

# ===================== RESUMEN "IA local" =====================
STOPWORDS = set("""
a al algo algunas algunos ante antes como con contra cual cuando de del desde donde dos e el ella ellas ellos en entre era erais eramos eran es esa esas ese eso esos esta estaba estabais estabamos estaban estado estais estamos estan estar este esto estos fue fui fuimos fueron ha habéis hemos han hasta hay la las le les lo los mas me mi mis mucho muy nada ni no nos o os para pero poco por porque que quien se sin sobre somos son soy su sus te tiene tieneis tenemos tienen tuve tuvo u un una uno y ya the of to in for on at by from as is are was were be been being this that these those with without into through about over after before under again further then once here there when where why how all any both each few more most other some such no nor not only own same so than too very can will just don should now
""".split())

def summarize_text(text: str, max_sentences: int = 6) -> list[str]:
    """Resumen extractivo muy simple: normaliza, puntúa y devuelve top frases."""
    # Limpieza básica
    text = re.sub(r"\s+", " ", text).strip()
    # Segmentar por frases
    sentences = re.split(r"(?<=[\.\!\?])\s+(?=[A-ZÁÉÍÓÚÑ])", text)
    if len(sentences) <= max_sentences:
        return sentences

    # Puntuación por frecuencia de términos (sin acentos, sin stopwords)
    def tokenize(s):
        s_norm = _norm_txt(s)
        tokens = re.findall(r"[a-záéíóúñ]+", s_norm)
        return [t for t in tokens if t not in STOPWORDS and len(t) > 2]

    # Term weights
    from collections import Counter
    global_counts = Counter()
    sent_tokens = []
    for s in sentences:
        toks = tokenize(s)
        sent_tokens.append(toks)
        global_counts.update(toks)

    # Score por suma de pesos + bonus por longitud moderada
    scores = []
    for toks, s in zip(sent_tokens, sentences):
        score = sum(global_counts.get(t, 0) for t in toks)
        length = len(s)
        if 80 <= length <= 300:
            score *= 1.15
        scores.append(score)

    # Top-N manteniendo orden original
    idx_sorted = sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)[:max_sentences]
    idx_sorted = sorted(idx_sorted)
    return [sentences[i].strip() for i in idx_sorted]

def extract_main_text(url: str) -> str:
    """Descarga una página y devuelve texto 'principal' (heurístico)."""
    html = safe_get(url)
    soup = BeautifulSoup(html, "lxml")
    # quitar nav/footer/aside/script/style
    for tag in soup(["script", "style", "noscript"]):
        tag.extract()
    for sel in ["header", "nav", "footer", "aside", ".sidebar", ".menu", ".breadcrumbs"]:
        for t in soup.select(sel):
            t.extract()
    # preferir article / main / contenido
    container = soup.find("article") or soup.find("main") or soup.find("div", {"class": re.compile(r"content|post|entry", re.I)}) or soup
    # juntar párrafos
    paras = [p.get_text(" ", strip=True) for p in container.find_all(["p", "li"])]
    txt = " ".join(p for p in paras if len(p) > 40)
    return re.sub(r"\s+", " ", txt).strip()

# ===================== UI =====================
st.title("Observatorio ESG — NFQ")

tabs = st.tabs(["Repositorio", "Alta nuevo documento", "Noticias", "Resumen (IA local)"])

# ------------ TAB 1: REPOSITORIO ------------
with tabs[0]:
    try:
        df_full = load_sheet(SHEET_ID, WORKSHEET)
    except Exception as e:
        st.error("No se pudo cargar el Google Sheet. Verifica permisos (Lector público), SHEET_ID y nombre de pestaña.")

    # Filtros
    with st.expander("Filtros", expanded=False):
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1: filtro_anio = st.multiselect("Año publicación", sorted([x for x in df_full["Año publicación"].dropna().unique()]))
        with col2: filtro_tema = st.multiselect("Tema ESG", sorted([str(x) for x in df_full["Tema ESG"].dropna().unique()]))
        with col3: filtro_tipo = st.multiselect("Tipo de documento", sorted([str(x) for x in df_full["Tipo de documento"].dropna().unique()]))
        with col4: filtro_ambito = st.multiselect("Ámbito de aplicación", sorted([str(x) for x in df_full["Ámbito de aplicación"].dropna().unique()]))
        with col5: filtro_estado = st.multiselect("Estado", sorted([str(x) for x in df_full["Estado"].dropna().unique()]))
        texto_busqueda = st.text_input("Búsqueda libre (Nombre, Documento, Descripción, Temática)")

    df = df_full.copy()
    if filtro_anio: df = df[df["Año publicación"].isin(filtro_anio)]
    if filtro_tema: df = df[df["Tema ESG"].astype(str).isin(filtro_tema)]
    if filtro_tipo: df = df[df["Tipo de documento"].astype(str).isin(filtro_tipo)]
    if filtro_ambito: df = df[df["Ámbito de aplicación"].astype(str).isin(filtro_ambito)]
    if filtro_estado: df = df[df["Estado"].astype(str).isin(filtro_estado)]
    if texto_busqueda:
        q = _norm_txt(texto_busqueda)
        mask = pd.Series(False, index=df.index)
        for col in ["Nombre","Documento","Descripción","Temática ESG"]:
            col_norm = df[col].apply(_norm_txt)
            mask = mask | col_norm.str.contains(q, na=False)
        df = df[mask]

    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Total documentos", len(df))
    with c2: st.metric("Años distintos", df["Año publicación"].nunique())
    with c3: st.metric("Temas ESG", df["Tema ESG"].nunique())
    with c4: st.metric("Autoridades emisoras", df["Autoridad emisora"].nunique())

    # ── Gráficos centrados y mejorados ──
    st.markdown("#### Vista general")

    # 1) Barras Año
    dfa = df.dropna(subset=["Año publicación"]).copy()
    if len(dfa) > 0:
        dfa["_count"] = 1
        dfa = dfa.sort_values("Año publicación")
        sel_year = alt.selection_point(fields=["Año publicación"], nearest=True, on="mouseover", empty="none")
        bars_year = (
            alt.Chart(dfa)
            .mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8)
            .encode(
                x=alt.X("Año publicación:O", title="Año", sort="ascending"),
                y=alt.Y("sum(_count):Q", title="Nº documentos"),
                color=alt.value(NFQ_ORANGE),
                opacity=alt.condition(sel_year, alt.value(1), alt.value(0.7)),
                tooltip=[alt.Tooltip("Año publicación:O", title="Año"),
                         alt.Tooltip("sum(_count):Q", title="Nº docs", format=",.0f")],
            ).add_params(sel_year).properties(height=240)
        )
        labels_year = (
            alt.Chart(dfa).mark_text(dy=-6, fontSize=12, color=NFQ_GREY)
            .encode(x=alt.X("Año publicación:O", sort="ascending"),
                    y=alt.Y("sum(_count):Q"),
                    text=alt.Text("sum(_count):Q", format=",.0f"))
        )
        c1c, c2c, c3c = st.columns([1,2,1]); 
        with c2c: st.altair_chart(bars_year + labels_year, use_container_width=True)

    # 2) Donut Tema ESG
    dft = df.dropna(subset=["Tema ESG"]).copy()
    if len(dft) > 0:
        dft = (dft.assign(_count=1).groupby("Tema ESG", as_index=False)["_count"].sum().sort_values("_count", ascending=False))
        donut = (
            alt.Chart(dft).mark_arc(outerRadius=110, innerRadius=58, cornerRadius=6)
            .encode(theta=alt.Theta("_count:Q", stack=True, title=None),
                    color=alt.Color("Tema ESG:N", legend=alt.Legend(title=None)),
                    tooltip=[alt.Tooltip("Tema ESG:N", title="Tema"),
                             alt.Tooltip("_count:Q", title="Nº docs", format=",.0f")])
            .properties(height=260)
        )
        labels_donut = (
            alt.Chart(dft).mark_text(radius=130, fontSize=12, color=NFQ_GREY)
            .encode(theta=alt.Theta("_count:Q", stack=True),
                    text=alt.Text("Tema ESG:N"))
        )
        c4c, c5c, c6c = st.columns([1,2,1]); 
        with c5c: st.altair_chart(donut + labels_donut, use_container_width=True)

    # 3) Ranking Tipo doc
    st.markdown("#### Top tipos de documento")
    df_tipo = df.dropna(subset=["Tipo de documento"]).copy()
    if len(df_tipo) > 0:
        df_tipo = (df_tipo.assign(_count=1).groupby("Tipo de documento", as_index=False)["_count"].sum()
                   .sort_values("_count", ascending=False).head(8).sort_values("_count", ascending=True))
        sel_tipo = alt.selection_point(fields=["Tipo de documento"], nearest=True, on="mouseover", empty="none")
        bars_tipo = (
            alt.Chart(df_tipo).mark_bar(cornerRadius=8)
            .encode(x=alt.X("_count:Q", title="Nº documentos"),
                    y=alt.Y("Tipo de documento:N", sort=alt.SortField("_count", order="ascending"), title=None),
                    color=alt.value(NFQ_PURPLE),
                    opacity=alt.condition(sel_tipo, alt.value(1), alt.value(0.75)),
                    tooltip=[alt.Tooltip("Tipo de documento:N", title="Tipo"),
                             alt.Tooltip("_count:Q", title="Nº docs", format=",.0f")])
            .add_params(sel_tipo).properties(height=300)
        )
        labels_tipo = (
            alt.Chart(df_tipo).mark_text(align="left", dx=6, fontSize=12, color=NFQ_GREY)
            .encode(x=alt.X("_count:Q"), y=alt.Y("Tipo de documento:N", sort=alt.SortField("_count", order="ascending")),
                    text=alt.Text("_count:Q", format=",.0f"))
        )
        c7c, c8c, c9c = st.columns([1,2,1]); 
        with c8c: st.altair_chart(bars_tipo + labels_tipo, use_container_width=True)

    # Tabla con links clicables
    st.markdown("#### Repositorio")
    st.dataframe(
        df,
        use_container_width=True,
        column_config={"Link": st.column_config.LinkColumn("Link", help="Abrir documento")},
        height=520
    )

# ------------ TAB 2: ALTA NUEVO ------------
with tabs[1]:
    st.markdown("#### Dar de alta un nuevo documento")
    if not FORM_ACTION_URL.strip():
        st.warning("Configura FORM_ACTION_URL (termina en /formResponse) para habilitar el alta.")
    missing_entries = [k for k,v in ENTRY_MAP.items() if v.strip()=="" and k in COLUMNS]
    if missing_entries:
        st.info("Faltan `entry.xxxxx` para: " + ", ".join(missing_entries))

    with st.form("alta_form"):
        colA, colB = st.columns(2)
        with colA:
            nombre = st.text_input("Nombre*", placeholder="Título breve del documento")
            documento = st.text_input("Documento", placeholder="Código/Identificador si aplica")
            link = st.text_input("Link", placeholder="https://...")
            autoridad = st.selectbox("Autoridad Emisora", ["", "EBA", "ESMA", "UE", "CNMV"])
            tipo = st.text_input("Tipo de documento", placeholder="Normativa, guía, consulta, informe...")
            ambito = st.text_input("Ámbito de aplicación", placeholder="UE, ES, Global...")
            tema_esg = st.selectbox("Tema ESG", ["", "E", "S", "G", "Mixto"])
            tematica_esg = st.text_input("Temática ESG", placeholder="Taxonomía, divulgación, riesgos, etc.")
            descripcion = st.text_area("Descripción", placeholder="Resumen breve")
            aplicacion = st.text_input("Aplicación", placeholder="Obligatoria/voluntaria, sectores, etc.")
        with colB:
            f_pub = st.date_input("Fecha de publicación", value=None)
            f_apl = st.date_input("Fecha de aplicación", value=None)
            comentarios = st.text_area("Comentarios")
            ug_bancos = st.checkbox("UG 01, 02, 03 - bancos", value=False)
            ug_am = st.checkbox("UG04 - Asset management", value=False)
            ug_seguros = st.checkbox("UG05 - Seguros", value=False)
            ug_latam = st.checkbox("UG06 - LATAM", value=False)
            ug_corp = st.checkbox("UG07 - Corporates", value=False)
            estado = st.selectbox("Estado", ["", "Borrador", "Propuesta", "En consulta", "Publicado", "Derogado", "Fuera de alcance"])
            mes_pub = st.text_input("Mes publicación", placeholder="Ej. enero / 01 / Q1")
            anio_pub = st.number_input("Año publicación", min_value=1900, max_value=2100, step=1, format="%d")

        submitted = st.form_submit_button("Añadir documento")
        if submitted:
            if not nombre.strip():
                st.error("El campo *Nombre* es obligatorio.")
            elif not FORM_ACTION_URL.strip():
                st.error("Falta configurar FORM_ACTION_URL (termina en /formResponse).")
            elif any(v.strip()=="" for v in ENTRY_MAP.values()):
                st.error("Faltan `entry.xxxxx` en ENTRY_MAP. Complétalos para enviar al Form.")
            else:
                payload = {
                    ENTRY_MAP["Nombre"]: nombre.strip(),
                    ENTRY_MAP["Documento"]: documento.strip(),
                    ENTRY_MAP["Link"]: link.strip(),
                    ENTRY_MAP["Autoridad emisora"]: autoridad.strip(),
                    ENTRY_MAP["Tipo de documento"]: tipo.strip(),
                    ENTRY_MAP["Ámbito de aplicación"]: ambito.strip(),
                    ENTRY_MAP["Tema ESG"]: tema_esg.strip(),
                    ENTRY_MAP["Temática ESG"]: tematica_esg.strip(),
                    ENTRY_MAP["Descripción"]: descripcion.strip(),
                    ENTRY_MAP["Aplicación"]: aplicacion.strip(),
                    ENTRY_MAP["Fecha de publicación"]: f_pub.isoformat() if f_pub else "",
                    ENTRY_MAP["Fecha de aplicación"]: f_apl.isoformat() if f_apl else "",
                    ENTRY_MAP["Comentarios"]: comentarios.strip(),
                    ENTRY_MAP["UG 01, 02, 03 - bancos"]: "Sí" if ug_bancos else "",
                    ENTRY_MAP["UG04 - Asset management"]: "Sí" if ug_am else "",
                    ENTRY_MAP["UG05 - Seguros"]: "Sí" if ug_seguros else "",
                    ENTRY_MAP["UG06 - LATAM"]: "Sí" if ug_latam else "",
                    ENTRY_MAP["UG07 - Corporates"]: "Sí" if ug_corp else "",
                    ENTRY_MAP["Estado"]: estado,
                    ENTRY_MAP["Mes publicación"]: str(mes_pub).strip(),
                    ENTRY_MAP["Año publicación"]: int(anio_pub) if anio_pub else ""
                }
                try:
                    r = requests.post(FORM_ACTION_URL, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=20)
                    if r.status_code in (200, 302):
                        st.success("Documento enviado correctamente.")
                        st.balloons()
                    else:
                        st.error(f"No se pudo enviar al Form (status {r.status_code}). Revisa FORM_ACTION_URL y ENTRY_MAP.")
                except Exception as e:
                    st.error(f"Error al enviar al Form: {e}")

# ------------ TAB 3: NOTICIAS (Scraping) ------------
with tabs[2]:
    st.subheader("Últimas noticias (CAF, NZBA/UNEPFI, PACTA, EBA, BIS)")
    kw_input = st.text_input("Palabras clave (coma separada)", value=", ".join(DEFAULT_KEYWORDS))
    kws = [k.strip() for k in kw_input.split(",") if k.strip()]
    with st.spinner("Cargando noticias..."):
        news_df = fetch_all_news(kws)

    st.caption("Sugerencia: añade/quita palabras clave para ajustar los resultados de EBA/BIS/NZBA.")
    if news_df.empty:
        st.info("No se encontraron resultados.")
    else:
        # Tarjetas
        for _, row in news_df.head(50).iterrows():
            st.markdown(
                f"""
                <div class="card">
                    <small>{row['source']} • {row.get('date_str','') or ''}</small>
                    <h4><a href="{row['url']}" target="_blank">{row['title']}</a></h4>
                    <small><a href="{row['url']}" target="_blank">{row['url']}</a></small>
                </div>
                """,
                unsafe_allow_html=True
            )
        with st.expander("Ver en tabla"):
            st.dataframe(news_df[["source","date_str","title","url"]].rename(columns={"date_str":"fecha"}), use_container_width=True)

# ------------ TAB 4: RESUMEN (IA local) ------------
with tabs[3]:
    st.subheader("Resumen automático de una noticia")
    if 'news_df' not in locals():
        st.info("Primero visita la pestaña Noticias para cargar resultados.")
    else:
        # Selector de noticia
        options = [f"{r['source']} — {r.get('date_str','')} — {r['title']}" for _, r in news_df.iterrows()]
        opt = st.selectbox("Elige una noticia", options) if options else None
        if opt:
            idx = options.index(opt)
            row = news_df.iloc[idx]
            url = row["url"]
            with st.spinner("Extrayendo y resumiendo contenido..."):
                try:
                    raw_text = extract_main_text(url)
                    bullets = summarize_text(raw_text, max_sentences=6)
                    st.markdown(f"**Fuente:** {row['source']}  \n**Fecha:** {row.get('date_str','')}  \n**URL:** {url}")
                    st.markdown("### Resumen (puntos clave)")
                    for b in bullets:
                        st.markdown(f"- {b}")
                    with st.expander("Texto extraído (depuración)"):
                        st.write(raw_text[:4000] + ("..." if len(raw_text) > 4000 else ""))
                except Exception as e:
                    st.error(f"No se pudo resumir la página: {e}")


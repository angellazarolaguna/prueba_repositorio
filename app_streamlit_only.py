import streamlit as st
import pandas as pd
import altair as alt
import requests
from urllib.parse import quote
from io import StringIO

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
NFQ_GREY = "#5c6773"  # añadido para tipografías/labels
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
</style>
""", unsafe_allow_html=True)

# Tema Altair (colores, barras redondeadas, tipografía)
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
            "legend": {
                "labelColor": NFQ_GREY,
                "titleColor": NFQ_GREY
            },
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
            import re
            m = re.search(r'HYPERLINK\("([^"]+)"', s, flags=re.IGNORECASE)
            return m.group(1) if m else ""
        return s
    if "Link" in df.columns:
        df["Link"] = df["Link"].apply(clean_link)
    return df

@st.cache_data(show_spinner=False, ttl=30)
def load_sheet(sheet_id: str, worksheet: str) -> pd.DataFrame:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={quote(worksheet)}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    df = pd.read_csv(StringIO(r.text))
    df = df.dropna(how="all")
    return ensure_schema(df)

# ===================== UI =====================
st.title("Observatorio ESG — NFQ")

tabs = st.tabs(["Repositorio", "Alta nuevo documento"])

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
        mask = pd.Series(False, index=df.index)
        for col in ["Nombre","Documento","Descripción","Temática ESG"]:
            mask = mask | df[col].astype(str).str.contains(texto_busqueda, case=False, na=False)
        df = df[mask]

    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Total documentos", len(df))
    with c2: st.metric("Años distintos", df["Año publicación"].nunique())
    with c3: st.metric("Temas ESG", df["Tema ESG"].nunique())
    with c4: st.metric("Autoridades emisoras", df["Autoridad emisora"].nunique())

    # ───────────────────── Gráficos centrados y mejorados ─────────────────────
    st.markdown("#### Vista general")

    # ===== 1) Documentos por año (barras redondeadas + labels + hover) =====
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
                tooltip=[
                    alt.Tooltip("Año publicación:O", title="Año"),
                    alt.Tooltip("sum(_count):Q", title="Nº docs", format=",.0f"),
                ],
            )
            .add_params(sel_year)
            .properties(height=240, padding={"left": 10, "right": 10, "top": 10, "bottom": 10})
            .configure_title(anchor="middle")
        )

        labels_year = (
            alt.Chart(dfa)
            .mark_text(dy=-6, fontSize=12, color=NFQ_GREY)
            .encode(
                x=alt.X("Año publicación:O", sort="ascending"),
                y=alt.Y("sum(_count):Q"),
                text=alt.Text("sum(_count):Q", format=",.0f"),
            )
        )

        c1c, c2c, c3c = st.columns([1, 2, 1])   # centrado real
        with c2c:
            st.altair_chart(bars_year + labels_year, use_container_width=True)

    st.markdown("")  # respiro

    # ===== 2) Distribución por Tema ESG (donut con etiquetas externas) =====
    dft = df.dropna(subset=["Tema ESG"]).copy()
    if len(dft) > 0:
        dft = (
            dft.assign(_count=1)
               .groupby("Tema ESG", as_index=False)["_count"].sum()
               .sort_values("_count", ascending=False)
        )

        donut = (
            alt.Chart(dft)
            .mark_arc(outerRadius=110, innerRadius=58, cornerRadius=6)
            .encode(
                theta=alt.Theta("_count:Q", stack=True, title=None),
                color=alt.Color("Tema ESG:N", legend=alt.Legend(title=None)),
                tooltip=[
                    alt.Tooltip("Tema ESG:N", title="Tema"),
                    alt.Tooltip("_count:Q", title="Nº docs", format=",.0f"),
                ],
            )
            .properties(height=260)
            .configure_title(anchor="middle")
        )

        labels_donut = (
            alt.Chart(dft)
            .mark_text(radius=130, fontSize=12, color=NFQ_GREY)
            .encode(
                theta=alt.Theta("_count:Q", stack=True),
                text=alt.Text("Tema ESG:N"),
            )
        )

        c4c, c5c, c6c = st.columns([1, 2, 1])   # centrado real
        with c5c:
            st.altair_chart(donut + labels_donut, use_container_width=True)

    st.markdown("")  # respiro

    # ===== 3) Top 8 Tipos de documento (ranking horizontal elegante) =====
    df_tipo = df.dropna(subset=["Tipo de documento"]).copy()
    if len(df_tipo) > 0:
        df_tipo = (
            df_tipo.assign(_count=1)
                   .groupby("Tipo de documento", as_index=False)["_count"].sum()
                   .sort_values("_count", ascending=False)
                   .head(8)
                   .sort_values("_count", ascending=True)
        )

        sel_tipo = alt.selection_point(fields=["Tipo de documento"], nearest=True, on="mouseover", empty="none")

        bars_tipo = (
            alt.Chart(df_tipo)
            .mark_bar(cornerRadius=8)
            .encode(
                x=alt.X("_count:Q", title="Nº documentos"),
                y=alt.Y("Tipo de documento:N", sort=alt.SortField("_count", order="ascending"), title=None),
                color=alt.value(NFQ_PURPLE),
                opacity=alt.condition(sel_tipo, alt.value(1), alt.value(0.75)),
                tooltip=[
                    alt.Tooltip("Tipo de documento:N", title="Tipo"),
                    alt.Tooltip("_count:Q", title="Nº docs", format=",.0f"),
                ],
            )
            .add_params(sel_tipo)
            .properties(height=300, padding={"left": 4, "right": 4, "top": 6, "bottom": 6})
        )

        labels_tipo = (
            alt.Chart(df_tipo)
            .mark_text(align="left", dx=6, fontSize=12, color=NFQ_GREY)
            .encode(
                x=alt.X("_count:Q"),
                y=alt.Y("Tipo de documento:N", sort=alt.SortField("_count", order="ascending")),
                text=alt.Text("_count:Q", format=",.0f"),
            )
        )

        c7c, c8c, c9c = st.columns([1, 2, 1])   # centrado real
        with c8c:
            st.altair_chart(bars_tipo + labels_tipo, use_container_width=True)

    # Tabla con links clicables
    st.markdown("#### Repositorio")
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "Link": st.column_config.LinkColumn("Link", help="Abrir documento"),
        },
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

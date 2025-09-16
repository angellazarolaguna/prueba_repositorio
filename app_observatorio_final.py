import streamlit as st
import pandas as pd
import altair as alt
import requests
from urllib.parse import quote
from io import StringIO
from datetime import date

st.set_page_config(page_title="Observatorio ESG", page_icon="📚", layout="wide")

# ===========================================================
# CONFIGURA AQUÍ
# ===========================================================
# Tu Google Sheet (pestaña BBDD)
SHEET_ID = "1tGyDxmB1TuBFiC8k-j19IoSkJO7gkdFCBIlG_hBPUCw"
WORKSHEET = "BBDD"

# Tu Google Form de alta (URL termina en /formResponse)
FORM_ACTION_URL = "https://docs.google.com/forms/d/e/1FAIpQLScTbCS0DRON_-aVzdA4y65_18cicMQdLy98uiapoXqc5B6xeQ/formResponse"

# Mapeo columnas → entry.xxxxx del Form (rellena con tus entry reales)
ENTRY_MAP = {
    "Nombre": "entry.xxxxx",
    "Documento": "entry.xxxxx",
    "Link": "entry.xxxxx",
    "Autoridad emisora": "entry.xxxxx",
    "Tipo de documento": "entry.xxxxx",
    "Ámbito de aplicación": "entry.xxxxx",
    "Tema ESG": "entry.xxxxx",
    "Temática ESG": "entry.xxxxx",
    "Descripción": "entry.xxxxx",
    "Aplicación": "entry.xxxxx",
    "Fecha de publicación": "entry.xxxxx",
    "Fecha de aplicación": "entry.xxxxx",
    "Comentarios": "entry.xxxxx",
    "UG 01, 02, 03 - bancos": "entry.xxxxx",
    "UG04 - Asset management": "entry.xxxxx",
    "UG05 - Seguros": "entry.xxxxx",
    "UG06 - LATAM": "entry.xxxxx",
    "UG07 - Corporates": "entry.xxxxx",
    "Estado": "entry.xxxxx",
    "Mes publicación": "entry.xxxxx",
    "Año publicación": "entry.xxxxx",
}

# ===========================================================
COLUMNS = [
    "Nombre","Documento","Link","Autoridad emisora","Tipo de documento",
    "Ámbito de aplicación","Tema ESG","Temática ESG","Descripción","Aplicación",
    "Fecha de publicación","Fecha de aplicación","Comentarios",
    "UG 01, 02, 03 - bancos","UG04 - Asset management","UG05 - Seguros",
    "UG06 - LATAM","UG07 - Corporates","Estado","Mes publicación","Año publicación"
]

def ensure_schema(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[COLUMNS]
    for c in ["Fecha de publicación","Fecha de aplicación"]:
        df[c] = pd.to_datetime(df[c], errors="coerce").dt.date
    df["Año publicación"] = pd.to_numeric(df["Año publicación"], errors="coerce").astype("Int64")
    df["Mes publicación"] = df["Mes publicación"].astype(str).replace({"<NA>": ""})
    return df

@st.cache_data(show_spinner=False, ttl=60)
def load_sheet(sheet_id: str, worksheet: str) -> pd.DataFrame:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={quote(worksheet)}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    df = pd.read_csv(StringIO(r.text))
    df = df.dropna(how="all")
    return ensure_schema(df)

# UI
st.title("📚 Observatorio ESG")

with st.sidebar:
    st.header("⚙️ Configuración")
    st.caption("Si no carga, revisa permisos del Sheet (lector público), SHEET_ID y nombre de pestaña.")
    debug = st.checkbox("Mostrar depuración", value=False)

try:
    df_full = load_sheet(SHEET_ID, WORKSHEET)
except Exception as e:
    st.error("❌ No se pudo cargar el Google Sheet.")
    if st.sidebar.checkbox("Ver detalle del error"):
        st.exception(e)
    st.stop()

if debug:
    st.info(f"CSV URL: https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={quote(WORKSHEET)}")
    st.write("Vista previa:", df_full.head(5))

# Filtros
with st.expander("🔎 Filtros", expanded=True):
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        filtro_anio = st.multiselect("Año publicación", sorted([x for x in df_full["Año publicación"].dropna().unique()]))
    with col2:
        filtro_tema = st.multiselect("Tema ESG", sorted([str(x) for x in df_full["Tema ESG"].dropna().unique()]))
    with col3:
        filtro_tipo = st.multiselect("Tipo de documento", sorted([str(x) for x in df_full["Tipo de documento"].dropna().unique()]))
    with col4:
        filtro_ambito = st.multiselect("Ámbito de aplicación", sorted([str(x) for x in df_full["Ámbito de aplicación"].dropna().unique()]))
    with col5:
        filtro_estado = st.multiselect("Estado", sorted([str(x) for x in df_full["Estado"].dropna().unique()]))
    texto_busqueda = st.text_input("Búsqueda libre (Nombre, Documento, Descripción, Temática)")

df = df_full.copy()
if filtro_anio:
    df = df[df["Año publicación"].isin(filtro_anio)]
if filtro_tema:
    df = df[df["Tema ESG"].astype(str).isin(filtro_tema)]
if filtro_tipo:
    df = df[df["Tipo de documento"].astype(str).isin(filtro_tipo)]
if filtro_ambito:
    df = df[df["Ámbito de aplicación"].astype(str).isin(filtro_ambito)]
if filtro_estado:
    df = df[df["Estado"].astype(str).isin(filtro_estado)]
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

st.markdown("### 📈 Vista general")
if len(df) > 0:
    chart1 = alt.Chart(df.dropna(subset=["Año publicación"])).mark_bar().encode(
        x=alt.X("Año publicación:O", title="Año"),
        y=alt.Y("count()", title="Nº documentos"),
        tooltip=[alt.Tooltip("Año publicación:O", title="Año"), alt.Tooltip("count()", title="Nº")]
    ).properties(height=300)
    st.altair_chart(chart1, use_container_width=True)

    chart2 = alt.Chart(df.dropna(subset=["Tema ESG"])).mark_bar().encode(
        x=alt.X("count()", title="Nº documentos"),
        y=alt.Y("Tema ESG:O", sort="-x", title="Tema ESG"),
        tooltip=[alt.Tooltip("Tema ESG:O", title="Tema"), alt.Tooltip("count()", title="Nº")]
    ).properties(height=300)
    st.altair_chart(chart2, use_container_width=True)
else:
    st.info("No hay registros que coincidan con los filtros.")

st.markdown("### 🧾 Tabla")
st.dataframe(df, use_container_width=True)

# Alta de documentos (via Google Form)
if FORM_ACTION_URL.strip():
    st.markdown("---")
    st.subheader("➕ Dar de alta nuevo documento (via Google Forms)")
    with st.form("alta_form"):
        colA, colB = st.columns(2)
        with colA:
            nombre = st.text_input("Nombre*", placeholder="Título breve del documento")
            documento = st.text_input("Documento")
            link = st.text_input("Link")
            autoridad = st.text_input("Autoridad emisora")
            tipo = st.text_input("Tipo de documento")
            ambito = st.text_input("Ámbito de aplicación")
            tema_esg = st.text_input("Tema ESG")
            tematica_esg = st.text_input("Temática ESG")
            descripcion = st.text_area("Descripción")
            aplicacion = st.text_input("Aplicación")
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
            mes_pub = st.text_input("Mes publicación")
            anio_pub = st.number_input("Año publicación", min_value=1900, max_value=2100, step=1, format="%d")

        submitted = st.form_submit_button("➕ Añadir")
        if submitted:
            if not nombre.strip():
                st.error("El campo *Nombre* es obligatorio.")
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
                    r = requests.post(FORM_ACTION_URL, data=payload, headers={
                        "Content-Type": "application/x-www-form-urlencoded"
                    }, timeout=20)
                    if r.status_code in (200, 302):
                        st.success("✅ Documento enviado al Google Form")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"No se pudo enviar al Form (status {r.status_code}).")
                except Exception as e:
                    st.error(f"Error al enviar al Form: {e}")

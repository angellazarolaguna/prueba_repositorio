
import streamlit as st
import pandas as pd
import altair as alt
import requests
from io import StringIO

st.set_page_config(page_title="Observatorio ESG (solo Streamlit)", page_icon="🌍", layout="wide")
st.title("🌍 Observatorio ESG — Solo Streamlit + Google Sheets + Google Forms")

COLUMNS = [
    "Nombre",
    "Documento",
    "Link",
    "Autoridad emisora",
    "Tipo de documento",
    "Ámbito de aplicación",
    "Tema ESG",
    "Temática ESG",
    "Descripción",
    "Aplicación",
    "Fecha de publicación",
    "Fecha de aplicación",
    "Comentarios",
    "UG 01, 02, 03 - bancos",
    "UG04 - Asset management",
    "UG05 - Seguros",
    "UG06 - LATAM",
    "UG07 - Corporates",
    "Estado",
    "Mes publicación",
    "Año publicación"
]

@st.cache_data(show_spinner=False, ttl=60)
def load_public_csv(url: str) -> pd.DataFrame:
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    csv_text = r.text
    df = pd.read_csv(StringIO(csv_text))
    # Normaliza columnas esperadas
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[COLUMNS]
    # Tipos
    for c in ["Fecha de publicación", "Fecha de aplicación"]:
        df[c] = pd.to_datetime(df[c], errors="coerce").dt.date
    if "Año publicación" in df.columns:
        df["Año publicación"] = pd.to_numeric(df["Año publicación"], errors="coerce").astype("Int64")
    if "Mes publicación" in df.columns:
        df["Mes publicación"] = df["Mes publicación"].astype(str).replace({"<NA>": ""})
    return df

# Config desde secrets
sheet_id = st.secrets["public"]["sheet_id"]
worksheet = st.secrets["public"]["worksheet"]
csv_url = st.secrets["public"]["csv_url"].replace("TU_SHEET_ID", sheet_id).replace("Hoja 1", worksheet)
form_action_url = st.secrets["public"]["form_action_url"]
entry_map = st.secrets["public"]["entry_map_json"]
entry_map = eval(entry_map) if isinstance(entry_map, str) else entry_map

with st.spinner("Cargando datos públicos del Google Sheet..."):
    df_full = load_public_csv(csv_url) if sheet_id else pd.DataFrame(columns=COLUMNS)

# Filtros
with st.expander("🔎 Filtros", expanded=True):
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        filtro_anio = st.multiselect("Año publicación", sorted([x for x in df_full["Año publicación"].dropna().unique()]))
    with col2:
        filtro_tema = st.multiselect("Tema ESG", sorted([x for x in df_full["Tema ESG"].dropna().astype(str).unique()]))
    with col3:
        filtro_tipo = st.multiselect("Tipo de documento", sorted([x for x in df_full["Tipo de documento"].dropna().astype(str).unique()]))
    with col4:
        filtro_ambito = st.multiselect("Ámbito de aplicación", sorted([x for x in df_full["Ámbito de aplicación"].dropna().astype(str).unique()]))
    with col5:
        filtro_estado = st.multiselect("Estado", sorted([x for x in df_full["Estado"].dropna().astype(str).unique()]))
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
with c1:
    st.metric("Total documentos", len(df))
with c2:
    st.metric("Años distintos", df["Año publicación"].nunique())
with c3:
    st.metric("Temas ESG", df["Tema ESG"].nunique())
with c4:
    st.metric("Autoridades emisoras", df["Autoridad emisora"].nunique())

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

st.markdown("### 🧾 Tabla (solo lectura)")
st.dataframe(df, use_container_width=True)

st.markdown("---")
st.subheader("➕ Dar de alta nuevo documento (vía Google Forms)")

with st.form("alta_form"):
    colA, colB = st.columns(2)
    with colA:
        nombre = st.text_input("Nombre*", placeholder="Título breve del documento")
        documento = st.text_input("Documento", placeholder="Código/Identificador si aplica")
        link = st.text_input("Link", placeholder="https://...")
        autoridad = st.text_input("Autoridad emisora", placeholder="Ej. EBA, ESMA, UE, CNMV...")
        tipo = st.text_input("Tipo de documento", placeholder="Normativa, guía, consulta, informe...")
        ambito = st.text_input("Ámbito de aplicación", placeholder="UE, ES, Global...")
        tema_esg = st.text_input("Tema ESG", placeholder="E, S o G / Mixto")
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

    submitted = st.form_submit_button("➕ Añadir")
    if submitted:
        if not nombre.strip():
            st.error("El campo *Nombre* es obligatorio.")
        else:
            # Construir payload para el Google Form
            payload = {
                entry_map["Nombre"]: nombre.strip(),
                entry_map["Documento"]: documento.strip(),
                entry_map["Link"]: link.strip(),
                entry_map["Autoridad emisora"]: autoridad.strip(),
                entry_map["Tipo de documento"]: tipo.strip(),
                entry_map["Ámbito de aplicación"]: ambito.strip(),
                entry_map["Tema ESG"]: tema_esg.strip(),
                entry_map["Temática ESG"]: tematica_esg.strip(),
                entry_map["Descripción"]: descripcion.strip(),
                entry_map["Aplicación"]: aplicacion.strip(),
                entry_map["Fecha de publicación"]: f_pub.isoformat() if f_pub else "",
                entry_map["Fecha de aplicación"]: f_apl.isoformat() if f_apl else "",
                entry_map["Comentarios"]: comentarios.strip(),
                entry_map["UG 01, 02, 03 - bancos"]: "Sí" if ug_bancos else "",
                entry_map["UG04 - Asset management"]: "Sí" if ug_am else "",
                entry_map["UG05 - Seguros"]: "Sí" if ug_seguros else "",
                entry_map["UG06 - LATAM"]: "Sí" if ug_latam else "",
                entry_map["UG07 - Corporates"]: "Sí" if ug_corp else "",
                entry_map["Estado"]: estado,
                entry_map["Mes publicación"]: str(mes_pub).strip(),
                entry_map["Año publicación"]: int(anio_pub) if anio_pub else ""
            }
            try:
                r = requests.post(form_action_url, data=payload, headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                }, timeout=20)
                # Google Forms devuelve 200/302 aunque no haya redirección visible; validamos por código de estado
                if r.status_code in (200, 302):
                    st.success("Documento enviado al Google Form ✅")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"No se pudo enviar al Form (status {r.status_code}). Revisa entry IDs y URL.")
            except Exception as e:
                st.error(f"Error al enviar al Form: {e}")

st.caption("Nota: este flujo no requiere credenciales de Google Cloud. Lectura pública del Sheet y altas mediante Google Forms.")

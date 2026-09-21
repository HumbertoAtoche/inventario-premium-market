import streamlit as st
import pandas as pd
import gspread
import hashlib
import io
import os
import re
import time
import html
import base64
import mimetypes
from datetime import datetime
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components

# =========================================================
# TIENDAS PREMIUM EIRL — INVENTARIO
# app.py — versión optimizada para Google Sheets + móvil
# =========================================================

# 👉 LOGOS DE LA EMPRESA
# LOGO_PATH   -> se muestra DENTRO de la app (login y barra lateral): assets/logo (2).png
# FAVICON_PATH -> ícono de la pestaña del navegador (favicon): assets/logo (3).png
# Ambos van en la carpeta "assets", al mismo nivel que este app.py, en tu repo de GitHub.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "assets", "logo (2).png")
LOGO_DISPONIBLE = os.path.isfile(LOGO_PATH)
LOGO_MIME = mimetypes.guess_type(LOGO_PATH)[0] or "image/png"

FAVICON_PATH = os.path.join(BASE_DIR, "assets", "logo (3).png")
FAVICON_DISPONIBLE = os.path.isfile(FAVICON_PATH)

try:
    st.set_page_config(
        page_title="Inventario | Tiendas Premium",
        page_icon=FAVICON_PATH if FAVICON_DISPONIBLE else (LOGO_PATH if LOGO_DISPONIBLE else "📦"),
        layout="wide",
        initial_sidebar_state="expanded",
    )
except Exception:
    # Si el logo todavía no existe o hay algún problema leyéndolo,
    # la app sigue funcionando con un ícono por defecto.
    st.set_page_config(
        page_title="Inventario | Tiendas Premium",
        page_icon="📦",
        layout="wide",
        initial_sidebar_state="expanded",
    )

APP_NAME = "Tiendas Premium"
COMPANY = "Tiendas Premium EIRL"
RUC = "20612107787"
AUTHOR = "Humberto Atoche"
SHEET_NAME = "BD_Inventario_PremiumMarket"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_NAMES = {
    "inventario": "Inventario",
    "conteos": "ConteoInventario",
    "sesiones": "SesionesInventario",
    "resumen": "ResumenInventario",
    "usuarios": "Usuarios",
}

HEADERS_INVENTARIO = [
    "CodigoBarras", "CodigoProducto", "Producto", "Descripcion", "Categoria",
    "Marca", "Unidad", "Sucursal", "StockSistema", "CostoUnitario",
    "PrecioVenta", "Estado"
]

HEADERS_CONTEO = [
    "IdSesion", "FechaHora", "Usuario", "NombreUsuario", "CodigoBarras",
    "CodigoProducto", "Producto", "Categoria", "Sucursal", "StockSistema",
    "StockFisico", "Diferencia", "CostoUnitario", "ValorFaltante", "ValorSobrante",
    "CostoDiferencia", "TipoDiferencia", "MetodoConteo", "Observacion"
]

HEADERS_SESIONES = [
    "IdSesion", "FechaInicio", "FechaFin", "NombreSesion", "UsuarioCreador",
    "Estado", "Sucursal", "Observacion"
]

HEADERS_RESUMEN = [
    "IdSesion", "Fecha", "NombreSesion", "Sucursal", "ProductosSistema",
    "ProductosContados", "ProductosOK", "ProductosFaltantes", "ProductosSobrantes",
    "UnidadesSistema", "UnidadesFisicas", "UnidadesFaltantes", "UnidadesSobrantes",
    "ValorFaltantes", "ValorSobrantes", "DesfaseNeto", "ExactitudInventario", "Estado"
]

HEADERS_USUARIOS = ["Usuario", "NombreCompleto", "Rol", "Password", "Estado"]
HEADERS_AUDITORIA = ["FechaHora", "Usuario", "NombreCompleto", "Accion", "Detalle", "IdSesion"]
NOMBRE_HOJA_AUDITORIA = "Auditoria"  # opcional: la app la crea sola la primera vez que se necesita

# ---------------------------------------------------------
# REGLAS DE CONTROL — ajústalas a la realidad de tu operación
# ---------------------------------------------------------
META_EXACTITUD = 98.0          # % de exactitud objetivo por sesión
UMBRAL_DIF_SOLES = 200.0       # diferencia >= S/ 200 => exige confirmar el conteo
UMBRAL_DIF_UNIDADES = 10       # diferencia >= 10 unidades Y ...
UMBRAL_DIF_PORCENTAJE = 30.0   # ... >= 30 % del stock del sistema => exige confirmar el conteo
CONTEO_CIEGO = False           # True: el CONTADOR no ve el stock del sistema mientras cuenta
HORAS_SESION_ALERTA = 24       # alerta si una sesión lleva más de 24 h abierta
MAX_INTENTOS_LOGIN = 5         # intentos fallidos antes de bloquear el ingreso
BLOQUEO_LOGIN_SEGUNDOS = 300   # duración del bloqueo (5 minutos)

# =========================================================
# ESTILOS
# =========================================================

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');

    :root {
        --red: #EC3237;
        --red-dark: #D02429;
        --green: #00A959;
        --green-dark: #008847;
        --blue: #1071B8;
        --text: #111827;
        --muted: #6B7280;
        --bg: #FAFAFA;
        --card: #FFFFFF;
        --border: #E5E7EB;
    }

    html, body, [class*="css"], .stMarkdown, div, button, input, select, textarea {
        font-family: 'Montserrat', sans-serif !important;
    }

    .stApp {
        background-color: #FAFAFA;
    }

    header[data-testid="stHeader"] {
        background-color: transparent !important;
        z-index: 100;
    }

    header[data-testid="stHeader"] button {
        color: #111827 !important;
    }

    .block-container {
        padding-bottom: 4rem;
    }

    /* ---------- ENCABEZADO (idéntico al market-header de la App 43) ---------- */
    .market-header,
    .premium-header {
        background-color: #FFFFFF;
        padding: 20px 24px;
        border-radius: 8px;
        border: 1px solid #E5E7EB;
        border-left: 4px solid #EC3237;
        margin-bottom: 24px;
    }
    .market-header h1,
    .premium-header h1 {
        color: #111827 !important;
        margin: 0;
        font-size: 1.3rem !important;
        font-weight: 600 !important;
        letter-spacing: -0.3px;
    }
    .market-header p,
    .premium-header p {
        color: #6B7280;
        margin: 4px 0 0 0;
        font-size: 0.85rem;
        font-weight: 400;
    }

    .section-title {
        color: #111827;
        font-size: 1rem;
        font-weight: 600;
        margin: 12px 0 10px;
    }

    /* ---------- TARJETAS (idénticas al info-card de la App 43) ---------- */
    .info-card,
    .card,
    .kpi-card,
    .product-card,
    .price-info-item {
        background-color: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        box-shadow: none;
    }
    .info-card,
    .card,
    .kpi-card {
        padding: 18px 20px;
        margin-bottom: 15px;
    }
    .info-label,
    .kpi-label,
    .stock-label,
    .price-info-item .lbl {
        color: #6B7280;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }
    .info-value,
    .kpi-value,
    .stock-number {
        color: #111827;
        font-size: 1.4rem;
        font-weight: 700;
        margin-top: 4px;
    }
    .kpi-card { min-height: 105px; }
    .kpi-note { color: #6B7280; font-size: 0.75rem; margin-top: 2px; }

    .product-card {
        border-top: 3px solid #1071B8;
        padding: 18px 20px;
        margin: 10px 0 15px;
    }
    .product-name { font-size: 1.15rem; font-weight: 700; color: #111827; line-height: 1.25; }
    .product-meta { color: #4B5563; font-size: 0.82rem; margin-top: 4px; }

    .stock-box {
        background-color: #F8FAFC;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 13px;
        text-align: center;
    }

    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 600;
    }
    .badge-ok { background: #DCFCE7; color: #15803D; }
    .badge-faltante { background: #FEE2E2; color: #B91C1C; }
    .badge-sobrante { background: #DCFCE7; color: #15803D; }
    .badge-abierta { background: #DBEAFE; color: #1D4ED8; }
    .badge-cerrada { background: #F3F4F6; color: #4B5563; }

    .price-hero {
        background-color: #FFFFFF;
        color: #111827;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 28px 22px;
        text-align: center;
        box-shadow: none;
        margin: 14px 0;
    }
    .price-hero .price-label { font-size: 0.8rem; font-weight: 600; text-transform: uppercase; color: #6B7280; letter-spacing: 0.8px; }
    .price-hero .price-value { font-size: 3rem; font-weight: 800; margin: 6px 0 2px; line-height: 1; color: #111827; }
    .price-hero .price-sub { font-size: 0.85rem; color: #6B7280; }

    .price-info-grid { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
    .price-info-item {
        flex: 1 1 120px;
        padding: 11px 12px;
        text-align: center;
    }
    .price-info-item .val { color: #111827; font-size: 1.05rem; font-weight: 700; margin-top: 3px; }

    .mobile-note {
        background-color: #FFFFFF;
        border: 1px solid #E5E7EB;
        color: #6B7280;
        border-radius: 8px;
        padding: 10px 12px;
        font-size: 0.82rem;
        margin-bottom: 12px;
    }

    /* ---------- BOTONES (idénticos a la App 43) ---------- */
    .stButton>button {
        background-color: #111827 !important;
        color: #FFFFFF !important;
        border-radius: 6px !important;
        border: none !important;
        font-weight: 500 !important;
        font-size: 0.82rem !important;
        height: 2.8em !important;
        transition: all 0.2s ease !important;
        letter-spacing: 0.3px;
    }
    .stButton>button:hover {
        background-color: #374151 !important;
    }
    .stButton>button[kind="primary"] {
        background-color: #EC3237 !important;
    }
    .stButton>button[kind="primary"]:hover {
        background-color: #D02429 !important;
    }

    .btn-ingreso > button {
        background-color: #00A959 !important;
    }
    .btn-ingreso > button:hover {
        background-color: #008847 !important;
    }

    .btn-salida > button {
        background-color: #EC3237 !important;
    }
    .btn-salida > button:hover {
        background-color: #D02429 !important;
    }

    /* ---------- SIDEBAR (copia exacta de la App 43) ---------- */
    [data-testid="stSidebar"] {
        background-color: #111827 !important;
        border-right: 1px solid #1F2937;
    }
    [data-testid="stSidebar"] * {
        color: #E5E7EB !important;
    }

    .btn-logout > button {
        background-color: transparent !important;
        border: 1px solid #374151 !important;
        color: #9CA3AF !important;
    }
    .btn-logout > button:hover {
        background-color: #1F2937 !important;
        color: #FFFFFF !important;
    }

    /* ---------- FORMULARIOS Y EXPANDERS (idénticos a la App 43) ---------- */
    div[data-testid="stForm"], div[data-testid="stExpander"] {
        border-radius: 8px !important;
        border: 1px solid #E5E7EB !important;
        background-color: #FFFFFF !important;
        padding: 20px !important;
        box-shadow: none !important;
    }

    /* ---------- FOOTER (idéntico a la App 43) ---------- */
    .app-footer {
        text-align: center;
        padding: 24px 10px 12px 10px;
        margin-top: 40px;
        border-top: 1px solid #E5E7EB;
        color: #6B7280;
        font-size: 0.8rem;
        line-height: 1.5;
    }
    .app-footer strong {
        color: #111827;
    }

    /* ---------- AJUSTES MÓVIL ---------- */
    @media (max-width: 768px) {
        .block-container { padding-left: .65rem; padding-right: .65rem; padding-bottom: 4rem; }
        .premium-header, .market-header { padding: 17px; }
        .premium-header h1, .market-header h1 { font-size: 1.15rem !important; }
        .premium-header p, .market-header p { font-size: 0.8rem; }
        .card, .info-card { padding: 13px; }
        .kpi-card { min-height: 88px; padding: 12px; }
        .kpi-value, .info-value { font-size: 1.25rem; }
        .product-card { padding: 14px; }
        .product-name { font-size: 1.05rem; }
        .price-hero { padding: 22px 16px; }
        .price-hero .price-value { font-size: 2.3rem; }
        .stButton>button { height: auto !important; min-height: 46px !important; }
        div[data-testid="stFormSubmitButton"] > button { min-height: 46px; }
        .app-footer { font-size: 0.72rem; padding-top: 20px; }
    }
</style>
""", unsafe_allow_html=True)


# =========================================================
# UTILIDADES
# =========================================================

def ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def fecha_actual():
    return datetime.now().strftime("%Y-%m-%d")


def limpiar_codigo(valor):
    if pd.isna(valor):
        return ""
    texto = str(valor).strip()
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto


def limpiar_numero(valor, default=0):
    try:
        if pd.isna(valor):
            return default
        texto = str(valor).strip().replace(",", "")
        if texto == "":
            return default
        return float(texto)
    except Exception:
        return default


def exportar_excel(hojas: dict):
    """Genera un archivo .xlsx en memoria a partir de un diccionario {nombre_hoja: DataFrame}."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for nombre, df in hojas.items():
            df.to_excel(writer, sheet_name=nombre[:31], index=False)
    buffer.seek(0)
    return buffer.getvalue()


def formato_soles(valor):
    try:
        return f"S/ {float(valor):,.2f}"
    except Exception:
        return "S/ 0.00"


def hash_password(password):
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()


def generar_id_sesion():
    return datetime.now().strftime("INV-%Y%m%d-%H%M%S-%f")


def generar_id_usuario():
    return datetime.now().strftime("USR-%Y%m%d%H%M%S%f")


def saludo_actual():
    hora = datetime.now().hour
    if hora < 12:
        return "Buenos días"
    if hora < 19:
        return "Buenas tardes"
    return "Buenas noches"


def safe_text(valor):
    return html.escape(str(valor))


def logo_tag(height=52, fallback_emoji="📦"):
    """
    Devuelve un <img> con el logo de la empresa leído directamente del archivo
    local images/logo.jpg (incrustado en Base64, sin depender de internet).
    Si el archivo todavía no existe, muestra automáticamente el emoji de respaldo.
    """
    b64 = _logo_base64()
    if not b64:
        return f'<span style="font-size:{height}px;line-height:1;">{fallback_emoji}</span>'
    return (
        f'<img src="data:{LOGO_MIME};base64,{b64}" alt="logo" '
        f'style="height:{height}px;max-width:100%;object-fit:contain;vertical-align:middle;">'
    )


@st.cache_data(show_spinner=False)
def _logo_base64():
    if not LOGO_DISPONIBLE:
        return ""
    try:
        with open(LOGO_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return ""


@st.cache_data(show_spinner=False)
def _beep_wav_base64(frecuencia=1500, duracion_ms=110, volumen=0.35):
    """Genera un beep corto en WAV (sin dependencias externas) y lo devuelve en Base64."""
    import struct
    import wave
    import math

    tasa = 22050
    n_muestras = int(tasa * duracion_ms / 1000)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(tasa)
        for i in range(n_muestras):
            valor = int(volumen * 32767 * math.sin(2 * math.pi * frecuencia * i / tasa))
            wav.writeframes(struct.pack("<h", valor))
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def sonido_confirmacion():
    """Reproduce un beep + vibración corta al confirmar un escaneo exitoso."""
    audio_b64 = _beep_wav_base64()
    components.html(
        f"""
        <audio id="beep_ok" autoplay>
            <source src="data:audio/wav;base64,{audio_b64}" type="audio/wav">
        </audio>
        <script>
            try {{ if (navigator.vibrate) {{ navigator.vibrate(70); }} }} catch (e) {{}}
        </script>
        """,
        height=0,
    )


def normalizar_df(df, headers):
    if df is None or df.empty:
        return pd.DataFrame(columns=headers)
    df = df.copy()
    for col in headers:
        if col not in df.columns:
            df[col] = ""
    return df[headers + [c for c in df.columns if c not in headers]]


def mostrar_error_google(exc, contexto="Google Sheets"):
    texto = str(exc)
    lower = texto.lower()
    if "429" in texto or "quota exceeded" in lower:
        st.error("⚠️ Google Sheets alcanzó temporalmente el límite de lecturas.")
        st.info("La aplicación no se desconectó. Espera unos segundos y utiliza **Actualizar datos**.")
    elif "403" in texto or "permission" in lower:
        st.error("🔒 Google Sheets rechazó el acceso.")
        st.info("Revisa que el Service Account tenga acceso al archivo de Google Sheets.")
    elif "404" in texto or "not found" in lower:
        st.error("📄 No se encontró el archivo o una de las hojas configuradas.")
    else:
        st.error(f"⚠️ No se pudo completar la operación con {contexto}.")
        st.caption("Este mensaje corresponde a Google Sheets y no significa que Streamlit se haya desconectado.")
    with st.expander("Detalle técnico"):
        st.code(texto)

# =========================================================
# GOOGLE SHEETS — CACHÉ INTELIGENTE
# =========================================================

@st.cache_resource(show_spinner=False)
def conectar_google():
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES,
    )
    client = gspread.authorize(credentials)
    return client.open(SHEET_NAME)


@st.cache_resource(show_spinner=False)
def obtener_hojas():
    """
    Se ejecuta una sola vez por recurso/cache.
    No hace worksheet(nombre) en cada rerun y no crea hojas automáticamente.
    """
    spreadsheet = conectar_google()
    metadata = spreadsheet.fetch_sheet_metadata()
    disponibles = {
        hoja["properties"]["title"]
        for hoja in metadata.get("sheets", [])
    }
    faltantes = [nombre for nombre in SHEET_NAMES.values() if nombre not in disponibles]
    if faltantes:
        raise RuntimeError(
            "Faltan estas hojas en el archivo " + SHEET_NAME + ": " + ", ".join(faltantes)
        )
    return {
        clave: spreadsheet.worksheet(nombre)
        for clave, nombre in SHEET_NAMES.items()
    }


def obtener_hoja(clave):
    return obtener_hojas()[clave]


def refrescar_conexion():
    conectar_google.clear()
    obtener_hojas.clear()


def actualizar_datos():
    """Refresco controlado: solo se ejecuta por acción explícita del usuario."""
    cargar_inventario.clear()
    cargar_usuarios.clear()
    cargar_conteos.clear()
    cargar_sesiones.clear()
    cargar_resumenes.clear()
    cargar_auditoria.clear()

# =========================================================
# CARGADORES — SOLO LECTURAS CACHEADAS
# =========================================================

@st.cache_data(ttl=60, show_spinner=False)
def cargar_inventario():
    ws = obtener_hoja("inventario")
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    df = normalizar_df(df, HEADERS_INVENTARIO)
    if df.empty:
        return df
    for col in ["CodigoBarras", "CodigoProducto", "Producto", "Descripcion", "Categoria", "Marca", "Unidad", "Sucursal", "Estado"]:
        df[col] = df[col].fillna("").astype(str).str.strip()
    for col in ["StockSistema", "CostoUnitario", "PrecioVenta"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=300, show_spinner=False)
def cargar_usuarios():
    ws = obtener_hoja("usuarios")
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    df = normalizar_df(df, HEADERS_USUARIOS)
    if df.empty:
        return df
    for col in HEADERS_USUARIOS:
        df[col] = df[col].fillna("").astype(str).str.strip()
    return df


@st.cache_data(ttl=30, show_spinner=False)
def cargar_conteos():
    ws = obtener_hoja("conteos")
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    df = normalizar_df(df, HEADERS_CONTEO)
    if df.empty:
        return df
    for col in ["IdSesion", "FechaHora", "Usuario", "NombreUsuario", "CodigoBarras", "CodigoProducto", "Producto", "Categoria", "Sucursal", "TipoDiferencia", "MetodoConteo", "Observacion"]:
        df[col] = df[col].fillna("").astype(str).str.strip()
    for col in ["StockSistema", "StockFisico", "Diferencia", "CostoUnitario", "ValorFaltante", "ValorSobrante", "CostoDiferencia"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=30, show_spinner=False)
def cargar_sesiones():
    ws = obtener_hoja("sesiones")
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    df = normalizar_df(df, HEADERS_SESIONES)
    if df.empty:
        return df
    for col in HEADERS_SESIONES:
        df[col] = df[col].fillna("").astype(str).str.strip()
    return df


@st.cache_data(ttl=120, show_spinner=False)
def cargar_resumenes():
    ws = obtener_hoja("resumen")
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    return normalizar_df(df, HEADERS_RESUMEN)

# =========================================================
# AUDITORÍA Y REGLAS DE CONTROL
# =========================================================

@st.cache_resource(show_spinner=False)
def _hoja_auditoria_resource():
    """Devuelve la hoja de auditoría (la crea si no existe). Si falla, no se cachea."""
    spreadsheet = conectar_google()
    try:
        return spreadsheet.worksheet(NOMBRE_HOJA_AUDITORIA)
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=NOMBRE_HOJA_AUDITORIA, rows=1000, cols=len(HEADERS_AUDITORIA))
        ws.append_row(HEADERS_AUDITORIA, value_input_option="RAW")
        return ws


@st.cache_data(ttl=60, show_spinner=False)
def cargar_auditoria():
    try:
        ws = _hoja_auditoria_resource()
        df = pd.DataFrame(ws.get_all_records())
    except Exception:
        return pd.DataFrame(columns=HEADERS_AUDITORIA)
    return normalizar_df(df, HEADERS_AUDITORIA)


def registrar_auditoria(accion, detalle="", id_sesion=""):
    """Bitácora de acciones críticas. Nunca interrumpe la operación principal."""
    try:
        usuario = st.session_state.get("usuario") or {}
        fila = [
            ahora(),
            usuario.get("Usuario", "SISTEMA"),
            usuario.get("NombreCompleto", ""),
            str(accion),
            str(detalle),
            str(id_sesion),
        ]
        _hoja_auditoria_resource().append_row(fila, value_input_option="RAW")
        cargar_auditoria.clear()
    except Exception:
        pass


def _claves_df(df):
    """Clave única por producto: código de barras, o código de producto, o nombre."""
    barras = df["CodigoBarras"].map(limpiar_codigo)
    codigo = df["CodigoProducto"].map(limpiar_codigo)
    nombre = df["Producto"].astype(str).str.strip()
    return barras.where(barras != "", codigo).where(lambda s: s != "", nombre)


def conteos_vigentes(df):
    """Último conteo de cada producto dentro de cada sesión (respeta los reconteos)."""
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame(columns=HEADERS_CONTEO)
    d = df.copy()
    d["_clave"] = d["IdSesion"].astype(str) + "|" + _claves_df(d)
    d = d.sort_values("FechaHora", kind="stable").drop_duplicates("_clave", keep="last")
    return d.drop(columns="_clave").sort_index()


def contar_productos_sesion(conteos, id_sesion):
    """Productos distintos contados en una sesión (un reconteo no suma dos veces)."""
    if conteos is None or conteos.empty:
        return 0
    dc = conteos[conteos["IdSesion"].astype(str) == str(id_sesion)]
    return len(conteos_vigentes(dc))


def ultimo_conteo_producto(id_sesion, producto):
    df = cargar_conteos()
    if df.empty:
        return None
    dc = df[df["IdSesion"].astype(str) == str(id_sesion)]
    if dc.empty:
        return None
    vig = conteos_vigentes(dc)
    clave = (
        limpiar_codigo(producto.get("CodigoBarras", ""))
        or limpiar_codigo(producto.get("CodigoProducto", ""))
        or str(producto.get("Producto", "")).strip()
    )
    coincide = vig[_claves_df(vig) == clave]
    return coincide.iloc[-1].to_dict() if not coincide.empty else None


def inventario_de_sucursal(inv, sucursal):
    """Productos que corresponden a la sucursal de la sesión.
    Si el nombre de la sucursal no coincide con ningún producto, devuelve todo el inventario
    (así nunca queda en cero por una diferencia de escritura)."""
    if inv is None or inv.empty:
        return inv
    suc = str(sucursal or "").strip().lower()
    if not suc:
        return inv
    filtrado = inv[inv["Sucursal"].astype(str).str.strip().str.lower() == suc]
    return filtrado if not filtrado.empty else inv


def es_diferencia_critica(stock_sistema, stock_fisico, costo):
    """True si la diferencia es lo bastante grande como para exigir confirmación."""
    dif = abs(limpiar_numero(stock_fisico) - limpiar_numero(stock_sistema))
    if dif == 0:
        return False
    valor = dif * limpiar_numero(costo)
    base = limpiar_numero(stock_sistema)
    porcentaje = (dif / base * 100) if base > 0 else 100.0
    return valor >= UMBRAL_DIF_SOLES or (dif >= UMBRAL_DIF_UNIDADES and porcentaje >= UMBRAL_DIF_PORCENTAJE)

# =========================================================
# OPERACIONES
# =========================================================

def autenticar(usuario, password):
    usuarios = cargar_usuarios()
    if usuarios.empty:
        return None
    usuario = str(usuario).strip().lower()
    fila = usuarios[usuarios["Usuario"].str.lower() == usuario]
    if fila.empty:
        return None
    registro = fila.iloc[0]
    if str(registro["Estado"]).strip().lower() not in ["activo", "activa", "1", "true", "sí", "si"]:
        return None
    guardada = str(registro["Password"]).strip()
    if password == guardada or hash_password(password) == guardada:
        return registro.to_dict()
    return None


def buscar_por_codigo(codigo, df=None):
    if df is None:
        df = cargar_inventario()
    codigo = limpiar_codigo(codigo)
    if not codigo or df.empty:
        return None
    for col in ["CodigoBarras", "CodigoProducto"]:
        mask = df[col].map(limpiar_codigo) == codigo
        if mask.any():
            return df.loc[mask].iloc[0].to_dict()
    return None


def buscar_productos(texto, df=None):
    if df is None:
        df = cargar_inventario()
    if df.empty:
        return df
    texto = str(texto).strip()
    if not texto:
        return df.head(50).copy()
    patron = re.escape(texto)
    mask = pd.Series(False, index=df.index)
    for col in ["CodigoBarras", "CodigoProducto", "Producto", "Descripcion", "Categoria", "Marca"]:
        mask = mask | df[col].astype(str).str.contains(patron, case=False, na=False, regex=True)
    return df.loc[mask].head(100).copy()


def obtener_sesion_abierta(usuario=None):
    df = cargar_sesiones()
    if df.empty:
        return None
    abiertas = df[df["Estado"].str.upper() == "ABIERTA"].copy()
    if usuario:
        propias = abiertas[abiertas["UsuarioCreador"].astype(str).str.lower() == str(usuario).lower()]
        if not propias.empty:
            return propias.iloc[-1].to_dict()
    if not abiertas.empty:
        return abiertas.iloc[-1].to_dict()
    return None


def producto_ya_contado(id_sesion, codigo):
    df = cargar_conteos()
    if df.empty:
        return False
    codigo = limpiar_codigo(codigo)
    return bool(((df["IdSesion"] == str(id_sesion)) & (df["CodigoBarras"].map(limpiar_codigo) == codigo)).any())


def guardar_conteo(sesion, usuario, producto, stock_fisico, metodo="Escáner", observacion="", es_reconteo=False):
    stock_sistema = limpiar_numero(producto.get("StockSistema", 0))
    costo = limpiar_numero(producto.get("CostoUnitario", 0))
    stock_fisico = limpiar_numero(stock_fisico)
    diferencia = stock_fisico - stock_sistema

    valor_faltante = abs(diferencia) * costo if diferencia < 0 else 0
    valor_sobrante = diferencia * costo if diferencia > 0 else 0
    costo_diferencia = valor_sobrante - valor_faltante

    if diferencia < 0:
        tipo = "FALTANTE"
    elif diferencia > 0:
        tipo = "SOBRANTE"
    else:
        tipo = "OK"

    obs = observacion.strip()
    if es_reconteo:
        obs = ("[RECONTEO] " + obs).strip()

    fila = [
        sesion["IdSesion"], ahora(), usuario["Usuario"], usuario["NombreCompleto"],
        limpiar_codigo(producto.get("CodigoBarras", "")),
        limpiar_codigo(producto.get("CodigoProducto", "")),
        producto.get("Producto", ""), producto.get("Categoria", ""), producto.get("Sucursal", ""),
        stock_sistema, stock_fisico, diferencia, costo, valor_faltante, valor_sobrante,
        costo_diferencia, tipo, metodo, obs
    ]
    obtener_hoja("conteos").append_row(fila, value_input_option="USER_ENTERED")
    cargar_conteos.clear()
    if es_reconteo:
        registrar_auditoria(
            "RECONTEO",
            f"{producto.get('Producto', '')} · físico {stock_fisico:,.0f} · sistema {stock_sistema:,.0f} · {tipo}",
            sesion["IdSesion"],
        )
    return tipo, diferencia, valor_faltante, valor_sobrante


def crear_sesion(nombre, sucursal, usuario, observacion=""):
    id_sesion = generar_id_sesion()
    fila = [
        id_sesion, ahora(), "", nombre.strip(), usuario["Usuario"],
        "ABIERTA", sucursal.strip(), observacion.strip()
    ]
    obtener_hoja("sesiones").append_row(fila, value_input_option="USER_ENTERED")
    cargar_sesiones.clear()
    registrar_auditoria("CREAR_SESION", f"{nombre.strip()} · {sucursal.strip()}", id_sesion)
    return id_sesion


def cerrar_sesion(id_sesion, detalle=""):
    ws = obtener_hoja("sesiones")
    # Acción poco frecuente: una sola lectura directa para localizar la fila.
    valores = ws.get_all_values()
    if not valores:
        return False
    try:
        headers = valores[0]
        idx_id = headers.index("IdSesion")
        idx_fin = headers.index("FechaFin")
        idx_estado = headers.index("Estado")
        for n, fila in enumerate(valores[1:], start=2):
            if len(fila) > idx_id and fila[idx_id] == str(id_sesion):
                ws.update_cell(n, idx_fin + 1, ahora())
                ws.update_cell(n, idx_estado + 1, "CERRADA")
                cargar_sesiones.clear()
                registrar_auditoria("CERRAR_SESION", detalle, id_sesion)
                return True
    except Exception:
        raise
    return False


def calcular_resumen(id_sesion):
    inv = cargar_inventario()
    conteos = cargar_conteos()
    sesiones = cargar_sesiones()

    if conteos.empty:
        dc = pd.DataFrame(columns=HEADERS_CONTEO)
    else:
        dc = conteos_vigentes(conteos[conteos["IdSesion"].astype(str) == str(id_sesion)].copy())

    ses = sesiones[sesiones["IdSesion"].astype(str) == str(id_sesion)] if not sesiones.empty else pd.DataFrame()
    nombre = ses.iloc[0]["NombreSesion"] if not ses.empty else str(id_sesion)
    sucursal = ses.iloc[0]["Sucursal"] if not ses.empty else ""
    estado = ses.iloc[0]["Estado"] if not ses.empty else ""

    productos_contados = len(dc)
    productos_ok = int((dc["TipoDiferencia"] == "OK").sum()) if not dc.empty else 0
    productos_faltantes = int((dc["TipoDiferencia"] == "FALTANTE").sum()) if not dc.empty else 0
    productos_sobrantes = int((dc["TipoDiferencia"] == "SOBRANTE").sum()) if not dc.empty else 0

    unidades_sistema = float(dc["StockSistema"].sum()) if not dc.empty else 0
    unidades_fisicas = float(dc["StockFisico"].sum()) if not dc.empty else 0
    unidades_faltantes = abs(float(dc.loc[dc["Diferencia"] < 0, "Diferencia"].sum())) if not dc.empty else 0
    unidades_sobrantes = float(dc.loc[dc["Diferencia"] > 0, "Diferencia"].sum()) if not dc.empty else 0
    valor_faltantes = float(dc["ValorFaltante"].sum()) if not dc.empty else 0
    valor_sobrantes = float(dc["ValorSobrante"].sum()) if not dc.empty else 0
    desfase_neto = valor_faltantes - valor_sobrantes
    exactitud = (productos_ok / productos_contados * 100) if productos_contados else 0

    return {
        "IdSesion": id_sesion,
        "Fecha": fecha_actual(),
        "NombreSesion": nombre,
        "Sucursal": sucursal,
        "ProductosSistema": len(inventario_de_sucursal(inv, sucursal)),
        "ProductosContados": productos_contados,
        "ProductosOK": productos_ok,
        "ProductosFaltantes": productos_faltantes,
        "ProductosSobrantes": productos_sobrantes,
        "UnidadesSistema": unidades_sistema,
        "UnidadesFisicas": unidades_fisicas,
        "UnidadesFaltantes": unidades_faltantes,
        "UnidadesSobrantes": unidades_sobrantes,
        "ValorFaltantes": valor_faltantes,
        "ValorSobrantes": valor_sobrantes,
        "DesfaseNeto": desfase_neto,
        "ExactitudInventario": exactitud,
        "Estado": estado,
    }


def guardar_resumen(resumen):
    fila = [resumen.get(col, "") for col in HEADERS_RESUMEN]
    obtener_hoja("resumen").append_row(fila, value_input_option="USER_ENTERED")
    cargar_resumenes.clear()


def crear_usuario(usuario, nombre, rol, password):
    df = cargar_usuarios()
    if not df.empty and (df["Usuario"].str.lower() == usuario.strip().lower()).any():
        raise ValueError("Ese usuario ya existe.")
    fila = [usuario.strip(), nombre.strip(), rol.strip().upper(), hash_password(password), "ACTIVO"]
    obtener_hoja("usuarios").append_row(fila, value_input_option="USER_ENTERED")
    cargar_usuarios.clear()
    registrar_auditoria("CREAR_USUARIO", f"{usuario.strip()} · {rol.strip().upper()}")

# =========================================================
# ANÁLISIS (funciones de cálculo puras, sin escrituras)
# =========================================================

def generar_ajustes(dc):
    """Lista de ajustes de stock lista para cargar en el sistema contable/ERP."""
    cols = ["CodigoBarras", "CodigoProducto", "Producto", "Sucursal", "StockSistema",
            "StockFisico", "Ajuste", "TipoAjuste", "CostoUnitario", "ImpactoSoles"]
    if dc is None or dc.empty:
        return pd.DataFrame(columns=cols)
    d = dc[dc["Diferencia"] != 0].copy()
    if d.empty:
        return pd.DataFrame(columns=cols)
    d["Ajuste"] = d["Diferencia"]
    d["TipoAjuste"] = d["Diferencia"].map(lambda x: "ENTRADA" if x > 0 else "SALIDA")
    d["ImpactoSoles"] = d["CostoDiferencia"]
    return d[cols].sort_values("ImpactoSoles").reset_index(drop=True)


def clasificar_abc(inv, corte_a=80.0, corte_b=95.0):
    """Clasificación ABC (Pareto) por valor de inventario a costo."""
    cols = ["Clase", "Producto", "CodigoProducto", "Categoria", "StockSistema",
            "CostoUnitario", "Valor", "% Valor", "% Acumulado"]
    if inv is None or inv.empty:
        return pd.DataFrame(columns=cols)
    d = inv.copy()
    d["Valor"] = d["StockSistema"].clip(lower=0) * d["CostoUnitario"]
    d = d[d["Valor"] > 0].sort_values("Valor", ascending=False)
    if d.empty:
        return pd.DataFrame(columns=cols)
    total = d["Valor"].sum()
    d["% Valor"] = d["Valor"] / total * 100
    d["% Acumulado"] = d["% Valor"].cumsum()
    previo = d["% Acumulado"] - d["% Valor"]
    d["Clase"] = "C"
    d.loc[previo < corte_b, "Clase"] = "B"
    d.loc[previo < corte_a, "Clase"] = "A"
    return d[cols].reset_index(drop=True)


def diagnosticar_inventario(inv):
    """Reglas de calidad de datos. Devuelve [(regla, severidad, DataFrame)]."""
    if inv is None or inv.empty:
        return []
    barras = inv["CodigoBarras"].map(limpiar_codigo)
    duplicado = (barras != "") & barras.duplicated(keep=False)
    reglas = [
        ("Stock negativo", "Alta", inv["StockSistema"] < 0),
        ("Sin costo unitario", "Alta", inv["CostoUnitario"] <= 0),
        ("Precio menor al costo", "Alta",
         (inv["PrecioVenta"] > 0) & (inv["CostoUnitario"] > 0) & (inv["PrecioVenta"] < inv["CostoUnitario"])),
        ("Sin precio de venta", "Media", inv["PrecioVenta"] <= 0),
        ("Código de barras duplicado", "Media", duplicado),
        ("Sin código de barras", "Media", barras == ""),
        ("Sin categoría", "Baja", inv["Categoria"].astype(str).str.strip() == ""),
        ("Stock en cero", "Info", inv["StockSistema"] == 0),
    ]
    return [(nombre, sev, inv[mask].copy()) for nombre, sev, mask in reglas]


def productos_pendientes(inv, conteos, id_sesion):
    """Productos del inventario que todavía no se cuentan en la sesión, del más valioso al menos."""
    if inv is None or inv.empty:
        return pd.DataFrame()
    contados = set()
    if conteos is not None and not conteos.empty:
        dc = conteos[conteos["IdSesion"].astype(str) == str(id_sesion)]
        if not dc.empty:
            contados = set(_claves_df(dc))
    d = inv[~_claves_df(inv).isin(contados)].copy()
    d["Valor"] = d["StockSistema"].clip(lower=0) * d["CostoUnitario"]
    return d.sort_values("Valor", ascending=False)


def productividad_contadores(conteos, id_sesion=None):
    cols = ["Contador", "Conteos", "OK", "Faltantes", "Sobrantes", "Exactitud %",
            "Horas activas", "Conteos/hora", "Impacto neto S/"]
    if conteos is None or conteos.empty:
        return pd.DataFrame(columns=cols)
    d = conteos.copy()
    if id_sesion:
        d = d[d["IdSesion"].astype(str) == str(id_sesion)]
    # Solo la primera pasada de cada producto: los reconteos no inflan la productividad ni la exactitud.
    d = d[~d["Observacion"].astype(str).str.startswith("[RECONTEO]")]
    if d.empty:
        return pd.DataFrame(columns=cols)
    d["_dt"] = pd.to_datetime(d["FechaHora"], errors="coerce")
    filas = []
    for nombre, g in d.groupby("NombreUsuario"):
        n = len(g)
        ok = int((g["TipoDiferencia"] == "OK").sum())
        horas = float("nan")
        ritmo = float("nan")
        if id_sesion:
            marcas = g["_dt"].dropna()
            if len(marcas) > 1:
                horas = (marcas.max() - marcas.min()).total_seconds() / 3600
                if horas >= 0.05:
                    ritmo = n / horas
        filas.append({
            "Contador": nombre,
            "Conteos": n,
            "OK": ok,
            "Faltantes": int((g["TipoDiferencia"] == "FALTANTE").sum()),
            "Sobrantes": int((g["TipoDiferencia"] == "SOBRANTE").sum()),
            "Exactitud %": round(ok / n * 100, 1) if n else 0.0,
            "Horas activas": round(horas, 2) if horas == horas else float("nan"),
            "Conteos/hora": round(ritmo, 1) if ritmo == ritmo else float("nan"),
            "Impacto neto S/": round(float(g["CostoDiferencia"].sum()), 2),
        })
    return pd.DataFrame(filas, columns=cols).sort_values("Conteos", ascending=False).reset_index(drop=True)


def tendencia_sesiones(resumenes):
    if resumenes is None or resumenes.empty:
        return pd.DataFrame()
    d = resumenes.copy()
    for col in ["ExactitudInventario", "DesfaseNeto", "ValorFaltantes", "ValorSobrantes", "ProductosContados"]:
        d[col] = pd.to_numeric(d[col], errors="coerce").fillna(0)
    d = d.drop_duplicates("IdSesion", keep="last").sort_values("Fecha", kind="stable")
    d["Etiqueta"] = d["Fecha"].astype(str) + " · " + d["NombreSesion"].astype(str)
    repetidos = d.groupby("Etiqueta").cumcount()
    d["Etiqueta"] = d["Etiqueta"] + repetidos.map(lambda i: "" if i == 0 else f" ({i + 1})")
    return d.reset_index(drop=True)


def alertas_operativas(inv, sesiones):
    """Alertas breves para el dashboard de inicio."""
    alertas = []
    if sesiones is not None and not sesiones.empty:
        abiertas = sesiones[sesiones["Estado"].str.upper() == "ABIERTA"]
        for _, s in abiertas.iterrows():
            inicio = pd.to_datetime(s["FechaInicio"], errors="coerce")
            if pd.notna(inicio):
                horas = (datetime.now() - inicio.to_pydatetime()).total_seconds() / 3600
                if horas >= HORAS_SESION_ALERTA:
                    alertas.append(
                        f"La sesión **{s['NombreSesion']}** lleva {horas:,.0f} h abierta. Revisa si ya debe cerrarse."
                    )
    if inv is not None and not inv.empty:
        negativos = int((inv["StockSistema"] < 0).sum())
        sin_costo = int((inv["CostoUnitario"] <= 0).sum())
        if negativos:
            alertas.append(f"Hay **{negativos:,}** producto(s) con stock negativo en el sistema.")
        if sin_costo:
            alertas.append(f"Hay **{sin_costo:,}** producto(s) sin costo unitario: su valor de inventario está subestimado.")
    return alertas

# =========================================================
# UI HELPERS
# =========================================================

def header(titulo, subtitulo=""):
    st.markdown(
        f"""
        <div class='premium-header'>
            <h1>{safe_text(titulo)}</h1>
            <p>{safe_text(subtitulo)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def footer():
    st.markdown("""
        <div class="app-footer">
            Desarrollado por <strong>Humberto Atoche Obeso</strong><br>
            <strong>Tiendas Premium E.I.R.L.</strong> • RUC 20612107786<br>
            Todos los derechos reservados
        </div>
    """, unsafe_allow_html=True)


def kpi(label, value, note=""):
    st.markdown(
        f"""
        <div class='kpi-card'>
            <div class='kpi-label'>{safe_text(label)}</div>
            <div class='kpi-value'>{safe_text(value)}</div>
            <div class='kpi-note'>{safe_text(note)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def badge(tipo):
    clase = {
        "OK": "badge-ok",
        "FALTANTE": "badge-faltante",
        "SOBRANTE": "badge-sobrante",
        "ABIERTA": "badge-abierta",
        "CERRADA": "badge-cerrada",
    }.get(str(tipo).upper(), "badge-cerrada")
    return f"<span class='badge {clase}'>{safe_text(tipo)}</span>"

# =========================================================
# LOGIN / SETUP
# =========================================================

def pantalla_setup_inicial():
    header("Configuración inicial", "No existen usuarios activos en la hoja Usuarios")
    st.info("Crea el primer usuario ADMIN para poder ingresar al sistema.")
    with st.form("form_admin_inicial"):
        c1, c2 = st.columns(2)
        usuario = c1.text_input("Usuario")
        nombre = c2.text_input("Nombre completo")
        p1, p2 = st.columns(2)
        password = p1.text_input("Contraseña", type="password")
        confirmacion = p2.text_input("Confirmar contraseña", type="password")
        if st.form_submit_button("🔐 Crear administrador", use_container_width=True):
            if not usuario.strip() or not nombre.strip() or not password:
                st.error("Completa todos los campos.")
            elif password != confirmacion:
                st.error("Las contraseñas no coinciden.")
            elif len(password) < 6:
                st.error("La contraseña debe tener al menos 6 caracteres.")
            else:
                try:
                    crear_usuario(usuario, nombre, "ADMIN", password)
                    st.success("Administrador creado. Ya puedes iniciar sesión.")
                except Exception as exc:
                    mostrar_error_google(exc, "creación del administrador")


def pantalla_login():
    usuarios = cargar_usuarios()
    if usuarios.empty:
        pantalla_setup_inicial()
        footer()
        return

    # --- LOGIN ESTILO CORPORATIVO TIENDAS PREMIUM / APP 39 ---
    st.markdown("<br><br>", unsafe_allow_html=True)
    c_log1, c_log2, c_log3 = st.columns([1, 1, 1])

    with c_log2:
        with st.container(border=True):
            st.markdown(
                f'<div style="text-align:center; padding: 8px 0 12px 0;">{logo_tag(72)}</div>',
                unsafe_allow_html=True,
            )
            st.markdown("""
                <div style='text-align: center; padding-bottom: 12px;'>
                    <span style='font-size: 0.75rem; font-weight: 700; letter-spacing: 1.5px; color: #EC3237;'>TIENDAS PREMIUM</span>
                    <h3 style='margin: 4px 0 0 0; font-weight: 600; color: #111827; font-size: 1.1rem;'>Iniciar Sesión</h3>
                </div>
            """, unsafe_allow_html=True)
            usuario = st.text_input(
                "Usuario",
                placeholder="Ingresa tu usuario",
            )
            password = st.text_input(
                "Contraseña",
                type="password",
                placeholder="Ingresa tu contraseña",
            )
            st.markdown("<br>", unsafe_allow_html=True)

            segundos_bloqueo = int(float(st.session_state.get("login_bloqueo_hasta", 0.0)) - time.time())
            if segundos_bloqueo > 0:
                st.error(f"Demasiados intentos fallidos. Intenta nuevamente en {segundos_bloqueo // 60 + 1} min.")

            if st.button("Ingresar al Sistema", use_container_width=True, disabled=segundos_bloqueo > 0):
                try:
                    registro = autenticar(usuario, password)
                    if registro:
                        st.session_state.autenticado = True
                        st.session_state.usuario = registro
                        st.session_state.pagina = "Inicio"
                        st.session_state.codigo_pendiente = ""
                        st.session_state.producto_pendiente = None
                        st.session_state.modo_inventario = "scanner"
                        st.session_state.login_intentos = 0
                        registrar_auditoria("LOGIN", "Inicio de sesión")
                        st.rerun()
                    else:
                        intentos = int(st.session_state.get("login_intentos", 0)) + 1
                        if intentos >= MAX_INTENTOS_LOGIN:
                            st.session_state.login_intentos = 0
                            st.session_state.login_bloqueo_hasta = time.time() + BLOQUEO_LOGIN_SEGUNDOS
                            registrar_auditoria("LOGIN_BLOQUEADO", f"Usuario ingresado: {str(usuario).strip()}")
                            st.error("Demasiados intentos fallidos. Acceso bloqueado por 5 minutos.")
                        else:
                            st.session_state.login_intentos = intentos
                            st.error(f"Credenciales incorrectas ({intentos}/{MAX_INTENTOS_LOGIN})")
                except Exception as exc:
                    mostrar_error_google(exc, "inicio de sesión")

    st.stop()


# =========================================================
# INICIO
# =========================================================

def pantalla_inicio():
    header("Dashboard de Inventario", f"{saludo_actual()}, {st.session_state.usuario.get('NombreCompleto', '')} 👋")

    c_refresh, c_info = st.columns([1, 3])
    with c_refresh:
        if st.button("🔄 Actualizar datos", use_container_width=True):
            actualizar_datos()
            st.rerun()
    with c_info:
        st.markdown("<div class='mobile-note'>⚡ Los datos se mantienen en caché para reducir lecturas a Google Sheets. Actualiza manualmente cuando necesites información reciente.</div>", unsafe_allow_html=True)

    inv = cargar_inventario()
    conteos = cargar_conteos()
    sesiones = cargar_sesiones()

    stock_total = float(inv["StockSistema"].sum()) if not inv.empty else 0
    valor_inventario = float((inv["StockSistema"] * inv["CostoUnitario"]).sum()) if not inv.empty else 0
    activos = int((inv["Estado"].str.upper().isin(["ACTIVO", "ACTIVA", "1", "SI", "SÍ"])).sum()) if not inv.empty else len(inv)
    sesiones_abiertas = int((sesiones["Estado"].str.upper() == "ABIERTA").sum()) if not sesiones.empty else 0

    k1, k2, k3, k4 = st.columns(4)
    with k1: kpi("Productos", f"{len(inv):,}", f"{activos:,} activos")
    with k2: kpi("Stock sistema", f"{stock_total:,.0f}", "unidades")
    with k3: kpi("Valor inventario", formato_soles(valor_inventario), "a costo")
    with k4: kpi("Sesiones abiertas", str(sesiones_abiertas), "en curso")

    alertas = alertas_operativas(inv, sesiones)
    if alertas:
        st.markdown("<div class='section-title'>🚨 Alertas</div>", unsafe_allow_html=True)
        for texto_alerta in alertas:
            st.warning(texto_alerta)

    st.markdown("<div class='section-title'>⚡ Acciones rápidas</div>", unsafe_allow_html=True)
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        if st.button("🧾 Nueva sesión", use_container_width=True):
            st.session_state.pagina = "Sesión"
            st.rerun()
    with a2:
        if st.button("📷 Iniciar inventario", use_container_width=True):
            st.session_state.pagina = "Inventario"
            st.rerun()
    with a3:
        if st.button("📊 Ver resultados", use_container_width=True):
            st.session_state.pagina = "Resultados"
            st.rerun()
    with a4:
        if st.button("💲 Consultar precio", use_container_width=True):
            st.session_state.pagina = "Precios"
            st.rerun()

    st.markdown("<div class='section-title'>📌 Últimos conteos</div>", unsafe_allow_html=True)
    if conteos.empty:
        st.info("Todavía no existen conteos registrados.")
    else:
        ult = conteos.tail(10).iloc[::-1].copy()
        mostrar = ult[["FechaHora", "NombreUsuario", "Producto", "StockSistema", "StockFisico", "Diferencia", "TipoDiferencia", "CostoDiferencia"]].copy()
        mostrar.columns = ["Fecha", "Usuario", "Producto", "Sistema", "Físico", "Dif.", "Resultado", "Impacto"]
        st.dataframe(
            mostrar,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Impacto": st.column_config.NumberColumn(format="S/ %.2f"),
                "Sistema": st.column_config.NumberColumn(format="%.0f"),
                "Físico": st.column_config.NumberColumn(format="%.0f"),
                "Dif.": st.column_config.NumberColumn(format="%.0f"),
            },
        )

# =========================================================
# SESIONES
# =========================================================

def pantalla_sesion():
    header("Sesiones de inventario", "Abre, controla y cierra jornadas de conteo")
    usuario = st.session_state.usuario
    sesion = obtener_sesion_abierta()

    if sesion:
        st.markdown(
            f"<div class='card'><b>🟢 Sesión activa</b><br><br><b>{safe_text(sesion['NombreSesion'])}</b><br>" \
            f"ID: {safe_text(sesion['IdSesion'])}<br>Sucursal: {safe_text(sesion['Sucursal'])}<br>" \
            f"Inicio: {safe_text(sesion['FechaInicio'])}<br>{badge('ABIERTA')}</div>",
            unsafe_allow_html=True,
        )
        conteos = cargar_conteos()
        total = contar_productos_sesion(conteos, sesion["IdSesion"])
        c1, c2 = st.columns(2)
        with c1: kpi("Productos contados", f"{total:,}", "en esta sesión")
        with c2:
            resumen = calcular_resumen(sesion["IdSesion"])
            kpi("Desfase neto", formato_soles(resumen["DesfaseNeto"]), "faltantes - sobrantes")

        total_inv = len(inventario_de_sucursal(cargar_inventario(), sesion["Sucursal"]))
        pendientes = max(total_inv - total, 0)
        confirmar_cierre = True
        if pendientes > 0:
            st.warning(
                f"Quedan {pendientes:,} producto(s) sin contar ({total:,} de {total_inv:,}). "
                "Si cierras ahora, esos productos no formarán parte del resultado."
            )
            confirmar_cierre = st.checkbox(
                "Entiendo que hay productos sin contar y deseo cerrar la sesión igualmente",
                key=f"confirmar_cierre_{sesion['IdSesion']}",
            )

        st.markdown("<div class='section-title'>Acciones</div>", unsafe_allow_html=True)
        a1, a2 = st.columns(2)
        with a1:
            if st.button("📷 Continuar inventario", use_container_width=True):
                st.session_state.pagina = "Inventario"
                st.rerun()
        with a2:
            if st.button("🔒 Cerrar sesión", use_container_width=True, disabled=not confirmar_cierre):
                try:
                    resumen = calcular_resumen(sesion["IdSesion"])
                    detalle_cierre = (
                        f"Contados {total:,}/{total_inv:,} · Exactitud {resumen['ExactitudInventario']:.1f}% · "
                        f"Desfase {formato_soles(resumen['DesfaseNeto'])}"
                    )
                    if not cerrar_sesion(sesion["IdSesion"], detalle_cierre):
                        st.error("No se encontró la sesión para cerrar.")
                    else:
                        resumen["Estado"] = "CERRADA"
                        guardar_resumen(resumen)
                        st.success("Sesión cerrada correctamente.")
                        st.rerun()
                except Exception as exc:
                    mostrar_error_google(exc, "cierre de sesión")
    else:
        st.markdown("<div class='card'><b>ℹ️ No hay una sesión abierta.</b><br>Crea una para comenzar el conteo físico.</div>", unsafe_allow_html=True)
        with st.form("crear_sesion"):
            nombre = st.text_input("Nombre de la sesión", placeholder="Ej. Inventario general septiembre")
            c1, c2 = st.columns(2)
            sucursal = c1.text_input("Sucursal", placeholder="Ej. Tarapoto")
            observacion = c2.text_input("Observación", placeholder="Opcional")
            crear = st.form_submit_button("➕ Crear sesión", use_container_width=True)
            if crear:
                if not nombre.strip() or not sucursal.strip():
                    st.error("Ingresa nombre de sesión y sucursal.")
                else:
                    try:
                        crear_sesion(nombre, sucursal, usuario, observacion)
                        st.success("Sesión creada correctamente.")
                        st.rerun()
                    except Exception as exc:
                        mostrar_error_google(exc, "creación de sesión")

# =========================================================
# SCANNER
# =========================================================

def pantalla_scanner(sesion=None):
    header("Escanear producto", "Usa la cámara del celular o ingresa el código manualmente")

    c_mode, c_stats = st.columns([2, 1])
    with c_mode:
        st.markdown(
            "<div class='mobile-note'>📱 Permite el acceso a la cámara. Apunta al código de barras "
            "dentro del recuadro — el sonido y la vibración confirman una lectura correcta.</div>",
            unsafe_allow_html=True,
        )
    if sesion:
        conteos = cargar_conteos()
        n = contar_productos_sesion(conteos, sesion["IdSesion"])
        with c_stats:
            kpi("Contados", f"{n:,}", "en esta sesión")

    try:
        from streamlit_qrcode_scanner import qrcode_scanner
        codigo = qrcode_scanner(key="premium_barcode_scanner")
        if codigo:
            codigo = limpiar_codigo(codigo)
            if codigo and codigo != st.session_state.get("ultimo_codigo_scan", ""):
                st.session_state.ultimo_codigo_scan = codigo
                st.session_state.codigo_pendiente = codigo
                sonido_confirmacion()
                st.rerun()
    except ImportError:
        st.warning("El escáner no está instalado. Agrega `streamlit-qrcode-scanner` a requirements.txt.")
    except Exception as exc:
        st.warning("No se pudo iniciar la cámara. Puedes utilizar la búsqueda manual.")
        with st.expander("💡 ¿Problemas con la cámara?"):
            st.markdown(
                "- Asegúrate de estar usando **HTTPS** (obligatorio para acceder a la cámara).\n"
                "- Revisa que el navegador tenga **permiso de cámara** habilitado para este sitio.\n"
                "- En iPhone, usa **Safari**; en Android, **Chrome** funciona mejor.\n"
                "- Si la cámara está siendo usada por otra app, ciérrala e intenta de nuevo."
            )
            st.code(str(exc))

    st.divider()
    with st.form("form_codigo_manual", clear_on_submit=True):
        codigo_manual = st.text_input(
            "Código de barras / código de producto",
            placeholder="Escanea o escribe el código y presiona Enter",
        )
        buscar = st.form_submit_button("🔎 Buscar código", use_container_width=True)
    if buscar and codigo_manual.strip():
        st.session_state.codigo_pendiente = limpiar_codigo(codigo_manual)
        st.rerun()

    if st.button("🔎 No puedo escanear — buscar por nombre", use_container_width=True):
        st.session_state.modo_inventario = "busqueda"
        st.session_state.codigo_pendiente = ""
        st.rerun()

    if sesion:
        conteos = cargar_conteos()
        if not conteos.empty:
            propios = conteos[conteos["IdSesion"].astype(str) == str(sesion["IdSesion"])].tail(5).iloc[::-1]
            if not propios.empty:
                st.markdown("<div class='section-title'>🕒 Últimos escaneados</div>", unsafe_allow_html=True)
                for _, fila in propios.iterrows():
                    st.markdown(
                        f"<div class='card' style='padding:10px 14px;margin-bottom:8px;display:flex;"
                        f"justify-content:space-between;align-items:center;'>"
                        f"<span><b>{safe_text(fila['Producto'])}</b> "
                        f"<span style='color:#6b7280;font-size:.78rem'>({safe_text(fila['FechaHora'])})</span></span>"
                        f"{badge(fila['TipoDiferencia'])}</div>",
                        unsafe_allow_html=True,
                    )

# =========================================================
# PRODUCTO
# =========================================================

def pantalla_producto(producto, sesion):
    codigo = limpiar_codigo(producto.get("CodigoBarras", ""))
    ya_contado = producto_ya_contado(sesion["IdSesion"], codigo)
    # El reconteo solo aplica a productos ya contados (evita etiquetar mal si la bandera quedó activa).
    es_reconteo = bool(st.session_state.get("reconteo_activo", False)) and ya_contado
    previo = ultimo_conteo_producto(sesion["IdSesion"], producto)

    if ya_contado and not es_reconteo:
        st.warning("⚠️ Este producto ya fue contado en esta sesión.")
        if previo:
            st.info(
                f"Último conteo: {limpiar_numero(previo.get('StockFisico', 0)):,.0f} unidades "
                f"por {previo.get('NombreUsuario', '')} · {previo.get('FechaHora', '')}."
            )
        c_re, c_back = st.columns(2)
        with c_re:
            if st.button("🔁 Hacer reconteo", type="primary", use_container_width=True):
                st.session_state.reconteo_activo = True
                st.rerun()
        with c_back:
            if st.button("↩️ Volver al escáner", use_container_width=True):
                st.session_state.producto_pendiente = None
                st.session_state.codigo_pendiente = ""
                st.rerun()
        return

    if es_reconteo:
        header("Reconteo físico", "Verifica nuevamente la cantidad: el último conteo será reemplazado en los resultados")
        if previo:
            st.info(
                f"Conteo anterior: {limpiar_numero(previo.get('StockFisico', 0)):,.0f} unidades "
                f"por {previo.get('NombreUsuario', '')} · {previo.get('FechaHora', '')}. "
                "El historial se conserva en el detalle."
            )
    else:
        header("Conteo físico", "Compara el stock del sistema con el conteo real")
    st.markdown(
        f"""
        <div class='product-card'>
            <div class='product-name'>{safe_text(producto.get('Producto','Producto sin nombre'))}</div>
            <div class='product-meta'>Código: {safe_text(producto.get('CodigoProducto',''))} · Barras: {safe_text(codigo)}</div>
            <div class='product-meta'>Categoría: {safe_text(producto.get('Categoria',''))} · Marca: {safe_text(producto.get('Marca',''))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    ciego = CONTEO_CIEGO and str(st.session_state.usuario.get("Rol", "")).upper() != "ADMIN"
    stock_txt = "🔒 Oculto" if ciego else f"{limpiar_numero(producto.get('StockSistema',0)):,.0f}"
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"<div class='stock-box'><div class='stock-label'>Stock sistema</div><div class='stock-number'>{stock_txt}</div></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='stock-box'><div class='stock-label'>Costo unitario</div><div class='stock-number'>{formato_soles(producto.get('CostoUnitario',0))}</div></div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div class='stock-box'><div class='stock-label'>Sucursal</div><div class='stock-number' style='font-size:1rem'>{safe_text(producto.get('Sucursal',''))}</div></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    fisico = st.number_input(
        "Cantidad física encontrada",
        min_value=0.0,
        value=0.0,
        step=1.0,
        key=f"fisico_{codigo}_{sesion['IdSesion']}",
    )
    diferencia = fisico - limpiar_numero(producto.get("StockSistema", 0))
    costo = limpiar_numero(producto.get("CostoUnitario", 0))

    if diferencia < 0:
        tipo = "FALTANTE"
        if not ciego:
            st.error(f"🔴 Faltante: {abs(diferencia):,.0f} unidades · {formato_soles(abs(diferencia) * costo)}")
    elif diferencia > 0:
        tipo = "SOBRANTE"
        if not ciego:
            st.success(f"🟢 Sobrante: {diferencia:,.0f} unidades · {formato_soles(diferencia * costo)}")
    else:
        tipo = "OK"
        if not ciego:
            st.success("🟢 Stock exacto: no existe diferencia.")
    if ciego:
        st.info("🔒 Conteo ciego: el resultado se calculará al guardar.")

    confirmado = True
    if es_diferencia_critica(producto.get("StockSistema", 0), fisico, costo):
        st.warning(
            "⚠️ La cantidad difiere de forma significativa del sistema. Revisa estantes, almacén y otras "
            "ubicaciones, y verifica que el producto sea el correcto antes de guardar."
        )
        confirmado = st.checkbox(
            "Confirmo que el conteo es correcto",
            key=f"confirma_dif_{codigo}_{sesion['IdSesion']}",
        )

    metodo = st.selectbox("Método de conteo", ["Escáner", "Búsqueda manual", "Código manual"])
    observacion = st.text_area("Observación", placeholder="Opcional")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Guardar conteo", type="primary", use_container_width=True, disabled=not confirmado):
            try:
                guardar_conteo(sesion, st.session_state.usuario, producto, fisico, metodo, observacion, es_reconteo=es_reconteo)
                st.success(f"{'Reconteo' if es_reconteo else 'Conteo'} guardado: {tipo}")
                sonido_confirmacion()
                st.session_state.reconteo_activo = False
                st.session_state.producto_pendiente = None
                st.session_state.codigo_pendiente = ""
                st.session_state.ultimo_codigo_scan = ""
                st.rerun()
            except Exception as exc:
                mostrar_error_google(exc, "guardar conteo")
    with c2:
        if st.button("↩️ Cancelar", use_container_width=True):
            st.session_state.reconteo_activo = False
            st.session_state.producto_pendiente = None
            st.session_state.codigo_pendiente = ""
            st.rerun()

# =========================================================
# BÚSQUEDA
# =========================================================

def pantalla_busqueda(sesion):
    header("Buscar producto", "Encuentra el producto por nombre, código, descripción o marca")
    texto = st.text_input("Buscar", placeholder="Ej. Inca Kola, 775..., Coca...")

    inv_completo = cargar_inventario()
    c1, c2 = st.columns(2)
    with c1:
        categorias = ["Todas"] + sorted([c for c in inv_completo["Categoria"].unique() if c]) if not inv_completo.empty else ["Todas"]
        cat_sel = st.selectbox("Filtrar por categoría", categorias)
    with c2:
        sucursales = ["Todas"] + sorted([s for s in inv_completo["Sucursal"].unique() if s]) if not inv_completo.empty else ["Todas"]
        suc_sel = st.selectbox("Filtrar por sucursal", sucursales)

    df = buscar_productos(texto)
    if cat_sel != "Todas":
        df = df[df["Categoria"] == cat_sel]
    if suc_sel != "Todas":
        df = df[df["Sucursal"] == suc_sel]

    if df.empty:
        st.info("No se encontraron productos.")
    else:
        st.caption(f"Mostrando {len(df):,} resultado(s).")
        for idx, producto in df.iterrows():
            codigo = limpiar_codigo(producto.get("CodigoBarras", ""))
            nombre = str(producto.get("Producto", "Sin nombre"))
            st.markdown(
                f"<div class='card'><b>{safe_text(nombre)}</b><br><span style='color:#6b7280;font-size:.8rem'>Código: {safe_text(producto.get('CodigoProducto',''))} · Barras: {safe_text(codigo)} · Stock: {limpiar_numero(producto.get('StockSistema',0)):,.0f}</span></div>",
                unsafe_allow_html=True,
            )
            if st.button("Seleccionar", key=f"sel_prod_{idx}_{codigo}", use_container_width=True):
                st.session_state.producto_pendiente = producto.to_dict()
                st.session_state.codigo_pendiente = codigo
                st.session_state.modo_inventario = "producto"
                st.rerun()

    if st.button("📷 Volver al escáner", use_container_width=True):
        st.session_state.modo_inventario = "scanner"
        st.rerun()

# =========================================================
# CONSULTA DE PRECIOS (para atención rápida en caja/piso)
# =========================================================

def tarjeta_precio(producto):
    nombre = producto.get("Producto", "Producto sin nombre")
    precio = limpiar_numero(producto.get("PrecioVenta", 0))
    stock = limpiar_numero(producto.get("StockSistema", 0))
    unidad = producto.get("Unidad", "") or "unidad"

    st.markdown(
        f"""
        <div class='price-hero'>
            <div class='price-label'>{safe_text(nombre)}</div>
            <div class='price-value'>{formato_soles(precio)}</div>
            <div class='price-sub'>Precio de venta al público</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class='price-info-grid'>
            <div class='price-info-item'><div class='lbl'>Código</div><div class='val'>{safe_text(producto.get('CodigoProducto','') or '—')}</div></div>
            <div class='price-info-item'><div class='lbl'>Marca</div><div class='val'>{safe_text(producto.get('Marca','') or '—')}</div></div>
            <div class='price-info-item'><div class='lbl'>Categoría</div><div class='val'>{safe_text(producto.get('Categoria','') or '—')}</div></div>
            <div class='price-info-item'><div class='lbl'>Stock</div><div class='val'>{stock:,.0f} {safe_text(unidad)}</div></div>
            <div class='price-info-item'><div class='lbl'>Sucursal</div><div class='val'>{safe_text(producto.get('Sucursal','') or '—')}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if stock <= 0:
        st.warning("⚠️ El sistema no registra stock disponible para este producto.")

    if st.button("🔎 Consultar otro producto", type="primary", use_container_width=True):
        st.session_state.precio_producto = None
        st.session_state.precio_ultimo_codigo_scan = ""
        st.rerun()


def pantalla_precios():
    header("Consulta de precios", "Escanea o busca un producto para informar su precio al instante")

    if st.session_state.get("precio_producto"):
        tarjeta_precio(st.session_state.precio_producto)
        return

    modo = st.session_state.get("precio_modo", "scanner")
    a1, a2 = st.columns(2)
    with a1:
        if st.button("📷 Escanear código", use_container_width=True, type="primary" if modo == "scanner" else "secondary"):
            st.session_state.precio_modo = "scanner"
            st.rerun()
    with a2:
        if st.button("🔎 Buscar por nombre", use_container_width=True, type="primary" if modo == "busqueda" else "secondary"):
            st.session_state.precio_modo = "busqueda"
            st.rerun()

    st.divider()

    if modo == "busqueda":
        texto = st.text_input("Buscar producto", placeholder="Ej. Inca Kola, 775..., Coca...", key="precio_texto_busqueda")
        df = buscar_productos(texto)
        if df.empty:
            st.info("Escribe un nombre, marca o código para ver resultados.")
        else:
            st.caption(f"Mostrando {len(df):,} resultado(s).")
            for idx, producto in df.iterrows():
                nombre = str(producto.get("Producto", "Sin nombre"))
                precio = formato_soles(producto.get("PrecioVenta", 0))
                st.markdown(
                    f"<div class='card'><b>{safe_text(nombre)}</b> — <span style='color:#1071b8;font-weight:800'>{precio}</span>"
                    f"<br><span style='color:#6b7280;font-size:.8rem'>Código: {safe_text(producto.get('CodigoProducto',''))}</span></div>",
                    unsafe_allow_html=True,
                )
                if st.button("Ver precio", key=f"precio_sel_{idx}", use_container_width=True):
                    st.session_state.precio_producto = producto.to_dict()
                    st.rerun()
        return

    st.markdown(
        "<div class='mobile-note'>📱 Apunta la cámara al código de barras. Ideal para responder consultas de precio en caja sin usar el conteo físico.</div>",
        unsafe_allow_html=True,
    )
    try:
        from streamlit_qrcode_scanner import qrcode_scanner
        codigo = qrcode_scanner(key="precio_barcode_scanner")
        if codigo:
            codigo = limpiar_codigo(codigo)
            if codigo and codigo != st.session_state.get("precio_ultimo_codigo_scan", ""):
                st.session_state.precio_ultimo_codigo_scan = codigo
                producto = buscar_por_codigo(codigo)
                if producto:
                    st.session_state.precio_producto = producto
                    sonido_confirmacion()
                    st.rerun()
                else:
                    st.error(f"No encontramos el código **{codigo}** en el inventario.")
    except ImportError:
        st.warning("El escáner no está instalado. Agrega `streamlit-qrcode-scanner` a requirements.txt.")
    except Exception as exc:
        st.warning("No se pudo iniciar la cámara. Usa la búsqueda por nombre.")
        with st.expander("Detalle técnico"):
            st.code(str(exc))

    st.divider()
    with st.form("form_codigo_precio", clear_on_submit=True):
        codigo_manual = st.text_input(
            "Código de barras / código de producto",
            placeholder="Escanea con un lector físico o escribe el código y presiona Enter",
        )
        buscar = st.form_submit_button("🔎 Consultar precio", use_container_width=True)
    if buscar and codigo_manual.strip():
        producto = buscar_por_codigo(codigo_manual)
        if producto:
            st.session_state.precio_producto = producto
            st.rerun()
        else:
            st.error(f"No encontramos el código **{limpiar_codigo(codigo_manual)}** en el inventario.")

# =========================================================
# INVENTARIO
# =========================================================

def pantalla_inventario():
    sesion = obtener_sesion_abierta()
    if not sesion:
        header("Inventario físico", "Primero debes abrir una sesión")
        st.warning("No existe una sesión abierta.")
        if st.button("🧾 Ir a Sesión", use_container_width=True):
            st.session_state.pagina = "Sesión"
            st.rerun()
        return

    conteos = cargar_conteos()
    contados = contar_productos_sesion(conteos, sesion["IdSesion"])
    total = len(inventario_de_sucursal(cargar_inventario(), sesion["Sucursal"]))
    porcentaje = (contados / total * 100) if total else 0

    st.markdown(
        f"<div class='mobile-note'>🧾 <b>{safe_text(sesion['NombreSesion'])}</b> · {safe_text(sesion['Sucursal'])} · {contados:,}/{total:,} productos · {porcentaje:.1f}%</div>",
        unsafe_allow_html=True,
    )
    st.progress(min(porcentaje / 100, 1.0))

    if st.session_state.get("producto_pendiente"):
        pantalla_producto(st.session_state.producto_pendiente, sesion)
        return

    codigo = st.session_state.get("codigo_pendiente", "")
    if codigo:
        producto = buscar_por_codigo(codigo)
        if producto:
            st.session_state.producto_pendiente = producto
            st.rerun()
        else:
            st.error(f"No encontramos el código **{codigo}** en el inventario.")
            if st.button("🔎 Buscar por nombre", use_container_width=True):
                st.session_state.modo_inventario = "busqueda"
                st.session_state.codigo_pendiente = ""
                st.rerun()
            if st.button("↩️ Volver", use_container_width=True):
                st.session_state.codigo_pendiente = ""
                st.rerun()
            return

    modo = st.session_state.get("modo_inventario", "scanner")
    if modo == "busqueda":
        pantalla_busqueda(sesion)
    else:
        pantalla_scanner(sesion)

# =========================================================
# RESULTADOS / DASHBOARD EJECUTIVO
# =========================================================

def pantalla_resultados():
    header("Resultados y dashboard ejecutivo", "Analiza exactitud, faltantes, sobrantes e impacto económico")
    sesiones = cargar_sesiones()
    conteos = cargar_conteos()

    if sesiones.empty:
        st.info("No existen sesiones registradas.")
        return

    opciones = sesiones.sort_values("FechaInicio", ascending=False)["IdSesion"].astype(str).tolist()
    seleccionado = st.selectbox("Seleccionar sesión", opciones, format_func=lambda x: (
        str(sesiones.loc[sesiones["IdSesion"].astype(str) == x, "NombreSesion"].iloc[0])
        if (sesiones["IdSesion"].astype(str) == x).any() else x
    ))

    resumen = calcular_resumen(seleccionado)
    dc_hist = conteos[conteos["IdSesion"].astype(str) == str(seleccionado)].copy() if not conteos.empty else pd.DataFrame()
    dc = conteos_vigentes(dc_hist)  # último conteo de cada producto (respeta reconteos)
    ajustes = generar_ajustes(dc)

    k1, k2, k3, k4 = st.columns(4)
    if resumen["ProductosContados"]:
        nota_exactitud = f"Meta {META_EXACTITUD:.0f}% · " + ("✅ cumple" if resumen["ExactitudInventario"] >= META_EXACTITUD else "⚠️ bajo la meta")
    else:
        nota_exactitud = f"Meta {META_EXACTITUD:.0f}%"
    with k1: kpi("Exactitud", f"{resumen['ExactitudInventario']:.1f}%", nota_exactitud)
    with k2: kpi("Faltantes", formato_soles(resumen["ValorFaltantes"]), f"{resumen['UnidadesFaltantes']:,.0f} unidades")
    with k3: kpi("Sobrantes", formato_soles(resumen["ValorSobrantes"]), f"{resumen['UnidadesSobrantes']:,.0f} unidades")
    with k4: kpi("Desfase neto", formato_soles(resumen["DesfaseNeto"]), "pérdida neta valorizada")

    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi("Contados", f"{resumen['ProductosContados']:,}", f"de {resumen['ProductosSistema']:,}")
    with c2: kpi("OK", f"{resumen['ProductosOK']:,}", "sin diferencia")
    with c3: kpi("Faltantes", f"{resumen['ProductosFaltantes']:,}", "productos")
    with c4: kpi("Sobrantes", f"{resumen['ProductosSobrantes']:,}", "productos")

    st.markdown("<div class='section-title'>🔴 Principales faltantes</div>", unsafe_allow_html=True)
    if dc.empty:
        st.info("No hay conteos para esta sesión.")
    else:
        falt = dc[dc["TipoDiferencia"] == "FALTANTE"].copy().sort_values("ValorFaltante", ascending=False).head(10)
        if falt.empty:
            st.success("No existen faltantes en esta sesión.")
        else:
            fshow = falt[["Producto", "CodigoProducto", "StockSistema", "StockFisico", "Diferencia", "CostoUnitario", "ValorFaltante", "NombreUsuario"]].copy()
            fshow.columns = ["Producto", "Código", "Sistema", "Físico", "Dif.", "Costo", "Faltante", "Usuario"]
            st.dataframe(fshow, use_container_width=True, hide_index=True, column_config={
                "Costo": st.column_config.NumberColumn(format="S/ %.2f"),
                "Faltante": st.column_config.NumberColumn(format="S/ %.2f"),
            })

    st.markdown("<div class='section-title'>🟢 Principales sobrantes</div>", unsafe_allow_html=True)
    if not dc.empty:
        sobr = dc[dc["TipoDiferencia"] == "SOBRANTE"].copy().sort_values("ValorSobrante", ascending=False).head(10)
        if sobr.empty:
            st.info("No existen sobrantes en esta sesión.")
        else:
            sshow = sobr[["Producto", "CodigoProducto", "StockSistema", "StockFisico", "Diferencia", "CostoUnitario", "ValorSobrante", "NombreUsuario"]].copy()
            sshow.columns = ["Producto", "Código", "Sistema", "Físico", "Dif.", "Costo", "Sobrante", "Usuario"]
            st.dataframe(sshow, use_container_width=True, hide_index=True, column_config={
                "Costo": st.column_config.NumberColumn(format="S/ %.2f"),
                "Sobrante": st.column_config.NumberColumn(format="S/ %.2f"),
            })

    if not dc.empty:
        st.markdown("<div class='section-title'>📊 Valor de faltantes por categoría</div>", unsafe_allow_html=True)
        por_categoria = (
            dc[dc["TipoDiferencia"] == "FALTANTE"]
            .groupby("Categoria")["ValorFaltante"]
            .sum()
            .sort_values(ascending=False)
        )
        if por_categoria.empty:
            st.info("No hay faltantes registrados por categoría en esta sesión.")
        else:
            st.bar_chart(por_categoria)

    if not dc.empty:
        st.markdown("<div class='section-title'>🔁 Diferencias significativas a revisar</div>", unsafe_allow_html=True)
        criticos = dc[dc.apply(lambda r: es_diferencia_critica(r["StockSistema"], r["StockFisico"], r["CostoUnitario"]), axis=1)].copy()
        if criticos.empty:
            st.success("No hay diferencias significativas que requieran reconteo.")
        else:
            cshow = criticos[["Producto", "CodigoProducto", "StockSistema", "StockFisico", "Diferencia", "CostoDiferencia", "NombreUsuario"]].copy()
            cshow.columns = ["Producto", "Código", "Sistema", "Físico", "Dif.", "Impacto", "Usuario"]
            st.dataframe(cshow, use_container_width=True, hide_index=True, column_config={
                "Impacto": st.column_config.NumberColumn(format="S/ %.2f"),
            })
            sesion_abierta = obtener_sesion_abierta()
            if sesion_abierta and str(sesion_abierta["IdSesion"]) == str(seleccionado):
                idx_rec = st.selectbox(
                    "Producto a recontar",
                    list(criticos.index),
                    format_func=lambda i: f"{criticos.loc[i, 'Producto']} · {criticos.loc[i, 'CodigoProducto']} ({criticos.loc[i, 'Diferencia']:+,.0f})",
                )
                if st.button("🔁 Iniciar reconteo", use_container_width=True):
                    fila_rec = criticos.loc[idx_rec]
                    prod_rec = buscar_por_codigo(fila_rec["CodigoBarras"]) or buscar_por_codigo(fila_rec["CodigoProducto"])
                    if prod_rec:
                        st.session_state.producto_pendiente = prod_rec
                        st.session_state.codigo_pendiente = ""
                        st.session_state.reconteo_activo = True
                        st.session_state.modo_inventario = "scanner"
                        st.session_state.pagina = "Inventario"
                        st.rerun()
                    else:
                        st.error("No se encontró el producto en el inventario actual.")
            else:
                st.caption("El reconteo solo está disponible mientras la sesión esté abierta.")

    st.markdown("<div class='section-title'>🧮 Ajustes sugeridos de stock</div>", unsafe_allow_html=True)
    if ajustes.empty:
        st.info("No hay diferencias que ajustar en esta sesión.")
    else:
        st.caption("Lista lista para cargar en tu sistema contable/ERP. Ajuste positivo = entrada, negativo = salida. Considera el último conteo de cada producto.")
        st.dataframe(ajustes, use_container_width=True, hide_index=True, column_config={
            "CostoUnitario": st.column_config.NumberColumn("Costo", format="S/ %.2f"),
            "ImpactoSoles": st.column_config.NumberColumn("Impacto", format="S/ %.2f"),
        })
        st.download_button(
            "📥 Descargar ajustes sugeridos (CSV)",
            data=ajustes.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"ajustes_{seleccionado}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.markdown("<div class='section-title'>📋 Detalle completo</div>", unsafe_allow_html=True)
    if not dc_hist.empty:
        st.caption("Los resultados usan el último conteo de cada producto; este detalle conserva todo el historial, incluidos los reconteos.")
        detalle = dc_hist.copy()
        st.dataframe(detalle, use_container_width=True, hide_index=True)

        csv = detalle.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 Descargar detalle CSV",
            data=csv,
            file_name=f"inventario_{seleccionado}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    resumen_csv = pd.DataFrame([resumen]).to_csv(index=False).encode("utf-8-sig")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "📥 Descargar resumen CSV",
            data=resumen_csv,
            file_name=f"resumen_{seleccionado}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with c2:
        try:
            excel_bytes = exportar_excel({
                "Detalle": dc_hist if not dc_hist.empty else pd.DataFrame(columns=HEADERS_CONTEO),
                "Resumen": pd.DataFrame([resumen]),
                "Ajustes": ajustes,
            })
            st.download_button(
                "📊 Descargar todo en Excel",
                data=excel_bytes,
                file_name=f"inventario_{seleccionado}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception:
            st.caption("Instala `openpyxl` en requirements.txt para habilitar la exportación a Excel.")

# =========================================================
# ANÁLISIS
# =========================================================

def _tab_pendientes():
    inv = cargar_inventario()
    sesion = obtener_sesion_abierta()
    if inv.empty:
        st.info("No hay productos en el inventario.")
        return
    if not sesion:
        st.info("No hay una sesión abierta. Abre una sesión para ver qué productos faltan por contar.")
        return
    inv = inventario_de_sucursal(inv, sesion["Sucursal"])

    pend = productos_pendientes(inv, cargar_conteos(), sesion["IdSesion"])
    total = len(inv)
    valor_total = float((inv["StockSistema"].clip(lower=0) * inv["CostoUnitario"]).sum())
    valor_pend = float(pend["Valor"].sum()) if not pend.empty else 0.0
    avance = (1 - len(pend) / total) * 100 if total else 0.0
    cobertura = (1 - valor_pend / valor_total) * 100 if valor_total else 0.0

    st.markdown(
        f"<div class='mobile-note'>🧾 <b>{safe_text(sesion['NombreSesion'])}</b> · {safe_text(sesion['Sucursal'])}</div>",
        unsafe_allow_html=True,
    )
    k1, k2, k3, k4 = st.columns(4)
    with k1: kpi("Pendientes", f"{len(pend):,}", f"de {total:,} productos")
    with k2: kpi("Avance", f"{avance:.1f}%", "por productos")
    with k3: kpi("Valor pendiente", formato_soles(valor_pend), "a costo")
    with k4: kpi("Cobertura por valor", f"{cobertura:.1f}%", "del valor ya contado")

    c1, c2 = st.columns(2)
    categorias = sorted([c for c in pend["Categoria"].unique() if c]) if not pend.empty else []
    cat_sel = c1.multiselect("Categorías (vacío = todas)", categorias)
    ocultar_cero = c2.checkbox("Ocultar productos con stock 0", value=True)

    vista = pend.copy()
    if cat_sel:
        vista = vista[vista["Categoria"].isin(cat_sel)]
    if ocultar_cero:
        vista = vista[vista["StockSistema"] != 0]
    if vista.empty:
        st.success("🎉 No quedan productos pendientes con estos filtros.")
        return

    st.caption(f"{len(vista):,} producto(s) pendientes, ordenados por valor: cuenta primero los más costosos para reducir el riesgo.")
    cols = ["Producto", "CodigoProducto", "CodigoBarras", "Categoria", "Marca", "Sucursal", "StockSistema", "Valor"]
    st.dataframe(
        vista[cols].head(300),
        use_container_width=True,
        hide_index=True,
        column_config={
            "StockSistema": st.column_config.NumberColumn("Stock", format="%.0f"),
            "Valor": st.column_config.NumberColumn("Valor a costo", format="S/ %.2f"),
        },
    )
    st.download_button(
        "📥 Descargar pendientes (CSV)",
        data=vista[cols].to_csv(index=False).encode("utf-8-sig"),
        file_name=f"pendientes_{sesion['IdSesion']}.csv",
        mime="text/csv",
        use_container_width=True,
    )


def _tab_abc():
    abc = clasificar_abc(cargar_inventario())
    if abc.empty:
        st.info("No hay productos con stock y costo para clasificar.")
        return
    st.caption(
        "Clasificación Pareto por valor de inventario a costo: **A** concentra el 80 % del valor, "
        "**B** el siguiente 15 % y **C** el último 5 %. Prioriza el conteo y el control en la clase A."
    )
    columnas = st.columns(3)
    for columna, clase in zip(columnas, ["A", "B", "C"]):
        sub = abc[abc["Clase"] == clase]
        with columna:
            kpi(f"Clase {clase}", f"{len(sub):,} productos", f"{sub['% Valor'].sum():.1f}% del valor")

    st.bar_chart(abc.groupby("Clase")["Valor"].sum())

    clase_sel = st.selectbox("Ver clase", ["Todas", "A", "B", "C"])
    vista = abc if clase_sel == "Todas" else abc[abc["Clase"] == clase_sel]
    st.dataframe(
        vista.head(300),
        use_container_width=True,
        hide_index=True,
        column_config={
            "StockSistema": st.column_config.NumberColumn("Stock", format="%.0f"),
            "CostoUnitario": st.column_config.NumberColumn("Costo", format="S/ %.2f"),
            "Valor": st.column_config.NumberColumn(format="S/ %.2f"),
            "% Valor": st.column_config.NumberColumn(format="%.2f%%"),
            "% Acumulado": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )
    st.download_button(
        "📥 Descargar clasificación ABC (CSV)",
        data=abc.to_csv(index=False).encode("utf-8-sig"),
        file_name="clasificacion_abc.csv",
        mime="text/csv",
        use_container_width=True,
    )


def _tab_salud():
    inv = cargar_inventario()
    if inv.empty:
        st.info("No hay productos en el inventario.")
        return
    hallazgos = diagnosticar_inventario(inv)
    afectados = set()
    for _, sev, d in hallazgos:
        if sev in ("Alta", "Media"):
            afectados.update(d.index)
    calidad = (1 - len(afectados) / len(inv)) * 100
    altas = sum(len(d) for _, sev, d in hallazgos if sev == "Alta")

    k1, k2, k3 = st.columns(3)
    with k1: kpi("Calidad de datos", f"{calidad:.1f}%", "productos sin alertas altas/medias")
    with k2: kpi("Hallazgos críticos", f"{altas:,}", "severidad alta")
    with k3: kpi("Productos revisados", f"{len(inv):,}", "en el inventario")

    resumen = pd.DataFrame([{"Regla": n, "Severidad": s, "Productos": len(d)} for n, s, d in hallazgos])
    st.dataframe(resumen, use_container_width=True, hide_index=True)

    con_datos = [(n, d) for n, s, d in hallazgos if not d.empty]
    if not con_datos:
        st.success("No se encontraron problemas en los datos del inventario.")
        return
    nombres = [n for n, _ in con_datos]
    regla_sel = st.selectbox("Ver detalle de", nombres)
    detalle = dict(con_datos)[regla_sel]
    cols = ["Producto", "CodigoProducto", "CodigoBarras", "Categoria", "Sucursal", "StockSistema", "CostoUnitario", "PrecioVenta"]
    st.dataframe(detalle[cols].head(300), use_container_width=True, hide_index=True)
    try:
        st.download_button(
            "📊 Descargar todos los hallazgos (Excel)",
            data=exportar_excel({n: d for n, d in con_datos}),
            file_name="salud_datos_inventario.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except Exception:
        st.caption("Instala `openpyxl` para exportar a Excel.")


def _tab_productividad():
    conteos = cargar_conteos()
    sesiones = cargar_sesiones()
    if conteos.empty:
        st.info("Todavía no hay conteos registrados.")
        return
    todas = "Todas las sesiones"
    ids = sesiones.sort_values("FechaInicio", ascending=False)["IdSesion"].astype(str).tolist() if not sesiones.empty else []
    nombres = {
        str(r["IdSesion"]): f"{r['NombreSesion']} ({str(r['FechaInicio'])[:10]})"
        for _, r in sesiones.iterrows()
    } if not sesiones.empty else {}
    sel = st.selectbox("Sesión", [todas] + ids, format_func=lambda x: x if x == todas else nombres.get(x, x))
    df = productividad_contadores(conteos, None if sel == todas else sel)
    if df.empty:
        st.info("No hay conteos para la sesión seleccionada.")
        return

    ritmo_max = df["Conteos/hora"].max()
    k1, k2, k3 = st.columns(3)
    with k1: kpi("Conteos", f"{int(df['Conteos'].sum()):,}", "registros")
    with k2: kpi("Contadores activos", f"{len(df):,}", "personas")
    with k3: kpi("Mejor ritmo", f"{ritmo_max:,.0f}/h" if ritmo_max == ritmo_max else "—", "por sesión seleccionada")

    st.bar_chart(df.set_index("Contador")["Conteos"])
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("La exactitud del contador mide qué porcentaje de sus conteos coincidió con el sistema en la primera pasada.")
    st.download_button(
        "📥 Descargar productividad (CSV)",
        data=df.to_csv(index=False).encode("utf-8-sig"),
        file_name="productividad_contadores.csv",
        mime="text/csv",
        use_container_width=True,
    )


def _tab_tendencia():
    t = tendencia_sesiones(cargar_resumenes())
    if t.empty:
        st.info("Cierra al menos una sesión para ver la tendencia de exactitud y desfase.")
        return

    ultima = t.iloc[-1]
    variacion = (ultima["ExactitudInventario"] - t.iloc[-2]["ExactitudInventario"]) if len(t) > 1 else None
    k1, k2, k3 = st.columns(3)
    with k1: kpi("Última exactitud", f"{ultima['ExactitudInventario']:.1f}%", f"Meta {META_EXACTITUD:.0f}%")
    with k2: kpi("Variación", f"{variacion:+.1f} pp" if variacion is not None else "—", "frente a la sesión anterior")
    with k3: kpi("Último desfase neto", formato_soles(ultima["DesfaseNeto"]), str(ultima["NombreSesion"]))

    st.markdown("<div class='section-title'>📈 Exactitud por sesión</div>", unsafe_allow_html=True)
    graf = t.set_index("Etiqueta")[["ExactitudInventario"]].rename(columns={"ExactitudInventario": "Exactitud %"})
    graf["Meta"] = META_EXACTITUD
    st.line_chart(graf)

    st.markdown("<div class='section-title'>💸 Desfase neto por sesión</div>", unsafe_allow_html=True)
    st.bar_chart(t.set_index("Etiqueta")["DesfaseNeto"])

    vista = t[["Fecha", "NombreSesion", "Sucursal", "ProductosContados", "ExactitudInventario", "ValorFaltantes", "ValorSobrantes", "DesfaseNeto"]]
    st.dataframe(vista, use_container_width=True, hide_index=True)


def pantalla_analisis():
    header("Análisis de inventario", "Prioriza el conteo, detecta problemas en los datos y mide el desempeño")
    es_admin = str(st.session_state.usuario.get("Rol", "")).upper() == "ADMIN"
    etiquetas = ["🎯 Pendientes", "🅰️ Análisis ABC"]
    if es_admin:
        etiquetas += ["🩺 Salud de datos", "👥 Productividad", "📈 Tendencia"]
    tabs = st.tabs(etiquetas)
    with tabs[0]:
        _tab_pendientes()
    with tabs[1]:
        _tab_abc()
    if es_admin:
        with tabs[2]:
            _tab_salud()
        with tabs[3]:
            _tab_productividad()
        with tabs[4]:
            _tab_tendencia()

# =========================================================
# ADMINISTRACIÓN
# =========================================================

def pantalla_admin():
    header("Administración", "Usuarios, inventario y control de sesiones")
    tab1, tab2, tab3, tab4 = st.tabs(["👤 Usuarios", "📦 Inventario", "🧾 Sesiones", "🛡️ Auditoría"])

    with tab1:
        usuarios = cargar_usuarios()
        if usuarios.empty:
            st.info("No existen usuarios.")
        else:
            vista = usuarios[["Usuario", "NombreCompleto", "Rol", "Estado"]].copy()
            st.dataframe(vista, use_container_width=True, hide_index=True)

        st.markdown("### Crear usuario")
        with st.form("crear_usuario_admin"):
            c1, c2 = st.columns(2)
            usuario = c1.text_input("Usuario")
            nombre = c2.text_input("Nombre completo")
            c3, c4 = st.columns(2)
            rol = c3.selectbox("Rol", ["CONTADOR", "ADMIN"])
            password = c4.text_input("Contraseña", type="password")
            confirmar = st.text_input("Confirmar contraseña", type="password")
            if st.form_submit_button("➕ Crear usuario", use_container_width=True):
                if not usuario.strip() or not nombre.strip() or not password:
                    st.error("Completa todos los campos.")
                elif password != confirmar:
                    st.error("Las contraseñas no coinciden.")
                elif len(password) < 6:
                    st.error("La contraseña debe tener al menos 6 caracteres.")
                else:
                    try:
                        crear_usuario(usuario, nombre, rol, password)
                        st.success("Usuario creado correctamente.")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
                    except Exception as exc:
                        mostrar_error_google(exc, "creación de usuario")

    with tab2:
        inv = cargar_inventario()
        k1, k2, k3 = st.columns(3)
        with k1: kpi("Productos", f"{len(inv):,}", "registros")
        with k2: kpi("Stock", f"{float(inv['StockSistema'].sum()) if not inv.empty else 0:,.0f}", "unidades")
        with k3: kpi("Valor", formato_soles((inv["StockSistema"] * inv["CostoUnitario"]).sum() if not inv.empty else 0), "a costo")
        if not inv.empty:
            st.dataframe(inv, use_container_width=True, hide_index=True)
            colcsv, colxlsx = st.columns(2)
            with colcsv:
                st.download_button(
                    "📥 Exportar inventario (CSV)",
                    data=inv.to_csv(index=False).encode("utf-8-sig"),
                    file_name="inventario_completo.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with colxlsx:
                try:
                    st.download_button(
                        "📊 Exportar inventario (Excel)",
                        data=exportar_excel({"Inventario": inv}),
                        file_name="inventario_completo.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                except Exception:
                    st.caption("Instala `openpyxl` para exportar a Excel.")

    with tab3:
        sesiones = cargar_sesiones()
        if sesiones.empty:
            st.info("No existen sesiones.")
        else:
            st.dataframe(sesiones.sort_values("FechaInicio", ascending=False), use_container_width=True, hide_index=True)

    with tab4:
        aud = cargar_auditoria()
        if aud.empty:
            st.info("Aún no hay eventos registrados. La bitácora guarda inicios de sesión, creación y cierre de sesiones, reconteos y altas de usuarios.")
        else:
            aud = aud.sort_values("FechaHora", ascending=False)
            acciones = ["Todas"] + sorted([a for a in aud["Accion"].astype(str).unique() if a])
            accion_sel = st.selectbox("Filtrar por acción", acciones)
            if accion_sel != "Todas":
                aud = aud[aud["Accion"].astype(str) == accion_sel]
            st.dataframe(aud.head(500), use_container_width=True, hide_index=True)
            st.download_button(
                "📥 Descargar bitácora (CSV)",
                data=aud.to_csv(index=False).encode("utf-8-sig"),
                file_name="auditoria_inventario.csv",
                mime="text/csv",
                use_container_width=True,
            )

# =========================================================
# SIDEBAR
# =========================================================

def _cambio_menu():
    """Callback del menú lateral: se ejecuta ANTES del rerun, por lo que la
    página queda actualizada con un solo clic."""
    st.session_state.pagina = st.session_state.get("nav_menu", "Inicio")


def sidebar():
    usuario = st.session_state.usuario
    rol = str(usuario.get("Rol", "CONTADOR")).upper()
    nombre_usuario = safe_text(usuario.get("NombreCompleto", ""))
    login_usuario = safe_text(usuario.get("Usuario", ""))

    # --- SIDEBAR (mismo diseño y estructura que App 43) ---
    st.sidebar.markdown(
        f'<div style="text-align:center; padding: 8px 0 14px 0;">{logo_tag(58)}</div>',
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("""
        <div style='padding: 8px 0 16px 0;'>
            <div style='font-size: 0.85rem; font-weight: 700; letter-spacing: 1px; color: #FFFFFF;'>
                TIENDAS <span style='color: #EC3237;'>PREMIUM</span>
            </div>
            <div style='font-size: 0.7rem; color: #6B7280; margin-top:2px;'>Sistema de Inventario</div>
        </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown(f"""
        <div style='background-color: #1F2937; padding: 10px 12px; border-radius: 6px; margin-bottom: 16px;'>
            <div style='font-size: 0.8rem; font-weight: 600; color: #F9FAFB;'>{nombre_usuario}</div>
            <div style='font-size: 0.68rem; color: #9CA3AF; text-transform: uppercase;'>{safe_text(rol)} • USUARIO {login_usuario}</div>
        </div>
    """, unsafe_allow_html=True)

    opciones = ["Inicio", "Precios", "Sesión", "Inventario", "Resultados", "Análisis"]
    if rol == "ADMIN":
        opciones.append("Administración")

    # Sincroniza el menú con la página actual (por ejemplo, cuando un botón
    # de la pantalla cambia de página). Se hace ANTES de crear el radio.
    actual = st.session_state.get("pagina", "Inicio")
    if actual not in opciones:
        actual = "Inicio"
        st.session_state.pagina = actual
    if st.session_state.get("nav_menu") != actual:
        st.session_state["nav_menu"] = actual

    seleccion = st.sidebar.radio(
        "Navegación",
        opciones,
        key="nav_menu",
        on_change=_cambio_menu,
    )
    st.session_state.pagina = seleccion

    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)
    if st.sidebar.button("Actualizar Datos", use_container_width=True, key="sb_actualizar_datos"):
        actualizar_datos()
        st.rerun()

    st.sidebar.markdown('<div class="btn-logout">', unsafe_allow_html=True)
    if st.sidebar.button("Cerrar Sesión", use_container_width=True, key="sb_cerrar_sesion"):
        for key in ["autenticado", "usuario", "pagina", "nav_menu", "reconteo_activo", "sesion_actual", "codigo_pendiente", "producto_pendiente", "modo_inventario", "ultimo_codigo_scan", "precio_producto", "precio_modo", "precio_ultimo_codigo_scan"]:
            st.session_state.pop(key, None)
        st.rerun()
    st.sidebar.markdown('</div>', unsafe_allow_html=True)

    st.sidebar.caption("Cache: inventario 60s · usuarios 5min · conteos/sesiones 30s")

# =========================================================
# ESTADO / ARRANQUE
# =========================================================

for key, default in {
    "autenticado": False,
    "usuario": None,
    "pagina": "Inicio",
    "codigo_pendiente": "",
    "producto_pendiente": None,
    "modo_inventario": "scanner",
    "ultimo_codigo_scan": "",
    "precio_producto": None,
    "precio_modo": "scanner",
    "precio_ultimo_codigo_scan": "",
    "reconteo_activo": False,
    "login_intentos": 0,
    "login_bloqueo_hasta": 0.0,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# =========================================================
# CONEXIÓN INICIAL — SIN PREPARAR_HOJAS REPETITIVO
# =========================================================

try:
    obtener_hojas()
except Exception as exc:
    header("Conexión con Google Sheets", "La aplicación está funcionando, pero no pudo acceder a los datos")
    mostrar_error_google(exc, "conexión inicial")
    if st.button("🔄 Reintentar conexión", use_container_width=True):
        refrescar_conexion()
        st.rerun()
    st.markdown("### Verifica")
    st.markdown("1. Que el archivo se llame **BD_Inventario_PremiumMarket**.")
    st.markdown("2. Que existan las hojas: **Inventario, ConteoInventario, SesionesInventario, ResumenInventario y Usuarios**.")
    st.markdown("3. Que el Service Account tenga acceso al archivo.")
    footer()
    st.stop()

if not st.session_state.autenticado:
    try:
        pantalla_login()
    except Exception as exc:
        mostrar_error_google(exc, "carga de login")
    st.stop()

sidebar()

try:
    pagina = st.session_state.get("pagina", "Inicio")
    if pagina == "Inicio":
        pantalla_inicio()
    elif pagina == "Precios":
        pantalla_precios()
    elif pagina == "Sesión":
        pantalla_sesion()
    elif pagina == "Inventario":
        pantalla_inventario()
    elif pagina == "Resultados":
        pantalla_resultados()
    elif pagina == "Análisis":
        pantalla_analisis()
    elif pagina == "Administración":
        if str(st.session_state.usuario.get("Rol", "")).upper() == "ADMIN":
            pantalla_admin()
        else:
            st.error("No tienes permisos para acceder a Administración.")
    footer()
except Exception as exc:
    mostrar_error_google(exc, "carga de la pantalla")
    footer()

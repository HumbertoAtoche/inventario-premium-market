import streamlit as st
import pandas as pd
import gspread
import hashlib
import io
import os
import re
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

# =========================================================
# ESTILOS
# =========================================================

st.markdown("""
<style>
    :root {
        --red: #ec3237;
        --red-dark: #c91f25;
        --green: #00a959;
        --green-dark: #078348;
        --blue: #1071b8;
        --text: #111827;
        --muted: #6b7280;
        --bg: #f7f8fa;
        --card: #ffffff;
        --border: #e5e7eb;
    }

    .stApp { background: var(--bg); }
    .block-container {
        padding-top: 1rem;
        padding-bottom: 4rem;
        max-width: 1450px;
        animation: fadeInUp .45s ease both;
    }

    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .premium-header {
        position: relative;
        overflow: hidden;
        background: linear-gradient(120deg, #ec3237 0%, #c91f25 45%, #a91820 100%);
        background-size: 220% 220%;
        animation: gradientShift 10s ease infinite;
        color: white;
        padding: 24px 28px;
        border-radius: 18px;
        margin-bottom: 18px;
        box-shadow: 0 10px 28px rgba(236,50,55,.18);
    }
    .premium-header::after {
        content: "";
        position: absolute;
        top: -60%; right: -10%;
        width: 260px; height: 260px;
        background: radial-gradient(circle, rgba(255,255,255,.14) 0%, rgba(255,255,255,0) 70%);
        pointer-events: none;
    }
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    .premium-header h1 { margin: 0; font-size: 1.65rem; font-weight: 800; position: relative; z-index: 1; }
    .premium-header p { margin: 5px 0 0; opacity: .92; font-size: .92rem; position: relative; z-index: 1; }

    .section-title { color: var(--text); font-size: 1.1rem; font-weight: 800; margin: 12px 0 10px; }

    .card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 18px;
        box-shadow: 0 4px 15px rgba(17,24,39,.045);
        margin-bottom: 14px;
        transition: box-shadow .15s ease, transform .15s ease;
    }
    .card:hover {
        box-shadow: 0 8px 20px rgba(17,24,39,.08);
        transform: translateY(-1px);
    }

    .kpi-card {
        background: white;
        border: 1px solid var(--border);
        border-top: 3px solid var(--red);
        border-radius: 16px;
        padding: 16px 17px;
        min-height: 105px;
        box-shadow: 0 4px 15px rgba(17,24,39,.045);
        transition: transform .15s ease, box-shadow .15s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 22px rgba(17,24,39,.08);
    }
    .kpi-label { color: var(--muted); font-size: .76rem; font-weight: 700; text-transform: uppercase; letter-spacing: .02em; }
    .kpi-value { color: var(--text); font-size: 1.55rem; font-weight: 850; margin-top: 5px; }
    .kpi-note { color: var(--muted); font-size: .75rem; margin-top: 2px; }

    .product-card {
        background: white;
        border: 1px solid var(--border);
        border-top: 4px solid var(--blue);
        border-radius: 18px;
        padding: 18px;
        box-shadow: 0 7px 22px rgba(17,24,39,.06);
        margin: 10px 0 15px;
        animation: fadeInUp .3s ease both;
    }
    .product-name { font-size: 1.22rem; font-weight: 850; color: var(--text); line-height: 1.25; }
    .product-meta { color: var(--muted); font-size: .82rem; margin-top: 4px; }

    .stock-box {
        background: #f8fafc;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 13px;
        text-align: center;
    }
    .stock-label { color: #6b7280; font-size: .72rem; font-weight: 700; text-transform: uppercase; }
    .stock-number { color: #111827; font-size: 1.45rem; font-weight: 850; }

    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: .72rem;
        font-weight: 800;
    }
    .badge-ok { background:#dcfce7; color:#166534; }
    .badge-faltante { background:#fee2e2; color:#b91c1c; }
    .badge-sobrante { background:#dcfce7; color:#166534; }
    .badge-abierta {
        background:#dbeafe; color:#1d4ed8;
        box-shadow: 0 0 0 0 rgba(29,78,216,.5);
        animation: pulseBadge 2s infinite;
    }
    .badge-cerrada { background:#f3f4f6; color:#4b5563; }

    @keyframes pulseBadge {
        0%   { box-shadow: 0 0 0 0 rgba(29,78,216,.35); }
        70%  { box-shadow: 0 0 0 7px rgba(29,78,216,0); }
        100% { box-shadow: 0 0 0 0 rgba(29,78,216,0); }
    }

    .price-hero {
        background: linear-gradient(135deg, #1071b8 0%, #0a5488 100%);
        color: white;
        border-radius: 20px;
        padding: 28px 22px;
        text-align: center;
        box-shadow: 0 10px 28px rgba(16,113,184,.25);
        margin: 14px 0;
    }
    .price-hero .price-label { font-size: .85rem; font-weight: 700; text-transform: uppercase; opacity: .85; letter-spacing: .04em; }
    .price-hero .price-value { font-size: 3rem; font-weight: 900; margin: 6px 0 2px; line-height: 1; }
    .price-hero .price-sub { font-size: .88rem; opacity: .9; }

    .price-info-grid { display:flex; gap:10px; flex-wrap:wrap; margin-top: 12px; }
    .price-info-item {
        flex: 1 1 120px;
        background: white;
        border: 1px solid var(--border);
        border-radius: 13px;
        padding: 11px 12px;
        text-align: center;
    }
    .price-info-item .lbl { color: var(--muted); font-size: .7rem; font-weight: 700; text-transform: uppercase; }
    .price-info-item .val { color: var(--text); font-size: 1.05rem; font-weight: 800; margin-top: 3px; }

    @media (max-width: 768px) {
        .price-hero { padding: 22px 16px; }
        .price-hero .price-value { font-size: 2.3rem; }
    }

    .st-key-login_card {
        max-width: 460px;
        margin: 6vh auto 0;
        background: white;
        border: 1px solid var(--border);
        border-top: 5px solid var(--red);
        border-radius: 22px;
        padding: 34px 30px 26px;
        box-shadow: 0 18px 45px rgba(17,24,39,.09);
        animation: fadeInUp .5s ease both;
    }
    .login-logo { text-align:center; margin-bottom: 10px; }
    .login-title { text-align:center; font-size:1.7rem; font-weight:900; color:#111827; }
    .login-subtitle { text-align:center; color:#6b7280; margin-bottom:22px; }
    .login-tag {
        text-align:center;
        color: var(--muted);
        font-size: .74rem;
        font-weight: 700;
        letter-spacing: .06em;
        text-transform: uppercase;
        margin-top: 4px;
    }

    .mobile-note {
        background: #fff7ed;
        border: 1px solid #fed7aa;
        color: #9a3412;
        border-radius: 12px;
        padding: 10px 12px;
        font-size: .82rem;
        margin-bottom: 12px;
    }

    .footer-premium {
        text-align: center;
        color: #8a8f98;
        font-size: .72rem;
        padding: 22px 5px 5px;
    }

    div[data-testid="stButton"] > button {
        border-radius: 11px;
        min-height: 44px;
        font-weight: 750;
    }
    div[data-testid="stFormSubmitButton"] > button {
        border-radius: 11px;
        min-height: 46px;
        font-weight: 800;
    }
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        border-radius: 10px;
    }

    @media (max-width: 768px) {
        .block-container { padding: .55rem .65rem 4rem; }
        .premium-header { padding: 17px; border-radius: 14px; }
        .premium-header h1 { font-size: 1.28rem; }
        .premium-header p { font-size: .8rem; }
        .card { padding: 13px; border-radius: 13px; }
        .kpi-card { min-height: 88px; padding: 12px; }
        .kpi-value { font-size: 1.25rem; }
        .product-card { padding: 14px; }
        .product-name { font-size: 1.05rem; }
        div[data-testid="stButton"] > button { min-height: 50px; }
        div[data-testid="stFormSubmitButton"] > button { min-height: 50px; }
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


def guardar_conteo(sesion, usuario, producto, stock_fisico, metodo="Escáner", observacion=""):
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

    fila = [
        sesion["IdSesion"], ahora(), usuario["Usuario"], usuario["NombreCompleto"],
        limpiar_codigo(producto.get("CodigoBarras", "")),
        limpiar_codigo(producto.get("CodigoProducto", "")),
        producto.get("Producto", ""), producto.get("Categoria", ""), producto.get("Sucursal", ""),
        stock_sistema, stock_fisico, diferencia, costo, valor_faltante, valor_sobrante,
        costo_diferencia, tipo, metodo, observacion.strip()
    ]
    obtener_hoja("conteos").append_row(fila, value_input_option="USER_ENTERED")
    cargar_conteos.clear()
    return tipo, diferencia, valor_faltante, valor_sobrante


def crear_sesion(nombre, sucursal, usuario, observacion=""):
    id_sesion = generar_id_sesion()
    fila = [
        id_sesion, ahora(), "", nombre.strip(), usuario["Usuario"],
        "ABIERTA", sucursal.strip(), observacion.strip()
    ]
    obtener_hoja("sesiones").append_row(fila, value_input_option="USER_ENTERED")
    cargar_sesiones.clear()
    return id_sesion


def cerrar_sesion(id_sesion):
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
        dc = conteos[conteos["IdSesion"].astype(str) == str(id_sesion)].copy()

    ses = sesiones[sesiones["IdSesion"].astype(str) == str(id_sesion)] if not sesiones.empty else pd.DataFrame()
    nombre = ses.iloc[0]["NombreSesion"] if not ses.empty else str(id_sesion)
    sucursal = ses.iloc[0]["Sucursal"] if not ses.empty else ""
    estado = ses.iloc[0]["Estado"] if not ses.empty else ""

    productos_contados = dc["CodigoBarras"].replace("", pd.NA).dropna().nunique() if not dc.empty else 0
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
        "ProductosSistema": len(inv),
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
    st.markdown(
        "<div class='footer-premium'>Desarrollado por Humberto Atoche, Tiendas Premium EIRL — RUC 20612107787</div>",
        unsafe_allow_html=True,
    )


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

    with st.container(key="login_card"):
        st.markdown(f"<div class='login-logo'>{logo_tag(72)}</div>", unsafe_allow_html=True)
        st.markdown("<div class='login-title'>Tiendas Premium</div>", unsafe_allow_html=True)
        st.markdown("<div class='login-subtitle'>Control de Inventario</div>", unsafe_allow_html=True)

        with st.form("login_form", border=False):
            usuario = st.text_input("Usuario", placeholder="Ingresa tu usuario")
            password = st.text_input("Contraseña", type="password", placeholder="Ingresa tu contraseña")
            entrar = st.form_submit_button("Ingresar", type="primary", use_container_width=True)

        if entrar:
            try:
                registro = autenticar(usuario, password)
                if registro:
                    st.session_state.autenticado = True
                    st.session_state.usuario = registro
                    st.session_state.pagina = "Inicio"
                    st.session_state.codigo_pendiente = ""
                    st.session_state.producto_pendiente = None
                    st.session_state.modo_inventario = "scanner"
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")
            except Exception as exc:
                mostrar_error_google(exc, "inicio de sesión")

        st.markdown(
            f"<div class='login-tag'>🔒 Acceso corporativo · {safe_text(COMPANY)}</div>",
            unsafe_allow_html=True,
        )

    footer()

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
        total = int((conteos["IdSesion"].astype(str) == str(sesion["IdSesion"])).sum()) if not conteos.empty else 0
        c1, c2 = st.columns(2)
        with c1: kpi("Productos contados", f"{total:,}", "en esta sesión")
        with c2:
            resumen = calcular_resumen(sesion["IdSesion"])
            kpi("Desfase neto", formato_soles(resumen["DesfaseNeto"]), "faltantes - sobrantes")

        st.markdown("<div class='section-title'>Acciones</div>", unsafe_allow_html=True)
        a1, a2 = st.columns(2)
        with a1:
            if st.button("📷 Continuar inventario", use_container_width=True):
                st.session_state.pagina = "Inventario"
                st.rerun()
        with a2:
            if st.button("🔒 Cerrar sesión", use_container_width=True):
                try:
                    resumen = calcular_resumen(sesion["IdSesion"])
                    if not cerrar_sesion(sesion["IdSesion"]):
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
        n = int((conteos["IdSesion"].astype(str) == str(sesion["IdSesion"])).sum()) if not conteos.empty else 0
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
    if producto_ya_contado(sesion["IdSesion"], codigo):
        st.warning("⚠️ Este producto ya fue contado en esta sesión.")
        if st.button("↩️ Volver al escáner", use_container_width=True):
            st.session_state.producto_pendiente = None
            st.session_state.codigo_pendiente = ""
            st.rerun()
        return

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

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"<div class='stock-box'><div class='stock-label'>Stock sistema</div><div class='stock-number'>{limpiar_numero(producto.get('StockSistema',0)):,.0f}</div></div>", unsafe_allow_html=True)
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
        impacto = abs(diferencia) * costo
        st.error(f"🔴 Faltante: {abs(diferencia):,.0f} unidades · {formato_soles(impacto)}")
        tipo = "FALTANTE"
    elif diferencia > 0:
        impacto = diferencia * costo
        st.success(f"🟢 Sobrante: {diferencia:,.0f} unidades · {formato_soles(impacto)}")
        tipo = "SOBRANTE"
    else:
        st.success("🟢 Stock exacto: no existe diferencia.")
        tipo = "OK"

    metodo = st.selectbox("Método de conteo", ["Escáner", "Búsqueda manual", "Código manual"])
    observacion = st.text_area("Observación", placeholder="Opcional")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Guardar conteo", type="primary", use_container_width=True):
            try:
                guardar_conteo(sesion, st.session_state.usuario, producto, fisico, metodo, observacion)
                st.success(f"Conteo guardado: {tipo}")
                sonido_confirmacion()
                st.session_state.producto_pendiente = None
                st.session_state.codigo_pendiente = ""
                st.session_state.ultimo_codigo_scan = ""
                st.rerun()
            except Exception as exc:
                mostrar_error_google(exc, "guardar conteo")
    with c2:
        if st.button("↩️ Cancelar", use_container_width=True):
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
    contados = int((conteos["IdSesion"].astype(str) == str(sesion["IdSesion"])).sum()) if not conteos.empty else 0
    total = len(cargar_inventario())
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
    dc = conteos[conteos["IdSesion"].astype(str) == str(seleccionado)].copy() if not conteos.empty else pd.DataFrame()

    k1, k2, k3, k4 = st.columns(4)
    with k1: kpi("Exactitud", f"{resumen['ExactitudInventario']:.1f}%", "productos OK")
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

    st.markdown("<div class='section-title'>📋 Detalle completo</div>", unsafe_allow_html=True)
    if not dc.empty:
        detalle = dc.copy()
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
                "Detalle": dc if not dc.empty else pd.DataFrame(columns=HEADERS_CONTEO),
                "Resumen": pd.DataFrame([resumen]),
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
# ADMINISTRACIÓN
# =========================================================

def pantalla_admin():
    header("Administración", "Usuarios, inventario y control de sesiones")
    tab1, tab2, tab3 = st.tabs(["👤 Usuarios", "📦 Inventario", "🧾 Sesiones"])

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

# =========================================================
# SIDEBAR
# =========================================================

def sidebar():
    usuario = st.session_state.usuario
    rol = str(usuario.get("Rol", "CONTADOR")).upper()
    rol_color = "#dbeafe;color:#1d4ed8" if rol == "ADMIN" else "#dcfce7;color:#166534"
    st.sidebar.markdown(
        f"<div style='display:flex;align-items:center;gap:10px;margin-bottom:8px;'>"
        f"{logo_tag(38)}<span style='font-size:1.2rem;font-weight:850;'>Tiendas Premium</span></div>",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        f"<div style='font-size:.85rem;color:#374151;margin-bottom:4px;'>{safe_text(usuario.get('NombreCompleto',''))}</div>"
        f"<span style='display:inline-block;background:{rol_color};padding:2px 10px;border-radius:999px;"
        f"font-size:.68rem;font-weight:800;letter-spacing:.03em;'>{safe_text(rol)}</span>",
        unsafe_allow_html=True,
    )
    st.sidebar.divider()

    opciones = ["Inicio", "Precios", "Sesión", "Inventario", "Resultados"]
    if rol == "ADMIN":
        opciones.append("Administración")

    actual = st.session_state.get("pagina", "Inicio")
    try:
        index = opciones.index(actual)
    except ValueError:
        index = 0
    seleccion = st.sidebar.radio("Menú", opciones, index=index)
    st.session_state.pagina = seleccion

    st.sidebar.divider()
    if st.sidebar.button("🔄 Actualizar datos", use_container_width=True):
        actualizar_datos()
        st.rerun()

    if st.sidebar.button("🚪 Cerrar sesión", use_container_width=True):
        for key in ["autenticado", "usuario", "pagina", "sesion_actual", "codigo_pendiente", "producto_pendiente", "modo_inventario", "ultimo_codigo_scan", "precio_producto", "precio_modo", "precio_ultimo_codigo_scan"]:
            st.session_state.pop(key, None)
        st.rerun()

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
    elif pagina == "Administración":
        if str(st.session_state.usuario.get("Rol", "")).upper() == "ADMIN":
            pantalla_admin()
        else:
            st.error("No tienes permisos para acceder a Administración.")
    footer()
except Exception as exc:
    mostrar_error_google(exc, "carga de la pantalla")
    footer()


# =========================================================
# DISEÑO CORPORATIVO APP 39 — CAPA VISUAL AGREGADA
# =========================================================
st.markdown("""
<style>
.premium-header{background:#FFFFFF!important;color:#111827!important;padding:20px 24px!important;border-radius:8px!important;border:1px solid #E5E7EB!important;border-left:4px solid #EC3237!important;margin-bottom:24px!important;box-shadow:none!important;animation:none!important}
.premium-header::after{display:none!important}
.premium-header h1{color:#111827!important;font-size:1.3rem!important;font-weight:600!important;letter-spacing:-.3px!important}
.premium-header p{color:#6B7280!important;opacity:1!important;font-size:.85rem!important;font-weight:400!important}
.section-title{color:#111827!important;font-size:1rem!important;font-weight:600!important;margin:12px 0 10px!important}
.card{background:#FFFFFF!important;border:1px solid #E5E7EB!important;border-radius:8px!important;padding:18px 20px!important;box-shadow:none!important;margin-bottom:15px!important;transform:none!important}
.card:hover{box-shadow:none!important;transform:none!important}
.kpi-card{background:#FFFFFF!important;border:1px solid #E5E7EB!important;border-top:none!important;border-radius:8px!important;padding:18px 20px!important;min-height:105px!important;box-shadow:none!important;transform:none!important}
.kpi-card:hover{transform:none!important;box-shadow:none!important}
.kpi-label{color:#6B7280!important;font-size:.7rem!important;font-weight:600!important;letter-spacing:.8px!important}
.kpi-value{color:#111827!important;font-size:1.4rem!important;font-weight:700!important}
.kpi-note{color:#6B7280!important;font-size:.75rem!important}
.product-card{background:#FFFFFF!important;border:1px solid #E5E7EB!important;border-top:3px solid #1071B8!important;border-radius:8px!important;padding:18px!important;box-shadow:none!important;animation:none!important}
.product-name{font-size:1.05rem!important;font-weight:700!important;color:#111827!important}
.product-meta{color:#4B5563!important;font-size:.82rem!important}
.stock-box{background:#F8FAFC!important;border:1px solid #E5E7EB!important;border-radius:8px!important;padding:13px!important}
.stock-label{color:#6B7280!important;font-size:.7rem!important;font-weight:600!important}
.stock-number{color:#111827!important;font-size:1.35rem!important;font-weight:700!important}
.price-hero{background:#FFFFFF!important;color:#111827!important;border:1px solid #E5E7EB!important;border-radius:8px!important;padding:24px 22px!important;box-shadow:none!important;margin:14px 0!important}
.price-hero .price-label{color:#6B7280!important;opacity:1!important}
.price-hero .price-value{color:#111827!important;font-size:2.3rem!important}
.price-hero .price-sub{color:#6B7280!important;opacity:1!important}
.price-info-item{background:#FFFFFF!important;border:1px solid #E5E7EB!important;border-radius:8px!important;box-shadow:none!important}
.mobile-note{background:#FFFFFF!important;border:1px solid #E5E7EB!important;color:#6B7280!important;border-radius:8px!important}
.footer-premium{border-top:1px solid #E5E7EB!important;color:#6B7280!important;font-size:.8rem!important;padding:24px 10px 12px!important;margin-top:40px!important}
</style>
""", unsafe_allow_html=True)


# =========================================================
# SIDEBAR APP 39 — CAPA VISUAL AGREGADA
# =========================================================
st.markdown("""
<style>
[data-testid="stSidebar"]{background-color:#111827!important;border-right:1px solid #1F2937!important}
[data-testid="stSidebar"] *{color:#E5E7EB!important}
[data-testid="stSidebar"] .stRadio label{color:#E5E7EB!important}
[data-testid="stSidebar"] .stButton>button{background-color:#111827!important;color:#FFFFFF!important;border:1px solid #374151!important;border-radius:6px!important}
[data-testid="stSidebar"] .stButton>button:hover{background-color:#1F2937!important}
</style>
""", unsafe_allow_html=True)

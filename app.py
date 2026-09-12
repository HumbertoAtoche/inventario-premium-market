import streamlit as st
import pandas as pd
import gspread
import hashlib
import io
import re
import html
from datetime import datetime
from google.oauth2.service_account import Credentials

# =========================================================
# TIENDAS PREMIUM EIRL — INVENTARIO
# app.py — versión optimizada para Google Sheets + móvil
# =========================================================

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
    .block-container { padding-top: 1rem; padding-bottom: 4rem; max-width: 1450px; }

    .premium-header {
        background: linear-gradient(135deg, #ec3237 0%, #c91f25 100%);
        color: white;
        padding: 22px 26px;
        border-radius: 18px;
        margin-bottom: 18px;
        box-shadow: 0 8px 25px rgba(236,50,55,.14);
    }
    .premium-header h1 { margin: 0; font-size: 1.65rem; font-weight: 800; }
    .premium-header p { margin: 5px 0 0; opacity: .92; font-size: .92rem; }

    .section-title { color: var(--text); font-size: 1.1rem; font-weight: 800; margin: 12px 0 10px; }

    .card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 18px;
        box-shadow: 0 4px 15px rgba(17,24,39,.045);
        margin-bottom: 14px;
    }

    .kpi-card {
        background: white;
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 16px 17px;
        min-height: 105px;
        box-shadow: 0 4px 15px rgba(17,24,39,.045);
    }
    .kpi-label { color: var(--muted); font-size: .76rem; font-weight: 700; text-transform: uppercase; letter-spacing: .02em; }
    .kpi-value { color: var(--text); font-size: 1.55rem; font-weight: 850; margin-top: 5px; }
    .kpi-note { color: var(--muted); font-size: .75rem; margin-top: 2px; }

    .product-card {
        background: white;
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 18px;
        box-shadow: 0 7px 22px rgba(17,24,39,.06);
        margin: 10px 0 15px;
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
    .badge-abierta { background:#dbeafe; color:#1d4ed8; }
    .badge-cerrada { background:#f3f4f6; color:#4b5563; }

    .login-wrap { max-width: 460px; margin: 7vh auto 0; }
    .login-logo { text-align:center; font-size: 3.3rem; margin-bottom: 5px; }
    .login-title { text-align:center; font-size:1.7rem; font-weight:900; color:#111827; }
    .login-subtitle { text-align:center; color:#6b7280; margin-bottom:20px; }

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


def safe_text(valor):
    return html.escape(str(valor))


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

    st.markdown("<div class='login-wrap'>", unsafe_allow_html=True)
    st.markdown("<div class='login-logo'>📦</div>", unsafe_allow_html=True)
    st.markdown("<div class='login-title'>Tiendas Premium</div>", unsafe_allow_html=True)
    st.markdown("<div class='login-subtitle'>Control de Inventario</div>", unsafe_allow_html=True)

    with st.form("login_form"):
        usuario = st.text_input("Usuario", placeholder="Ingresa tu usuario")
        password = st.text_input("Contraseña", type="password", placeholder="Ingresa tu contraseña")
        entrar = st.form_submit_button("Ingresar", use_container_width=True)

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

    st.markdown("</div>", unsafe_allow_html=True)
    footer()

# =========================================================
# INICIO
# =========================================================

def pantalla_inicio():
    header("Dashboard de Inventario", f"Bienvenido, {st.session_state.usuario.get('NombreCompleto', '')}")

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
    a1, a2, a3 = st.columns(3)
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

def pantalla_scanner():
    header("Escanear producto", "Usa la cámara del celular o ingresa el código manualmente")
    st.markdown("<div class='mobile-note'>📱 En celular, permite el acceso a la cámara. El escáner funciona mejor usando HTTPS.</div>", unsafe_allow_html=True)

    try:
        from streamlit_qrcode_scanner import qrcode_scanner
        codigo = qrcode_scanner(key="premium_barcode_scanner")
        if codigo:
            codigo = limpiar_codigo(codigo)
            if codigo and codigo != st.session_state.get("ultimo_codigo_scan", ""):
                st.session_state.ultimo_codigo_scan = codigo
                st.session_state.codigo_pendiente = codigo
                st.rerun()
    except ImportError:
        st.warning("El escáner no está instalado. Agrega `streamlit-qrcode-scanner` a requirements.txt.")
    except Exception as exc:
        st.warning("No se pudo iniciar la cámara. Puedes utilizar la búsqueda manual.")
        with st.expander("Detalle técnico"):
            st.code(str(exc))

    st.divider()
    codigo_manual = st.text_input("Código de barras / código de producto", key="codigo_manual", placeholder="Escanea o escribe el código")
    if st.button("🔎 Buscar código", use_container_width=True):
        if codigo_manual.strip():
            st.session_state.codigo_pendiente = limpiar_codigo(codigo_manual)
            st.rerun()

    if st.button("🔎 No puedo escanear — buscar por nombre", use_container_width=True):
        st.session_state.modo_inventario = "busqueda"
        st.session_state.codigo_pendiente = ""
        st.rerun()

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
    df = buscar_productos(texto)

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
        pantalla_scanner()

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
    st.download_button(
        "📥 Descargar resumen CSV",
        data=resumen_csv,
        file_name=f"resumen_{seleccionado}.csv",
        mime="text/csv",
        use_container_width=True,
    )

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
    st.sidebar.markdown("# 📦 Tiendas Premium")
    st.sidebar.caption(f"{usuario.get('NombreCompleto','')} · {rol}")
    st.sidebar.divider()

    opciones = ["Inicio", "Sesión", "Inventario", "Resultados"]
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
        for key in ["autenticado", "usuario", "pagina", "sesion_actual", "codigo_pendiente", "producto_pendiente", "modo_inventario", "ultimo_codigo_scan"]:
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

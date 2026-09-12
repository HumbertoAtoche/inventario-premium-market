from pathlib import Path

app_code = r'''import streamlit as st
import pandas as pd
import gspread
import hashlib
import io
import re
from datetime import datetime
from google.oauth2.service_account import Credentials

# ============================================================
# TIENDAS PREMIUM | SISTEMA DE INVENTARIO
# Versión optimizada para Streamlit + Google Sheets
#
# Objetivos:
# - Reducir lecturas repetitivas de Google Sheets.
# - Evitar errores 429 por exceso de lecturas.
# - Mantener una UX rápida y mobile-first.
# - Inventario físico vs. stock sistema.
# - Valorización de faltantes y sobrantes.
# - Usuarios, sesiones y trazabilidad.
# ============================================================

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

SHEET_HEADERS = {
    "Inventario": [
        "CodigoBarras", "CodigoProducto", "Producto", "Descripcion",
        "Categoria", "Marca", "Unidad", "Sucursal", "StockSistema",
        "CostoUnitario", "PrecioVenta", "Estado"
    ],
    "ConteoInventario": [
        "IdSesion", "FechaHora", "Usuario", "NombreUsuario",
        "CodigoBarras", "CodigoProducto", "Producto", "Categoria",
        "Sucursal", "StockSistema", "StockFisico", "Diferencia",
        "CostoUnitario", "ValorFaltante", "ValorSobrante",
        "CostoDiferencia", "TipoDiferencia", "MetodoConteo",
        "Observacion"
    ],
    "SesionesInventario": [
        "IdSesion", "FechaInicio", "FechaFin", "NombreSesion",
        "UsuarioCreador", "Estado", "Sucursal", "Observacion"
    ],
    "ResumenInventario": [
        "IdSesion", "Fecha", "NombreSesion", "Sucursal",
        "ProductosSistema", "ProductosContados", "ProductosOK",
        "ProductosFaltantes", "ProductosSobrantes", "UnidadesSistema",
        "UnidadesFisicas", "UnidadesFaltantes", "UnidadesSobrantes",
        "ValorFaltantes", "ValorSobrantes", "DesfaseNeto",
        "ExactitudInventario", "Estado"
    ],
    "Usuarios": [
        "Usuario", "NombreCompleto", "Rol", "Password", "Estado"
    ],
}

# ============================================================
# ESTILOS
# ============================================================

st.markdown(
    """
<style>
:root {
    --red: #ec3237;
    --red-dark: #c91f25;
    --green: #00a959;
    --blue: #1071b8;
    --orange: #d88700;
    --bg: #f6f7f9;
    --text: #202124;
    --muted: #6b7280;
    --border: #e7e9ee;
}

.stApp {
    background: var(--bg);
}

#MainMenu, header, footer {
    visibility: hidden;
}

.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 1500px;
}

.premium-header {
    background: linear-gradient(135deg, #ec3237 0%, #c91f25 100%);
    padding: 22px 25px;
    border-radius: 20px;
    color: white;
    margin-bottom: 20px;
    box-shadow: 0 8px 25px rgba(236,50,55,.18);
}

.premium-header h1 {
    margin: 0;
    font-size: 30px;
    font-weight: 900;
    letter-spacing: -.5px;
}

.premium-header p {
    margin: 5px 0 0 0;
    opacity: .92;
}

.card, .kpi, .product-card {
    background: white;
    border-radius: 17px;
    border: 1px solid var(--border);
    box-shadow: 0 4px 16px rgba(0,0,0,.045);
}

.card {
    padding: 20px;
    margin-bottom: 16px;
}

.kpi {
    padding: 17px;
    min-height: 112px;
}

.kpi-title {
    color: var(--muted);
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .25px;
}

.kpi-value {
    color: var(--text);
    font-size: 27px;
    font-weight: 900;
    margin-top: 8px;
}

.kpi-danger { color: var(--red); }
.kpi-success { color: var(--green); }
.kpi-warning { color: var(--orange); }
.kpi-blue { color: var(--blue); }

.product-card {
    padding: 22px;
    margin: 10px 0 16px;
}

.product-name {
    font-size: 23px;
    font-weight: 900;
    color: var(--text);
    line-height: 1.15;
}

.product-code {
    color: var(--muted);
    font-size: 12px;
    margin-bottom: 7px;
}

.stock-system {
    font-size: 35px;
    font-weight: 950;
    color: var(--blue);
    line-height: 1.1;
}

.badge {
    display: inline-block;
    padding: 5px 11px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 800;
}

.badge-ok {
    background: #e8f8ef;
    color: #008544;
}

.badge-danger {
    background: #fde8e9;
    color: #c52228;
}

.badge-warning {
    background: #fff4dc;
    color: #9a6700;
}

.badge-blue {
    background: #e8f2fb;
    color: #0d5d96;
}

.hero-number {
    font-size: 42px;
    font-weight: 950;
    line-height: 1;
    margin: 7px 0;
}

.muted {
    color: var(--muted);
}

.section-title {
    font-size: 19px;
    font-weight: 850;
    margin: 22px 0 10px;
}

.premium-footer {
    text-align: center;
    color: #888;
    font-size: 12px;
    margin-top: 42px;
    padding: 22px 10px;
    border-top: 1px solid #e5e7eb;
}

div.stButton > button,
div.stDownloadButton > button {
    border-radius: 12px;
    min-height: 45px;
    font-weight: 750;
}

.big-button button {
    min-height: 60px !important;
    font-size: 17px !important;
}

[data-testid="stMetric"] {
    background: white;
    border: 1px solid var(--border);
    padding: 14px;
    border-radius: 15px;
}

@media (max-width: 768px) {
    .block-container {
        padding-left: .75rem;
        padding-right: .75rem;
        padding-top: .7rem;
    }

    .premium-header {
        padding: 18px;
        border-radius: 16px;
    }

    .premium-header h1 {
        font-size: 23px;
    }

    .premium-header p {
        font-size: 12px;
    }

    .kpi {
        min-height: 90px;
        padding: 13px;
    }

    .kpi-value {
        font-size: 21px;
    }

    .product-card {
        padding: 17px;
    }

    .product-name {
        font-size: 19px;
    }

    .stock-system {
        font-size: 30px;
    }

    .hero-number {
        font-size: 34px;
    }
}
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# ESTADO
# ============================================================

DEFAULT_STATE = {
    "autenticado": False,
    "pagina": "Inicio",
    "sesion_actual": None,
    "codigo_pendiente": None,
    "producto_pendiente": None,
    "metodo_pendiente": "BUSQUEDA",
    "modo_inventario": "scanner",
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ============================================================
# UTILIDADES
# ============================================================

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


def limpiar_numero(valor, default=0.0):
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


def generar_id_sesion():
    return datetime.now().strftime("INV-%Y%m%d-%H%M%S-%f")[:-3]


def hash_password(password):
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()


def escapar_html(valor):
    texto = "" if pd.isna(valor) else str(valor)
    return (
        texto.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


def mostrar_error_google(error):
    texto = str(error)
    if "429" in texto or "Quota exceeded" in texto:
        st.error(
            "⚠️ Google Sheets alcanzó temporalmente el límite de lecturas. "
            "La aplicación está protegida para no seguir haciendo llamadas innecesarias."
        )
        st.info(
            "Espera unos segundos y vuelve a intentar. "
            "No necesitas cerrar el navegador."
        )
        return
    st.error("⚠️ No se pudo acceder a Google Sheets.")
    st.caption("Detalle técnico:")
    st.code(texto)


def limpiar_cache_datos(*funciones):
    for funcion in funciones:
        try:
            funcion.clear()
        except Exception:
            pass


# ============================================================
# GOOGLE SHEETS — ARQUITECTURA ANTI-429
# ============================================================

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
    Lee los metadatos UNA SOLA VEZ por recurso/cache.
    No crea hojas automáticamente durante cada rerun.
    Las cinco hojas ya forman parte de la estructura del sistema.
    """
    spreadsheet = conectar_google()

    metadata = spreadsheet.fetch_sheet_metadata()

    disponibles = {
        hoja["properties"]["title"]
        for hoja in metadata.get("sheets", [])
    }

    faltantes = [
        nombre for nombre in SHEET_HEADERS
        if nombre not in disponibles
    ]

    if faltantes:
        raise RuntimeError(
            "Faltan estas hojas en Google Sheets: "
            + ", ".join(faltantes)
            + ". Créelas antes de usar el sistema."
        )

    return {
        nombre: spreadsheet.worksheet(nombre)
        for nombre in SHEET_HEADERS
    }


def obtener_hoja(nombre):
    return obtener_hojas()[nombre]


# ============================================================
# CARGA DE DATA
# ============================================================

def normalizar_columnas(df, headers):
    if df.empty:
        return pd.DataFrame(columns=headers)

    for columna in headers:
        if columna not in df.columns:
            df[columna] = ""

    return df[headers]


@st.cache_data(ttl=60, show_spinner=False)
def cargar_inventario():
    worksheet = obtener_hoja("Inventario")
    data = worksheet.get_all_records()
    df = normalizar_columnas(pd.DataFrame(data), SHEET_HEADERS["Inventario"])

    if df.empty:
        return df

    df["CodigoBarras"] = df["CodigoBarras"].apply(limpiar_codigo)
    df["CodigoProducto"] = df["CodigoProducto"].fillna("").astype(str)
    df["Producto"] = df["Producto"].fillna("").astype(str)
    df["Descripcion"] = df["Descripcion"].fillna("").astype(str)
    df["Categoria"] = df["Categoria"].fillna("").astype(str)
    df["Marca"] = df["Marca"].fillna("").astype(str)
    df["Unidad"] = df["Unidad"].fillna("").astype(str)
    df["Sucursal"] = df["Sucursal"].fillna("").astype(str)
    df["Estado"] = df["Estado"].fillna("").astype(str)

    df["StockSistema"] = df["StockSistema"].apply(limpiar_numero)
    df["CostoUnitario"] = df["CostoUnitario"].apply(limpiar_numero)
    df["PrecioVenta"] = df["PrecioVenta"].apply(limpiar_numero)

    return df


@st.cache_data(ttl=300, show_spinner=False)
def cargar_usuarios():
    worksheet = obtener_hoja("Usuarios")
    data = worksheet.get_all_records()
    df = normalizar_columnas(pd.DataFrame(data), SHEET_HEADERS["Usuarios"])

    if df.empty:
        return df

    for columna in SHEET_HEADERS["Usuarios"]:
        df[columna] = df[columna].fillna("").astype(str)

    return df


@st.cache_data(ttl=30, show_spinner=False)
def cargar_conteos():
    worksheet = obtener_hoja("ConteoInventario")
    data = worksheet.get_all_records()
    df = normalizar_columnas(pd.DataFrame(data), SHEET_HEADERS["ConteoInventario"])

    if df.empty:
        return df

    numeric_cols = [
        "StockSistema", "StockFisico", "Diferencia",
        "CostoUnitario", "ValorFaltante", "ValorSobrante",
        "CostoDiferencia",
    ]

    for columna in numeric_cols:
        df[columna] = df[columna].apply(limpiar_numero)

    return df


@st.cache_data(ttl=30, show_spinner=False)
def cargar_sesiones():
    worksheet = obtener_hoja("SesionesInventario")
    data = worksheet.get_all_records()
    df = normalizar_columnas(pd.DataFrame(data), SHEET_HEADERS["SesionesInventario"])

    if df.empty:
        return df

    for columna in SHEET_HEADERS["SesionesInventario"]:
        df[columna] = df[columna].fillna("").astype(str)

    return df


@st.cache_data(ttl=60, show_spinner=False)
def cargar_resumenes():
    worksheet = obtener_hoja("ResumenInventario")
    data = worksheet.get_all_records()
    df = normalizar_columnas(pd.DataFrame(data), SHEET_HEADERS["ResumenInventario"])

    if df.empty:
        return df

    numeric_cols = [
        "ProductosSistema", "ProductosContados", "ProductosOK",
        "ProductosFaltantes", "ProductosSobrantes", "UnidadesSistema",
        "UnidadesFisicas", "UnidadesFaltantes", "UnidadesSobrantes",
        "ValorFaltantes", "ValorSobrantes", "DesfaseNeto",
        "ExactitudInventario",
    ]

    for columna in numeric_cols:
        df[columna] = df[columna].apply(limpiar_numero)

    return df


def actualizar_datos_despues_de_escritura(tipo):
    if tipo == "conteo":
        limpiar_cache_datos(cargar_conteos)
    elif tipo == "sesion":
        limpiar_cache_datos(cargar_sesiones)
    elif tipo == "usuario":
        limpiar_cache_datos(cargar_usuarios)
    elif tipo == "resumen":
        limpiar_cache_datos(cargar_resumenes)


# ============================================================
# AUTENTICACIÓN
# ============================================================

def autenticar(usuario, password):
    usuarios = cargar_usuarios()

    if usuarios.empty:
        return None

    encontrados = usuarios[
        (usuarios["Usuario"].str.strip().str.lower() == usuario.strip().lower())
        & (usuarios["Estado"].str.strip().str.upper() == "ACTIVO")
    ]

    if encontrados.empty:
        return None

    fila = encontrados.iloc[0]
    password_guardada = str(fila["Password"])

    if password == password_guardada:
        return fila.to_dict()

    if hash_password(password) == password_guardada:
        return fila.to_dict()

    return None


# ============================================================
# BÚSQUEDA DE PRODUCTOS
# ============================================================

def buscar_por_codigo(codigo):
    df = cargar_inventario()
    codigo = limpiar_codigo(codigo)

    if df.empty or not codigo:
        return pd.DataFrame()

    return df[
        df["CodigoBarras"].astype(str).str.strip() == codigo
    ]


def buscar_productos(texto):
    df = cargar_inventario()

    if df.empty:
        return pd.DataFrame()

    texto = str(texto).strip().lower()

    if not texto:
        return pd.DataFrame()

    columnas_busqueda = [
        "CodigoBarras", "CodigoProducto", "Producto",
        "Descripcion", "Categoria", "Marca"
    ]

    mascara = pd.Series(False, index=df.index)

    for columna in columnas_busqueda:
        mascara |= (
            df[columna]
            .fillna("")
            .astype(str)
            .str.lower()
            .str.contains(re.escape(texto), na=False)
        )

    return df[mascara].head(50)


# ============================================================
# SESIONES
# ============================================================

def obtener_sesion_abierta(usuario=None):
    df = cargar_sesiones()

    if df.empty:
        return None

    filtro = df["Estado"].astype(str).str.upper() == "ABIERTO"

    if usuario:
        filtro &= (
            df["UsuarioCreador"]
            .astype(str)
            .str.lower()
            == str(usuario).lower()
        )

    resultados = df[filtro]

    if resultados.empty:
        return None

    return resultados.iloc[-1].to_dict()


def crear_sesion(nombre, usuario, sucursal, observacion=""):
    id_sesion = generar_id_sesion()

    fila = [
        id_sesion,
        ahora(),
        "",
        nombre.strip(),
        usuario,
        "ABIERTO",
        sucursal.strip(),
        observacion.strip(),
    ]

    obtener_hoja("SesionesInventario").append_row(
        fila,
        value_input_option="USER_ENTERED",
    )

    actualizar_datos_despues_de_escritura("sesion")

    return id_sesion


def cerrar_sesion(id_sesion):
    worksheet = obtener_hoja("SesionesInventario")
    data = worksheet.get_all_values()

    if len(data) <= 1:
        return False

    headers = data[0]

    try:
        col_id = headers.index("IdSesion") + 1
        col_fin = headers.index("FechaFin") + 1
        col_estado = headers.index("Estado") + 1
    except ValueError:
        return False

    for numero_fila, fila in enumerate(data[1:], start=2):
        if len(fila) >= col_id and fila[col_id - 1] == id_sesion:
            worksheet.update_cell(numero_fila, col_fin, ahora())
            worksheet.update_cell(numero_fila, col_estado, "CERRADO")
            actualizar_datos_despues_de_escritura("sesion")
            return True

    return False


# ============================================================
# CONTEO
# ============================================================

def producto_ya_contado(id_sesion, codigo):
    df = cargar_conteos()

    if df.empty:
        return pd.DataFrame()

    codigo = limpiar_codigo(codigo)

    return df[
        (df["IdSesion"].astype(str) == str(id_sesion))
        & (df["CodigoBarras"].apply(limpiar_codigo) == codigo)
    ]


def guardar_conteo(
    sesion,
    usuario,
    nombre_usuario,
    producto,
    stock_fisico,
    metodo="ESCANER",
    observacion="",
):
    stock_sistema = limpiar_numero(producto["StockSistema"])
    costo = limpiar_numero(producto["CostoUnitario"])
    stock_fisico = max(0, int(stock_fisico))

    diferencia = stock_fisico - stock_sistema

    valor_faltante = abs(diferencia) * costo if diferencia < 0 else 0
    valor_sobrante = diferencia * costo if diferencia > 0 else 0
    costo_diferencia = valor_sobrante - valor_faltante

    if diferencia == 0:
        tipo = "OK"
    elif diferencia < 0:
        tipo = "FALTANTE"
    else:
        tipo = "SOBRANTE"

    fila = [
        sesion["IdSesion"],
        ahora(),
        usuario,
        nombre_usuario,
        limpiar_codigo(producto["CodigoBarras"]),
        str(producto["CodigoProducto"]),
        str(producto["Producto"]),
        str(producto["Categoria"]),
        str(producto["Sucursal"]),
        stock_sistema,
        stock_fisico,
        diferencia,
        costo,
        valor_faltante,
        valor_sobrante,
        costo_diferencia,
        tipo,
        metodo,
        observacion.strip(),
    ]

    obtener_hoja("ConteoInventario").append_row(
        fila,
        value_input_option="USER_ENTERED",
    )

    actualizar_datos_despues_de_escritura("conteo")


# ============================================================
# RESUMEN
# ============================================================

def calcular_resumen(id_sesion):
    inventario = cargar_inventario()
    conteos = cargar_conteos()

    if inventario.empty:
        return None

    conteos_sesion = conteos[
        conteos["IdSesion"].astype(str) == str(id_sesion)
    ].copy()

    productos_sistema = len(inventario)

    productos_contados = (
        conteos_sesion["CodigoBarras"].nunique()
        if not conteos_sesion.empty else 0
    )

    productos_ok = (
        len(conteos_sesion[conteos_sesion["TipoDiferencia"] == "OK"])
        if not conteos_sesion.empty else 0
    )

    productos_faltantes = (
        len(conteos_sesion[conteos_sesion["TipoDiferencia"] == "FALTANTE"])
        if not conteos_sesion.empty else 0
    )

    productos_sobrantes = (
        len(conteos_sesion[conteos_sesion["TipoDiferencia"] == "SOBRANTE"])
        if not conteos_sesion.empty else 0
    )

    unidades_sistema = (
        conteos_sesion["StockSistema"].sum()
        if not conteos_sesion.empty else 0
    )

    unidades_fisicas = (
        conteos_sesion["StockFisico"].sum()
        if not conteos_sesion.empty else 0
    )

    unidades_faltantes = (
        abs(conteos_sesion.loc[
            conteos_sesion["Diferencia"] < 0, "Diferencia"
        ].sum())
        if not conteos_sesion.empty else 0
    )

    unidades_sobrantes = (
        conteos_sesion.loc[
            conteos_sesion["Diferencia"] > 0, "Diferencia"
        ].sum()
        if not conteos_sesion.empty else 0
    )

    valor_faltantes = (
        conteos_sesion["ValorFaltante"].sum()
        if not conteos_sesion.empty else 0
    )

    valor_sobrantes = (
        conteos_sesion["ValorSobrante"].sum()
        if not conteos_sesion.empty else 0
    )

    desfase_neto = valor_faltantes - valor_sobrantes

    exactitud = (
        productos_ok / productos_contados * 100
        if productos_contados > 0 else 0
    )

    cobertura = (
        productos_contados / productos_sistema * 100
        if productos_sistema > 0 else 0
    )

    return {
        "ProductosSistema": productos_sistema,
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
        "Cobertura": cobertura,
    }


def guardar_resumen(id_sesion):
    sesiones = cargar_sesiones()

    if sesiones.empty:
        return False

    fila_sesion = sesiones[
        sesiones["IdSesion"].astype(str) == str(id_sesion)
    ]

    if fila_sesion.empty:
        return False

    sesion = fila_sesion.iloc[0]
    resumen = calcular_resumen(id_sesion)

    if resumen is None:
        return False

    fila = [
        id_sesion,
        fecha_actual(),
        sesion["NombreSesion"],
        sesion["Sucursal"],
        resumen["ProductosSistema"],
        resumen["ProductosContados"],
        resumen["ProductosOK"],
        resumen["ProductosFaltantes"],
        resumen["ProductosSobrantes"],
        resumen["UnidadesSistema"],
        resumen["UnidadesFisicas"],
        resumen["UnidadesFaltantes"],
        resumen["UnidadesSobrantes"],
        resumen["ValorFaltantes"],
        resumen["ValorSobrantes"],
        resumen["DesfaseNeto"],
        resumen["ExactitudInventario"],
        "CERRADO",
    ]

    obtener_hoja("ResumenInventario").append_row(
        fila,
        value_input_option="USER_ENTERED",
    )

    actualizar_datos_despues_de_escritura("resumen")
    return True


# ============================================================
# COMPONENTES VISUALES
# ============================================================

def header():
    st.markdown(
        f"""
        <div class="premium-header">
            <h1>📦 {APP_NAME}</h1>
            <p>Sistema de Inventario y Control de Stock</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def footer():
    st.markdown(
        f"""
        <div class="premium-footer">
            Desarrollado por <b>{AUTHOR}</b><br>
            {COMPANY} — RUC {RUC}
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi(titulo, valor, clase=""):
    st.markdown(
        f"""
        <div class="kpi">
            <div class="kpi-title">{titulo}</div>
            <div class="kpi-value {clase}">{valor}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def estado_badge(tipo):
    tipo = str(tipo).upper()
    if tipo == "OK":
        return '<span class="badge badge-ok">● OK</span>'
    if tipo == "FALTANTE":
        return '<span class="badge badge-danger">● FALTANTE</span>'
    if tipo == "SOBRANTE":
        return '<span class="badge badge-warning">● SOBRANTE</span>'
    return f'<span class="badge badge-blue">{escapar_html(tipo)}</span>'


# ============================================================
# LOGIN
# ============================================================

def pantalla_login():
    st.markdown(
        """
        <div style="
            max-width:500px;
            margin:70px auto 20px auto;
            text-align:center;
        ">
            <div style="font-size:58px;">📦</div>
            <h1 style="font-weight:950;margin:5px 0;">TIENDAS PREMIUM</h1>
            <p style="color:#777;">Sistema de Inventario</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("login_form", clear_on_submit=False):
        usuario = st.text_input(
            "Usuario",
            placeholder="Ingresa tu usuario",
            autocomplete="username",
        )

        password = st.text_input(
            "Contraseña",
            type="password",
            placeholder="Ingresa tu contraseña",
            autocomplete="current-password",
        )

        ingresar = st.form_submit_button(
            "🔐 INGRESAR",
            use_container_width=True,
            type="primary",
        )

        if ingresar:
            if not usuario or not password:
                st.warning("Ingresa usuario y contraseña.")
                return

            try:
                resultado = autenticar(usuario, password)
            except Exception as e:
                mostrar_error_google(e)
                return

            if resultado:
                st.session_state.autenticado = True
                st.session_state.usuario = str(resultado["Usuario"])
                st.session_state.nombre_usuario = str(resultado["NombreCompleto"])
                st.session_state.rol = str(resultado["Rol"]).upper()
                st.session_state.sesion_actual = None
                st.session_state.producto_pendiente = None
                st.session_state.codigo_pendiente = None
                st.session_state.modo_inventario = "scanner"
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")

    footer()


# ============================================================
# INICIO / DASHBOARD
# ============================================================

def pantalla_inicio():
    header()

    nombre = st.session_state.nombre_usuario

    st.markdown(
        f"""
        <div class="card">
            <div style="font-size:12px;color:#777;font-weight:700;">PANEL DE CONTROL</div>
            <h2 style="margin:5px 0;">Hola, {escapar_html(nombre)} 👋</h2>
            <p style="margin:0;color:#777;">
                Gestiona inventarios, conteos y diferencias desde un solo lugar.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        inventario = cargar_inventario()
        conteos = cargar_conteos()
        sesiones = cargar_sesiones()
    except Exception as e:
        mostrar_error_google(e)
        return

    if inventario.empty:
        st.warning("La hoja Inventario no contiene productos.")
        footer()
        return

    stock_total = inventario["StockSistema"].sum()
    valor_inventario = (
        inventario["StockSistema"] * inventario["CostoUnitario"]
    ).sum()

    activos = inventario[
        inventario["Estado"].astype(str).str.upper() == "ACTIVO"
    ]

    abiertos = sesiones[
        sesiones["Estado"].astype(str).str.upper() == "ABIERTO"
    ] if not sesiones.empty else pd.DataFrame()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        kpi("Productos registrados", f"{len(inventario):,}")

    with col2:
        kpi("Stock total", f"{stock_total:,.0f}", "kpi-blue")

    with col3:
        kpi("Valor inventario", formato_soles(valor_inventario))

    with col4:
        kpi("Productos activos", f"{len(activos):,}", "kpi-success")

    st.markdown("### 🚀 Acciones rápidas")

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("📷 Escanear producto", use_container_width=True, type="primary"):
            st.session_state.pagina = "Inventario"
            st.session_state.modo_inventario = "scanner"
            st.rerun()

    with c2:
        if st.button("🔎 Buscar producto", use_container_width=True):
            st.session_state.pagina = "Inventario"
            st.session_state.modo_inventario = "buscar"
            st.rerun()

    with c3:
        if st.button("📊 Ver resultados", use_container_width=True):
            st.session_state.pagina = "Resultados"
            st.rerun()

    st.markdown("### 📋 Estado operativo")

    if not abiertos.empty:
        st.success(
            f"🟢 Hay {len(abiertos)} sesión(es) de inventario abierta(s)."
        )
    else:
        st.info("No hay sesiones de inventario abiertas.")

    if not conteos.empty:
        st.markdown("### 🕘 Últimos conteos")
        ultimos = conteos.tail(10).iloc[::-1].copy()

        columnas = [
            "FechaHora", "Producto", "StockSistema",
            "StockFisico", "Diferencia", "TipoDiferencia",
            "Usuario"
        ]

        st.dataframe(
            ultimos[columnas],
            use_container_width=True,
            hide_index=True,
        )

    footer()


# ============================================================
# SESIÓN
# ============================================================

def pantalla_sesion():
    header()
    st.markdown("### 📋 Sesión de inventario")

    try:
        sesion = obtener_sesion_abierta()
    except Exception as e:
        mostrar_error_google(e)
        return

    if sesion:
        resumen = calcular_resumen(sesion["IdSesion"])

        st.markdown(
            f"""
            <div class="card">
                <span class="badge badge-ok">● ABIERTA</span>
                <h2 style="margin:10px 0 4px;">{escapar_html(sesion['NombreSesion'])}</h2>
                <div class="muted">
                    ID: {escapar_html(sesion['IdSesion'])}<br>
                    Sucursal: {escapar_html(sesion['Sucursal'])}<br>
                    Creada por: {escapar_html(sesion['UsuarioCreador'])}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if resumen:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                kpi("Contados", f"{resumen['ProductosContados']:,}", "kpi-blue")
            with c2:
                kpi("Cobertura", f"{resumen['Cobertura']:.1f}%", "kpi-blue")
            with c3:
                kpi("OK", f"{resumen['ProductosOK']:,}", "kpi-success")
            with c4:
                kpi("Desfase", formato_soles(resumen["DesfaseNeto"]), "kpi-danger")

        if st.button("➡️ Continuar inventario", use_container_width=True, type="primary"):
            st.session_state.sesion_actual = sesion
            st.session_state.pagina = "Inventario"
            st.rerun()

        if st.button("🔒 Cerrar inventario", use_container_width=True):
            if guardar_resumen(sesion["IdSesion"]):
                if cerrar_sesion(sesion["IdSesion"]):
                    st.session_state.sesion_actual = None
                    st.success("✅ Inventario cerrado y resumen guardado.")
                    st.rerun()
            else:
                st.error("No fue posible guardar el resumen.")

        return

    st.info("No existe una sesión de inventario abierta.")

    with st.form("crear_sesion", clear_on_submit=True):
        nombre = st.text_input(
            "Nombre del inventario",
            value=f"Inventario {fecha_actual()}",
        )

        sucursal = st.text_input(
            "Sucursal",
            value="PRINCIPAL",
        )

        observacion = st.text_area(
            "Observación",
            placeholder="Ej. inventario mensual, inventario sorpresa..."
        )

        crear = st.form_submit_button(
            "🚀 CREAR INVENTARIO",
            use_container_width=True,
            type="primary",
        )

        if crear:
            if not nombre.strip():
                st.error("Ingresa un nombre para el inventario.")
                return

            try:
                id_sesion = crear_sesion(
                    nombre,
                    st.session_state.usuario,
                    sucursal,
                    observacion,
                )
                st.session_state.pagina = "Inventario"
                st.session_state.sesion_actual = None
                st.success(f"Inventario creado: {id_sesion}")
                st.rerun()
            except Exception as e:
                mostrar_error_google(e)

    footer()


# ============================================================
# ESCÁNER
# ============================================================

def pantalla_scanner():
    st.markdown("### 📷 Escanear código de barras")

    st.info(
        "Apunta la cámara trasera del celular al código de barras. "
        "Si no se detecta, puedes buscar el producto manualmente."
    )

    try:
        from streamlit_qrcode_scanner import qrcode_scanner

        codigo = qrcode_scanner(
            key="premium_barcode_scanner",
        )

        if codigo:
            codigo = limpiar_codigo(codigo)
            st.session_state.codigo_pendiente = codigo
            st.session_state.producto_pendiente = None
            st.session_state.metodo_pendiente = "ESCANER"
            st.rerun()

    except Exception as e:
        st.error("No se pudo cargar el lector de cámara.")
        st.caption(
            "Verifica que streamlit-qrcode-scanner esté instalado "
            "y que la aplicación se esté ejecutando con HTTPS."
        )
        st.code(str(e))

    st.markdown("---")

    if st.button("🔎 Buscar manualmente", use_container_width=True):
        st.session_state.modo_inventario = "buscar"
        st.rerun()


# ============================================================
# PRODUCTO / CONTEO
# ============================================================

def pantalla_producto(producto, metodo="ESCANER"):
    stock_sistema = limpiar_numero(producto["StockSistema"])
    costo = limpiar_numero(producto["CostoUnitario"])

    nombre_producto = escapar_html(producto["Producto"])
    descripcion = escapar_html(producto["Descripcion"])
    codigo = escapar_html(limpiar_codigo(producto["CodigoBarras"]))
    unidad = escapar_html(producto["Unidad"])

    st.markdown(
        f"""
        <div class="product-card">
            <div class="product-code">CÓDIGO DE BARRAS · {codigo}</div>
            <div class="product-name">{nombre_producto}</div>
            <div class="muted" style="margin:6px 0 14px;">{descripcion}</div>
            <hr>
            <div class="muted">STOCK EN SISTEMA</div>
            <div class="stock-system">{stock_sistema:,.0f} {unidad}</div>
            <div style="margin-top:8px;">
                Costo unitario: <b>{formato_soles(costo)}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### 📦 Conteo físico")

    cantidad = st.number_input(
        "Cantidad encontrada",
        min_value=0,
        value=0,
        step=1,
        key="cantidad_fisica",
    )

    observacion = st.text_input(
        "Observación opcional",
        placeholder="Ej. producto abierto, dañado, caja incompleta..."
    )

    diferencia = cantidad - stock_sistema

    if diferencia == 0:
        st.success("🟢 Stock físico = stock sistema. Sin diferencia.")
    elif diferencia < 0:
        valor = abs(diferencia) * costo
        st.error(
            f"🔴 Faltante: {abs(diferencia):,.0f} unidades · "
            f"Impacto: {formato_soles(valor)}"
        )
    else:
        valor = diferencia * costo
        st.warning(
            f"🔵 Sobrante: {diferencia:,.0f} unidades · "
            f"Valor: {formato_soles(valor)}"
        )

    c1, c2 = st.columns(2)

    with c1:
        if st.button(
            "💾 GUARDAR CONTEO",
            use_container_width=True,
            type="primary",
        ):
            sesion = st.session_state.sesion_actual

            if not sesion:
                st.error("No hay una sesión de inventario activa.")
                return

            codigo = limpiar_codigo(producto["CodigoBarras"])
            existentes = producto_ya_contado(
                sesion["IdSesion"],
                codigo,
            )

            if not existentes.empty:
                st.warning(
                    "⚠️ Este producto ya fue contado en esta sesión."
                )

                ultimo = existentes.tail(1).iloc[0]

                st.dataframe(
                    pd.DataFrame([{
                        "Fecha": ultimo["FechaHora"],
                        "Stock sistema": ultimo["StockSistema"],
                        "Stock físico": ultimo["StockFisico"],
                        "Diferencia": ultimo["Diferencia"],
                        "Resultado": ultimo["TipoDiferencia"],
                        "Usuario": ultimo["Usuario"],
                    }]),
                    use_container_width=True,
                    hide_index=True,
                )

            else:
                try:
                    guardar_conteo(
                        sesion,
                        st.session_state.usuario,
                        st.session_state.nombre_usuario,
                        producto,
                        cantidad,
                        metodo,
                        observacion,
                    )

                    st.session_state.codigo_pendiente = None
                    st.session_state.producto_pendiente = None
                    st.session_state.modo_inventario = "scanner"

                    st.success("✅ Conteo guardado correctamente.")
                    st.rerun()

                except Exception as e:
                    mostrar_error_google(e)

    with c2:
        if st.button("↩️ Cancelar", use_container_width=True):
            st.session_state.codigo_pendiente = None
            st.session_state.producto_pendiente = None
            st.session_state.modo_inventario = "scanner"
            st.rerun()


# ============================================================
# BÚSQUEDA
# ============================================================

def pantalla_busqueda():
    st.markdown("### 🔎 Buscar producto")

    texto = st.text_input(
        "Nombre, marca, código o descripción",
        placeholder="Ej. Inca Kola, 775123, Coca Cola...",
        key="busqueda_producto",
    )

    if not texto:
        st.info("Escribe algo para buscar.")
        return

    try:
        resultados = buscar_productos(texto)
    except Exception as e:
        mostrar_error_google(e)
        return

    if resultados.empty:
        st.warning("No encontramos coincidencias.")
        return

    st.markdown(f"**{len(resultados)} coincidencias encontradas**")

    for indice, producto in resultados.iterrows():
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])

            with c1:
                st.markdown(f"**{producto['Producto']}**")
                st.caption(
                    f"Código: {limpiar_codigo(producto['CodigoBarras'])} · "
                    f"Stock: {producto['StockSistema']:,.0f} · "
                    f"Costo: {formato_soles(producto['CostoUnitario'])}"
                )

            with c2:
                if st.button(
                    "SELECCIONAR",
                    key=f"select_{indice}",
                    use_container_width=True,
                ):
                    st.session_state.producto_pendiente = producto.to_dict()
                    st.session_state.codigo_pendiente = None
                    st.session_state.metodo_pendiente = "BUSQUEDA"
                    st.rerun()


# ============================================================
# INVENTARIO
# ============================================================

def pantalla_inventario():
    header()

    sesion = st.session_state.sesion_actual

    if not sesion:
        try:
            sesion = obtener_sesion_abierta()
        except Exception as e:
            mostrar_error_google(e)
            return

        if sesion:
            st.session_state.sesion_actual = sesion

    if not sesion:
        st.warning(
            "Primero debes crear o seleccionar una sesión de inventario."
        )

        if st.button("📋 Ir a sesiones", use_container_width=True):
            st.session_state.pagina = "Sesión"
            st.rerun()

        return

    try:
        conteos = cargar_conteos()
        inventario = cargar_inventario()
    except Exception as e:
        mostrar_error_google(e)
        return

    conteos_sesion = conteos[
        conteos["IdSesion"].astype(str) == str(sesion["IdSesion"])
    ] if not conteos.empty else pd.DataFrame()

    total = len(inventario)

    contados = (
        conteos_sesion["CodigoBarras"].nunique()
        if not conteos_sesion.empty else 0
    )

    avance = contados / total * 100 if total else 0

    st.markdown(
        f"""
        <div class="card">
            <span class="badge badge-blue">INVENTARIO ACTIVO</span>
            <h3 style="margin:8px 0 2px;">{escapar_html(sesion['NombreSesion'])}</h3>
            <div class="muted">
                Sucursal: {escapar_html(sesion['Sucursal'])}
                · Usuario: {escapar_html(st.session_state.nombre_usuario)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        kpi("Productos contados", f"{contados:,}", "kpi-blue")
    with c2:
        kpi("Pendientes", f"{max(total-contados,0):,}")
    with c3:
        kpi("Avance", f"{avance:.1f}%", "kpi-success")

    st.progress(min(avance / 100, 1.0))

    if avance >= 100:
        st.success("🎉 Todos los productos del maestro fueron contados.")

    # --------------------------------------------------------
    # PRODUCTO PENDIENTE
    # --------------------------------------------------------

    if st.session_state.get("producto_pendiente"):
        pantalla_producto(
            st.session_state.producto_pendiente,
            st.session_state.get("metodo_pendiente", "BUSQUEDA"),
        )
        return

    # --------------------------------------------------------
    # CÓDIGO PENDIENTE
    # --------------------------------------------------------

    if st.session_state.get("codigo_pendiente"):
        codigo = st.session_state.codigo_pendiente

        try:
            resultados = buscar_por_codigo(codigo)
        except Exception as e:
            mostrar_error_google(e)
            return

        if resultados.empty:
            st.error(
                f"❌ El código {codigo} no existe en el inventario."
            )

            c1, c2 = st.columns(2)

            with c1:
                if st.button("🔎 Buscar por nombre", use_container_width=True):
                    st.session_state.codigo_pendiente = None
                    st.session_state.modo_inventario = "buscar"
                    st.rerun()

            with c2:
                if st.button("📷 Escanear otro", use_container_width=True):
                    st.session_state.codigo_pendiente = None
                    st.rerun()

            return

        producto = resultados.iloc[0].to_dict()
        st.session_state.producto_pendiente = producto
        st.session_state.metodo_pendiente = "ESCANER"
        st.rerun()

    # --------------------------------------------------------
    # MODO
    # --------------------------------------------------------

    modo = st.session_state.get("modo_inventario", "scanner")

    c1, c2 = st.columns(2)

    with c1:
        if st.button(
            "📷 ESCANEAR",
            use_container_width=True,
            type="primary" if modo == "scanner" else "secondary",
        ):
            st.session_state.modo_inventario = "scanner"
            st.rerun()

    with c2:
        if st.button(
            "🔎 BUSCAR",
            use_container_width=True,
            type="primary" if modo == "buscar" else "secondary",
        ):
            st.session_state.modo_inventario = "buscar"
            st.rerun()

    st.markdown("---")

    if modo == "scanner":
        pantalla_scanner()
    else:
        pantalla_busqueda()

    st.markdown("---")
    st.markdown("### 📊 Resumen de la sesión")

    if not conteos_sesion.empty:
        ok = len(conteos_sesion[conteos_sesion["TipoDiferencia"] == "OK"])
        faltantes = len(
            conteos_sesion[conteos_sesion["TipoDiferencia"] == "FALTANTE"]
        )
        sobrantes = len(
            conteos_sesion[conteos_sesion["TipoDiferencia"] == "SOBRANTE"]
        )
        impacto = conteos_sesion["ValorFaltante"].sum() - conteos_sesion["ValorSobrante"].sum()
    else:
        ok = faltantes = sobrantes = 0
        impacto = 0

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        kpi("OK", f"{ok:,}", "kpi-success")
    with c2:
        kpi("Faltantes", f"{faltantes:,}", "kpi-danger")
    with c3:
        kpi("Sobrantes", f"{sobrantes:,}", "kpi-warning")
    with c4:
        kpi("Desfase neto", formato_soles(impacto), "kpi-danger")


# ============================================================
# RESULTADOS / DASHBOARD EJECUTIVO
# ============================================================

def pantalla_resultados():
    header()

    try:
        sesiones = cargar_sesiones()
        conteos = cargar_conteos()
    except Exception as e:
        mostrar_error_google(e)
        return

    if sesiones.empty:
        st.info("Todavía no existen sesiones de inventario.")
        footer()
        return

    opciones = sesiones["IdSesion"].astype(str).tolist()

    id_sesion = st.selectbox(
        "Selecciona una sesión",
        opciones,
        format_func=lambda x: (
            sesiones.loc[
                sesiones["IdSesion"].astype(str) == str(x),
                "NombreSesion"
            ].iloc[0]
            if not sesiones.loc[
                sesiones["IdSesion"].astype(str) == str(x)
            ].empty else x
        ),
    )

    sesion_df = sesiones[
        sesiones["IdSesion"].astype(str) == str(id_sesion)
    ]

    if sesion_df.empty:
        return

    sesion = sesion_df.iloc[0]
    resumen = calcular_resumen(id_sesion)

    if resumen is None:
        return

    st.markdown(
        f"""
        <div class="card">
            <span class="badge {'badge-ok' if str(sesion['Estado']).upper() == 'CERRADO' else 'badge-blue'}">
                ● {escapar_html(sesion['Estado'])}
            </span>
            <h2 style="margin:9px 0 3px;">{escapar_html(sesion['NombreSesion'])}</h2>
            <div class="muted">
                ID: {escapar_html(id_sesion)} ·
                Sucursal: {escapar_html(sesion['Sucursal'])} ·
                Responsable: {escapar_html(sesion['UsuarioCreador'])}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### 📊 Indicadores ejecutivos")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        kpi("Cobertura", f"{resumen['Cobertura']:.1f}%", "kpi-blue")
    with c2:
        kpi("Exactitud", f"{resumen['ExactitudInventario']:.1f}%", "kpi-success")
    with c3:
        kpi("Productos con faltante", f"{resumen['ProductosFaltantes']:,}", "kpi-danger")
    with c4:
        kpi("Desfase neto", formato_soles(resumen["DesfaseNeto"]), "kpi-danger")

    st.markdown("### 💰 Impacto económico")

    c1, c2, c3 = st.columns(3)

    with c1:
        kpi(
            "🔴 Valor faltantes",
            formato_soles(resumen["ValorFaltantes"]),
            "kpi-danger",
        )

    with c2:
        kpi(
            "🔵 Valor sobrantes",
            formato_soles(resumen["ValorSobrantes"]),
            "kpi-warning",
        )

    with c3:
        neto = resumen["DesfaseNeto"]
        clase = "kpi-danger" if neto > 0 else "kpi-success"
        kpi(
            "Resultado neto",
            formato_soles(neto),
            clase,
        )

    st.markdown("### 📦 Unidades")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        kpi("Sistema", f"{resumen['UnidadesSistema']:,.0f}", "kpi-blue")
    with c2:
        kpi("Físico", f"{resumen['UnidadesFisicas']:,.0f}")
    with c3:
        kpi("Faltantes", f"{resumen['UnidadesFaltantes']:,.0f}", "kpi-danger")
    with c4:
        kpi("Sobrantes", f"{resumen['UnidadesSobrantes']:,.0f}", "kpi-warning")

    datos = conteos[
        conteos["IdSesion"].astype(str) == str(id_sesion)
    ].copy()

    if datos.empty:
        st.info("Esta sesión todavía no tiene conteos.")
        footer()
        return

    faltantes = datos[
        datos["TipoDiferencia"].astype(str) == "FALTANTE"
    ].sort_values("ValorFaltante", ascending=False)

    sobrantes = datos[
        datos["TipoDiferencia"].astype(str) == "SOBRANTE"
    ].sort_values("ValorSobrante", ascending=False)

    st.markdown("### 🔴 Principales faltantes")

    if faltantes.empty:
        st.success("No existen faltantes en esta sesión.")
    else:
        st.dataframe(
            faltantes[
                [
                    "Producto", "StockSistema", "StockFisico",
                    "Diferencia", "CostoUnitario",
                    "ValorFaltante", "Usuario"
                ]
            ].head(20),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("### 🔵 Principales sobrantes")

    if sobrantes.empty:
        st.info("No existen sobrantes en esta sesión.")
    else:
        st.dataframe(
            sobrantes[
                [
                    "Producto", "StockSistema", "StockFisico",
                    "Diferencia", "CostoUnitario",
                    "ValorSobrante", "Usuario"
                ]
            ].head(20),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("### 📋 Detalle completo")

    filtro = st.selectbox(
        "Filtrar resultado",
        ["Todos", "OK", "FALTANTE", "SOBRANTE"],
        key="filtro_resultados",
    )

    detalle = datos.copy()

    if filtro != "Todos":
        detalle = detalle[
            detalle["TipoDiferencia"].astype(str) == filtro
        ]

    st.dataframe(
        detalle,
        use_container_width=True,
        hide_index=True,
    )

    csv = detalle.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        "⬇️ Descargar detalle CSV",
        csv,
        file_name=f"{id_sesion}_{filtro.lower()}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    footer()


# ============================================================
# ADMINISTRACIÓN
# ============================================================

def pantalla_admin():
    header()

    if st.session_state.rol != "ADMIN":
        st.error("No tienes permisos para acceder.")
        return

    st.markdown("### ⚙️ Administración")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["👥 Usuarios", "📦 Inventario", "📋 Sesiones", "🔄 Actualización"]
    )

    with tab1:
        try:
            usuarios = cargar_usuarios()
        except Exception as e:
            mostrar_error_google(e)
            return

        if usuarios.empty:
            st.warning("No existen usuarios registrados.")
        else:
            st.dataframe(
                usuarios,
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("#### Crear usuario")

        with st.form("nuevo_usuario", clear_on_submit=True):
            usuario = st.text_input("Usuario")
            nombre = st.text_input("Nombre completo")
            rol = st.selectbox("Rol", ["CONTADOR", "ADMIN"])
            password = st.text_input("Contraseña", type="password")
            estado = st.selectbox("Estado", ["ACTIVO", "INACTIVO"])

            guardar = st.form_submit_button(
                "Crear usuario",
                use_container_width=True,
                type="primary",
            )

            if guardar:
                if not usuario.strip() or not password:
                    st.error("Usuario y contraseña son obligatorios.")
                else:
                    existe = usuarios[
                        usuarios["Usuario"].astype(str).str.lower()
                        == usuario.strip().lower()
                    ]

                    if not existe.empty:
                        st.error("El usuario ya existe.")
                    else:
                        try:
                            obtener_hoja("Usuarios").append_row(
                                [
                                    usuario.strip(),
                                    nombre.strip(),
                                    rol,
                                    hash_password(password),
                                    estado,
                                ],
                                value_input_option="USER_ENTERED",
                            )

                            actualizar_datos_despues_de_escritura("usuario")
                            st.success("✅ Usuario creado.")
                            st.rerun()

                        except Exception as e:
                            mostrar_error_google(e)

    with tab2:
        try:
            inventario = cargar_inventario()
        except Exception as e:
            mostrar_error_google(e)
            return

        c1, c2, c3 = st.columns(3)

        with c1:
            kpi("Productos", f"{len(inventario):,}")
        with c2:
            kpi("Stock", f"{inventario['StockSistema'].sum():,.0f}", "kpi-blue")
        with c3:
            kpi(
                "Valor costo",
                formato_soles(
                    (
                        inventario["StockSistema"]
                        * inventario["CostoUnitario"]
                    ).sum()
                ),
            )

        st.dataframe(
            inventario,
            use_container_width=True,
            hide_index=True,
        )

    with tab3:
        try:
            sesiones = cargar_sesiones()
        except Exception as e:
            mostrar_error_google(e)
            return

        st.dataframe(
            sesiones.sort_values(
                "FechaInicio",
                ascending=False
            ) if not sesiones.empty else sesiones,
            use_container_width=True,
            hide_index=True,
        )

    with tab4:
        st.markdown("#### Estado de conexión")

        try:
            _ = conectar_google()
            hojas = obtener_hojas()
            st.success(
                f"🟢 Conectado correctamente a **{SHEET_NAME}**"
            )
            st.caption(
                f"{len(hojas)} hojas verificadas."
            )
        except Exception as e:
            mostrar_error_google(e)

        st.markdown("#### Actualización controlada")

        st.info(
            "La aplicación utiliza caché para reducir llamadas a Google Sheets. "
            "Usa este botón solo cuando necesites forzar una actualización."
        )

        if st.button(
            "🔄 Actualizar datos ahora",
            use_container_width=True,
        ):
            limpiar_cache_datos(
                cargar_inventario,
                cargar_usuarios,
                cargar_conteos,
                cargar_sesiones,
                cargar_resumenes,
            )
            st.success("Datos actualizados.")
            st.rerun()

        st.markdown("#### Arquitectura de protección")

        st.markdown(
            """
            - Conexión de Google Sheets: **cacheada como recurso**.
            - Metadatos de hojas: **consultados una sola vez por recurso**.
            - Inventario: cache de **60 segundos**.
            - Usuarios: cache de **5 minutos**.
            - Conteos y sesiones: cache de **30 segundos**.
            - Después de escribir, se invalida **solo el dataset afectado**.
            - No se utiliza `st.cache_data.clear()` de forma global.
            """
        )

    footer()


# ============================================================
# SIDEBAR
# ============================================================

def sidebar():
    with st.sidebar:
        st.markdown(
            """
            <div style="text-align:center;padding:8px 4px 14px;">
                <div style="font-size:42px;">📦</div>
                <h2 style="margin:0;font-weight:900;">TIENDAS PREMIUM</h2>
                <small style="color:#777;">Inventario</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")

        st.write(f"👤 **{st.session_state.nombre_usuario}**")
        st.caption(f"Rol: {st.session_state.rol}")

        st.markdown("---")

        opciones = [
            "Inicio",
            "Sesión",
            "Inventario",
            "Resultados",
        ]

        if st.session_state.rol == "ADMIN":
            opciones.append("Administración")

        pagina_actual = st.session_state.pagina
        if pagina_actual not in opciones:
            pagina_actual = "Inicio"

        pagina = st.radio(
            "Navegación",
            opciones,
            index=opciones.index(pagina_actual),
        )

        st.session_state.pagina = pagina

        st.markdown("---")

        if st.button(
            "🔄 Refrescar datos",
            use_container_width=True,
        ):
            limpiar_cache_datos(
                cargar_inventario,
                cargar_usuarios,
                cargar_conteos,
                cargar_sesiones,
                cargar_resumenes,
            )
            st.rerun()

        if st.button(
            "🚪 Cerrar sesión",
            use_container_width=True,
        ):
            for clave in list(st.session_state.keys()):
                del st.session_state[clave]
            st.rerun()


# ============================================================
# INICIALIZACIÓN DE GOOGLE SHEETS
# ============================================================

def validar_conexion_inicial():
    try:
        obtener_hojas()
        return True
    except Exception as e:
        mostrar_error_google(e)
        return False


# ============================================================
# MAIN
# ============================================================

if not validar_conexion_inicial():
    st.stop()

if not st.session_state.autenticado:
    pantalla_login()
    st.stop()

sidebar()

try:
    if st.session_state.pagina == "Inicio":
        pantalla_inicio()

    elif st.session_state.pagina == "Sesión":
        pantalla_sesion()

    elif st.session_state.pagina == "Inventario":
        pantalla_inventario()

    elif st.session_state.pagina == "Resultados":
        pantalla_resultados()

    elif st.session_state.pagina == "Administración":
        pantalla_admin()

except Exception as e:
    mostrar_error_google(e)
    st.stop()
'''

path = Path("/mnt/data/app.py")
path.write_text(app_code, encoding="utf-8")

print(f"Archivo creado: {path}")
print(f"Líneas: {len(app_code.splitlines()):,}")
print(f"Caracteres: {len(app_code):,}")

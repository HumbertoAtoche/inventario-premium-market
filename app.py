import streamlit as st
import pandas as pd
import gspread
import hashlib
import io
import re
from datetime import datetime
from google.oauth2.service_account import Credentials

# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="Inventario | Tiendas Premium",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_NAME = "Tiendas Premium"
COMPANY = "Tiendas Premium EIRL"
RUC = "20612107787"
AUTHOR = "Humberto Atoche"

SHEET_NAME = "BD_Inventario_PremiumMarket"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ============================================================
# ESTILOS
# ============================================================

st.markdown("""
<style>

    .stApp {
        background: #f7f8fa;
    }

    #MainMenu {
        visibility: hidden;
    }

    footer {
        visibility: hidden;
    }

    header {
        visibility: hidden;
    }

    .premium-header {
        background: linear-gradient(135deg, #ec3237 0%, #c91f25 100%);
        padding: 22px 25px;
        border-radius: 18px;
        color: white;
        margin-bottom: 20px;
        box-shadow: 0 6px 20px rgba(236,50,55,0.18);
    }

    .premium-header h1 {
        margin: 0;
        font-size: 30px;
        font-weight: 800;
    }

    .premium-header p {
        margin: 4px 0 0 0;
        opacity: .9;
    }

    .card {
        background: white;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 3px 14px rgba(0,0,0,.06);
        border: 1px solid #eeeeee;
        margin-bottom: 15px;
    }

    .kpi {
        background: white;
        border-radius: 16px;
        padding: 18px;
        border: 1px solid #eeeeee;
        box-shadow: 0 3px 12px rgba(0,0,0,.05);
        min-height: 115px;
    }

    .kpi-title {
        color: #777;
        font-size: 13px;
        font-weight: 600;
    }

    .kpi-value {
        font-size: 28px;
        font-weight: 800;
        margin-top: 8px;
        color: #222;
    }

    .kpi-danger {
        color: #ec3237;
    }

    .kpi-success {
        color: #00a959;
    }

    .kpi-warning {
        color: #d88700;
    }

    .product-card {
        background: white;
        border-radius: 18px;
        padding: 24px;
        border: 1px solid #e8e8e8;
        box-shadow: 0 5px 18px rgba(0,0,0,.07);
        margin: 10px 0;
    }

    .product-name {
        font-size: 23px;
        font-weight: 800;
        color: #222;
    }

    .product-code {
        color: #777;
        font-size: 13px;
    }

    .stock-system {
        font-size: 34px;
        font-weight: 900;
        color: #1071b8;
    }

    .premium-footer {
        text-align: center;
        color: #888;
        font-size: 12px;
        margin-top: 40px;
        padding: 20px;
        border-top: 1px solid #eee;
    }

    .badge {
        display: inline-block;
        padding: 5px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 700;
    }

    .badge-ok {
        background: #e7f7ee;
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

    div.stButton > button {
        border-radius: 12px;
        min-height: 45px;
        font-weight: 700;
    }

    .big-button button {
        min-height: 60px !important;
        font-size: 18px !important;
    }

    @media (max-width: 768px) {

        .premium-header h1 {
            font-size: 24px;
        }

        .kpi-value {
            font-size: 22px;
        }

        .product-name {
            font-size: 19px;
        }

    }

</style>
""", unsafe_allow_html=True)


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

    valor = str(valor).strip()

    # Evita problemas cuando Sheets devuelve 775123.0
    if valor.endswith(".0"):
        valor = valor[:-2]

    return valor


def limpiar_numero(valor, default=0):
    try:
        if pd.isna(valor):
            return default

        texto = str(valor).strip().replace(",", "")

        if texto == "":
            return default

        return float(texto)

    except:
        return default


def formato_soles(valor):
    try:
        return f"S/ {float(valor):,.2f}"
    except:
        return "S/ 0.00"


def generar_id_sesion():
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"INV-{timestamp}"


def hash_password(password):
    return hashlib.sha256(
        str(password).encode("utf-8")
    ).hexdigest()


# ============================================================
# GOOGLE SHEETS
# ============================================================

@st.cache_resource
def conectar_google():

    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )

    client = gspread.authorize(credentials)

    spreadsheet = client.open(SHEET_NAME)

    return spreadsheet


def obtener_hoja(nombre):

    spreadsheet = conectar_google()

    try:
        return spreadsheet.worksheet(nombre)

    except gspread.WorksheetNotFound:

        return spreadsheet.add_worksheet(
            title=nombre,
            rows=1000,
            cols=30
        )


def asegurar_encabezados(nombre_hoja, encabezados):

    worksheet = obtener_hoja(nombre_hoja)

    valores = worksheet.get_all_values()

    if not valores:

        worksheet.append_row(encabezados)

        return worksheet

    actuales = valores[0]

    faltantes = [
        columna
        for columna in encabezados
        if columna not in actuales
    ]

    if faltantes:

        nuevos = actuales + faltantes

        worksheet.update(
            "1:1",
            [nuevos]
        )

    return worksheet


# ============================================================
# ESTRUCTURA DE HOJAS
# ============================================================

HEADERS_INVENTARIO = [
    "CodigoBarras",
    "CodigoProducto",
    "Producto",
    "Descripcion",
    "Categoria",
    "Marca",
    "Unidad",
    "Sucursal",
    "StockSistema",
    "CostoUnitario",
    "PrecioVenta",
    "Estado"
]

HEADERS_CONTEO = [
    "IdSesion",
    "FechaHora",
    "Usuario",
    "NombreUsuario",
    "CodigoBarras",
    "CodigoProducto",
    "Producto",
    "Categoria",
    "Sucursal",
    "StockSistema",
    "StockFisico",
    "Diferencia",
    "CostoUnitario",
    "ValorFaltante",
    "ValorSobrante",
    "CostoDiferencia",
    "TipoDiferencia",
    "MetodoConteo",
    "Observacion"
]

HEADERS_SESIONES = [
    "IdSesion",
    "FechaInicio",
    "FechaFin",
    "NombreSesion",
    "UsuarioCreador",
    "Estado",
    "Sucursal",
    "Observacion"
]

HEADERS_RESUMEN = [
    "IdSesion",
    "Fecha",
    "NombreSesion",
    "Sucursal",
    "ProductosSistema",
    "ProductosContados",
    "ProductosOK",
    "ProductosFaltantes",
    "ProductosSobrantes",
    "UnidadesSistema",
    "UnidadesFisicas",
    "UnidadesFaltantes",
    "UnidadesSobrantes",
    "ValorFaltantes",
    "ValorSobrantes",
    "DesfaseNeto",
    "ExactitudInventario",
    "Estado"
]

HEADERS_USUARIOS = [
    "Usuario",
    "NombreCompleto",
    "Rol",
    "Password",
    "Estado"
]


def preparar_hojas():

    asegurar_encabezados(
        "Inventario",
        HEADERS_INVENTARIO
    )

    asegurar_encabezados(
        "ConteoInventario",
        HEADERS_CONTEO
    )

    asegurar_encabezados(
        "SesionesInventario",
        HEADERS_SESIONES
    )

    asegurar_encabezados(
        "ResumenInventario",
        HEADERS_RESUMEN
    )

    asegurar_encabezados(
        "Usuarios",
        HEADERS_USUARIOS
    )


# ============================================================
# LECTURA DE DATA
# ============================================================

@st.cache_data(ttl=30)
def cargar_inventario():

    worksheet = obtener_hoja("Inventario")

    data = worksheet.get_all_records()

    df = pd.DataFrame(data)

    if df.empty:
        return pd.DataFrame(columns=HEADERS_INVENTARIO)

    for columna in HEADERS_INVENTARIO:

        if columna not in df.columns:
            df[columna] = ""

    df["CodigoBarras"] = df["CodigoBarras"].apply(
        limpiar_codigo
    )

    df["StockSistema"] = df["StockSistema"].apply(
        limpiar_numero
    )

    df["CostoUnitario"] = df["CostoUnitario"].apply(
        limpiar_numero
    )

    df["PrecioVenta"] = df["PrecioVenta"].apply(
        limpiar_numero
    )

    return df


@st.cache_data(ttl=15)
def cargar_usuarios():

    worksheet = obtener_hoja("Usuarios")

    data = worksheet.get_all_records()

    df = pd.DataFrame(data)

    if df.empty:
        return pd.DataFrame(columns=HEADERS_USUARIOS)

    for columna in HEADERS_USUARIOS:

        if columna not in df.columns:
            df[columna] = ""

    return df


@st.cache_data(ttl=10)
def cargar_conteos():

    worksheet = obtener_hoja("ConteoInventario")

    data = worksheet.get_all_records()

    df = pd.DataFrame(data)

    if df.empty:
        return pd.DataFrame(columns=HEADERS_CONTEO)

    for columna in HEADERS_CONTEO:

        if columna not in df.columns:
            df[columna] = ""

    df["StockSistema"] = df["StockSistema"].apply(
        limpiar_numero
    )

    df["StockFisico"] = df["StockFisico"].apply(
        limpiar_numero
    )

    df["Diferencia"] = df["Diferencia"].apply(
        limpiar_numero
    )

    df["CostoUnitario"] = df["CostoUnitario"].apply(
        limpiar_numero
    )

    df["ValorFaltante"] = df["ValorFaltante"].apply(
        limpiar_numero
    )

    df["ValorSobrante"] = df["ValorSobrante"].apply(
        limpiar_numero
    )

    df["CostoDiferencia"] = df["CostoDiferencia"].apply(
        limpiar_numero
    )

    return df


@st.cache_data(ttl=10)
def cargar_sesiones():

    worksheet = obtener_hoja("SesionesInventario")

    data = worksheet.get_all_records()

    df = pd.DataFrame(data)

    if df.empty:
        return pd.DataFrame(columns=HEADERS_SESIONES)

    for columna in HEADERS_SESIONES:

        if columna not in df.columns:
            df[columna] = ""

    return df


# ============================================================
# AUTENTICACIÓN
# ============================================================

def autenticar(usuario, password):

    usuarios = cargar_usuarios()

    if usuarios.empty:
        return None

    usuarios["Usuario"] = usuarios["Usuario"].astype(str)
    usuarios["Estado"] = usuarios["Estado"].astype(str)

    encontrados = usuarios[
        (
            usuarios["Usuario"].str.strip().str.lower()
            == usuario.strip().lower()
        )
        &
        (
            usuarios["Estado"].str.upper()
            == "ACTIVO"
        )
    ]

    if encontrados.empty:
        return None

    fila = encontrados.iloc[0]

    password_guardada = str(fila["Password"])

    # Permite inicialmente contraseña normal.
    # Si después quieres hash, se activa fácilmente.
    if password == password_guardada:
        return fila.to_dict()

    # También soporta SHA256
    if hash_password(password) == password_guardada:
        return fila.to_dict()

    return None


# ============================================================
# INVENTARIO
# ============================================================

def buscar_por_codigo(codigo):

    df = cargar_inventario()

    codigo = limpiar_codigo(codigo)

    if df.empty:
        return pd.DataFrame()

    return df[
        df["CodigoBarras"].astype(str).str.strip()
        == codigo
    ]


def buscar_productos(texto):

    df = cargar_inventario()

    if df.empty:
        return pd.DataFrame()

    texto = str(texto).strip().lower()

    if not texto:
        return pd.DataFrame()

    columnas_busqueda = [
        "CodigoBarras",
        "CodigoProducto",
        "Producto",
        "Descripcion",
        "Categoria",
        "Marca"
    ]

    mascara = pd.Series(
        False,
        index=df.index
    )

    for columna in columnas_busqueda:

        mascara = (
            mascara
            |
            df[columna]
            .fillna("")
            .astype(str)
            .str.lower()
            .str.contains(
                re.escape(texto),
                na=False
            )
        )

    return df[mascara].head(50)


def guardar_conteo(
    sesion,
    usuario,
    nombre_usuario,
    producto,
    stock_fisico,
    metodo="ESCANER",
    observacion=""
):

    stock_sistema = limpiar_numero(
        producto["StockSistema"]
    )

    costo = limpiar_numero(
        producto["CostoUnitario"]
    )

    diferencia = (
        stock_fisico
        -
        stock_sistema
    )

    valor_faltante = 0
    valor_sobrante = 0

    if diferencia < 0:
        valor_faltante = abs(diferencia) * costo

    elif diferencia > 0:
        valor_sobrante = diferencia * costo

    costo_diferencia = (
        valor_sobrante
        -
        valor_faltante
    )

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
        observacion
    ]

    worksheet = obtener_hoja("ConteoInventario")

    worksheet.append_row(
        fila,
        value_input_option="USER_ENTERED"
    )

    st.cache_data.clear()


def producto_ya_contado(id_sesion, codigo):

    df = cargar_conteos()

    if df.empty:
        return pd.DataFrame()

    return df[
        (df["IdSesion"].astype(str) == str(id_sesion))
        &
        (
            df["CodigoBarras"].apply(limpiar_codigo)
            ==
            limpiar_codigo(codigo)
        )
    ]


def obtener_sesion_abierta(usuario=None):

    df = cargar_sesiones()

    if df.empty:
        return None

    filtro = (
        df["Estado"]
        .astype(str)
        .str.upper()
        ==
        "ABIERTO"
    )

    if usuario:
        filtro &= (
            df["UsuarioCreador"]
            .astype(str)
            .str.lower()
            ==
            usuario.lower()
        )

    resultados = df[filtro]

    if resultados.empty:
        return None

    return resultados.iloc[-1].to_dict()


def crear_sesion(
    nombre,
    usuario,
    sucursal,
    observacion=""
):

    id_sesion = generar_id_sesion()

    fila = [
        id_sesion,
        ahora(),
        "",
        nombre,
        usuario,
        "ABIERTO",
        sucursal,
        observacion
    ]

    worksheet = obtener_hoja("SesionesInventario")

    worksheet.append_row(
        fila,
        value_input_option="USER_ENTERED"
    )

    st.cache_data.clear()

    return id_sesion


def cerrar_sesion(id_sesion):

    worksheet = obtener_hoja("SesionesInventario")

    data = worksheet.get_all_values()

    if len(data) <= 1:
        return

    headers = data[0]

    try:
        col_id = headers.index("IdSesion") + 1
        col_fin = headers.index("FechaFin") + 1
        col_estado = headers.index("Estado") + 1

    except ValueError:
        return

    for numero_fila, fila in enumerate(data[1:], start=2):

        if len(fila) >= col_id:

            if fila[col_id - 1] == id_sesion:

                worksheet.update_cell(
                    numero_fila,
                    col_fin,
                    ahora()
                )

                worksheet.update_cell(
                    numero_fila,
                    col_estado,
                    "CERRADO"
                )

                break

    st.cache_data.clear()


# ============================================================
# RESUMEN
# ============================================================

def calcular_resumen(id_sesion):

    inventario = cargar_inventario()
    conteos = cargar_conteos()

    if inventario.empty:
        return None

    conteos_sesion = conteos[
        conteos["IdSesion"].astype(str)
        ==
        str(id_sesion)
    ].copy()

    productos_sistema = len(inventario)

    productos_contados = (
        conteos_sesion["CodigoBarras"]
        .nunique()
        if not conteos_sesion.empty
        else 0
    )

    productos_ok = (
        len(
            conteos_sesion[
                conteos_sesion["TipoDiferencia"]
                .astype(str)
                == "OK"
            ]
        )
        if not conteos_sesion.empty
        else 0
    )

    productos_faltantes = (
        len(
            conteos_sesion[
                conteos_sesion["TipoDiferencia"]
                .astype(str)
                == "FALTANTE"
            ]
        )
        if not conteos_sesion.empty
        else 0
    )

    productos_sobrantes = (
        len(
            conteos_sesion[
                conteos_sesion["TipoDiferencia"]
                .astype(str)
                == "SOBRANTE"
            ]
        )
        if not conteos_sesion.empty
        else 0
    )

    unidades_sistema = (
        conteos_sesion["StockSistema"].sum()
        if not conteos_sesion.empty
        else 0
    )

    unidades_fisicas = (
        conteos_sesion["StockFisico"].sum()
        if not conteos_sesion.empty
        else 0
    )

    unidades_faltantes = (
        abs(
            conteos_sesion[
                conteos_sesion["Diferencia"] < 0
            ]["Diferencia"].sum()
        )
        if not conteos_sesion.empty
        else 0
    )

    unidades_sobrantes = (
        conteos_sesion[
            conteos_sesion["Diferencia"] > 0
        ]["Diferencia"].sum()
        if not conteos_sesion.empty
        else 0
    )

    valor_faltantes = (
        conteos_sesion["ValorFaltante"].sum()
        if not conteos_sesion.empty
        else 0
    )

    valor_sobrantes = (
        conteos_sesion["ValorSobrante"].sum()
        if not conteos_sesion.empty
        else 0
    )

    desfase_neto = (
        valor_faltantes
        -
        valor_sobrantes
    )

    if productos_contados > 0:

        exactitud = (
            productos_ok
            /
            productos_contados
        ) * 100

    else:
        exactitud = 0

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
        "ExactitudInventario": exactitud
    }


def guardar_resumen(id_sesion):

    sesiones = cargar_sesiones()

    if sesiones.empty:
        return

    fila_sesion = sesiones[
        sesiones["IdSesion"].astype(str)
        ==
        str(id_sesion)
    ]

    if fila_sesion.empty:
        return

    sesion = fila_sesion.iloc[0]

    resumen = calcular_resumen(id_sesion)

    if resumen is None:
        return

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
        "CERRADO"
    ]

    worksheet = obtener_hoja("ResumenInventario")

    worksheet.append_row(
        fila,
        value_input_option="USER_ENTERED"
    )

    st.cache_data.clear()


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
        unsafe_allow_html=True
    )


def footer():

    st.markdown(
        f"""
        <div class="premium-footer">
            Desarrollado por <b>{AUTHOR}</b><br>
            {COMPANY} — RUC {RUC}
        </div>
        """,
        unsafe_allow_html=True
    )


def kpi(titulo, valor, clase=""):

    st.markdown(
        f"""
        <div class="kpi">
            <div class="kpi-title">{titulo}</div>
            <div class="kpi-value {clase}">
                {valor}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# LOGIN
# ============================================================

def pantalla_login():

    st.markdown(
        """
        <div style="
            max-width:500px;
            margin:80px auto 20px auto;
            text-align:center;
        ">
            <div style="
                font-size:55px;
                margin-bottom:10px;
            ">📦</div>

            <h1 style="
                font-weight:900;
                margin-bottom:5px;
            ">
                TIENDAS PREMIUM
            </h1>

            <p style="color:#777;">
                Sistema de Inventario
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.form("login_form"):

        usuario = st.text_input(
            "Usuario",
            placeholder="Ingresa tu usuario"
        )

        password = st.text_input(
            "Contraseña",
            type="password",
            placeholder="Ingresa tu contraseña"
        )

        ingresar = st.form_submit_button(
            "🔐 INGRESAR",
            use_container_width=True
        )

        if ingresar:

            if not usuario or not password:

                st.error(
                    "Ingresa usuario y contraseña."
                )

            else:

                resultado = autenticar(
                    usuario,
                    password
                )

                if resultado:

                    st.session_state.autenticado = True
                    st.session_state.usuario = resultado["Usuario"]
                    st.session_state.nombre_usuario = resultado["NombreCompleto"]
                    st.session_state.rol = resultado["Rol"].upper()

                    st.session_state.sesion_actual = None
                    st.session_state.producto_pendiente = None
                    st.session_state.codigo_pendiente = None

                    st.rerun()

                else:

                    st.error(
                        "Usuario o contraseña incorrectos."
                    )

    footer()


# ============================================================
# INICIO
# ============================================================

def pantalla_inicio():

    header()

    usuario = st.session_state.nombre_usuario

    st.markdown(
        f"""
        <div class="card">
            <h2>Hola, {usuario} 👋</h2>
            <p style="color:#777;">
                Bienvenido al sistema de inventario.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    inventario = cargar_inventario()

    conteos = cargar_conteos()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        kpi(
            "Productos registrados",
            f"{len(inventario):,}"
        )

    with col2:
        kpi(
            "Stock total sistema",
            f"{inventario['StockSistema'].sum():,.0f}"
        )

    with col3:
        kpi(
            "Valor inventario",
            formato_soles(
                (
                    inventario["StockSistema"]
                    *
                    inventario["CostoUnitario"]
                ).sum()
            )
        )

    with col4:
        kpi(
            "Productos activos",
            f"{len(inventario[inventario['Estado'].astype(str).str.upper() == 'ACTIVO']):,}"
        )

    st.markdown("### 🚀 Acciones rápidas")

    col1, col2, col3 = st.columns(3)

    with col1:

        if st.button(
            "📷 Escanear producto",
            use_container_width=True
        ):

            st.session_state.pagina = "Inventario"
            st.session_state.modo_inventario = "scanner"

            st.rerun()

    with col2:

        if st.button(
            "🔎 Buscar producto",
            use_container_width=True
        ):

            st.session_state.pagina = "Inventario"
            st.session_state.modo_inventario = "buscar"

            st.rerun()

    with col3:

        if st.button(
            "📊 Resultados",
            use_container_width=True
        ):

            st.session_state.pagina = "Resultados"

            st.rerun()

    if not conteos.empty:

        st.markdown("### Últimos conteos")

        st.dataframe(
            conteos.tail(10).iloc[::-1],
            use_container_width=True,
            hide_index=True
        )

    footer()


# ============================================================
# CREAR / SELECCIONAR SESIÓN
# ============================================================

def pantalla_sesion():

    header()

    st.subheader("📋 Sesión de inventario")

    sesion = obtener_sesion_abierta()

    if sesion:

        st.success(
            f"Sesión abierta: {sesion['NombreSesion']}"
        )

        st.write(
            f"**ID:** {sesion['IdSesion']}"
        )

        st.write(
            f"**Sucursal:** {sesion['Sucursal']}"
        )

        if st.button(
            "➡️ Continuar inventario",
            use_container_width=True
        ):

            st.session_state.sesion_actual = sesion
            st.session_state.pagina = "Inventario"

            st.rerun()

        if st.button(
            "🔒 Cerrar sesión",
            use_container_width=True
        ):

            guardar_resumen(
                sesion["IdSesion"]
            )

            cerrar_sesion(
                sesion["IdSesion"]
            )

            st.session_state.sesion_actual = None

            st.success(
                "Inventario cerrado correctamente."
            )

            st.rerun()

        return

    st.info(
        "No existe una sesión de inventario abierta."
    )

    with st.form("crear_sesion"):

        nombre = st.text_input(
            "Nombre del inventario",
            value=f"Inventario {fecha_actual()}"
        )

        sucursal = st.text_input(
            "Sucursal",
            value="PRINCIPAL"
        )

        observacion = st.text_area(
            "Observación"
        )

        crear = st.form_submit_button(
            "🚀 CREAR INVENTARIO",
            use_container_width=True
        )

        if crear:

            if not nombre.strip():

                st.error(
                    "Ingresa un nombre para el inventario."
                )

            else:

                id_sesion = crear_sesion(
                    nombre,
                    st.session_state.usuario,
                    sucursal,
                    observacion
                )

                st.success(
                    f"Inventario creado: {id_sesion}"
                )

                st.rerun()

    footer()


# ============================================================
# ESCÁNER
# ============================================================

def pantalla_scanner():

    st.subheader("📷 Escanear código de barras")

    st.info(
        "Apunta la cámara al código de barras del producto."
    )

    try:

        from streamlit_qrcode_scanner import qrcode_scanner

        codigo = qrcode_scanner(
            key="premium_barcode_scanner"
        )

        if codigo:

            codigo = limpiar_codigo(codigo)

            st.session_state.codigo_pendiente = codigo

            st.rerun()

    except Exception as e:

        st.error(
            "No se pudo cargar el lector de cámara."
        )

        st.code(str(e))

    st.markdown("---")

    if st.button(
        "🔎 Buscar manualmente",
        use_container_width=True
    ):

        st.session_state.modo_inventario = "buscar"

        st.rerun()


# ============================================================
# PRODUCTO DETECTADO
# ============================================================

def pantalla_producto(producto, metodo="ESCANER"):

    if producto is None:
        return

    st.markdown(
        f"""
        <div class="product-card">

            <div class="product-code">
                Código de barras:
                {limpiar_codigo(producto["CodigoBarras"])}
            </div>

            <div class="product-name">
                {producto["Producto"]}
            </div>

            <p>
                {producto["Descripcion"]}
            </p>

            <hr>

            <div>
                <b>Stock sistema</b>
            </div>

            <div class="stock-system">
                {producto["StockSistema"]:,.0f}
                {producto["Unidad"]}
            </div>

            <p>
                Costo unitario:
                <b>{formato_soles(producto["CostoUnitario"])}</b>
            </p>

        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("### 📦 Conteo físico")

    cantidad = st.number_input(
        "Cantidad encontrada",
        min_value=0,
        value=0,
        step=1,
        key="cantidad_fisica"
    )

    observacion = st.text_input(
        "Observación (opcional)",
        placeholder="Ej. producto abierto, dañado, etc."
    )

    diferencia = (
        cantidad
        -
        producto["StockSistema"]
    )

    if diferencia == 0:

        st.success(
            "🟢 El stock físico coincide con el sistema."
        )

    elif diferencia < 0:

        valor = abs(diferencia) * producto["CostoUnitario"]

        st.error(
            f"🔴 Faltante de {abs(diferencia):,.0f} unidades — "
            f"{formato_soles(valor)}"
        )

    else:

        valor = diferencia * producto["CostoUnitario"]

        st.warning(
            f"🔵 Sobrante de {diferencia:,.0f} unidades — "
            f"{formato_soles(valor)}"
        )

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "💾 GUARDAR CONTEO",
            type="primary",
            use_container_width=True
        ):

            sesion = st.session_state.sesion_actual

            codigo = limpiar_codigo(
                producto["CodigoBarras"]
            )

            existentes = producto_ya_contado(
                sesion["IdSesion"],
                codigo
            )

            if not existentes.empty:

                st.warning(
                    "⚠️ Este producto ya fue contado "
                    "en esta sesión."
                )

                st.dataframe(
                    existentes.tail(1),
                    use_container_width=True,
                    hide_index=True
                )

            else:

                guardar_conteo(
                    sesion,
                    st.session_state.usuario,
                    st.session_state.nombre_usuario,
                    producto,
                    cantidad,
                    metodo,
                    observacion
                )

                st.session_state.codigo_pendiente = None
                st.session_state.producto_pendiente = None
                st.session_state.modo_inventario = "scanner"

                st.success(
                    "✅ Conteo guardado correctamente."
                )

                st.rerun()

    with col2:

        if st.button(
            "↩️ Cancelar",
            use_container_width=True
        ):

            st.session_state.codigo_pendiente = None
            st.session_state.producto_pendiente = None

            st.rerun()


# ============================================================
# BÚSQUEDA MANUAL
# ============================================================

def pantalla_busqueda():

    st.subheader("🔎 Buscar producto")

    texto = st.text_input(
        "Escribe nombre, marca, código o descripción",
        placeholder="Ej. Inca Kola"
    )

    if texto:

        resultados = buscar_productos(
            texto
        )

        if resultados.empty:

            st.warning(
                "No encontramos coincidencias."
            )

            return

        st.markdown(
            f"### {len(resultados)} coincidencias"
        )

        for indice, producto in resultados.iterrows():

            with st.container(border=True):

                col1, col2 = st.columns(
                    [4, 1]
                )

                with col1:

                    st.markdown(
                        f"**{producto['Producto']}**"
                    )

                    st.caption(
                        f"Código: {producto['CodigoBarras']} | "
                        f"Stock: {producto['StockSistema']:,.0f} | "
                        f"Costo: {formato_soles(producto['CostoUnitario'])}"
                    )

                with col2:

                    if st.button(
                        "SELECCIONAR",
                        key=f"select_{indice}",
                        use_container_width=True
                    ):

                        st.session_state.producto_pendiente = producto.to_dict()

                        st.rerun()


# ============================================================
# PANTALLA INVENTARIO
# ============================================================

def pantalla_inventario():

    header()

    sesion = st.session_state.sesion_actual

    if not sesion:

        sesion = obtener_sesion_abierta()

        if sesion:
            st.session_state.sesion_actual = sesion

    if not sesion:

        st.warning(
            "Primero debes crear o seleccionar una sesión de inventario."
        )

        if st.button(
            "📋 Ir a sesiones",
            use_container_width=True
        ):

            st.session_state.pagina = "Sesión"

            st.rerun()

        return

    st.markdown(
        f"""
        <div class="card">
            <b>Inventario:</b> {sesion['NombreSesion']}<br>
            <b>ID:</b> {sesion['IdSesion']}<br>
            <b>Sucursal:</b> {sesion['Sucursal']}
        </div>
        """,
        unsafe_allow_html=True
    )

    # --------------------------------------------------------
    # SI HAY PRODUCTO PENDIENTE
    # --------------------------------------------------------

    if st.session_state.get(
        "producto_pendiente"
    ):

        producto = st.session_state.producto_pendiente

        pantalla_producto(
            producto,
            st.session_state.get(
                "metodo_pendiente",
                "BUSQUEDA"
            )
        )

        return

    # --------------------------------------------------------
    # SI HAY CÓDIGO PENDIENTE
    # --------------------------------------------------------

    if st.session_state.get(
        "codigo_pendiente"
    ):

        codigo = st.session_state.codigo_pendiente

        resultados = buscar_por_codigo(
            codigo
        )

        if resultados.empty:

            st.error(
                f"❌ El código {codigo} "
                "no existe en el inventario."
            )

            st.info(
                "Puedes buscar el producto manualmente."
            )

            if st.button(
                "🔎 Buscar por nombre",
                use_container_width=True
            ):

                st.session_state.codigo_pendiente = None
                st.session_state.modo_inventario = "buscar"

                st.rerun()

            if st.button(
                "📷 Escanear otro",
                use_container_width=True
            ):

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

    modo = st.session_state.get(
        "modo_inventario",
        "scanner"
    )

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "📷 ESCANEAR",
            use_container_width=True,
            type="primary"
        ):

            st.session_state.modo_inventario = "scanner"

            st.rerun()

    with col2:

        if st.button(
            "🔎 BUSCAR",
            use_container_width=True
        ):

            st.session_state.modo_inventario = "buscar"

            st.rerun()

    st.markdown("---")

    if modo == "scanner":

        pantalla_scanner()

    else:

        pantalla_busqueda()

    # --------------------------------------------------------
    # AVANCE
    # --------------------------------------------------------

    conteos = cargar_conteos()

    conteos_sesion = conteos[
        conteos["IdSesion"].astype(str)
        ==
        str(sesion["IdSesion"])
    ]

    inventario = cargar_inventario()

    total = len(inventario)

    contados = (
        conteos_sesion["CodigoBarras"]
        .nunique()
        if not conteos_sesion.empty
        else 0
    )

    avance = (
        contados / total * 100
        if total > 0
        else 0
    )

    st.markdown("---")

    st.subheader("📊 Avance")

    st.progress(
        min(avance / 100, 1.0)
    )

    st.write(
        f"**{contados:,}** de **{total:,}** "
        f"productos — **{avance:.1f}%**"
    )


# ============================================================
# RESULTADOS
# ============================================================

def pantalla_resultados():

    header()

    sesiones = cargar_sesiones()

    if sesiones.empty:

        st.info(
            "Todavía no existen sesiones."
        )

        return

    opciones = sesiones[
        "IdSesion"
    ].astype(str).tolist()

    id_sesion = st.selectbox(
        "Selecciona una sesión",
        opciones
    )

    sesion = sesiones[
        sesiones["IdSesion"].astype(str)
        ==
        str(id_sesion)
    ].iloc[0]

    resumen = calcular_resumen(
        id_sesion
    )

    if resumen is None:
        return

    st.markdown(
        f"""
        <div class="card">
            <h2>{sesion['NombreSesion']}</h2>
            <p>
                ID: {id_sesion}<br>
                Sucursal: {sesion['Sucursal']}<br>
                Estado: {sesion['Estado']}
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        kpi(
            "Productos sistema",
            f"{resumen['ProductosSistema']:,}"
        )

    with col2:

        kpi(
            "Productos contados",
            f"{resumen['ProductosContados']:,}"
        )

    with col3:

        kpi(
            "Exactitud",
            f"{resumen['ExactitudInventario']:.1f}%",
            "kpi-success"
        )

    with col4:

        kpi(
            "Desfase neto",
            formato_soles(
                resumen["DesfaseNeto"]
            ),
            "kpi-danger"
        )

    st.markdown("### 💰 Impacto económico")

    col1, col2, col3 = st.columns(3)

    with col1:

        kpi(
            "🔴 Faltantes",
            formato_soles(
                resumen["ValorFaltantes"]
            ),
            "kpi-danger"
        )

    with col2:

        kpi(
            "🔵 Sobrantes",
            formato_soles(
                resumen["ValorSobrantes"]
            ),
            "kpi-warning"
        )

    with col3:

        kpi(
            "⚠️ Desfase neto",
            formato_soles(
                resumen["DesfaseNeto"]
            ),
            "kpi-danger"
        )

    st.markdown("### 📦 Unidades")

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        kpi(
            "Coincidencias",
            f"{resumen['ProductosOK']:,}",
            "kpi-success"
        )

    with col2:

        kpi(
            "Productos faltantes",
            f"{resumen['ProductosFaltantes']:,}",
            "kpi-danger"
        )

    with col3:

        kpi(
            "Productos sobrantes",
            f"{resumen['ProductosSobrantes']:,}",
            "kpi-warning"
        )

    with col4:

        kpi(
            "Unidades faltantes",
            f"{resumen['UnidadesFaltantes']:,.0f}",
            "kpi-danger"
        )

    conteos = cargar_conteos()

    datos = conteos[
        conteos["IdSesion"].astype(str)
        ==
        str(id_sesion)
    ].copy()

    if not datos.empty:

        st.markdown(
            "### 🔴 Principales faltantes"
        )

        faltantes = datos[
            datos["TipoDiferencia"]
            .astype(str)
            == "FALTANTE"
        ].copy()

        if not faltantes.empty:

            faltantes = faltantes.sort_values(
                "ValorFaltante",
                ascending=False
            )

            st.dataframe(
                faltantes[
                    [
                        "Producto",
                        "StockSistema",
                        "StockFisico",
                        "Diferencia",
                        "CostoUnitario",
                        "ValorFaltante",
                        "Usuario"
                    ]
                ].head(20),
                use_container_width=True,
                hide_index=True
            )

        st.markdown(
            "### 🔵 Principales sobrantes"
        )

        sobrantes = datos[
            datos["TipoDiferencia"]
            .astype(str)
            == "SOBRANTE"
        ].copy()

        if not sobrantes.empty:

            sobrantes = sobrantes.sort_values(
                "ValorSobrante",
                ascending=False
            )

            st.dataframe(
                sobrantes[
                    [
                        "Producto",
                        "StockSistema",
                        "StockFisico",
                        "Diferencia",
                        "CostoUnitario",
                        "ValorSobrante",
                        "Usuario"
                    ]
                ].head(20),
                use_container_width=True,
                hide_index=True
            )

        st.markdown(
            "### 📋 Detalle completo"
        )

        st.dataframe(
            datos,
            use_container_width=True,
            hide_index=True
        )

        csv = datos.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            "⬇️ Descargar detalle CSV",
            csv,
            file_name=f"{id_sesion}.csv",
            mime="text/csv",
            use_container_width=True
        )

    footer()


# ============================================================
# ADMINISTRACIÓN
# ============================================================

def pantalla_admin():

    header()

    if st.session_state.rol != "ADMIN":

        st.error(
            "No tienes permisos para acceder."
        )

        return

    st.subheader(
        "⚙️ Administración"
    )

    tab1, tab2, tab3 = st.tabs(
        [
            "👥 Usuarios",
            "📦 Inventario",
            "📋 Sesiones"
        ]
    )

    # --------------------------------------------------------
    # USUARIOS
    # --------------------------------------------------------

    with tab1:

        usuarios = cargar_usuarios()

        st.dataframe(
            usuarios,
            use_container_width=True,
            hide_index=True
        )

        st.markdown(
            "### Crear usuario"
        )

        with st.form("nuevo_usuario"):

            usuario = st.text_input(
                "Usuario"
            )

            nombre = st.text_input(
                "Nombre completo"
            )

            rol = st.selectbox(
                "Rol",
                [
                    "CONTADOR",
                    "ADMIN"
                ]
            )

            password = st.text_input(
                "Contraseña",
                type="password"
            )

            estado = st.selectbox(
                "Estado",
                [
                    "ACTIVO",
                    "INACTIVO"
                ]
            )

            guardar = st.form_submit_button(
                "Crear usuario",
                use_container_width=True
            )

            if guardar:

                if not usuario or not password:

                    st.error(
                        "Usuario y contraseña son obligatorios."
                    )

                else:

                    existe = usuarios[
                        usuarios["Usuario"]
                        .astype(str)
                        .str.lower()
                        ==
                        usuario.lower()
                    ]

                    if not existe.empty:

                        st.error(
                            "El usuario ya existe."
                        )

                    else:

                        worksheet = obtener_hoja(
                            "Usuarios"
                        )

                        worksheet.append_row(
                            [
                                usuario,
                                nombre,
                                rol,
                                password,
                                estado
                            ],
                            value_input_option="USER_ENTERED"
                        )

                        st.cache_data.clear()

                        st.success(
                            "Usuario creado."
                        )

                        st.rerun()

    # --------------------------------------------------------
    # INVENTARIO
    # --------------------------------------------------------

    with tab2:

        inventario = cargar_inventario()

        st.write(
            f"Productos registrados: **{len(inventario):,}**"
        )

        st.dataframe(
            inventario,
            use_container_width=True,
            hide_index=True
        )

    # --------------------------------------------------------
    # SESIONES
    # --------------------------------------------------------

    with tab3:

        sesiones = cargar_sesiones()

        st.dataframe(
            sesiones,
            use_container_width=True,
            hide_index=True
        )

    footer()


# ============================================================
# CARGA INICIAL
# ============================================================

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if "pagina" not in st.session_state:
    st.session_state.pagina = "Inicio"

if "sesion_actual" not in st.session_state:
    st.session_state.sesion_actual = None

if "codigo_pendiente" not in st.session_state:
    st.session_state.codigo_pendiente = None

if "producto_pendiente" not in st.session_state:
    st.session_state.producto_pendiente = None

if "modo_inventario" not in st.session_state:
    st.session_state.modo_inventario = "scanner"


# ============================================================
# PREPARAR SHEETS
# ============================================================

try:

    preparar_hojas()

except Exception as e:

    st.error(
        "No se pudo conectar con Google Sheets."
    )

    st.exception(e)

    st.stop()


# ============================================================
# LOGIN
# ============================================================

if not st.session_state.autenticado:

    pantalla_login()

    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        f"""
        <div style="text-align:center;padding:10px;">
            <div style="font-size:40px;">📦</div>
            <h2 style="margin:0;">
                TIENDAS PREMIUM
            </h2>
            <small>
                Inventario
            </small>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("---")

    st.write(
        f"👤 **{st.session_state.nombre_usuario}**"
    )

    st.caption(
        f"Rol: {st.session_state.rol}"
    )

    st.markdown("---")

    opciones_menu = [
        "Inicio",
        "Sesión",
        "Inventario",
        "Resultados"
    ]

    if st.session_state.rol == "ADMIN":

        opciones_menu.append(
            "Administración"
        )

    pagina = st.radio(
        "Navegación",
        opciones_menu,
        index=opciones_menu.index(
            st.session_state.pagina
        )
        if st.session_state.pagina in opciones_menu
        else 0
    )

    st.session_state.pagina = pagina

    st.markdown("---")

    if st.button(
        "🚪 Cerrar sesión",
        use_container_width=True
    ):

        for clave in list(
            st.session_state.keys()
        ):

            del st.session_state[clave]

        st.rerun()


# ============================================================
# ROUTER
# ============================================================

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

import streamlit as st
import pandas as pd
import gspread
import hashlib
import hmac
import secrets
import math
import json
import zipfile
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
RUC = "20612107786"
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
    "ValorFaltantes", "ValorSobrantes", "DesfaseNeto", "ExactitudInventario", "Estado", "CoberturaInventario", "ProductosPendientes", "CerosVerificados", "NoLocalizados", "ObservacionCierre"
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

# ETAPA 3 — ZONAS DE TRABAJO (sin asignar productos de antemano)
ZONAS_PREDETERMINADAS = ["Góndola Pared Derecha", "Góndola Central 1", "Góndola Central 2", "Máquinas de Frío y Bebidas", "Mostrador", "Góndola de Snacks", "Bolsas de Regalo"]
HOJA_ZONAS = "ZonasInventario"
HEADERS_ZONAS = ["IdSesion", "Zona", "Responsable", "Estado", "FechaInicio", "FechaFin", "ActualizadoPor"]
HOJA_CONTEOS_ZONA = "ConteosPorZona"
HEADERS_CONTEOS_ZONA = ["IdSesion", "FechaHora", "Usuario", "NombreUsuario", "Zona", "CodigoBarras", "CodigoProducto", "Producto", "Categoria", "Sucursal", "StockSistema", "StockFisico", "CostoUnitario", "MetodoConteo", "Observacion", "TipoRegistro", "IdRegistro"]

# =========================================================
# SISTEMA DE DISEÑO TIENDAS PREMIUM
# Mismo sistema visual que la app de Asistencia (colores, tipografía, sidebar,
# tarjetas, botones, login, navegación móvil). Un solo bloque ordenado: reemplaza
# las capas de CSS superpuestas que tenía esta app. No altera lógica ni Google Sheets.
# =========================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');

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

    .market-header {
        background-color: #FFFFFF;
        padding: 20px 24px;
        border-radius: 8px;
        border: 1px solid #E5E7EB;
        border-left: 4px solid #EC3237;
        margin-bottom: 24px;
    }
    .market-header h1 {
        color: #111827 !important;
        margin: 0;
        font-size: 1.3rem !important;
        font-weight: 600 !important;
        letter-spacing: -0.3px;
    }
    .market-header p {
        color: #6B7280;
        margin: 4px 0 0 0;
        font-size: 0.85rem;
        font-weight: 400;
    }

    .info-card {
        background-color: #FFFFFF;
        padding: 18px 20px;
        border-radius: 8px;
        border: 1px solid #E5E7EB;
        margin-bottom: 15px;
    }
    .info-label {
        color: #6B7280;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }
    .info-value {
        color: #111827;
        font-size: 1.4rem;
        font-weight: 700;
        margin-top: 4px;
    }

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

    div[data-testid="stForm"], div[data-testid="stExpander"] {
        border-radius: 8px !important;
        border: 1px solid #E5E7EB !important;
        background-color: #FFFFFF !important;
        padding: 20px !important;
        box-shadow: none !important;
    }

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
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
:root{
  --tp-red:#EC3237; --tp-red-dk:#C9262B; --tp-red-soft:#FDECEC;
  --tp-ink:#0F172A; --tp-ink-2:#334155; --tp-mute:#64748B;
  --tp-bg:#F3F4F7; --tp-surface:#FFFFFF; --tp-line:#E3E6EC;
  --tp-ok:#0B8F57; --tp-ok-soft:#E3F6EC; --tp-warn:#B45309; --tp-warn-soft:#FEF3C7;
  --tp-bad:#B42318; --tp-bad-soft:#FEE4E2; --tp-info:#1D4ED8; --tp-info-soft:#E0EAFF;
  --tp-r-sm:10px; --tp-r-md:14px; --tp-r-lg:20px;
  --tp-sh-1:0 1px 2px rgba(15,23,42,.05),0 1px 3px rgba(15,23,42,.04);
  --tp-sh-2:0 8px 24px -8px rgba(15,23,42,.14);
}
.stApp{background:var(--tp-bg);}
.block-container{max-width:1240px;padding-top:4.2rem;padding-bottom:3rem;}
#MainMenu,footer,[data-testid="stDecoration"],[data-testid="stAppDeployButton"],[data-testid="stMainMenu"],.stDeployButton{visibility:hidden;display:none;}
header[data-testid="stHeader"]{background:transparent!important;}
[data-testid="stToolbar"]{visibility:visible!important;display:flex!important;}
/* Botón para abrir el menú de vistas (siempre visible) */
[data-testid="stExpandSidebarButton"],[data-testid="stSidebarCollapsedControl"],[data-testid="collapsedControl"]{
  display:flex!important;visibility:visible!important;opacity:1!important;z-index:1000;
  position:fixed;top:12px;left:12px;width:46px;height:46px;align-items:center;justify-content:center;
  background:var(--tp-ink)!important;border-radius:14px;box-shadow:var(--tp-sh-2);}
[data-testid="stExpandSidebarButton"] *,[data-testid="stSidebarCollapsedControl"] *,[data-testid="collapsedControl"] *{color:#fff!important;fill:#fff!important;}
[data-testid="stExpandSidebarButton"]:hover,[data-testid="stSidebarCollapsedControl"]:hover{background:var(--tp-red)!important;}
[data-testid="stSidebarCollapseButton"] button,[data-testid="stSidebarCollapseButton"] *{color:#AEB8CC!important;}
h1,h2,h3,h4,h5{color:var(--tp-ink);letter-spacing:-.01em;}
h5{font-size:1.02rem!important;font-weight:650!important;margin:.4rem 0 .6rem!important;}
[data-testid="stMetricValue"],.info-value,.tp-kpi-val{font-variant-numeric:tabular-nums;}
:focus-visible{outline:3px solid rgba(236,50,55,.35)!important;outline-offset:2px;border-radius:8px;}

/* Encabezado de página */
.market-header{position:relative;background:var(--tp-surface);border:1px solid var(--tp-line);border-left:1px solid var(--tp-line);
  border-radius:var(--tp-r-lg);padding:22px 26px 20px;margin-bottom:22px;box-shadow:var(--tp-sh-1);}
.market-header::before{content:"";position:absolute;left:26px;top:0;width:36px;height:4px;background:var(--tp-red);border-radius:0 0 4px 4px;}
.market-header h1{font-size:1.45rem!important;font-weight:700!important;margin-top:6px!important;color:var(--tp-ink)!important;}
.market-header p{font-size:.9rem;color:var(--tp-mute);}

/* Tarjetas y contenedores */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]){border-radius:var(--tp-r-md);}
div[data-testid="stVerticalBlockBorderWrapper"]{border-color:var(--tp-line)!important;background:var(--tp-surface);box-shadow:var(--tp-sh-1);}
.info-card,.cal-card{border-radius:var(--tp-r-md)!important;border:1px solid var(--tp-line)!important;box-shadow:var(--tp-sh-1);}
div[data-testid="stForm"],div[data-testid="stExpander"]{border-radius:var(--tp-r-md)!important;border:1px solid var(--tp-line)!important;box-shadow:var(--tp-sh-1)!important;}
[data-testid="stMetric"]{background:var(--tp-surface);border:1px solid var(--tp-line);border-radius:var(--tp-r-md);padding:16px 18px;box-shadow:var(--tp-sh-1);}
[data-testid="stMetricLabel"] p{font-size:.78rem!important;font-weight:600;color:var(--tp-mute)!important;}
[data-testid="stMetricValue"]{font-weight:700;color:var(--tp-ink);}

/* Botones */
.stButton>button,.stDownloadButton>button,.stFormSubmitButton>button{min-height:46px;border-radius:var(--tp-r-sm)!important;font-weight:600!important;font-size:.9rem!important;
  box-shadow:var(--tp-sh-1);transition:transform .12s ease,box-shadow .12s ease,background-color .12s ease!important;}
.stButton>button:hover{transform:translateY(-1px);box-shadow:var(--tp-sh-2);}
.stButton>button:active{transform:translateY(0) scale(.98);}
.stDownloadButton>button{background:var(--tp-surface)!important;color:var(--tp-ink)!important;border:1px solid var(--tp-line)!important;}
.stDownloadButton>button:hover{border-color:var(--tp-ink)!important;background:#F8FAFC!important;}
.btn-ingreso>button,.btn-salida>button{min-height:64px!important;font-size:1.05rem!important;border-radius:var(--tp-r-md)!important;}
.btn-ingreso>button{background:var(--tp-ok)!important;}
.btn-ingreso>button:hover{background:#087548!important;}

/* Campos */
[data-baseweb="input"],[data-baseweb="select"]>div,[data-baseweb="textarea"],.stDateInput>div>div,.stNumberInput>div>div{border-radius:var(--tp-r-sm)!important;}
[data-baseweb="input"],[data-baseweb="textarea"],[data-baseweb="select"]>div{border:1px solid var(--tp-line)!important;background:var(--tp-surface)!important;}
[data-baseweb="input"]:focus-within,[data-baseweb="textarea"]:focus-within,[data-baseweb="select"]>div:focus-within{border-color:var(--tp-red)!important;box-shadow:0 0 0 3px rgba(236,50,55,.15)!important;}
[data-testid="stWidgetLabel"] p{font-size:.82rem;font-weight:600;color:var(--tp-ink-2);}

/* Pestañas */
.stTabs [data-baseweb="tab-list"]{gap:6px;overflow-x:auto;scrollbar-width:none;border-bottom:1px solid var(--tp-line);}
.stTabs [data-baseweb="tab-list"]::-webkit-scrollbar{display:none;}
.stTabs [data-baseweb="tab"]{height:46px;padding:0 14px;font-weight:600;color:var(--tp-mute);white-space:nowrap;}
.stTabs [aria-selected="true"]{color:var(--tp-ink)!important;}
.stTabs [data-baseweb="tab-highlight"]{background:var(--tp-red)!important;height:3px;border-radius:3px;}

/* Tablas, alertas, progreso */
[data-testid="stDataFrame"]{border:1px solid var(--tp-line);border-radius:var(--tp-r-md);overflow:hidden;box-shadow:var(--tp-sh-1);}
[data-testid="stAlert"]{border-radius:var(--tp-r-md);border:1px solid var(--tp-line);}
.stProgress>div>div>div>div{background:var(--tp-red)!important;border-radius:999px;}
.stProgress>div>div>div{border-radius:999px;}

/* Barra lateral como navegación */
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0F172A 0%,#111C33 100%)!important;border-right:none;}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"]{display:none;}
[data-testid="stSidebar"] [role="radiogroup"]{gap:2px;}
[data-testid="stSidebar"] [role="radiogroup"] label{position:relative;padding:10px 14px 10px 16px;border-radius:12px;cursor:pointer;transition:background .12s ease;}
[data-testid="stSidebar"] [role="radiogroup"] label>div:first-child{display:none;}
[data-testid="stSidebar"] [role="radiogroup"] label p{font-size:.88rem;font-weight:500;color:#AEB8CC!important;}
[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:rgba(255,255,255,.06);}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:rgba(236,50,55,.16);}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked)::before{content:"";position:absolute;left:0;top:10px;bottom:10px;width:3px;border-radius:3px;background:var(--tp-red);}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p{color:#FFFFFF!important;font-weight:650;}
.tp-user{display:flex;align-items:center;gap:12px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.08);padding:12px;border-radius:14px;margin-bottom:18px;}
.tp-user b{display:block;font-size:.84rem;color:#fff!important;line-height:1.25;}
.tp-user span{font-size:.7rem;color:#8EA0BE!important;}
.btn-logout>button{border-radius:12px!important;border:1px solid rgba(255,255,255,.18)!important;box-shadow:none!important;}

/* Componentes reutilizables */
.tp-avatar{flex:0 0 auto;width:40px;height:40px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;
  background:var(--tp-red);color:#fff!important;font-weight:700;font-size:.85rem;letter-spacing:.02em;}
.tp-chip{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;font-size:.74rem;font-weight:650;line-height:1.5;}
.tp-chip::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor;}
.tp-chip.ok{background:var(--tp-ok-soft);color:var(--tp-ok);} .tp-chip.warn{background:var(--tp-warn-soft);color:var(--tp-warn);}
.tp-chip.bad{background:var(--tp-bad-soft);color:var(--tp-bad);} .tp-chip.info{background:var(--tp-info-soft);color:var(--tp-info);}
.tp-chip.neutral{background:#EEF1F5;color:var(--tp-ink-2);}
.tp-kpi{background:var(--tp-surface);border:1px solid var(--tp-line);border-radius:var(--tp-r-md);padding:16px 18px;box-shadow:var(--tp-sh-1);}
.tp-kpi-lbl{font-size:.78rem;font-weight:600;color:var(--tp-mute);}
.tp-kpi-val{font-size:1.7rem;font-weight:700;color:var(--tp-ink);margin-top:2px;}
.tp-kpi-sub{font-size:.78rem;color:var(--tp-mute);margin-top:2px;}
.app-footer{margin-top:40px;padding:22px 0;border-top:1px solid var(--tp-line);color:var(--tp-mute);font-size:.78rem;line-height:1.7;text-align:center;}

/* Pantallas medianas y celulares */
@media (max-width:900px){
  .block-container{padding:4.2rem .9rem 5rem;}
  .market-header{padding:18px 18px 16px;border-radius:var(--tp-r-md);margin-bottom:16px;}
  .market-header::before{left:18px;}
  .market-header h1{font-size:1.2rem!important;}
}
@media (max-width:640px){
  html,body,input,select,textarea{font-size:16px;}
  [data-testid="stHorizontalBlock"]{gap:.75rem!important;}
  .stButton>button,.stDownloadButton>button{min-height:50px;width:100%;}
  .btn-ingreso>button,.btn-salida>button{min-height:70px!important;}
  [data-testid="stMetric"],.tp-kpi{padding:14px 16px;}
  .cal-card{overflow-x:auto;-webkit-overflow-scrolling:touch;padding:14px!important;}
  .cal-table{min-width:540px;}
  .boleta-container{padding:16px!important;overflow-x:auto;}
  [data-testid="stDataFrame"]{overflow-x:auto;}
  .stTabs [data-baseweb="tab"]{padding:0 10px;font-size:.84rem;}
}
@supports (padding:max(0px)){.block-container{padding-bottom:max(3rem,env(safe-area-inset-bottom));}}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important;}}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* Barra lateral clara */
[data-testid="stSidebar"]{background:#FFFFFF!important;border-right:1px solid var(--tp-line)!important;}
[data-testid="stSidebar"] *{color:var(--tp-ink)!important;}
[data-testid="stSidebar"] [role="radiogroup"] label>div:not(:has([data-testid="stMarkdownContainer"])){display:none!important;}
[data-testid="stSidebar"] [role="radiogroup"] label p{color:var(--tp-ink-2)!important;font-weight:550;}
[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:#F3F4F7;}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:var(--tp-red-soft);}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p{color:var(--tp-red-dk)!important;font-weight:700;}
[data-testid="stSidebarCollapseButton"] *{color:var(--tp-mute)!important;}
.tp-user{background:#F6F7FA;border:1px solid var(--tp-line);}
.tp-user b{color:var(--tp-ink)!important;} .tp-user span{color:var(--tp-mute)!important;}
[data-testid="stSidebar"] .tp-avatar{color:#fff!important;}
.tp-avatar{width:46px;height:46px;object-fit:cover;box-shadow:0 0 0 2px #fff,0 0 0 4px var(--tp-red);}
.tp-brand{padding:2px 2px 16px;} .tp-brand-name{font-weight:800;font-size:1rem;letter-spacing:-.01em;}
[data-testid="stSidebar"] .tp-brand-name span{color:var(--tp-red)!important;} .tp-brand-sub{font-size:.72rem;color:var(--tp-mute)!important;}
.btn-logout>button{background:#fff!important;border:1px solid var(--tp-line)!important;}
.btn-logout>button:hover{background:var(--tp-red-soft)!important;border-color:var(--tp-red)!important;}
/* Marcación: tarjeta de estado y lista */
.tp-hero{box-sizing:border-box;min-height:132px;background:var(--tp-surface);border:1px solid var(--tp-line);border-radius:var(--tp-r-lg);padding:18px 20px;box-shadow:var(--tp-sh-1);}
.tp-hero-top{display:flex;gap:14px;align-items:center;margin-bottom:16px;}
.tp-hero-hi{font-weight:700;font-size:1.08rem;margin-bottom:5px;}
.tp-prog-lbl{display:flex;justify-content:space-between;font-size:.76rem;color:var(--tp-mute);font-weight:600;margin-bottom:6px;}
.tp-prog{height:8px;background:#EEF1F5;border-radius:999px;overflow:hidden;}
.tp-prog i{display:block;height:100%;background:linear-gradient(90deg,var(--tp-red),#F26B6F);border-radius:999px;}
.tp-row{display:flex;align-items:center;gap:12px;background:var(--tp-surface);border:1px solid var(--tp-line);border-radius:14px;padding:12px 14px;margin-bottom:8px;}
.tp-row-time{font-weight:700;font-variant-numeric:tabular-nums;min-width:48px;}
.tp-row-main{flex:1;min-width:0;} .tp-row-main b{display:block;font-size:.9rem;}
.tp-row-main span{display:block;font-size:.78rem;color:var(--tp-mute);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.tp-chips{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end;}
/* Barra inferior (celular) */
.st-key-tp_bottomnav{display:none;}
@media (max-width:900px){
  .st-key-tp_bottomnav{display:block;position:fixed;left:0;right:0;bottom:0;z-index:999;background:rgba(255,255,255,.96);backdrop-filter:blur(10px);
    border-top:1px solid var(--tp-line);padding:6px 8px calc(6px + env(safe-area-inset-bottom,0px));box-shadow:0 -8px 24px -12px rgba(15,23,42,.25);}
  .st-key-tp_bottomnav [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:4px!important;}
  .st-key-tp_bottomnav [data-testid="stColumn"],.st-key-tp_bottomnav [data-testid="column"]{min-width:0!important;flex:1 1 0!important;width:auto!important;}
  .st-key-tp_bottomnav button{background:transparent!important;color:var(--tp-mute)!important;box-shadow:none!important;border:none!important;min-height:56px!important;padding:4px 2px!important;border-radius:12px!important;}
  .st-key-tp_bottomnav button>div{display:flex;flex-direction:column;align-items:center;gap:2px;}
  .st-key-tp_bottomnav button p{font-size:.68rem!important;font-weight:650!important;margin:0;color:inherit!important;}
  .st-key-tp_bottomnav button[kind="primary"],.st-key-tp_bottomnav [data-testid="stBaseButton-primary"]{background:var(--tp-red-soft)!important;color:var(--tp-red-dk)!important;}
  .st-key-tp_bottomnav button:hover{transform:none!important;}
  .tp-row{padding:10px 12px;}
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* Ajustes finales: botón de menú, cerrar sesión y opciones */
[data-testid="stSidebar"] [role="radiogroup"] label>*:not(input):not([data-testid="stMarkdownContainer"]):not(:has([data-testid="stMarkdownContainer"])){display:none!important;}
[data-testid="stSidebar"] .stButton>button{background:#fff!important;border:1.5px solid var(--tp-red)!important;box-shadow:none!important;}
[data-testid="stSidebar"] .stButton>button *{color:#111827!important;font-weight:650;}
[data-testid="stSidebar"] .stButton>button:hover{background:var(--tp-red)!important;}
[data-testid="stSidebar"] .stButton>button:hover *{color:#111827!important;}
[data-testid="stSidebar"] .stButton>button{color:#111827!important;}
[data-testid="stExpandSidebarButton"],[data-testid="stSidebarCollapsedControl"],[data-testid="collapsedControl"]{background:#fff!important;border:1.5px solid var(--tp-red)!important;}
[data-testid="stExpandSidebarButton"] *,[data-testid="stSidebarCollapsedControl"] *,[data-testid="collapsedControl"] *{color:var(--tp-red)!important;fill:var(--tp-red)!important;}
[data-testid="stExpandSidebarButton"] button,[data-testid="stSidebarCollapsedControl"] button{background:transparent!important;}
[data-testid="stExpandSidebarButton"]:hover,[data-testid="stSidebarCollapsedControl"]:hover,[data-testid="collapsedControl"]:hover{background:var(--tp-red)!important;}
[data-testid="stExpandSidebarButton"]:hover *,[data-testid="stSidebarCollapsedControl"]:hover *,[data-testid="collapsedControl"]:hover *{color:#fff!important;fill:#fff!important;}
/* Tarjetas de solicitud + línea de tiempo */
.tp-card{background:var(--tp-surface);border:1px solid var(--tp-line);border-radius:16px;padding:16px 18px;margin-bottom:12px;box-shadow:var(--tp-sh-1);}
.tp-card-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;}
.tp-card-title{font-weight:700;font-size:.95rem;} .tp-card-sub{font-size:.76rem;color:var(--tp-mute);margin-top:2px;}
.tp-card-body{font-size:.86rem;color:var(--tp-ink-2);margin:10px 0 14px;line-height:1.55;}
.tp-resp{background:#F6F7FA;border-left:3px solid var(--tp-red);border-radius:8px;padding:10px 12px;font-size:.82rem;margin-top:12px;color:var(--tp-ink-2);}
.tp-tl{display:flex;}
.tp-tl-step{flex:1;position:relative;text-align:center;font-size:.7rem;font-weight:600;color:var(--tp-mute);}
.tp-tl-step::before{content:"";position:relative;z-index:1;display:block;width:14px;height:14px;margin:0 auto 6px;border-radius:50%;background:#fff;border:2px solid #CBD2DC;}
.tp-tl-step::after{content:"";position:absolute;top:6px;left:-50%;width:100%;height:2px;background:#CBD2DC;}
.tp-tl-step:first-child::after{display:none;}
.tp-tl-step.done{color:var(--tp-ink-2);} .tp-tl-step.done::before{background:var(--tp-ok);border-color:var(--tp-ok);} .tp-tl-step.done::after{background:var(--tp-ok);}
.tp-tl-step.now{color:var(--tp-warn);} .tp-tl-step.now::before{background:#F59E0B;border-color:#F59E0B;box-shadow:0 0 0 4px rgba(245,158,11,.2);} .tp-tl-step.now::after{background:var(--tp-ok);}
.tp-tl-step.bad{color:var(--tp-bad);} .tp-tl-step.bad::before{background:var(--tp-bad);border-color:var(--tp-bad);} .tp-tl-step.bad::after{background:var(--tp-bad);}
.tp-notif{display:flex;align-items:center;justify-content:space-between;gap:8px;background:var(--tp-warn-soft);border-radius:12px;padding:9px 12px;margin:-6px 0 14px;font-size:.78rem;font-weight:650;}
[data-testid="stSidebar"] .tp-notif,[data-testid="stSidebar"] .tp-notif *{color:var(--tp-warn)!important;}
/* Tabla en PC, tarjetas en celular */
.st-key-vista_tarjetas{display:none;}
@media (max-width:900px){.st-key-vista_tabla{display:none;}.st-key-vista_tarjetas{display:block;}}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
.tp-card.flat{border:none;box-shadow:none;padding:0;margin:0 0 8px;}
[class*="st-key-ap_"] button{background:var(--tp-ok)!important;color:#fff!important;border:none!important;}
[class*="st-key-ap_"] button:hover{background:#087548!important;}
[class*="st-key-rec_"] button{background:#fff!important;border:1.5px solid var(--tp-red)!important;}
[class*="st-key-rec_"] button *{color:var(--tp-red)!important;}
[class*="st-key-rec_"] button:hover{background:var(--tp-red-soft)!important;}
[class*="st-key-ap_"] button *{color:#fff!important;}
.tp-sec{display:flex;justify-content:space-between;align-items:center;gap:10px;margin:6px 0 16px;}
.tp-sec-title{font-size:1.12rem;font-weight:700;color:var(--tp-ink);} .tp-sec-sub{font-size:.8rem;color:var(--tp-mute);}
.tp-op-head{display:flex;align-items:center;gap:12px;margin-bottom:16px;} .tp-op-head .tp-chip{margin-left:auto;}
.tp-mgrid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-bottom:14px;}
.tp-m{background:#F6F7FA;border-radius:12px;padding:12px 14px;}
.tp-m-l{font-size:.66rem;font-weight:700;color:var(--tp-mute);text-transform:uppercase;letter-spacing:.07em;}
.tp-m-v{font-size:1.05rem;font-weight:700;margin-top:5px;color:var(--tp-ink);font-variant-numeric:tabular-nums;} .tp-m-v.pos{color:var(--tp-ok);}
.tp-m .tp-prog{margin-top:9px;height:6px;}
.tp-ngrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:10px;}
.tp-note{border:1px solid var(--tp-line);border-radius:12px;padding:12px 14px;}
.tp-note-t{font-size:.66rem;font-weight:700;color:var(--tp-mute);text-transform:uppercase;letter-spacing:.07em;margin-bottom:6px;}
.tp-note ul{margin:0;padding-left:16px;font-size:.84rem;color:var(--tp-ink-2);line-height:1.8;} .tp-note li.mute{color:var(--tp-mute);list-style:none;margin-left:-16px;}
@media (max-width:900px){.tp-mgrid{grid-template-columns:repeat(2,minmax(0,1fr));}}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* Quita el espacio vacío superior: los bloques de estilo y el iframe invisible no deben ocupar lugar */
[data-testid="stElementContainer"]:has(style),.element-container:has(style),[data-testid="stElementContainer"]:has(iframe[height="0"]),.element-container:has(iframe[height="0"]){display:none!important;}
.stApp:has([data-testid="stSidebar"][aria-expanded="true"]) .block-container{padding-top:3.2rem;}
[data-testid="stToolbarActions"],[data-testid="stAppDeployButton"]{display:none!important;}
.tp-steps{margin:2px 0 14px;padding:0;list-style:none;counter-reset:paso;}
.tp-steps li{counter-increment:paso;position:relative;padding:5px 0 5px 34px;font-size:.84rem;line-height:1.45;color:var(--tp-ink-2);}
.tp-steps li::before{content:counter(paso);position:absolute;left:0;top:4px;width:23px;height:23px;border-radius:50%;background:var(--tp-red-soft);color:var(--tp-red-dk);font-weight:700;font-size:.74rem;display:flex;align-items:center;justify-content:center;}
.tp-steps-t{font-size:.7rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--tp-mute);margin:8px 0 4px;display:flex;gap:8px;align-items:center;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
.tp-kpi.al-bad{border-left:4px solid var(--tp-bad);} .tp-kpi.al-warn{border-left:4px solid #F59E0B;} .tp-kpi.al-info{border-left:4px solid var(--tp-info);} .tp-kpi.al-ok{border-left:4px solid var(--tp-ok);}
.tp-banner{display:flex;align-items:center;gap:16px;border-radius:20px;padding:20px 24px;border:1px solid var(--tp-line);box-shadow:var(--tp-sh-1);}
.tp-banner.ok{background:linear-gradient(120deg,#E3F6EC,#F4FBF7);border-color:#BFE8D2;} .tp-banner.warn{background:linear-gradient(120deg,#FEF3C7,#FFFBEB);border-color:#F8DE95;} .tp-banner.bad{background:linear-gradient(120deg,#FEE4E2,#FFF5F4);border-color:#F9C4C0;}
.tp-banner b{font-size:1.1rem;color:var(--tp-ink);display:block;} .tp-banner span.s{font-size:.84rem;color:var(--tp-ink-2);}
.tp-al-ico{flex:0 0 auto;width:42px;height:42px;border-radius:13px;display:flex;align-items:center;justify-content:center;}
.tp-al-ico.bad{background:var(--tp-bad-soft);color:var(--tp-bad);} .tp-al-ico.warn{background:var(--tp-warn-soft);color:var(--tp-warn);} .tp-al-ico.info{background:var(--tp-info-soft);color:var(--tp-info);} .tp-al-ico.ok{background:var(--tp-ok-soft);color:var(--tp-ok);}
/* Saludo de cumpleaños */
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
.stFormSubmitButton>button{background:linear-gradient(135deg,#EC3237,#C9262B)!important;border:none!important;box-shadow:0 14px 26px -12px rgba(236,50,55,.6);}
.stFormSubmitButton>button *{color:#fff!important;font-weight:700;}
.tp-callout{display:flex;gap:12px;align-items:flex-start;border-radius:14px;padding:14px 16px;margin:6px 0 14px;font-size:.88rem;line-height:1.55;color:var(--tp-ink-2);border:1px solid var(--tp-line);}
.tp-callout.info{background:var(--tp-info-soft);border-color:#C7D8FB;} .tp-callout.ok{background:var(--tp-ok-soft);border-color:#BFE8D2;} .tp-callout.warn{background:var(--tp-warn-soft);border-color:#F8DE95;}
.tp-callout i{flex:0 0 auto;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-style:normal;font-weight:800;font-size:.8rem;background:#fff;}
.tp-callout.info i{color:var(--tp-info);} .tp-callout.ok i{color:var(--tp-ok);} .tp-callout.warn i{color:var(--tp-warn);}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* Transición entre pestañas: la página entra suavemente */
@keyframes tpPgA{from{opacity:.5;transform:translateY(12px);}to{opacity:1;transform:none;}}
@keyframes tpPgB{from{opacity:.5;transform:translateY(12px);}to{opacity:1;transform:none;}}
.stApp:has(.tp-pg-a) .block-container{animation:tpPgA .45s cubic-bezier(.2,.7,.2,1);}
.stApp:has(.tp-pg-b) .block-container{animation:tpPgB .45s cubic-bezier(.2,.7,.2,1);}
[data-testid="stElementContainer"]:has(.tp-pg-a),[data-testid="stElementContainer"]:has(.tp-pg-b),.element-container:has(.tp-pg-a),.element-container:has(.tp-pg-b){display:none!important;}
[data-testid="stStatusWidget"]{display:none!important;}
[data-stale="true"],.stale-element{opacity:.45!important;transition:opacity .25s ease;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
[data-testid="stSidebar"] a.tp-negosy{display:flex;align-items:center;justify-content:space-between;gap:10px;background:linear-gradient(135deg,#0F172A 0%,#1B2A4A 100%);
  border-radius:14px;padding:12px 16px;margin:6px 0 12px;text-decoration:none;box-shadow:var(--tp-sh-1);transition:transform .12s ease,box-shadow .12s ease;}
[data-testid="stSidebar"] a.tp-negosy:hover{transform:translateY(-1px);box-shadow:var(--tp-sh-2);}
[data-testid="stSidebar"] a.tp-negosy .tp-negosy-t{display:block;font-weight:800;font-size:.95rem;letter-spacing:.01em;color:#FFFFFF!important;}
[data-testid="stSidebar"] a.tp-negosy .tp-negosy-s{display:block;font-size:.7rem;color:#9FB0CC!important;margin-top:1px;}
[data-testid="stSidebar"] a.tp-negosy svg{flex:0 0 auto;color:#FF8A8E!important;stroke:#FF8A8E!important;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* Acciones generales: superficie clara, acento corporativo y contraste accesible. */
.stButton > button:not([kind="primary"]):not([data-testid="stBaseButton-primary"]),
.stDownloadButton > button:not([kind="primary"]) {
  background:#FFFFFF !important; color:#334155 !important;
  border:1px solid #D9E0E9 !important; border-radius:11px !important;
  box-shadow:0 2px 5px rgba(24,39,75,.05) !important;
}
.stButton > button:not([kind="primary"]):hover,
.stDownloadButton > button:not([kind="primary"]):hover {
  background:#FFF4F4 !important; border-color:#EC3237 !important;
  color:#C8252B !important; box-shadow:0 4px 10px rgba(236,50,55,.09) !important;
}
.stButton > button:not([kind="primary"]) *,
.stDownloadButton > button:not([kind="primary"]) * {color:inherit !important;}
/* Botón de acción principal: rojo de Tiendas Premium, no negro. */
.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"] {
  background:#EC3237 !important; border:1px solid #EC3237 !important;
  color:#FFFFFF !important; border-radius:11px !important;
  box-shadow:0 3px 9px rgba(236,50,55,.17) !important;
}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="stBaseButton-primary"]:hover {
  background:#D6282D !important; border-color:#D6282D !important;
}
.stButton > button[kind="primary"] *,
.stButton > button[data-testid="stBaseButton-primary"] * {color:#FFFFFF !important;}
/* En formularios, guardar/confirmar conserva el acento rojo existente. */
.stFormSubmitButton > button {border-radius:11px !important;}
/* Se respetan los botones de ingreso/salida, chatbot, menú lateral y navegación móvil. */
.btn-ingreso > button, .btn-ingreso button {background:#00A959 !important;color:#fff !important;border-color:#00A959 !important;}
.btn-salida > button, .btn-salida button {background:#EC3237 !important;color:#fff !important;border-color:#EC3237 !important;}
.st-key-tp_chat_fab button {border-radius:50% !important;background-color:#EC3237 !important;}
.st-key-tp_bottomnav button:not([kind="primary"]) {background:transparent !important;border:none !important;box-shadow:none !important;}
/* Acceso a Negosy: visible sin desentonar con la marca. */
[data-testid="stSidebar"] a.tp-negosy {
  background:linear-gradient(120deg,#EC3237 0%,#D52C32 100%) !important;
  border:1px solid #C9272D !important;border-radius:12px !important;
  box-shadow:0 4px 12px rgba(236,50,55,.18) !important;
  transition:transform .15s ease,box-shadow .15s ease !important;
}
[data-testid="stSidebar"] a.tp-negosy:hover {
  transform:translateY(-2px) !important;
  box-shadow:0 7px 17px rgba(236,50,55,.26) !important;
}
[data-testid="stSidebar"] a.tp-negosy .tp-negosy-t {color:#FFFFFF !important;}
[data-testid="stSidebar"] a.tp-negosy .tp-negosy-s {color:#FFE5E6 !important;}
[data-testid="stSidebar"] a.tp-negosy svg {color:#FFFFFF !important;stroke:#FFFFFF !important;}
/* Navegación lateral original: no modificar selección, disposición ni etiquetas. */
</style>
""", unsafe_allow_html=True)

st.markdown(r"""<style>
/* Tablets: controles y tarjetas se acomodan sin desbordar */
@media screen and (max-width: 900px) {
  .main .block-container {max-width:100%!important;padding-left:16px!important;padding-right:16px!important;}
  [data-testid="stMainBlockContainer"] {max-width:100%!important;}
  [data-testid="stHorizontalBlock"] {flex-wrap:wrap!important;}
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {min-width:min(260px,100%)!important;flex:1 1 260px!important;}
  .tp-up-calendar {max-width:100%!important;overflow-x:auto!important;-webkit-overflow-scrolling:touch;}
  .tp-up-calendar table {min-width:850px!important;}
  .tp-shift-detail-wrap {max-width:100%!important;overflow-x:auto!important;-webkit-overflow-scrolling:touch;}
  .tp-cal-grid {grid-template-columns:repeat(3,minmax(0,1fr))!important;}
  .tp-mgrid {grid-template-columns:repeat(2,minmax(0,1fr))!important;}
}
/* Teléfonos: una columna, tipografía legible y acciones táctiles */
@media screen and (max-width: 640px) {
  html,body {max-width:100%;overflow-x:hidden;}
  .main .block-container,[data-testid="stMainBlockContainer"] {padding:64px 12px 36px!important;max-width:100%!important;overflow-x:clip;}
  [data-testid="stHorizontalBlock"] {gap:10px!important;flex-wrap:wrap!important;}
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {flex:1 1 100%!important;min-width:0!important;width:100%!important;}
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] > div {min-width:0!important;}
  [data-testid="stSidebar"] {max-width:min(86vw,320px)!important;}
  [data-testid="stSidebar"] [role="radiogroup"] label {min-height:44px;}
  .market-header {padding:16px!important;margin-bottom:12px!important;}
  .market-header h1 {font-size:1.18rem!important;line-height:1.3!important;}
  .tp-kpi,.cal-card,.boleta-container {max-width:100%;box-sizing:border-box;}
  .tp-kpi-val {font-size:1.4rem!important;}
  .stButton>button,.stDownloadButton>button,.stFormSubmitButton>button {min-height:46px!important;max-width:100%;white-space:normal!important;line-height:1.3!important;}
  [data-baseweb="input"] input,[data-baseweb="textarea"] textarea {font-size:16px!important;}
  [data-testid="stDataFrame"],[data-testid="stDataEditor"] {max-width:100%!important;overflow-x:auto!important;}
  .stTabs [data-baseweb="tab-list"] {overflow-x:auto!important;flex-wrap:nowrap!important;}
  .stTabs [data-baseweb="tab"] {flex-shrink:0!important;}
  .tp-cal-shell {padding:12px!important;margin:8px 0 12px!important;}
  .tp-cal-head {align-items:flex-start!important;gap:8px!important;}
  .tp-cal-head h3 {font-size:1rem!important;}
  .tp-cal-grid {grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:7px!important;}
  .tp-cal-day {min-height:112px!important;border-radius:10px!important;}
  .tp-cal-date {padding:8px!important;}
  .tp-cal-body {padding:9px 8px!important;gap:5px!important;}
  .tp-cal-body b {font-size:.78rem!important;}
  .tp-cal-body span {font-size:.73rem!important;}
  .tp-cal-legend {gap:8px!important;}
  .tp-up-calendar {width:100%!important;overflow-x:auto!important;border-radius:10px!important;}
  .tp-up-calendar table {min-width:820px!important;}
  .tp-up-calendar th.tp-up-person {min-width:145px!important;width:145px!important;}
  .tp-up-calendar thead th:first-child {width:145px!important;}
  .tp-up-calendar th.tp-up-person,.tp-up-calendar thead th:first-child {position:sticky;left:0;z-index:2;background:#fff;box-shadow:2px 0 5px rgba(0,0,0,.05);}
  .tp-up-calendar thead th:first-child {background:#f8fafc;z-index:3;}
  .tp-shift-detail-wrap {width:100%!important;overflow-x:auto!important;border-radius:0!important;}
  table.tp-shift-detail {min-width:950px!important;border-radius:0!important;}
  .tp-mgrid,.tp-id-grid {grid-template-columns:1fr!important;}
  .tp-hb {display:flex!important;flex-wrap:wrap!important;gap:8px!important;}
  .tp-hb-t {flex-basis:100%!important;}
  .tp-lg-hero {padding:16px!important;min-height:0!important;border-radius:16px!important;}
  .tp-lg-h {font-size:1.32rem!important;line-height:1.25!important;}
  .tp-lg-p {font-size:.88rem!important;line-height:1.5!important;}
  .tp-lg-quote {margin-top:12px!important;padding:12px!important;}
  .tp-lg-quote p {font-size:.86rem!important;}
  .tp-lg-who .tp-avatar {width:64px!important;height:64px!important;}
  .tp-lg-t {font-size:1.2rem!important;}
  .tp-lg-note {font-size:.71rem!important;line-height:1.4!important;}
  .st-key-tp_chat_fab {right:10px!important;top:60px!important;}
  .st-key-tp_chat_panel {right:8px!important;top:125px!important;width:calc(100vw - 16px)!important;max-height:65dvh!important;}
}
@media screen and (max-width:380px) {
  .main .block-container,[data-testid="stMainBlockContainer"] {padding-left:9px!important;padding-right:9px!important;}
  .tp-cal-grid {grid-template-columns:1fr!important;}
  .tp-cal-day {min-height:0!important;}
  .tp-cal-body {gap:3px!important;}
  .tp-cal-legend {font-size:.65rem!important;}
}
</style>""", unsafe_allow_html=True)

st.markdown(r"""<style>
@media (max-width: 767px) {
  html { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }
  body, .stApp, [data-testid="stAppViewContainer"] { width:100%; max-width:100%; }
  [data-testid="stMainBlockContainer"], .main .block-container {
    width:100%!important; max-width:100%!important;
    padding: max(70px, env(safe-area-inset-top)) 12px calc(28px + env(safe-area-inset-bottom))!important;
    box-sizing:border-box!important;
  }
  /* No recortar elementos desplegables ni ventanas de Streamlit */
  [data-testid="stMain"], [data-testid="stVerticalBlock"], [data-testid="stVerticalBlockBorderWrapper"] {
    min-width:0!important; max-width:100%;
  }
  [data-testid="stHorizontalBlock"] { flex-wrap:wrap!important; gap:12px!important; align-items:stretch!important; }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    flex:1 1 100%!important; width:100%!important; min-width:0!important; max-width:100%!important;
  }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] > div { min-width:0!important; }
  [data-testid="stForm"], [data-testid="stExpander"], [data-testid="stVerticalBlockBorderWrapper"] {
    max-width:100%; box-sizing:border-box;
  }
  [data-testid="stForm"] { padding:12px!important; }
  [data-testid="stWidgetLabel"] p { line-height:1.35!important; }
  [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
  [data-testid="stTextArea"] textarea, [data-baseweb="select"] input {
    font-size:16px!important; min-height:44px;
  }
  [data-testid="stButton"] button, [data-testid="stFormSubmitButton"] button,
  [data-testid="stDownloadButton"] button, [data-testid="stPopover"] button {
    min-height:48px!important; width:100%; touch-action:manipulation;
    white-space:normal!important; overflow-wrap:anywhere; line-height:1.3!important;
  }
  /* Ingreso y salida: botones cómodos y diferenciados en móvil */
  .btn-ingreso button, .btn-salida button { min-height:60px!important; font-size:1rem!important; }
  .tp-hero, .tp-card, .tp-kpi, .market-header, .cal-card, .boleta-container {
    max-width:100%!important; min-width:0!important; box-sizing:border-box!important;
    overflow-wrap:anywhere;
  }
  .tp-hero-top { flex-wrap:wrap; }
  .tp-hero-hi { overflow-wrap:anywhere; }
  .tp-kpi-val { overflow-wrap:anywhere; font-size:clamp(1.25rem,6vw,1.7rem)!important; }
  .tp-mgrid, .tp-gridk, .tp-id-grid { grid-template-columns:minmax(0,1fr)!important; }
  .tp-cal-grid { grid-template-columns:repeat(2,minmax(0,1fr))!important; }
  .tp-up-calendar, .tp-shift-detail-wrap, .cal-card, .boleta-container,
  [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
    max-width:100%!important; overflow-x:auto!important; -webkit-overflow-scrolling:touch;
  }
  .stTabs [data-baseweb="tab-list"] { max-width:100%; overflow-x:auto!important; scrollbar-width:thin; }
  .stTabs [data-baseweb="tab"] { white-space:nowrap!important; min-height:44px; }
  /* Dialogos de cumpleaños, botellas y formularios: visibles sin salir de pantalla */
  [role="dialog"] { max-width:calc(100vw - 20px)!important; max-height:calc(100dvh - 32px)!important;
    overflow-y:auto!important; box-sizing:border-box!important; }
  [data-testid="stDialog"] { max-width:100vw!important; }
  [data-testid="stDialog"] [data-testid="stVerticalBlock"] { min-width:0!important; }
  [data-testid="stDialog"] button { min-height:48px!important; white-space:normal!important; }
  [data-testid="stSidebar"] { width:min(88vw,330px)!important; max-width:min(88vw,330px)!important; }
  [data-testid="stSidebar"] button { min-height:44px; }
  /* Chatbot: sin tapar la navegación ni el contenido inferior */
  .st-key-tp_chat_fab { right:12px!important; top:70px!important; }
  .st-key-tp_chat_panel { right:8px!important; top:135px!important;
    width:calc(100vw - 16px)!important; max-width:calc(100vw - 16px)!important;
    max-height:calc(100dvh - 150px)!important; overflow-y:auto!important; }
  [data-testid="stToastContainer"] { max-width:calc(100vw - 20px)!important; }
  [data-testid="stToast"] { max-width:calc(100vw - 24px)!important; }
}
@media (max-width: 390px) {
  [data-testid="stMainBlockContainer"], .main .block-container { padding-left:9px!important; padding-right:9px!important; }
  .tp-cal-grid { grid-template-columns:minmax(0,1fr)!important; }
  .tp-cal-day { min-height:0!important; }
}
@media (orientation: landscape) and (max-height: 480px) {
  [role="dialog"] { max-height:calc(100dvh - 12px)!important; }
  .st-key-tp_chat_panel { top:65px!important; max-height:calc(100dvh - 75px)!important; }
}
</style>""", unsafe_allow_html=True)

st.markdown(r"""
<style>
/* =====================================================================
   Componentes propios de Inventario, escritos con los tokens de Asistencia
   (mismos colores, radios, sombras y tipografía: --tp-*)
   ===================================================================== */
.section-title{font-size:1.02rem;font-weight:700;color:var(--tp-ink);margin:20px 0 10px;letter-spacing:-.01em;}
.card{background:var(--tp-surface);border:1px solid var(--tp-line);border-radius:var(--tp-r-md);padding:14px 18px;margin-bottom:12px;box-shadow:var(--tp-sh-1);color:var(--tp-ink-2);font-size:.9rem;line-height:1.5;}
.card b{color:var(--tp-ink);}
.mobile-note{background:var(--tp-info-soft);border:1px solid #C7D8FB;border-radius:14px;padding:12px 16px;margin:6px 0 14px;font-size:.84rem;line-height:1.55;color:var(--tp-ink-2);}
.mobile-note b{color:var(--tp-ink);}
.tp-kpi{min-height:128px;}

/* Ficha de producto */
.product-card{background:var(--tp-surface);border:1px solid var(--tp-line);border-top:3px solid var(--tp-red);border-radius:var(--tp-r-md);padding:18px 20px;margin:10px 0 15px;box-shadow:var(--tp-sh-1);}
.product-name{font-size:1.15rem;font-weight:700;color:var(--tp-ink);line-height:1.25;}
.product-meta{color:var(--tp-ink-2);font-size:.82rem;margin-top:4px;}
.stock-box{background:#F6F7FA;border:1px solid var(--tp-line);border-radius:12px;padding:13px;text-align:center;}
.stock-label{font-size:.66rem;font-weight:700;color:var(--tp-mute);text-transform:uppercase;letter-spacing:.07em;}
.stock-number{font-size:1.5rem;font-weight:700;color:var(--tp-ink);margin-top:4px;font-variant-numeric:tabular-nums;}

/* Consulta de precios */
.price-hero{background:var(--tp-surface);border:1px solid var(--tp-line);border-radius:var(--tp-r-lg);padding:26px 22px;text-align:center;box-shadow:var(--tp-sh-1);margin:14px 0;}
.price-hero .price-label{font-size:.72rem;font-weight:700;text-transform:uppercase;color:var(--tp-mute);letter-spacing:.09em;}
.price-hero .price-value{font-size:3rem;font-weight:800;margin:6px 0 2px;line-height:1;color:var(--tp-ink);font-variant-numeric:tabular-nums;}
.price-hero .price-sub{font-size:.85rem;color:var(--tp-mute);}
.price-info-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin-top:12px;}
.price-info-item{background:#F6F7FA;border-radius:12px;padding:12px;text-align:center;}
.price-info-item .lbl{font-size:.66rem;font-weight:700;color:var(--tp-mute);text-transform:uppercase;letter-spacing:.07em;}
.price-info-item .val{font-size:1.05rem;font-weight:700;margin-top:5px;color:var(--tp-ink);font-variant-numeric:tabular-nums;}

/* Plan de compras (Stock Intelligence) */
.psi-executive{position:relative;background:var(--tp-surface);border:1px solid var(--tp-line);border-radius:var(--tp-r-lg);padding:22px 24px 20px;margin:10px 0 18px;box-shadow:var(--tp-sh-1);}
.psi-executive::before{content:"";position:absolute;left:24px;top:0;width:36px;height:4px;background:var(--tp-red);border-radius:0 0 4px 4px;}
.psi-executive h3{font-size:1.04rem;color:var(--tp-ink);margin:4px 0 7px;font-weight:700;}
.psi-executive p{font-size:.92rem;color:var(--tp-ink-2);line-height:1.6;margin:0;}
.psi-eyebrow{color:var(--tp-mute);font-size:.7rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;margin:12px 0 8px;}
.psi-section{display:flex;align-items:center;gap:10px;margin:22px 0 12px;color:var(--tp-ink);font-size:1.08rem;font-weight:700;}
.psi-section .psi-index{display:inline-grid;place-items:center;width:28px;height:28px;border-radius:9px;background:var(--tp-red-soft);color:var(--tp-red-dk);font-size:.8rem;font-weight:700;}
.psi-smallnote{color:var(--tp-mute);font-size:.83rem;margin:0 0 10px;}

@media (max-width:640px){
  .price-hero{padding:22px 16px;} .price-hero .price-value{font-size:2.3rem;}
  .product-card{padding:14px;} .psi-executive{padding:18px 16px 16px;}
  .psi-executive::before{left:16px;}
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------
# COMPONENTES UI REUTILIZABLES (mismos que la app de Asistencia)
# ---------------------------------------------------------
_html = html
NEGOSY_URL = "https://app.negosy.com/accounts/login/"
# Opcional: pega aquí el enlace de la app de Asistencia para mostrar el acceso directo en la barra lateral.
ASISTENCIA_URL = ""

# Seguridad de sesión (idéntica a Asistencia): 10 h máximo y cierre tras 30 min sin actividad.
SESION_MAX_SEGUNDOS = 10 * 60 * 60
INACTIVIDAD_MAX_SEGUNDOS = 30 * 60
# Si prefieres NO mostrar el nombre al escribir el usuario (antes de autenticar), pon False.
LOGIN_MOSTRAR_FOTO = True


def ui_iniciales(nombre):
    p = [x for x in str(nombre).split() if x]
    return (p[0][0] + (p[1][0] if len(p) > 1 else "")).upper() if p else "?"


def ui_avatar(nombre, size=46):
    dim = f"width:{size}px;height:{size}px;font-size:{max(12, int(size * 0.34))}px;"
    return f'<span class="tp-avatar" style="{dim}">{_html.escape(ui_iniciales(nombre))}</span>'


def ui_chip(texto, tipo="neutral"):
    """tipo: ok | warn | bad | info | neutral"""
    return f'<span class="tp-chip {tipo}">{texto}</span>'


def ui_kpi(etiqueta, valor, detalle=""):
    sub = f'<div class="tp-kpi-sub">{detalle}</div>' if detalle else ""
    return f'<div class="tp-kpi"><div class="tp-kpi-lbl">{etiqueta}</div><div class="tp-kpi-val">{valor}</div>{sub}</div>'


def ui_card_container(key):
    """Contenedor que ES la tarjeta blanca (todo el contenido dentro del mismo fondo)."""
    try:
        return st.container(key=f"tpc_{key}")
    except TypeError:
        return st.container(border=True)


def ui_callout(texto, tono="info"):
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", _html.escape(str(texto)))
    ic = {"info": "i", "ok": "✓", "warn": "!"}[tono]
    st.markdown(f'<div class="tp-callout {tono}"><i>{ic}</i><div>{t}</div></div>', unsafe_allow_html=True)


def ui_seccion(titulo, sub=""):
    s = f'<div class="tp-sec-sub">{_html.escape(sub)}</div>' if sub else ""
    st.markdown(f'<div class="tp-sec"><div><div class="tp-sec-title">{_html.escape(titulo)}</div>{s}</div></div>', unsafe_allow_html=True)


def ui_icono_app():
    """Ícono cuadrado con fondo blanco y el logo centrado (180 px iPhone, 512 px Android)."""
    from PIL import Image, ImageDraw, ImageFont

    def _icono(sz):
        im = Image.new("RGBA", (sz, sz), (255, 255, 255, 255))
        try:
            ruta = FAVICON_PATH if os.path.exists(FAVICON_PATH) else LOGO_PATH
            lg = Image.open(ruta).convert("RGBA")
            lg.thumbnail((int(sz * 0.74), int(sz * 0.74)), Image.LANCZOS)
            im.paste(lg, ((sz - lg.width) // 2, (sz - lg.height) // 2), lg)
        except Exception:
            d = ImageDraw.Draw(im)
            d.rounded_rectangle((sz * .12, sz * .12, sz * .88, sz * .88), radius=sz * .2, fill=(236, 50, 55, 255))
            try:
                d.text((sz * .5, sz * .5), "P", fill="white", anchor="mm", font=ImageFont.load_default(size=int(sz * .5)))
            except Exception:
                pass
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    return _icono(180), _icono(512)


def ui_pwa_inyectar():
    """Pide al celular: ícono propio, nombre corto, color de marca y pantalla completa al añadir a inicio."""
    try:
        i180, i512 = ui_icono_app()
    except Exception:
        return
    js = """<script>(function(){try{
var d=window.parent.document,h=d.head;
function meta(n,c){var m=d.querySelector('meta[name="'+n+'"]');if(!m){m=d.createElement('meta');m.name=n;h.appendChild(m);}m.content=c;}
d.querySelectorAll('link[rel="apple-touch-icon"],link[rel="manifest"]').forEach(function(e){e.remove();});
var a=d.createElement('link');a.rel='apple-touch-icon';a.setAttribute('sizes','180x180');a.href='__I180__';h.appendChild(a);
meta('apple-mobile-web-app-capable','yes');meta('mobile-web-app-capable','yes');
meta('apple-mobile-web-app-title','Inventario');meta('application-name','Inventario');
meta('apple-mobile-web-app-status-bar-style','default');meta('theme-color','#EC3237');
var L=window.parent.location,mf={name:'Inventario · Tiendas Premium',short_name:'Inventario',start_url:L.origin+L.pathname,scope:L.origin+'/',display:'standalone',
background_color:'#FFFFFF',theme_color:'#EC3237',icons:[{src:'__I512__',sizes:'512x512',type:'image/png',purpose:'any'}]};
var m=d.createElement('link');m.rel='manifest';m.href='data:application/manifest+json,'+encodeURIComponent(JSON.stringify(mf));h.appendChild(m);
}catch(e){}})();</script>"""
    components.html(js.replace("__I180__", i180).replace("__I512__", i512), height=0)


def ui_guia_instalar(cont):
    ua = ""
    try:
        ua = str(st.context.headers.get("User-Agent", ""))
    except Exception:
        pass
    es_ios, es_and = any(x in ua for x in ("iPhone", "iPad", "iPod")), "Android" in ua
    ios = ('<div class="tp-steps-t">iPhone · Safari ' + (ui_chip("Tu dispositivo", "ok") if es_ios else "") + '</div><ol class="tp-steps">'
           '<li>Abre esta página en <b>Safari</b>.</li><li>Toca el botón <b>Compartir</b> (cuadro con flecha hacia arriba).</li>'
           '<li>Elige <b>Añadir a pantalla de inicio</b>.</li><li>Toca <b>Añadir</b>. Listo: aparece el ícono de Inventario.</li></ol>')
    andr = ('<div class="tp-steps-t">Android · Chrome ' + (ui_chip("Tu dispositivo", "ok") if es_and else "") + '</div><ol class="tp-steps">'
            '<li>Abre esta página en <b>Chrome</b>.</li><li>Toca el menú <b>⋮</b> (arriba a la derecha).</li>'
            '<li>Elige <b>Instalar app</b> o <b>Añadir a pantalla de inicio</b>.</li><li>Confirma con <b>Instalar</b>.</li></ol>')
    with cont.expander("Instalar en tu celular"):
        st.markdown((andr + ios) if es_and else (ios + andr), unsafe_allow_html=True)
        st.caption("Cada vez que abras la app te pedirá tu usuario y contraseña por seguridad.")


def _norm_txt(x):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(x).lower()) if unicodedata.category(c) != "Mn")


def _ir_a(destino):
    """Navega a una sección y limpia la búsqueda (se usa en botones con on_click)."""
    st.session_state["pagina"] = destino
    st.session_state["gs_q"] = ""


def _limpiar_busqueda():
    st.session_state["gs_q"] = ""



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
    """PBKDF2 para usuarios nuevos. Mantiene compatibilidad de lectura con SHA256 legado."""
    salt = secrets.token_bytes(16)
    rondas = 310000
    derivada = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), salt, rondas)
    return f"pbkdf2_sha256${rondas}${salt.hex()}${derivada.hex()}"


def verificar_password(password, guardada):
    guardada = str(guardada or "").strip()
    if guardada.startswith("pbkdf2_sha256$"):
        try:
            _, rondas, salt, esperado = guardada.split("$", 3)
            derivada = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), bytes.fromhex(salt), int(rondas))
            return hmac.compare_digest(derivada, bytes.fromhex(esperado))
        except (ValueError, TypeError):
            return False
    if len(guardada) == 64:
        return hmac.compare_digest(hashlib.sha256(str(password).encode("utf-8")).hexdigest(), guardada)
    # Compatibilidad transitoria con contraseñas antiguas en texto plano.
    return bool(guardada) and hmac.compare_digest(str(password), guardada)



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
    cargar_universo.clear()
    cargar_no_localizados.clear()

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
    for col in ["IdSesion", "FechaHora", "Usuario", "NombreUsuario", "CodigoBarras", "CodigoProducto", "Producto", "Categoria", "Sucursal", "TipoDiferencia", "MetodoConteo", "Observacion"]:
        df[col] = df[col].fillna("").astype(str).str.strip()
    for col in ["StockSistema", "StockFisico", "Diferencia", "CostoUnitario", "ValorFaltante", "ValorSobrante", "CostoDiferencia"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    zonas = consolidar_conteos_zona()
    if not zonas.empty:
        if not df.empty:
            df = df.copy()
            df["_join"] = df["IdSesion"].astype(str) + "|" + df["Sucursal"].astype(str).str.casefold() + "|" + _claves_df(df).astype(str).str.casefold()
            zonas["_join"] = zonas["IdSesion"].astype(str) + "|" + zonas["Sucursal"].astype(str).str.casefold() + "|" + _claves_df(zonas).astype(str).str.casefold()
            df = df[~df["_join"].isin(set(zonas["_join"]))].drop(columns="_join")
            zonas = zonas.drop(columns="_join")
        df = pd.concat([df, zonas], ignore_index=True)
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


# ETAPA 1 — universo fijo y excepciones de verificación (hojas auxiliares)
HOJA_UNIVERSO = "UniversoInventario"
HOJA_NO_LOCALIZADOS = "NoLocalizadosInventario"
HEADERS_UNIVERSO = ["IdSesion"] + HEADERS_INVENTARIO
HEADERS_NO_LOCALIZADOS = ["IdSesion", "FechaHora", "Usuario", "CodigoBarras", "CodigoProducto", "Producto", "Sucursal", "Motivo"]

@st.cache_resource(show_spinner=False)
def hoja_control(nombre, encabezados):
    libro = conectar_google()
    try:
        return libro.worksheet(nombre)
    except gspread.exceptions.WorksheetNotFound:
        hoja = libro.add_worksheet(title=nombre, rows=2000, cols=len(encabezados))
        hoja.append_row(encabezados, value_input_option="RAW")
        return hoja

@st.cache_data(ttl=30, show_spinner=False)
def cargar_universo():
    return normalizar_df(pd.DataFrame(hoja_control(HOJA_UNIVERSO, HEADERS_UNIVERSO).get_all_records()), HEADERS_UNIVERSO)

@st.cache_data(ttl=30, show_spinner=False)
def cargar_no_localizados():
    return normalizar_df(pd.DataFrame(hoja_control(HOJA_NO_LOCALIZADOS, HEADERS_NO_LOCALIZADOS).get_all_records()), HEADERS_NO_LOCALIZADOS)

def clave_producto(df):
    # Se identifica por sucursal + código; evita colisiones entre tiendas.
    return df["Sucursal"].astype(str).str.strip().str.casefold() + "|" + _claves_df(df).astype(str).str.strip().str.casefold()

def universo_sesion(id_sesion, sucursal=""):
    universo = cargar_universo()
    subset = universo[universo["IdSesion"].astype(str) == str(id_sesion)]
    if not subset.empty:
        d = subset[HEADERS_INVENTARIO].copy()
        for col in ["StockSistema", "CostoUnitario", "PrecioVenta"]:
            d[col] = pd.to_numeric(d[col], errors="coerce").fillna(0)
        return d.drop_duplicates(subset=["Sucursal", "CodigoProducto", "CodigoBarras"], keep="first")
    # Sesiones históricas anteriores a la actualización: catálogo actual, identificado como estimación.
    return inventario_de_sucursal(cargar_inventario(), sucursal)

def localizados_vigentes(id_sesion):
    d = cargar_no_localizados()
    d = d[d["IdSesion"].astype(str) == str(id_sesion)]
    return d.drop_duplicates(["IdSesion", "Sucursal", "CodigoBarras", "CodigoProducto"], keep="last")

def estado_cobertura(id_sesion, sucursal=""):
    inv = universo_sesion(id_sesion, sucursal).copy()
    if inv.empty:
        return inv.assign(EstadoVerificacion=pd.Series(dtype=str))
    inv["_clave"] = clave_producto(inv)
    if inv["_clave"].duplicated().any():
        raise ValueError("Existen productos con códigos duplicados en la misma sucursal. Corrige el catálogo antes de calcular la cobertura.")
    inv["EstadoVerificacion"] = "PENDIENTE"
    nc = localizados_vigentes(id_sesion)
    if not nc.empty:
        inv.loc[inv["_clave"].isin(set(clave_producto(nc))), "EstadoVerificacion"] = "NO LOCALIZADO"
    conteos = cargar_conteos()
    dc = conteos_vigentes(conteos[conteos["IdSesion"].astype(str) == str(id_sesion)]) if not conteos.empty else conteos
    if not dc.empty:
        estados = dc.copy()
        estados["_clave"] = clave_producto(estados)
        estados["_estado"] = estados.apply(lambda r: "CERO VERIFICADO" if limpiar_numero(r["StockSistema"]) == 0 and limpiar_numero(r["StockFisico"]) == 0 else ("CONFORME" if limpiar_numero(r["Diferencia"]) == 0 else ("FALTANTE" if limpiar_numero(r["Diferencia"]) < 0 else "SOBRANTE")), axis=1)
        inv["EstadoVerificacion"] = inv["_clave"].map(estados.drop_duplicates("_clave", keep="last").set_index("_clave")["_estado"]).fillna(inv["EstadoVerificacion"])
    return inv.drop(columns="_clave")

def metricas_cobertura(id_sesion, sucursal=""):
    d = estado_cobertura(id_sesion, sucursal)
    total = len(d)
    contados = int(d["EstadoVerificacion"].isin(["CONFORME", "CERO VERIFICADO", "FALTANTE", "SOBRANTE"]).sum()) if total else 0
    conformes = int(d["EstadoVerificacion"].isin(["CONFORME", "CERO VERIFICADO"]).sum()) if total else 0
    return {"total": total, "contados": contados, "pendientes": total-contados,
            "ceros": int((d["EstadoVerificacion"] == "CERO VERIFICADO").sum()) if total else 0,
            "no_localizados": int((d["EstadoVerificacion"] == "NO LOCALIZADO").sum()) if total else 0,
            "cobertura": 100*contados/total if total else 0,
            "exactitud": 100*conformes/contados if contados else 0}

def registrar_no_localizado(sesion, producto, motivo):
    if not motivo.strip():
        raise ValueError("Indica dónde se buscó o por qué no se pudo localizar el producto.")
    if ultimo_conteo_producto(sesion["IdSesion"], producto) is not None:
        raise ValueError("El producto ya tiene un conteo; utiliza reconteo para modificarlo.")
    fila = [sesion["IdSesion"], ahora(), st.session_state.usuario["Usuario"],
            limpiar_codigo(producto.get("CodigoBarras", "")), limpiar_codigo(producto.get("CodigoProducto", "")),
            producto.get("Producto", ""), producto.get("Sucursal", ""), motivo.strip()]
    hoja_control(HOJA_NO_LOCALIZADOS, HEADERS_NO_LOCALIZADOS).append_row(fila, value_input_option="RAW")
    cargar_no_localizados.clear()
    registrar_auditoria("NO_LOCALIZADO", f"{producto.get('Producto', '')}: {motivo}", sesion["IdSesion"])

def guardar_universo_sesion(id_sesion, sucursal):
    inv = inventario_de_sucursal(cargar_inventario(), sucursal)
    if inv.empty:
        raise ValueError("La sucursal no tiene productos; no se puede iniciar el inventario.")
    if clave_producto(inv).duplicated().any():
        raise ValueError("Existen códigos de producto duplicados en la sucursal. Corrige el catálogo antes de abrir la sesión.")
    rows = [[id_sesion] + [str(r.get(c, "")) for c in HEADERS_INVENTARIO] for _, r in inv.iterrows()]
    ws = hoja_control(HOJA_UNIVERSO, HEADERS_UNIVERSO)
    for i in range(0, len(rows), 300):
        ws.append_rows(rows[i:i+300], value_input_option="RAW")
    cargar_universo.clear()

# ETAPA 2 — configuración individual, validaciones y prioridad histórica
HOJA_CONFIG_CONTEO = "ConfiguracionConteo"
HEADERS_CONFIG_CONTEO = ["Usuario", "ConteoCiego", "ActualizadoPor", "FechaActualizacion"]
HOJA_RECONTEOS = "ControlReconteos"
HEADERS_RECONTEOS = ["IdSesion", "CodigoBarras", "CodigoProducto", "Sucursal", "FechaSolicitud", "SolicitadoPor", "Motivo", "Estado", "FechaResolucion", "ResueltoPor", "ConteoAnterior", "ConteoNuevo"]

def _verdadero(v):
    return str(v).strip().lower() in ("1", "true", "si", "sí", "activo", "on")

@st.cache_data(ttl=45, show_spinner=False)
def cargar_config_conteo():
    return normalizar_df(pd.DataFrame(hoja_control(HOJA_CONFIG_CONTEO, HEADERS_CONFIG_CONTEO).get_all_records()), HEADERS_CONFIG_CONTEO)

@st.cache_data(ttl=30, show_spinner=False)
def cargar_control_reconteos():
    return normalizar_df(pd.DataFrame(hoja_control(HOJA_RECONTEOS, HEADERS_RECONTEOS).get_all_records()), HEADERS_RECONTEOS)

def conteo_ciego_usuario(usuario):
    if str(usuario.get("Rol", "")).upper() == "ADMIN":
        return False
    d = cargar_config_conteo()
    fila = d[d["Usuario"].astype(str).str.casefold() == str(usuario.get("Usuario", "")).casefold()]
    return _verdadero(fila.iloc[-1]["ConteoCiego"]) if not fila.empty else bool(CONTEO_CIEGO)

def configurar_conteo_ciego(nombre_usuario, activo, administrador):
    ws = hoja_control(HOJA_CONFIG_CONTEO, HEADERS_CONFIG_CONTEO)
    filas = ws.get_all_values()
    objetivo = str(nombre_usuario).strip().casefold()
    numero = next((i for i, r in enumerate(filas[1:], 2) if r and r[0].strip().casefold() == objetivo), None)
    registro = [nombre_usuario, "SI" if activo else "NO", administrador, ahora()]
    if numero:
        ws.update(f"A{numero}:D{numero}", [registro], value_input_option="RAW")
    else:
        ws.append_row(registro, value_input_option="RAW")
    cargar_config_conteo.clear()
    registrar_auditoria("CONFIG_CONTEO_CIEGO", f"{nombre_usuario}: {'SI' if activo else 'NO'}")

def _clave_registro(p):
    return (str(p.get("Sucursal", "")).strip().casefold(),
            limpiar_codigo(p.get("CodigoBarras", "")) or limpiar_codigo(p.get("CodigoProducto", "")) or str(p.get("Producto", "")).strip())

def solicitudes_producto(id_sesion, producto):
    d = cargar_control_reconteos()
    if d.empty:
        return d
    clave = _clave_registro(producto)
    return d[(d["IdSesion"].astype(str) == str(id_sesion)) &
             (d.apply(_clave_registro, axis=1) == clave)]

def solicitud_pendiente(id_sesion, producto):
    d = solicitudes_producto(id_sesion, producto)
    return not d.empty and str(d.iloc[-1]["Estado"]).upper() == "PENDIENTE"

def solicitar_reconteo(sesion, producto, usuario, motivo):
    if not motivo.strip():
        raise ValueError("El motivo del reconteo es obligatorio.")
    if solicitud_pendiente(sesion["IdSesion"], producto):
        return
    ws = hoja_control(HOJA_RECONTEOS, HEADERS_RECONTEOS)
    ws.append_row([sesion["IdSesion"], limpiar_codigo(producto.get("CodigoBarras", "")),
                   limpiar_codigo(producto.get("CodigoProducto", "")), producto.get("Sucursal", ""),
                   ahora(), usuario.get("Usuario", ""), motivo.strip(), "PENDIENTE", "", "", "", ""], value_input_option="RAW")
    cargar_control_reconteos.clear()
    registrar_auditoria("SOLICITAR_RECONTEO", f"{producto.get('Producto', '')} · {motivo}", sesion["IdSesion"])

def resolver_reconteo(sesion, producto, usuario, anterior, nuevo):
    ws = hoja_control(HOJA_RECONTEOS, HEADERS_RECONTEOS)
    valores = ws.get_all_values()
    clave = _clave_registro(producto)
    for n in range(len(valores)-1, 0, -1):
        r = valores[n]
        if len(r) >= 8 and r[0] == str(sesion["IdSesion"]) and _clave_registro(dict(zip(HEADERS_RECONTEOS, r))) == clave and r[7] == "PENDIENTE":
            ws.update(f"H{n+1}:L{n+1}", [["RESUELTO", ahora(), usuario.get("Usuario", ""), anterior, nuevo]], value_input_option="RAW")
            cargar_control_reconteos.clear()
            return

def pendientes_anteriores(sesion):
    sesiones = cargar_sesiones()
    anteriores = sesiones[(sesiones["IdSesion"].astype(str) != str(sesion["IdSesion"])) &
                         (sesiones["Sucursal"].astype(str).str.strip().str.casefold() == str(sesion["Sucursal"]).strip().casefold()) &
                         (sesiones["Estado"].astype(str).str.upper() == "CERRADA")].copy()
    if anteriores.empty:
        return pd.DataFrame()
    anteriores = anteriores.sort_values("FechaInicio", ascending=False)
    previa = anteriores.iloc[0]
    anterior = estado_cobertura(previa["IdSesion"], previa["Sucursal"])
    actual = estado_cobertura(sesion["IdSesion"], sesion["Sucursal"])
    if anterior.empty or actual.empty:
        return pd.DataFrame()
    claves = set(clave_producto(anterior[anterior["EstadoVerificacion"].isin(["PENDIENTE", "NO LOCALIZADO"])]))
    resultado = actual[clave_producto(actual).isin(claves) & actual["EstadoVerificacion"].isin(["PENDIENTE", "NO LOCALIZADO"])].copy()
    resultado["SesionAnterior"] = previa["NombreSesion"]
    return resultado

# =========================================================
# ETAPA 3 — ZONAS, ASIGNACIONES Y CONSOLIDACIÓN
# =========================================================
@st.cache_data(ttl=15, show_spinner=False)
def cargar_zonas():
    return normalizar_df(pd.DataFrame(hoja_control(HOJA_ZONAS, HEADERS_ZONAS).get_all_records()), HEADERS_ZONAS)

@st.cache_data(ttl=15, show_spinner=False)
def cargar_conteos_zona():
    df = normalizar_df(pd.DataFrame(hoja_control(HOJA_CONTEOS_ZONA, HEADERS_CONTEOS_ZONA).get_all_records()), HEADERS_CONTEOS_ZONA)
    for c in ("StockSistema", "StockFisico", "CostoUnitario"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df

def zonas_sesion(id_sesion):
    d = cargar_zonas()
    return d[d["IdSesion"].astype(str) == str(id_sesion)].copy()

def zona_usuario(sesion, usuario):
    zona = st.session_state.get("zona_activa", "")
    d = zonas_sesion(sesion["IdSesion"])
    match = d[d["Zona"] == zona]
    if match.empty:
        return None
    z = match.iloc[-1].to_dict()
    if str(usuario.get("Rol", "")).upper() != "ADMIN" and str(z["Responsable"]).strip().casefold() != str(usuario.get("Usuario", "")).strip().casefold():
        return None
    return z if str(z["Estado"]).upper() == "EN PROCESO" else None

def ultimo_conteo_zona(id_sesion, zona, producto):
    d = cargar_conteos_zona()
    d = d[(d["IdSesion"].astype(str) == str(id_sesion)) & (d["Zona"] == zona)]
    if d.empty:
        return None
    k = _clave_registro(producto)
    d = d[d.apply(lambda r: _clave_registro(r) == k, axis=1)]
    return d.iloc[-1].to_dict() if not d.empty else None

def guardar_conteo_zona(sesion, usuario, producto, fisico, metodo, observacion, reconteo):
    zona = zona_usuario(sesion, usuario)
    if zona is None:
        raise ValueError("Selecciona una zona asignada y abierta antes de guardar.")
    if str(sesion.get("Estado", "")).upper() != "ABIERTA":
        raise ValueError("La sesión está cerrada.")
    cargar_conteos_zona.clear()
    previo = ultimo_conteo_zona(sesion["IdSesion"], zona["Zona"], producto)
    # No combinar un conteo general previo con uno por zonas sin conciliación explícita.
    raw = normalizar_df(pd.DataFrame(obtener_hoja("conteos").get_all_records()), HEADERS_CONTEO)
    if not raw.empty:
        anteriores = raw[raw["IdSesion"].astype(str) == str(sesion["IdSesion"])]
        if not anteriores.empty and any(_clave_registro(r) == _clave_registro(producto) for _, r in anteriores.iterrows()):
            raise ValueError("Este producto ya tiene un conteo general en la sesión. No puede mezclarse con el conteo por zonas; utiliza una nueva sesión para ese producto.")
    if previo and not reconteo:
        raise ValueError("Este producto ya fue contado en esta zona. Usa Reconteo para corregirlo.")
    if not previo and reconteo:
        raise ValueError("No existe conteo previo en esta zona.")
    if reconteo and not observacion.strip():
        raise ValueError("Indica el motivo del reconteo.")
    from uuid import uuid4
    fila = [sesion["IdSesion"], ahora(), usuario["Usuario"], usuario["NombreCompleto"], zona["Zona"], limpiar_codigo(producto.get("CodigoBarras", "")), limpiar_codigo(producto.get("CodigoProducto", "")), producto.get("Producto", ""), producto.get("Categoria", ""), producto.get("Sucursal", ""), limpiar_numero(producto.get("StockSistema", 0)), float(fisico), limpiar_numero(producto.get("CostoUnitario", 0)), metodo, observacion.strip(), "RECONTEO" if reconteo else "CONTEO", str(uuid4())]
    hoja_control(HOJA_CONTEOS_ZONA, HEADERS_CONTEOS_ZONA).append_row(fila, value_input_option="RAW")
    cargar_conteos_zona.clear()
    cargar_conteos.clear()
    registrar_auditoria("RECONTEO_ZONA" if reconteo else "CONTEO_ZONA", f"{zona['Zona']} · {producto.get('Producto','')} · {fisico} unidades · {observacion}", sesion["IdSesion"])
    return True

def consolidar_conteos_zona():
    d = cargar_conteos_zona()
    if d.empty:
        return pd.DataFrame(columns=HEADERS_CONTEO)
    d = d.copy()
    d["_clave"] = d["IdSesion"].astype(str) + "|" + d["Sucursal"].astype(str).str.casefold() + "|" + _claves_df(d).astype(str).str.casefold()
    # Un reconteo sustituye únicamente la cantidad previa de SU zona.
    d = d.drop_duplicates(["_clave", "Zona"], keep="last")
    filas = []
    for (_, _), g in d.groupby(["IdSesion", "_clave"], sort=False):
        p = g.iloc[-1]
        fisico = float(g["StockFisico"].sum())
        sistema = float(p["StockSistema"])
        costo = float(p["CostoUnitario"])
        dif = fisico - sistema
        filas.append(dict(IdSesion=p["IdSesion"], FechaHora=p["FechaHora"], Usuario=p["Usuario"], NombreUsuario=" / ".join(sorted(set(g["NombreUsuario"].astype(str)))), CodigoBarras=p["CodigoBarras"], CodigoProducto=p["CodigoProducto"], Producto=p["Producto"], Categoria=p["Categoria"], Sucursal=p["Sucursal"], StockSistema=sistema, StockFisico=fisico, Diferencia=dif, CostoUnitario=costo, ValorFaltante=max(-dif,0)*costo, ValorSobrante=max(dif,0)*costo, CostoDiferencia=dif*costo, TipoDiferencia="FALTANTE" if dif<0 else "SOBRANTE" if dif>0 else "OK", MetodoConteo="Por zonas", Observacion=" | ".join(f"{r.Zona}: {r.StockFisico:g}" for r in g.itertuples())))
    return normalizar_df(pd.DataFrame(filas), HEADERS_CONTEO)

def guardar_zona_estado(id_sesion, zona, responsable, estado, actor):
    ws = hoja_control(HOJA_ZONAS, HEADERS_ZONAS)
    datos = ws.get_all_values()
    if not datos:
        raise ValueError("No hay datos de zonas.")
    h = datos[0]
    for i, r in enumerate(datos[1:], start=2):
        if len(r)>1 and r[0] == id_sesion and r[1] == zona:
            previo = r[h.index("Estado")] if len(r)>h.index("Estado") else ""
            inicio = r[h.index("FechaInicio")] if len(r)>h.index("FechaInicio") else ""
            fin = r[h.index("FechaFin")] if len(r)>h.index("FechaFin") else ""
            valores = [id_sesion,zona,responsable,estado, inicio or (ahora() if estado=="EN PROCESO" else ""), ahora() if estado=="FINALIZADA" else ("" if previo=="FINALIZADA" else fin),actor]
            ws.update(f"A{i}:G{i}", [valores], value_input_option="RAW")
            cargar_zonas.clear()
            registrar_auditoria("ESTADO_ZONA", f"{zona}: {previo} → {estado}; responsable {responsable}", id_sesion)
            return
    raise ValueError("Zona no encontrada.")

def crear_zonas_iniciales(sesion):
    if not zonas_sesion(sesion["IdSesion"]).empty:
        return
    hoja_control(HOJA_ZONAS, HEADERS_ZONAS).append_rows([[sesion["IdSesion"], z, "", "PENDIENTE", "", "", ""] for z in ZONAS_PREDETERMINADAS], value_input_option="RAW")
    cargar_zonas.clear()

def pantalla_zonas():
    header("Zonas de inventario", "Asigna góndolas y áreas sin registrar productos previamente")
    sesion = obtener_sesion_abierta()
    if not sesion:
        st.info("Abre una sesión de inventario para gestionar zonas.")
        return
    usuario = st.session_state.usuario
    admin = str(usuario.get("Rol", "")).upper() == "ADMIN"
    d = zonas_sesion(sesion["IdSesion"])
    if d.empty:
        st.info("Esta sesión todavía no tiene zonas configuradas. Puede seguir usándose el inventario general.")
        if admin and st.button("Crear las 7 zonas de Tiendas Premium", type="primary"):
            crear_zonas_iniciales(sesion)
            st.rerun()
        return
    d["Conteos"] = 0
    cz = cargar_conteos_zona()
    cz = cz[cz["IdSesion"].astype(str) == str(sesion["IdSesion"])]
    if not cz.empty:
        cz = cz.drop_duplicates(["Zona", "CodigoBarras", "CodigoProducto"], keep="last")
        d["Conteos"] = d["Zona"].map(cz.groupby("Zona").size()).fillna(0).astype(int)
    st.dataframe(d[["Zona","Responsable","Estado","Conteos","FechaInicio","FechaFin"]], hide_index=True, use_container_width=True)
    st.caption("Las zonas finalizadas quedan bloqueadas. El avance global se mide por productos únicos; no se inventa un porcentaje por zona.")
    if admin:
        with st.expander("Administrar zonas y responsables", expanded=True):
            usuarios = cargar_usuarios()
            nombres = [str(u) for u in usuarios["Usuario"].tolist()] if not usuarios.empty else []
            zona = st.selectbox("Zona", d["Zona"].tolist(), key="adm_zona")
            actual = d[d["Zona"] == zona].iloc[-1]
            resp = st.selectbox("Responsable", [""] + nombres, index=([""]+nombres).index(actual["Responsable"]) if actual["Responsable"] in nombres else 0)
            estado = st.selectbox("Estado", ["PENDIENTE", "EN PROCESO", "FINALIZADA"], index=["PENDIENTE", "EN PROCESO", "FINALIZADA"].index(actual["Estado"]) if actual["Estado"] in ["PENDIENTE", "EN PROCESO", "FINALIZADA"] else 0)
            if st.button("Guardar asignación / estado", type="primary"):
                guardar_zona_estado(sesion["IdSesion"], zona, resp, estado, usuario["Usuario"])
                st.rerun()
            nueva = st.text_input("Agregar otra zona (opcional)")
            if st.button("Agregar zona") and nueva.strip():
                if nueva.strip().casefold() in d["Zona"].astype(str).str.casefold().tolist():
                    st.warning("La zona ya existe.")
                else:
                    hoja_control(HOJA_ZONAS, HEADERS_ZONAS).append_row([sesion["IdSesion"], nueva.strip(), "", "PENDIENTE", "", "", usuario["Usuario"]], value_input_option="RAW")
                    cargar_zonas.clear()
                    st.rerun()
    mias = d[(d["Responsable"].astype(str).str.casefold() == str(usuario["Usuario"]).casefold()) | admin]
    if not mias.empty:
        st.subheader("Mis zonas")
        zona_elegida = st.selectbox("Selecciona la zona de conteo", ["— Sin zona (inventario general) —"] + mias[mias["Estado"] != "FINALIZADA"]["Zona"].tolist())
        if st.button("Trabajar en esta zona", type="primary"):
            if not zona_elegida.startswith("—"):
                rz = d[d["Zona"] == zona_elegida].iloc[-1]
                if rz["Estado"] == "PENDIENTE":
                    guardar_zona_estado(sesion["IdSesion"], zona_elegida, rz["Responsable"], "EN PROCESO", usuario["Usuario"])
            st.session_state.zona_activa = "" if zona_elegida.startswith("—") else zona_elegida
            st.session_state.producto_pendiente = None
            st.session_state.pagina = "Inventario"
            st.rerun()
        zfinal = st.selectbox("Finalizar una de mis zonas", ["—"] + mias[mias["Estado"] != "FINALIZADA"]["Zona"].tolist())
        if zfinal != "—" and st.checkbox("Confirmo que terminé de revisar esta zona") and st.button("Finalizar zona"):
            r = d[d["Zona"] == zfinal].iloc[-1]
            guardar_zona_estado(sesion["IdSesion"], zfinal, r["Responsable"], "FINALIZADA", usuario["Usuario"])
            if st.session_state.get("zona_activa") == zfinal:
                st.session_state.zona_activa = ""
            st.rerun()

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
    return filtrado  # Nunca mezclar sucursales si el nombre no coincide


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
    if verificar_password(password, guardada):
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
    return bool(((df["IdSesion"] == str(id_sesion)) & ((df["CodigoBarras"].map(limpiar_codigo) == codigo) if codigo else (df["CodigoBarras"].map(limpiar_codigo) == "__NO_COINCIDE__"))).any())


def guardar_conteo(sesion, usuario, producto, stock_fisico, metodo="Escáner", observacion="", es_reconteo=False):
    # Comprobación contra datos actualizados: evita guardar accidentalmente un segundo primer conteo.
    cargar_conteos.clear()
    anterior = ultimo_conteo_producto(sesion["IdSesion"], producto)
    if ultimo_conteo_zona(sesion["IdSesion"], st.session_state.get("zona_activa", ""), producto) is not None or (not cargar_conteos_zona().empty and any((r["IdSesion"] == sesion["IdSesion"] and _clave_registro(r) == _clave_registro(producto)) for _, r in cargar_conteos_zona().iterrows())):
        raise ValueError("Este producto tiene conteos por zonas. Selecciona su zona para modificar la cantidad.")
    if anterior is not None and not es_reconteo:
        raise ValueError("Este producto ya fue contado. Abre el flujo de reconteo para modificarlo.")
    if anterior is None and es_reconteo:
        raise ValueError("No existe conteo anterior para corregir.")
    if es_reconteo and not observacion.strip():
        raise ValueError("Debes indicar el motivo de corrección para guardar el reconteo.")
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
    if not es_reconteo and es_diferencia_critica(stock_sistema, stock_fisico, costo):
        try:
            solicitar_reconteo(sesion, producto, usuario, "Diferencia crítica automática")
        except Exception:
            registrar_auditoria("ALERTA_RECONTEO", f"Pendiente de solicitud: {producto.get('Producto', '')}", sesion["IdSesion"])
    if es_reconteo:
        resolver_reconteo(sesion, producto, usuario, anterior.get("StockFisico", ""), stock_fisico)
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
    guardar_universo_sesion(id_sesion, sucursal.strip())
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

    cobertura = metricas_cobertura(id_sesion, sucursal)
    productos_contados = cobertura["contados"]
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
        "ProductosSistema": cobertura["total"],
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
        "CoberturaInventario": cobertura["cobertura"],
        "ProductosPendientes": cobertura["pendientes"],
        "CerosVerificados": cobertura["ceros"],
        "NoLocalizados": cobertura["no_localizados"],
        "ObservacionCierre": "",
    }


def guardar_resumen(resumen):
    fila = [resumen.get(col, "") for col in HEADERS_RESUMEN]
    ws = obtener_hoja("resumen")
    encabezado_actual = ws.row_values(1)
    if encabezado_actual != HEADERS_RESUMEN:
        ws.update("A1", [HEADERS_RESUMEN])
    ws.append_row(fila, value_input_option="USER_ENTERED")
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


def lista_diferencias(dc, tipo):
    """Lista COMPLETA de faltantes (tipo='FALTANTE') o sobrantes (tipo='SOBRANTE'),
    con cantidades en positivo, lista para cuadrar con el sistema de ventas."""
    es_falt = tipo == "FALTANTE"
    col_cant = "CantidadFaltante" if es_falt else "CantidadSobrante"
    col_valor = "ValorFaltante" if es_falt else "ValorSobrante"
    cols = ["CodigoBarras", "CodigoProducto", "Producto", "Categoria", "Sucursal",
            "StockSistema", "StockFisico", col_cant, "CostoUnitario", col_valor]
    if dc is None or dc.empty:
        return pd.DataFrame(columns=cols)
    d = dc[dc["TipoDiferencia"] == tipo].copy()
    if d.empty:
        return pd.DataFrame(columns=cols)
    d[col_cant] = d["Diferencia"].abs()
    return d[cols].sort_values(col_valor, ascending=False).reset_index(drop=True)


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
    sub = f"<p>{safe_text(subtitulo)}</p>" if subtitulo else ""
    st.markdown(
        f'<div class="market-header"><h1>{safe_text(titulo)}</h1>{sub}</div>',
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
    st.markdown(ui_kpi(safe_text(label), safe_text(value), safe_text(note)), unsafe_allow_html=True)


def badge(tipo):
    clase = {
        "OK": "ok",
        "FALTANTE": "bad",
        "SOBRANTE": "ok",
        "ABIERTA": "info",
        "CERRADA": "neutral",
    }.get(str(tipo).upper(), "neutral")
    return ui_chip(safe_text(tipo), clase)



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

    # Composición visual idéntica al acceso de Asistencia.
    # La autenticación, permisos y seguridad de Inventario se mantienen independientes.
    st.markdown("""
<style>
.stApp:has(.tp-lg-hero){background:radial-gradient(1100px 560px at 8% -10%,#FDECEC 0%,transparent 60%),radial-gradient(900px 520px at 100% 110%,#E4EBF8 0%,transparent 58%),var(--tp-bg);}
.stApp:has(.tp-lg-hero) .block-container{padding-top:1.6rem;max-width:1180px;}
.tp-lg-hero{position:relative;overflow:hidden;border-radius:28px;padding:36px 38px;min-height:640px;color:#fff;display:flex;flex-direction:column;justify-content:space-between;
  background:linear-gradient(150deg,#0B1220 0%,#111C33 55%,#1B2A4A 100%);box-shadow:0 30px 60px -30px rgba(15,23,42,.6);}
.tp-lg-hero::before{content:"";position:absolute;width:540px;height:540px;right:-190px;top:-170px;border-radius:50%;background:radial-gradient(circle,rgba(236,50,55,.55),rgba(236,50,55,0) 68%);}
.tp-lg-hero::after{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.045) 1px,transparent 1px);background-size:44px 44px;-webkit-mask-image:linear-gradient(180deg,#000,transparent 88%);mask-image:linear-gradient(180deg,#000,transparent 88%);}
.tp-lg-hero>*{position:relative;z-index:1;}
.tp-lg-logo{display:inline-flex;background:#fff;border-radius:16px;padding:10px 18px;box-shadow:0 12px 30px -12px rgba(0,0,0,.6);}
.tp-lg-k{font-size:.72rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#FF8A8E;margin:34px 0 10px;}
.tp-lg-h{font-size:2.2rem;font-weight:800;line-height:1.14;letter-spacing:-.02em;margin:0 0 14px;color:#fff;}
.tp-lg-h em{font-style:normal;color:#FF6B70;}
.tp-lg-p{color:#B7C2D9;font-size:.98rem;line-height:1.65;max-width:440px;margin:0;}
.tp-lg-feat{display:grid;gap:10px;margin-top:26px;max-width:460px;}
.tp-lg-feat div{display:flex;align-items:center;gap:12px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:14px;padding:12px 14px;font-size:.87rem;font-weight:600;color:#E6ECF8;}
.tp-lg-feat i{flex:0 0 auto;width:32px;height:32px;border-radius:10px;background:rgba(236,50,55,.2);color:#FF8A8E;display:flex;align-items:center;justify-content:center;}
.tp-lg-quote{position:relative;margin-top:26px;padding:18px 20px 18px 24px;border-radius:16px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);}
.tp-lg-quote::before{content:"";position:absolute;left:0;top:16px;bottom:16px;width:4px;border-radius:4px;background:#EC3237;}
.tp-lg-quote small{display:block;font-size:.68rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#FF8A8E;margin-bottom:8px;}
.tp-lg-quote p{margin:0;font-size:1.1rem;font-weight:600;line-height:1.5;color:#fff;}
.tp-lg-spacer{height:64px;}
.tp-lg-who{display:flex;flex-direction:column;align-items:center;text-align:center;margin-bottom:10px;animation:tpPop .4s ease;}
.tp-lg-who .tp-avatar{box-shadow:0 0 0 3px #fff,0 0 0 6px var(--tp-red),0 14px 30px -10px rgba(236,50,55,.55);}
.tp-lg-t{font-size:1.45rem;font-weight:800;color:var(--tp-ink);margin-top:16px;letter-spacing:-.01em;}
.tp-lg-s{font-size:.86rem;color:var(--tp-mute);margin-top:4px;}
.tp-lg-lock{width:58px;height:58px;border-radius:18px;background:var(--tp-red-soft);color:var(--tp-red);display:flex;align-items:center;justify-content:center;}
@keyframes tpPop{from{opacity:0;transform:translateY(8px) scale(.97);}to{opacity:1;transform:none;}}
.st-key-tpc_login_form{padding:32px 30px 26px!important;border-radius:26px!important;box-shadow:var(--tp-sh-2)!important;}
.st-key-tpc_login_form [data-baseweb="input"]{min-height:50px;background:#F6F7FA!important;}
.st-key-tpc_login_form .stButton>button{min-height:52px;border:none!important;background:linear-gradient(135deg,#EC3237,#C9262B)!important;box-shadow:0 14px 26px -12px rgba(236,50,55,.7);}
.st-key-tpc_login_form .stButton>button *{color:#111827!important;font-weight:700;}
.st-key-tpc_login_form .stButton>button{color:#111827!important;}
.tp-lg-note{display:flex;gap:8px;align-items:center;justify-content:center;font-size:.76rem;color:var(--tp-mute);margin-top:14px;}
@media (max-width:900px){.tp-lg-hero{min-height:0;padding:22px;border-radius:22px;}.tp-lg-k{margin-top:20px;}.tp-lg-h{font-size:1.5rem;}.tp-lg-feat,.tp-lg-spacer{display:none;}.tp-lg-quote{margin-top:16px;padding:14px 16px 14px 20px;}.tp-lg-quote p{font-size:.95rem;}}
</style>
""", unsafe_allow_html=True)

    _ico = lambda d: f'<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{d}</svg>'
    _i1 = _ico("<rect x='3' y='7' width='18' height='14' rx='2'/><path d='M3 11h18M8 7V3h8v4'/>")
    _i2 = _ico("<path d='M4 20V10M10 20V4M16 20v-8M22 20V7'/>")
    _i3 = _ico("<path d='M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z'/><path d='M9 12l2 2 4-4'/>")
    _lock = _ico("<rect x='5' y='11' width='14' height='9' rx='2'/><path d='M8 11V8a4 4 0 018 0v3'/>")
    _FRASES = [
        "Un inventario preciso ayuda a tomar mejores decisiones.",
        "Lo que se cuenta bien hoy, se vende mejor mañana.",
        "Comprar con información es cuidar el capital de la tienda.",
        "Un equipo organizado logra mejores resultados.",
        "Cada producto en su lugar es una venta que no se pierde.",
        "Contar con cuidado es la mejor forma de evitar sorpresas.",
        "Una venta bien atendida es un cliente para toda la vida.",
        "La constancia convierte un buen conteo en un gran control.",
        "Tú eres la cara de Premium: haz que te recuerden.",
        "Trabajando en equipo, las metas se hacen más pequeñas.",
    ]
    try:
        from zoneinfo import ZoneInfo as _ZoneInfo
        _ahora_lg = datetime.now(_ZoneInfo("America/Lima"))
    except Exception:
        _ahora_lg = datetime.now()
    _frase = _FRASES[_ahora_lg.toordinal() % len(_FRASES)]
    _saludo_h = "Buenos días" if _ahora_lg.hour < 12 else ("Buenas tardes" if _ahora_lg.hour < 19 else "Buenas noches")
    _hero = f"""<div class="tp-lg-hero"><div>
<span class="tp-lg-logo">{logo_tag(40)}</span>
<div class="tp-lg-k">{_saludo_h}, equipo Premium</div>
<div class="tp-lg-h">Tu inventario y tus compras, <em>en un solo lugar.</em></div>
<p class="tp-lg-p">Control de existencias, conteos y compras de Tiendas Premium, con información clara y al instante.</p>
<div class="tp-lg-feat">
<div><i>{_i1}</i>Inventario y conteos por producto</div>
<div><i>{_i2}</i>Pronósticos de demanda y reposición inteligente</div>
<div><i>{_i3}</i>Acceso protegido con cierre automático de sesión</div>
</div></div>
<div class="tp-lg-quote"><small>Frase del día</small><p>{_frase}</p></div></div>"""
    c_hero, c_form = st.columns([1.15, 1], gap="large")
    with c_hero:
        st.markdown("".join(x.strip() for x in _hero.splitlines()), unsafe_allow_html=True)
    with c_form:
        st.markdown('<div class="tp-lg-spacer"></div>', unsafe_allow_html=True)
        with ui_card_container("login_form"):
            _motivo = st.session_state.pop("_sesion_expirada", "")
            if _motivo:
                ui_callout(f"Tu sesión se cerró automáticamente por {_motivo}. Por favor, vuelve a iniciar sesión.", "warn")
            _saludo = st.empty()
            usuario = st.text_input("Usuario", placeholder="Tu usuario", key="tp_inv_login_user")
            password = st.text_input("Contraseña", type="password", placeholder="Tu contraseña", key="tp_inv_login_pass")
            _u_key = usuario.strip().lower()
            _fila_u = usuarios[usuarios["Usuario"].str.lower() == _u_key] if _u_key else usuarios.iloc[0:0]
            if not _fila_u.empty and LOGIN_MOSTRAR_FOTO:
                _nom_u = str(_fila_u.iloc[0]["NombreCompleto"]).strip() or str(_fila_u.iloc[0]["Usuario"])
                _saludo.markdown(f'<div class="tp-lg-who">{ui_avatar(_nom_u, 96)}<div class="tp-lg-t">Hola, {_html.escape(_nom_u.split()[0])}</div><div class="tp-lg-s">Ingresa tu contraseña para continuar</div></div>', unsafe_allow_html=True)
            else:
                _saludo.markdown(f'<div class="tp-lg-who"><div class="tp-lg-lock">{_lock}</div><div class="tp-lg-t">Bienvenido</div><div class="tp-lg-s">Ingresa con tu usuario y tu contraseña</div></div>', unsafe_allow_html=True)
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            segundos_bloqueo = int(float(st.session_state.get("login_bloqueo_hasta", 0.0)) - time.time())
            if segundos_bloqueo > 0:
                st.error(f"Demasiados intentos fallidos. Por seguridad, espera {segundos_bloqueo // 60 + 1} minuto(s) e inténtalo de nuevo.")
            _clic = st.button("Ingresar al sistema", use_container_width=True, key="login_btn", disabled=segundos_bloqueo > 0)
            if segundos_bloqueo <= 0 and (_clic or (usuario.strip() and password)):
                _intento = (_u_key, password)
                if st.session_state.get("login_ult_intento") == _intento and st.session_state.get("login_ult_msg"):
                    # Mismo intento repetido (por ejemplo, al recargar): se muestra el aviso sin contarlo otra vez.
                    st.error(st.session_state["login_ult_msg"])
                else:
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
                            st.session_state.login_timestamp = time.time()
                            st.session_state.ultima_actividad = time.time()
                            st.session_state.pop("login_ult_intento", None)
                            st.session_state.pop("login_ult_msg", None)
                            registrar_auditoria("LOGIN", "Inicio de sesión")
                            st.success("Acceso concedido")
                            st.rerun()
                        else:
                            intentos = int(st.session_state.get("login_intentos", 0)) + 1
                            if intentos >= MAX_INTENTOS_LOGIN:
                                st.session_state.login_intentos = 0
                                st.session_state.login_bloqueo_hasta = time.time() + BLOQUEO_LOGIN_SEGUNDOS
                                registrar_auditoria("LOGIN_BLOQUEADO", f"Usuario ingresado: {str(usuario).strip()}")
                                _msg = f"Demasiados intentos fallidos. Acceso bloqueado por {BLOQUEO_LOGIN_SEGUNDOS // 60} minutos."
                                st.session_state.pop("login_ult_intento", None)   # al terminar el bloqueo se podrá reintentar
                                st.session_state.pop("login_ult_msg", None)
                            else:
                                st.session_state.login_intentos = intentos
                                _msg = f"Usuario o contraseña incorrectos. Te quedan {MAX_INTENTOS_LOGIN - intentos} intento(s) antes de un bloqueo temporal."
                                st.session_state["login_ult_intento"] = _intento
                                st.session_state["login_ult_msg"] = _msg
                            st.error(_msg)
                    except Exception as exc:
                        mostrar_error_google(exc, "inicio de sesión")
            st.markdown('<div class="tp-lg-note">Conexión protegida · La sesión se cierra tras 30 min de inactividad</div>', unsafe_allow_html=True)
        ui_guia_instalar(st)
    st.stop()


# =========================================================
# INICIO
# =========================================================

def pantalla_inicio():
    usuario = st.session_state.usuario
    nombre = str(usuario.get("NombreCompleto", "")).strip() or str(usuario.get("Usuario", ""))
    primer_nombre = nombre.split()[0] if nombre.split() else ""
    header("Dashboard de Inventario", f"{saludo_actual()}, {nombre} · Resumen de existencias, conteos y compras")

    inv = cargar_inventario()
    conteos = cargar_conteos()
    sesiones = cargar_sesiones()

    sesion_actual = obtener_sesion_abierta()
    estado_txt, estado_chip, pct, val_prog = "Sin inventario activo", "neutral", 0, "—"
    if sesion_actual:
        m = metricas_cobertura(sesion_actual["IdSesion"], sesion_actual["Sucursal"])
        pct = int(max(0, min(100, m["cobertura"]))) if m["total"] else 0
        estado_txt = f"Inventario en curso · {safe_text(sesion_actual['NombreSesion'])}"
        estado_chip = "ok"
        val_prog = f"{m['cobertura']:.1f}% · {m['pendientes']} pendientes · Exactitud {m['exactitud']:.1f}%"

    hc1, hc2 = st.columns([1.5, 1])
    with hc1:
        st.markdown(
            f'<div class="tp-hero"><div class="tp-hero-top">{ui_avatar(nombre, 54)}<div>'
            f'<div class="tp-hero-hi">Hola, {safe_text(primer_nombre)}</div>{ui_chip(estado_txt, estado_chip)}</div></div>'
            f'<div class="tp-prog-lbl"><span>Cobertura del inventario</span><span>{val_prog}</span></div>'
            f'<div class="tp-prog"><i style="width:{pct}%"></i></div></div>',
            unsafe_allow_html=True,
        )
    with hc2:
        components.html("""<body style="margin:0;font-family:Montserrat,Arial,sans-serif"><div style="box-sizing:border-box;height:132px;background:#fff;border:1px solid #E3E6EC;border-radius:20px;display:flex;flex-direction:column;align-items:center;justify-content:center;box-shadow:0 1px 3px rgba(15,23,42,.05)"><div id="t" style="font-size:2.3rem;font-weight:700;color:#0F172A;font-variant-numeric:tabular-nums">--:--:--</div><div id="d" style="font-size:.8rem;color:#64748B;font-weight:600;text-transform:capitalize"></div></div><script>function u(){var n=new Date();document.getElementById("t").textContent=n.toLocaleTimeString("es-PE",{timeZone:"America/Lima",hour12:false});document.getElementById("d").textContent=n.toLocaleDateString("es-PE",{timeZone:"America/Lima",weekday:"long",day:"numeric",month:"long"})}u();setInterval(u,1000)</script></body>""", height=134)
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    stock_total = float(inv["StockSistema"].sum()) if not inv.empty else 0
    valor_inventario = float((inv["StockSistema"] * inv["CostoUnitario"]).sum()) if not inv.empty else 0
    activos = int((inv["Estado"].str.upper().isin(["ACTIVO", "ACTIVA", "1", "SI", "SÍ"])).sum()) if not inv.empty else len(inv)
    sesiones_abiertas = int((sesiones["Estado"].str.upper() == "ABIERTA").sum()) if not sesiones.empty else 0

    k1, k2, k3, k4 = st.columns(4)
    with k1: kpi("Productos", f"{len(inv):,}", f"{activos:,} activos")
    with k2: kpi("Stock sistema", f"{stock_total:,.0f}", "unidades")
    with k3: kpi("Valor inventario", formato_soles(valor_inventario), "a costo")
    with k4: kpi("Sesiones abiertas", str(sesiones_abiertas), "en curso")
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    c_refresh, c_info = st.columns([1, 3])
    with c_refresh:
        if st.button("Actualizar datos", use_container_width=True, key="inicio_actualizar"):
            actualizar_datos()
            st.rerun()
    with c_info:
        ui_callout("Los datos se mantienen en caché para reducir lecturas a Google Sheets. Actualiza manualmente cuando necesites información reciente.")

    alertas = alertas_operativas(inv, sesiones)
    if alertas:
        ui_seccion("Alertas", "Puntos que requieren tu atención")
        for texto_alerta in alertas:
            ui_callout(texto_alerta, "warn")

    ui_seccion("Acciones rápidas", "Atajos a las tareas más frecuentes")
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        st.button("Nueva sesión", use_container_width=True, key="qa_sesion", on_click=_ir_a, args=("Sesión",))
    with a2:
        st.button("Iniciar inventario", use_container_width=True, key="qa_inventario", type="primary", on_click=_ir_a, args=("Inventario",))
    with a3:
        st.button("Ver resultados", use_container_width=True, key="qa_resultados", on_click=_ir_a, args=("Resultados",))
    with a4:
        st.button("Consultar precio", use_container_width=True, key="qa_precios", on_click=_ir_a, args=("Precios",))

    ui_seccion("Últimos conteos", "Los 10 registros más recientes")
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

        m = metricas_cobertura(sesion["IdSesion"], sesion["Sucursal"])
        st.progress(m["cobertura"] / 100, text=f"Cobertura {m['cobertura']:.1f}% · {m['contados']:,}/{m['total']:,} verificados")
        a, b, c = st.columns(3)
        with a: kpi("Pendientes", f"{m['pendientes']:,}", "sin conteo físico")
        with b: kpi("Ceros verificados", f"{m['ceros']:,}", "comprobados")
        with c: kpi("Exactitud", f"{m['exactitud']:.1f}%", "de los contados")
        if m["pendientes"]:
            st.warning(f"Se puede cerrar parcialmente, pero {m['pendientes']:,} productos quedarán pendientes, no como faltantes.")
        observacion_cierre = st.text_area("Observación de cierre", placeholder="Motivo del cierre parcial", key=f"obs_cierre_{sesion['IdSesion']}")
        confirmar_cierre = st.checkbox("Confirmo el cierre y el registro de los productos pendientes", key=f"confirmar_cierre_{sesion['IdSesion']}")
        a1, a2 = st.columns(2)
        with a1:
            if st.button("📷 Continuar inventario", use_container_width=True):
                st.session_state.pagina = "Inventario"
                st.rerun()
        with a2:
            if st.button("🔒 Cerrar sesión", use_container_width=True, disabled=not confirmar_cierre):
                if m["pendientes"] and not observacion_cierre.strip():
                    st.error("Para un cierre parcial debes indicar el motivo.")
                else:
                    try:
                        resumen = calcular_resumen(sesion["IdSesion"])
                        resumen["ObservacionCierre"] = observacion_cierre.strip()
                        detalle_cierre = f"Cobertura {m['cobertura']:.1f}% · pendientes {m['pendientes']} · {observacion_cierre.strip()}"
                        if not cerrar_sesion(sesion["IdSesion"], detalle_cierre):
                            st.error("No se encontró la sesión para cerrar.")
                        else:
                            resumen["Estado"] = "CERRADA"
                            guardar_resumen(resumen)
                            st.success("Sesión cerrada; pendientes conservados en el universo de la sesión.")
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
                ui_seccion("Últimos escaneados")
                for _, fila in propios.iterrows():
                    st.markdown(
                        f"<div class='card' style='padding:10px 14px;margin-bottom:8px;display:flex;"
                        f"justify-content:space-between;align-items:center;'>"
                        f"<span><b>{safe_text(fila['Producto'])}</b> "
                        f"<span style='color:#6b7280;font-size:.78rem'>({safe_text(fila['FechaHora'])})</span></span>"
                        f"{'' if conteo_ciego_usuario(st.session_state.usuario) else badge(fila['TipoDiferencia'])}</div>",
                        unsafe_allow_html=True,
                    )

# =========================================================
# PRODUCTO
# =========================================================

def pantalla_producto(producto, sesion):
    codigo = limpiar_codigo(producto.get("CodigoBarras", "")) or limpiar_codigo(producto.get("CodigoProducto", "")) or str(producto.get("Producto", ""))
    zona = st.session_state.get("zona_activa", "")
    zona_habilitada = zona_usuario(sesion, st.session_state.usuario) if zona else None
    if zona and zona_habilitada is None:
        st.error("La zona seleccionada está finalizada o no te corresponde. Ve a Zonas.")
        return
    previo_zona = ultimo_conteo_zona(sesion["IdSesion"], zona, producto) if zona_habilitada else None
    ya_contado = (previo_zona is not None) if zona_habilitada else (ultimo_conteo_producto(sesion["IdSesion"], producto) is not None)
    # El reconteo solo aplica a productos ya contados (evita etiquetar mal si la bandera quedó activa).
    es_reconteo = bool(st.session_state.get("reconteo_activo", False)) and ya_contado
    previo = previo_zona if zona_habilitada else ultimo_conteo_producto(sesion["IdSesion"], producto)

    if zona_habilitada:
        st.info(f"📍 Conteo en: **{zona}** · Las cantidades de distintas zonas se sumarán.")
    if ya_contado and not es_reconteo:
        st.warning("⚠️ Este producto ya fue contado en esta sesión.")
        if previo and not conteo_ciego_usuario(st.session_state.usuario):
            st.info(
                f"Último conteo: {limpiar_numero(previo.get('StockFisico', 0)):,.0f} unidades "
                f"por {previo.get('NombreUsuario', '')} · {previo.get('FechaHora', '')}."
            )
        critico = es_diferencia_critica(previo.get("StockSistema", 0), previo.get("StockFisico", 0), previo.get("CostoUnitario", 0)) if previo else False
        if critico and not conteo_ciego_usuario(st.session_state.usuario):
            st.error("Diferencia significativa: se recomienda reconteo independiente.")
            if not solicitud_pendiente(sesion["IdSesion"], producto):
                if st.button("Solicitar reconteo por diferencia", key=f"solicitud_{codigo}"):
                    solicitar_reconteo(sesion, producto, st.session_state.usuario, "Diferencia crítica detectada")
                    st.rerun()
            else:
                st.warning("Reconteo pendiente de resolución.")
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
        if previo and not conteo_ciego_usuario(st.session_state.usuario):
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

    ciego = conteo_ciego_usuario(st.session_state.usuario)
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

    if zona_habilitada:
        st.caption("El faltante o sobrante se calcula al consolidar todas las zonas; aquí registras solo lo encontrado en esta zona.")
    if diferencia < 0:
        tipo = "FALTANTE"
        if not ciego and not zona_habilitada:
            st.error(f"🔴 Faltante: {abs(diferencia):,.0f} unidades · {formato_soles(abs(diferencia) * costo)}")
    elif diferencia > 0:
        tipo = "SOBRANTE"
        if not ciego and not zona_habilitada:
            st.success(f"🟢 Sobrante: {diferencia:,.0f} unidades · {formato_soles(diferencia * costo)}")
    else:
        tipo = "OK"
        if not ciego and not zona_habilitada:
            st.success("🟢 Stock exacto: no existe diferencia.")
    if ciego:
        st.info("🔒 Conteo ciego: el resultado se calculará al guardar.")

    confirmado = True
    if not ciego and not zona_habilitada and es_diferencia_critica(producto.get("StockSistema", 0), fisico, costo):
        st.warning(
            "⚠️ La cantidad difiere de forma significativa del sistema. Revisa estantes, almacén y otras "
            "ubicaciones, y verifica que el producto sea el correcto antes de guardar."
        )
        confirmado = st.checkbox(
            "Confirmo que el conteo es correcto",
            key=f"confirma_dif_{codigo}_{sesion['IdSesion']}",
        )

    verificacion = st.checkbox("He verificado físicamente este producto y confirmo la cantidad indicada (incluido cero).", key=f"verificado_{sesion['IdSesion']}_{codigo}")
    metodo = st.selectbox("Método de conteo", ["Escáner", "Búsqueda manual", "Código manual"])
    observacion = st.text_area("Observación", placeholder="Opcional")

    if not ya_contado:
        with st.expander("🔎 No encuentro este producto"):
            motivo_no_localizado = st.text_area("Dónde se buscó / motivo", key=f"motivo_nl_{sesion['IdSesion']}_{codigo}")
            if st.button("Registrar como no localizado", key=f"nl_{sesion['IdSesion']}_{codigo}"):
                try:
                    registrar_no_localizado(sesion, producto, motivo_no_localizado)
                    st.session_state.producto_pendiente = None
                    st.session_state.codigo_pendiente = ""
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
    c1, c2 = st.columns(2)
    with c1:
        motivo_valido = (not es_reconteo) or bool(observacion.strip())
        if es_reconteo and not motivo_valido:
            st.caption("El motivo de corrección es obligatorio para un reconteo.")
        if st.button("💾 Guardar conteo", type="primary", use_container_width=True, disabled=not (confirmado and verificacion and motivo_valido)):
            try:
                if zona_habilitada:
                    guardar_conteo_zona(sesion, st.session_state.usuario, producto, fisico, metodo, observacion, es_reconteo)
                else:
                    guardar_conteo(sesion, st.session_state.usuario, producto, fisico, metodo, observacion, es_reconteo)
                st.success("Cantidad guardada en la zona." if zona_habilitada else (f"{'Reconteo' if es_reconteo else 'Conteo'} guardado correctamente" if ciego else f"{'Reconteo' if es_reconteo else 'Conteo'} guardado: {tipo}"))
                sonido_confirmacion()
                st.session_state.reconteo_activo = False
                st.session_state.producto_pendiente = None
                st.session_state.codigo_pendiente = ""
                st.session_state.ultimo_codigo_scan = ""
                st.rerun()
            except Exception as exc:
                if isinstance(exc, ValueError):
                    st.error(str(exc))
                else:
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
                f"<div class='card'><b>{safe_text(nombre)}</b><br><span style='color:#6b7280;font-size:.8rem'>Código: {safe_text(producto.get('CodigoProducto',''))} · Barras: {safe_text(codigo)} · Stock: {"Oculto" if conteo_ciego_usuario(st.session_state.usuario) else f"{limpiar_numero(producto.get('StockSistema',0)):,.0f}"}</span></div>",
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

    zona_actual = st.session_state.get("zona_activa", "")
    if zona_actual:
        st.info(f"📍 Zona activa: **{zona_actual}**")
        if st.button("Cambiar de zona"):
            st.session_state.pagina = "Zonas"
            st.rerun()
    elif not zonas_sesion(sesion["IdSesion"]).empty:
        st.warning("Estás en modo general (sin zona). Para registrar cantidades por góndola, selecciona una zona en el menú Zonas.")
    m = metricas_cobertura(sesion["IdSesion"], sesion["Sucursal"])
    contados, total, porcentaje = m["contados"], m["total"], m["cobertura"]

    st.markdown(
        f"<div class='mobile-note'>🧾 <b>{safe_text(sesion['NombreSesion'])}</b> · {safe_text(sesion['Sucursal'])} · {contados:,}/{total:,} productos · {porcentaje:.1f}%</div>",
        unsafe_allow_html=True,
    )
    st.progress(min(porcentaje / 100, 1.0))
    with st.expander("⭐ Prioridad: pendientes del inventario anterior"):
        try:
            previos = pendientes_anteriores(sesion)
            if previos.empty:
                st.info("No hay pendientes históricos aplicables, o ya fueron verificados.")
            else:
                st.caption(f"{len(previos)} productos pendientes del inventario anterior, aún sin verificar en esta sesión.")
                columnas_prioridad = ["Producto", "CodigoProducto", "CodigoBarras", "Categoria", "EstadoVerificacion"]
                if not conteo_ciego_usuario(st.session_state.usuario):
                    columnas_prioridad.insert(4, "StockSistema")
                st.dataframe(previos[columnas_prioridad], hide_index=True, use_container_width=True)
                st.download_button("Descargar prioridades (Excel)", data=exportar_excel({"Prioridad":previos[columnas_prioridad]}), file_name=f"prioridades_{sesion['IdSesion']}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except Exception as exc:
            st.warning(f"No fue posible cargar las prioridades históricas: {exc}")

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
    sesion_fila = sesiones[sesiones["IdSesion"].astype(str) == seleccionado].iloc[0]
    cobertura_det = estado_cobertura(seleccionado, sesion_fila["Sucursal"])
    m = metricas_cobertura(seleccionado, sesion_fila["Sucursal"])
    st.progress(m["cobertura"]/100 if m["total"] else 0, text=f"Cobertura {m['cobertura']:.1f}% · {m['pendientes']} pendientes · {m['ceros']} ceros verificados")
    st.caption(f"Exactitud de los productos verificados: {m['exactitud']:.1f}% · No localizados: {m['no_localizados']}")
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

    ui_seccion("Principales faltantes")
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

    ui_seccion("Principales sobrantes")
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
        ui_seccion("Valor de faltantes por categoría")
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
        ui_seccion("Diferencias significativas a revisar")
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

    ui_seccion("Listas de faltantes y sobrantes (para tu sistema de ventas)")
    if dc.empty:
        st.info("No hay conteos para generar listas en esta sesión.")
    else:
        lista_falt = lista_diferencias(dc, "FALTANTE")
        lista_sobr = lista_diferencias(dc, "SOBRANTE")
        st.caption("Listas completas (no solo las 10 principales), con las cantidades en positivo. Usan el último conteo de cada producto.")
        xlsx_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        tab_f, tab_s = st.tabs([f"🔴 Faltantes ({len(lista_falt)})", f"🟢 Sobrantes ({len(lista_sobr)})"])
        for tab, lista, nombre, hoja, col_valor in (
            (tab_f, lista_falt, "faltantes", "Faltantes", "ValorFaltante"),
            (tab_s, lista_sobr, "sobrantes", "Sobrantes", "ValorSobrante"),
        ):
            with tab:
                if lista.empty:
                    st.info(f"No existen {nombre} en esta sesión.")
                    continue
                st.dataframe(lista, use_container_width=True, hide_index=True, column_config={
                    "CostoUnitario": st.column_config.NumberColumn("Costo", format="S/ %.2f"),
                    col_valor: st.column_config.NumberColumn("Valor", format="S/ %.2f"),
                })
                b1, b2 = st.columns(2)
                with b1:
                    try:
                        st.download_button(
                            f"📊 Descargar {nombre} (Excel)",
                            data=exportar_excel({hoja: lista}),
                            file_name=f"{nombre}_{seleccionado}.xlsx",
                            mime=xlsx_mime,
                            use_container_width=True,
                            key=f"dl_{nombre}_xlsx",
                        )
                    except Exception:
                        st.caption("Instala `openpyxl` en requirements.txt para exportar a Excel.")
                with b2:
                    st.download_button(
                        f"📥 Descargar {nombre} (CSV)",
                        data=lista.to_csv(index=False).encode("utf-8-sig"),
                        file_name=f"{nombre}_{seleccionado}.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key=f"dl_{nombre}_csv",
                    )

    ui_seccion("Ajustes sugeridos de stock")
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

    ui_seccion("Detalle completo")
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
                "Faltantes": lista_diferencias(dc, "FALTANTE"),
                "Sobrantes": lista_diferencias(dc, "SOBRANTE"),
                "Pendientes": cobertura_det[cobertura_det["EstadoVerificacion"].isin(["PENDIENTE", "NO LOCALIZADO"])],
                "Cobertura": cobertura_det,
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
    sesiones = cargar_sesiones()
    if sesiones.empty:
        st.info("Todavía no existen sesiones.")
        return
    ids = sesiones["IdSesion"].astype(str).iloc[::-1].tolist()
    seleccion = st.selectbox("Sesión a revisar (abierta o histórica)", ids, key="pend_sesion")
    ses = sesiones[sesiones["IdSesion"].astype(str) == seleccion].iloc[0]
    d = estado_cobertura(seleccion, ses["Sucursal"])
    m = metricas_cobertura(seleccion, ses["Sucursal"])
    st.progress(m["cobertura"]/100 if m["total"] else 0, text=f"Cobertura: {m['cobertura']:.1f}%")
    c1,c2,c3,c4 = st.columns(4)
    with c1: kpi("Esperados", str(m["total"]))
    with c2: kpi("Verificados", str(m["contados"]))
    with c3: kpi("Pendientes", str(m["pendientes"]))
    with c4: kpi("Exactitud", f"{m['exactitud']:.1f}%")
    if not d.empty:
        st.caption(f"Ceros verificados: {m['ceros']} · No localizados: {m['no_localizados']} (continúan pendientes)")
        filtro_estado = st.multiselect("Estados", sorted(d["EstadoVerificacion"].unique()), default=["PENDIENTE", "NO LOCALIZADO"])
        texto = st.text_input("Buscar nombre, código, marca o categoría", key="buscar_pendientes")
        cats = sorted([str(x) for x in d["Categoria"].dropna().unique() if str(x).strip()])
        categorias = st.multiselect("Categorías", cats, key="cats_pendientes")
        solo_cero = st.checkbox("Solo productos con stock sistema cero", value=False)
        vista = d[d["EstadoVerificacion"].isin(filtro_estado)] if filtro_estado else d.iloc[0:0]
        if categorias: vista = vista[vista["Categoria"].isin(categorias)]
        if solo_cero: vista = vista[vista["StockSistema"] == 0]
        if texto.strip():
            mask = pd.Series(False, index=vista.index)
            for col in ["Producto", "CodigoProducto", "CodigoBarras", "Marca", "Categoria"]:
                mask |= vista[col].astype(str).str.contains(re.escape(texto.strip()), case=False, na=False)
            vista = vista[mask]
        columnas = ["Producto", "CodigoProducto", "CodigoBarras", "Categoria", "Marca", "Sucursal", "StockSistema", "EstadoVerificacion"]
        st.caption(f"Mostrando {len(vista):,} productos · No se ocultan los de stock cero")
        st.dataframe(vista[columnas], use_container_width=True, hide_index=True)
        st.download_button("📊 Descargar lista filtrada (Excel)", data=exportar_excel({"Cobertura":vista[columnas]}), file_name=f"cobertura_{seleccion}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        pendientes = d[d["EstadoVerificacion"].isin(["PENDIENTE", "NO LOCALIZADO"])]
        st.download_button("📊 Descargar TODOS los pendientes (Excel)", data=exportar_excel({"Pendientes":pendientes[columnas]}), file_name=f"pendientes_completos_{seleccion}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    if cargar_universo()["IdSesion"].astype(str).eq(seleccion).sum() == 0:
        st.warning("Sesión anterior a esta actualización: cobertura estimada con el catálogo actual; no existe fotografía histórica.")


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

    ui_seccion("Exactitud por sesión")
    graf = t.set_index("Etiqueta")[["ExactitudInventario"]].rename(columns={"ExactitudInventario": "Exactitud %"})
    graf["Meta"] = META_EXACTITUD
    st.line_chart(graf)

    ui_seccion("Desfase neto por sesión")
    st.bar_chart(t.set_index("Etiqueta")["DesfaseNeto"])

    vista = t[["Fecha", "NombreSesion", "Sucursal", "ProductosContados", "ExactitudInventario", "ValorFaltantes", "ValorSobrantes", "DesfaseNeto"]]
    st.dataframe(vista, use_container_width=True, hide_index=True)


# =========================================================
# ETAPA 4 — INTELIGENCIA DE INVENTARIOS
# Solo sesiones cerradas; no confunde pendientes con faltantes.
# =========================================================

def _e4_sesiones_cerradas(sucursal="Todas"):
    ses = cargar_sesiones().copy()
    if ses.empty:
        return ses
    ses = ses[ses["Estado"].astype(str).str.upper() == "CERRADA"].copy()
    if sucursal != "Todas":
        ses = ses[ses["Sucursal"].astype(str) == sucursal]
    return ses.drop_duplicates("IdSesion", keep="last")


def _e4_conteos_historicos(sesiones):
    """Una observación por producto/sesión; respeta los reconteos y las zonas."""
    if sesiones.empty:
        return pd.DataFrame()
    todos = cargar_conteos()
    if todos.empty:
        return pd.DataFrame()
    d = todos[todos["IdSesion"].astype(str).isin(set(sesiones["IdSesion"].astype(str)))].copy()
    if d.empty:
        return d
    d = conteos_vigentes(d)
    # Se usa la misma consolidación que en resultados: los conteos por zona
    # están reflejados en ConteoInventario por el mecanismo de consolidación.
    d["_ProductoClave"] = clave_producto(d)
    d["_SesionClave"] = d["IdSesion"].astype(str)
    for col in ["StockSistema", "StockFisico", "Diferencia", "CostoUnitario", "ValorFaltante", "ValorSobrante"]:
        d[col] = pd.to_numeric(d[col], errors="coerce").fillna(0)
    d = d.merge(sesiones[["IdSesion", "NombreSesion", "FechaFin"]].astype(str), on="IdSesion", how="left")
    return d


def _e4_resumen_historico(sesiones):
    if sesiones.empty:
        return pd.DataFrame()
    r = cargar_resumenes().copy()
    if r.empty:
        return r
    r = r[r["IdSesion"].astype(str).isin(set(sesiones["IdSesion"].astype(str)))].copy()
    if r.empty:
        return r
    r = r.drop_duplicates("IdSesion", keep="last")
    for col in ["CoberturaInventario", "ExactitudInventario", "ValorFaltantes", "ValorSobrantes", "DesfaseNeto", "ProductosPendientes"]:
        r[col] = pd.to_numeric(r[col], errors="coerce")
    r = r.merge(sesiones[["IdSesion", "FechaFin"]].astype(str), on="IdSesion", how="left")
    r["OrdenFecha"] = pd.to_datetime(r["FechaFin"], errors="coerce")
    r = r.sort_values(["OrdenFecha", "IdSesion"], kind="stable")
    r["Sesión"] = r["NombreSesion"].astype(str) + " · " + r["IdSesion"].astype(str).str[-6:]
    return r


def _e4_recurrencias(conteos, minimo=2):
    if conteos.empty:
        return pd.DataFrame()
    d = conteos[conteos["Diferencia"].abs() > 0.000001].copy()
    if d.empty:
        return pd.DataFrame()
    d["PerdidaSoles"] = d["ValorFaltante"].clip(lower=0)
    d["SobranteSoles"] = d["ValorSobrante"].clip(lower=0)
    agrupado = d.groupby("_ProductoClave", as_index=False).agg(
        Producto=("Producto", "last"), Categoria=("Categoria", "last"),
        Sucursal=("Sucursal", "last"), SesionesConDiferencia=("IdSesion", "nunique"),
        PerdidaAcumulada=("PerdidaSoles", "sum"), SobranteAcumulado=("SobranteSoles", "sum"),
        UltimaFecha=("FechaFin", "max"),
    )
    return agrupado[agrupado["SesionesConDiferencia"] >= minimo].sort_values(
        ["SesionesConDiferencia", "PerdidaAcumulada"], ascending=False)


def _e4_criticidad(inventario, recurrencias):
    """Criticidad de control, no pronóstico de demanda: ABC valor + recurrencia."""
    abc = clasificar_abc(inventario)
    if abc.empty:
        return abc
    d = abc.copy()
    # Vincular por código de producto dentro de sucursal cuando esté disponible.
    # Si no existe coincidencia fiable, no se imputa recurrencia.
    d["SesionesConDiferencia"] = 0
    if not recurrencias.empty and "CodigoProducto" in d.columns:
        # El ABC actual no incluye sucursal; evitar atribuir recurrencias
        # entre sucursales usando un código que podría estar repetido.
        pass
    d["Criticidad"] = d["Clase"].map({"A": "ALTA", "B": "MEDIA", "C": "BAJA"}).fillna("SIN CLASE")
    return d


def _e4_alertas_stock(inv):
    """Alertas descriptivas, sin inventar rotación ni puntos de reposición."""
    if inv.empty:
        return pd.DataFrame()
    d = inv.copy()
    d["StockSistema"] = pd.to_numeric(d["StockSistema"], errors="coerce").fillna(0)
    d["CostoUnitario"] = pd.to_numeric(d["CostoUnitario"], errors="coerce").fillna(0)
    d["Alerta"] = d["StockSistema"].apply(lambda x: "STOCK NEGATIVO" if x < 0 else ("SIN STOCK" if x == 0 else ""))
    d.loc[(d["CostoUnitario"] <= 0) & (d["Alerta"] == ""), "Alerta"] = "SIN COSTO"
    return d[d["Alerta"] != ""][["Sucursal", "CodigoProducto", "Producto", "Categoria", "StockSistema", "CostoUnitario", "Alerta"]]


def _tab_inteligencia():
    st.markdown("### Inteligencia de inventarios")
    st.caption("Histórico de sesiones cerradas. Los productos pendientes o no localizados NO se clasifican como pérdidas.")
    sesiones_all = cargar_sesiones()
    if sesiones_all.empty:
        st.info("Todavía no hay sesiones para analizar.")
        return
    sucursales = sorted([str(x) for x in sesiones_all["Sucursal"].dropna().unique() if str(x).strip()])
    suc = st.selectbox("Sucursal", ["Todas"] + sucursales, key="e4_sucursal")
    ses = _e4_sesiones_cerradas(suc)
    if ses.empty:
        st.info("No existen sesiones cerradas para esta sucursal.")
        return
    resumen = _e4_resumen_historico(ses)
    conteos = _e4_conteos_historicos(ses)
    tabs = st.tabs(["📊 Ejecutivo", "🔁 Recurrentes", "💸 Pérdidas", "🅰️ ABC y criticidad", "🚨 Stock y reposición"])
    with tabs[0]:
        if resumen.empty:
            st.warning("No hay resúmenes históricos guardados. Cierra sesiones nuevas para alimentar las tendencias.")
        else:
            ultimo = resumen.iloc[-1]
            c1, c2, c3, c4 = st.columns(4)
            with c1: kpi("Sesiones cerradas", str(len(resumen)), "histórico filtrado")
            with c2: kpi("Cobertura final", f"{ultimo['CoberturaInventario']:.1f}%" if pd.notna(ultimo["CoberturaInventario"]) else "—", "última sesión")
            with c3: kpi("Exactitud final", f"{ultimo['ExactitudInventario']:.1f}%" if pd.notna(ultimo["ExactitudInventario"]) else "—", "solo productos verificados")
            with c4: kpi("Pérdida bruta", formato_soles(resumen["ValorFaltantes"].sum()), "suma histórica de faltantes")
            graf = resumen.set_index("Sesión")[["CoberturaInventario", "ExactitudInventario"]].rename(columns={"CoberturaInventario":"Cobertura %", "ExactitudInventario":"Exactitud %"})
            st.markdown("#### Evolución de cobertura y exactitud")
            st.line_chart(graf)
            st.markdown("#### Diferencias valorizadas por sesión")
            st.bar_chart(resumen.set_index("Sesión")[["ValorFaltantes", "ValorSobrantes"]].rename(columns={"ValorFaltantes":"Faltantes S/", "ValorSobrantes":"Sobrantes S/"}))
            st.dataframe(resumen[["Fecha", "NombreSesion", "Sucursal", "CoberturaInventario", "ExactitudInventario", "ProductosPendientes", "ValorFaltantes", "ValorSobrantes"]], use_container_width=True, hide_index=True)
            st.download_button("📥 Exportar histórico ejecutivo (Excel)", exportar_excel({"Tendencias":resumen.drop(columns=["OrdenFecha"])}), file_name="inteligencia_historico.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="e4_xls_hist")
    with tabs[1]:
        umbral = st.number_input("Mínimo de sesiones con diferencias", min_value=2, max_value=max(2, len(ses)), value=2, key="e4_recur_min")
        rec = _e4_recurrencias(conteos, umbral) if not conteos.empty else pd.DataFrame()
        if rec.empty:
            st.info("No se identifican diferencias recurrentes con el criterio seleccionado.")
        else:
            st.dataframe(rec.drop(columns=["_ProductoClave"]), use_container_width=True, hide_index=True)
            st.download_button("📥 Exportar recurrencias (Excel)", exportar_excel({"Recurrentes":rec.drop(columns=["_ProductoClave"])}), file_name="productos_recurrentes.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="e4_xls_rec")
        st.caption("Se cuenta una vez por producto y sesión, incluso si hubo varios reconteos.")
    with tabs[2]:
        if conteos.empty:
            st.info("No existen conteos históricos para valorizar.")
        else:
            perd = conteos[conteos["ValorFaltante"] > 0].copy()
            if perd.empty:
                st.success("No hay faltantes valorizados en las sesiones cerradas seleccionadas.")
            else:
                ranking = perd.groupby("_ProductoClave", as_index=False).agg(Producto=("Producto", "last"), Categoria=("Categoria", "last"), Sucursal=("Sucursal", "last"), Sesiones=("IdSesion", "nunique"), UnidadesFaltantes=("Diferencia", lambda v: float(-v[v < 0].sum())), PerdidaSoles=("ValorFaltante", "sum")).sort_values("PerdidaSoles", ascending=False)
                c1,c2=st.columns(2)
                with c1: kpi("Pérdida bruta histórica", formato_soles(perd["ValorFaltante"].sum()), "sin descontar sobrantes")
                with c2: kpi("Productos con pérdida", f"{len(ranking):,}", "productos distintos")
                st.bar_chart(ranking.head(15).set_index("Producto")["PerdidaSoles"])
                st.dataframe(ranking.drop(columns=["_ProductoClave"]), use_container_width=True, hide_index=True)
                st.download_button("📥 Exportar ranking de pérdidas (Excel)", exportar_excel({"Perdidas":ranking.drop(columns=["_ProductoClave"])}), file_name="ranking_perdidas.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="e4_xls_perd")
    with tabs[3]:
        inv = cargar_inventario()
        if suc != "Todas":
            inv = inv[inv["Sucursal"].astype(str) == suc].copy()
        abc = _e4_criticidad(inv, pd.DataFrame())
        if abc.empty:
            st.info("No hay stock valorizado suficiente para calcular ABC.")
        else:
            st.caption("ABC por valor actual a costo: A hasta 80 %, B hasta 95 %, C restante. Criticidad inicial basada en ABC, no en ventas.")
            st.dataframe(abc, use_container_width=True, hide_index=True)
            st.download_button("📥 Exportar ABC y criticidad (Excel)", exportar_excel({"ABC_Criticidad":abc}), file_name="abc_criticidad.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="e4_xls_abc")
    with tabs[4]:
        inv = cargar_inventario()
        if suc != "Todas":
            inv = inv[inv["Sucursal"].astype(str) == suc].copy()
        alertas = _e4_alertas_stock(inv)
        if alertas.empty:
            st.success("Sin alertas básicas de stock negativo, stock cero o costo faltante.")
        else:
            st.dataframe(alertas, use_container_width=True, hide_index=True)
            st.download_button("📥 Exportar alertas (Excel)", exportar_excel({"Alertas":alertas}), file_name="alertas_stock.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="e4_xls_alertas")
        st.info("Las sugerencias de cantidad a reponer, punto de pedido y días de cobertura se habilitarán cuando existan movimientos/ventas con fecha, producto, sucursal y unidades. No se estimará demanda a partir de conteos físicos.")


def pantalla_analisis():
    header("Análisis de inventario", "Prioriza el conteo, detecta problemas en los datos y mide el desempeño")
    es_admin = str(st.session_state.usuario.get("Rol", "")).upper() == "ADMIN"
    etiquetas = ["🎯 Pendientes", "🅰️ Análisis ABC"]
    if es_admin:
        etiquetas += ["🩺 Salud de datos", "👥 Productividad", "📈 Tendencia", "🧠 Inteligencia"]
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
        with tabs[5]:
            _tab_inteligencia()

# =========================================================
# ADMINISTRACIÓN
# =========================================================

def pantalla_admin():
    header("Administración", "Usuarios, inventario y control de sesiones")
    tab1, tab2, tab3, tab4 = st.tabs(["👤 Usuarios", "📦 Inventario", "🧾 Sesiones", "🛡️ Auditoría"])

    with tab1:
        st.markdown("### Conteo ciego por usuario")
        st.caption("Los contadores configurados no verán stock de sistema, diferencia ni conteos anteriores durante la captura. Los administradores conservan acceso de supervisión.")
        usuarios_cfg = cargar_usuarios()
        if not usuarios_cfg.empty:
            candidatos = usuarios_cfg[usuarios_cfg["Rol"].astype(str).str.upper() != "ADMIN"]["Usuario"].astype(str).tolist()
            if candidatos:
                seleccionado_cfg = st.selectbox("Contador", candidatos, key="cfg_contador")
                actual_cfg = conteo_ciego_usuario({"Usuario":seleccionado_cfg,"Rol":"CONTADOR"})
                habilitar_cfg = st.checkbox("Habilitar conteo ciego", value=actual_cfg, key=f"cfg_ciego_{seleccionado_cfg}")
                if st.button("Guardar configuración de conteo ciego"):
                    try:
                        configurar_conteo_ciego(seleccionado_cfg, habilitar_cfg, st.session_state.usuario.get("Usuario", ""))
                        st.success("Configuración guardada.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
        st.divider()
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
                elif len(password) < 10:
                    st.error("La contraseña debe tener al menos 10 caracteres.")
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
        st.markdown("### Solicitudes de reconteo")
        solicitudes = cargar_control_reconteos()
        if solicitudes.empty:
            st.caption("Sin solicitudes de reconteo registradas.")
        else:
            st.dataframe(solicitudes.sort_values("FechaSolicitud", ascending=False), hide_index=True, use_container_width=True)
        st.divider()
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
# ETAPA 5 — INTELIGENCIA DE COMPRAS / VENTAS
# Hoja VentasProductos: conserva exactamente las 25 columnas del reporte.
# =========================================================
VENTAS_HOJA = "VentasProductos"
VENTAS_COLUMNAS = [
    "N", "FECHA/HORA", "COMPROBANTE", "CÓDIGO DE BARRA", "CLIENTE",
    "PRODUCTO", "OBSERVACIÓN", "VARIANTE", "EQUIVALENCIA", "USUARIOS",
    "EMPLEADOS", "ALMACÉN", "TIPO", "SKU", "CATEGORÍA", "SUBCATEGORÍA",
    "U.M.", "PRECIO PROMEDIO", "COSTO*", "MONEDA", "CANTIDAD EQUIVALENCIA",
    "PRECIO X UNIDAD", "DESCUENTO", "CANTIDAD", "TOTAL",
]

@st.cache_resource(show_spinner=False)
def hoja_ventas():
    return hoja_control(VENTAS_HOJA, VENTAS_COLUMNAS)

@st.cache_data(ttl=120, show_spinner=False)
def cargar_ventas():
    hoja = hoja_ventas()
    valores = hoja.get_all_values()
    if not valores:
        return pd.DataFrame(columns=VENTAS_COLUMNAS)
    cabecera = [str(v).strip() for v in valores[0]]
    if cabecera[:len(VENTAS_COLUMNAS)] != VENTAS_COLUMNAS:
        raise ValueError("La hoja VentasProductos debe comenzar en la fila 1 con los 25 encabezados del reporte, desde N hasta TOTAL. No copies la fila de título general del Excel.")
    datos = [r[:len(VENTAS_COLUMNAS)] + [""] * max(0, len(VENTAS_COLUMNAS) - len(r)) for r in valores[1:] if any(str(x).strip() for x in r)]
    return pd.DataFrame(datos, columns=VENTAS_COLUMNAS)


def preparar_ventas(df):
    if df.empty:
        d = df.copy()
        for col in ["Fecha", "Dia", "Clave", "Cantidad", "CantidadValida", "VentaTotal", "CostoTotal", "MargenTotal"]:
            d[col] = pd.Series(dtype="object")
        return d
    d = df.copy()
    d["Fecha"] = pd.to_datetime(d["FECHA/HORA"].astype(str).str.strip(), format="%d-%m-%Y %H:%M", errors="coerce")
    fallos = d["Fecha"].isna()
    if fallos.any():
        d.loc[fallos, "Fecha"] = pd.to_datetime(d.loc[fallos, "FECHA/HORA"], dayfirst=True, errors="coerce")
    d = d[d["Fecha"].notna()].copy()
    d["Dia"] = d["Fecha"].dt.normalize()
    d["Clave"] = d["CÓDIGO DE BARRA"].astype(str).str.strip()
    d["Clave"] = d["Clave"].where(d["Clave"] != "", d["SKU"].astype(str).str.strip())
    d["Clave"] = d["Clave"].where(d["Clave"] != "", d["PRODUCTO"].astype(str).str.strip())
    d["Cantidad"] = pd.to_numeric(d["CANTIDAD"].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    d["VentaTotal"] = pd.to_numeric(d["TOTAL"].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    d["CostoTotal"] = pd.to_numeric(d["COSTO*"].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    d["MargenTotal"] = d["VentaTotal"] - d["CostoTotal"]
    d["CantidadValida"] = d["Cantidad"].notna() & (d["Cantidad"] > 0)
    return d


def diagnostico_ventas(df):
    if df.empty:
        return 0, 0, 0
    return len(df), int(df["CantidadValida"].sum()), int((~df["CantidadValida"]).sum())


def resumen_demanda(df, inventario, dias_entrega, dias_seguridad, ventana, objetivo_servicio):
    """Demanda por días calendario, sin extrapolar ventas ausentes como ceros confiables."""
    if df.empty:
        return pd.DataFrame()
    fecha_fin = df["Dia"].max()
    inicio = fecha_fin - pd.Timedelta(days=ventana - 1)
    recientes = df[(df["Dia"] >= inicio) & (df["Dia"] <= fecha_fin)].copy()
    if recientes.empty:
        return pd.DataFrame()
    # Sólo se consideran días de operación conocidos; los días sin exportación
    # pueden ser días sin ventas o días faltantes, y requieren confirmación.
    dias_base = max(1, min(ventana, (fecha_fin - df["Dia"].min()).days + 1))
    recientes = recientes[recientes["CantidadValida"]].copy()
    if recientes.empty:
        return pd.DataFrame()
    a = recientes.groupby("Clave", as_index=False).agg(
        Producto=("PRODUCTO", "first"), Categoria=("CATEGORÍA", "first"),
        Unidades=("Cantidad", "sum"), Lineas=("Clave", "size"),
        VentaTotal=("VentaTotal", "sum"), CostoTotal=("CostoTotal", "sum"),
        DiasConVenta=("Dia", "nunique"),
    )
    a["DemandaDiaria"] = a["Unidades"] / dias_base
    a["MargenTotal"] = a["VentaTotal"] - a["CostoTotal"]
    a["MargenPorcentaje"] = (100 * a["MargenTotal"] / a["VentaTotal"].replace(0, float("nan"))).round(1)
    # Incluye días sin ventas del producto dentro de la ventana, no solo días con venta.
    diario = recientes.groupby(["Clave", "Dia"])["Cantidad"].sum().reset_index()
    suma_cuadrados = diario.assign(Cuadrado=diario["Cantidad"] ** 2).groupby("Clave")["Cuadrado"].sum()
    # Desviación poblacional con días cero, suponiendo que la carga del periodo es completa.
    a["DesviacionDiaria"] = ((a["Clave"].map(suma_cuadrados).fillna(0) / dias_base - a["DemandaDiaria"] ** 2).clip(lower=0)) ** 0.5
    z = {90:1.282, 95:1.645, 98:2.054, 99:2.326}.get(int(objetivo_servicio), 1.645)
    a["StockSeguridad"] = (z * a["DesviacionDiaria"] * math.sqrt(max(1, dias_entrega)) + a["DemandaDiaria"] * dias_seguridad).apply(math.ceil)
    a["PuntoPedido"] = (a["DemandaDiaria"] * dias_entrega + a["StockSeguridad"]).apply(math.ceil)
    a["StockObjetivo"] = (a["DemandaDiaria"] * (dias_entrega + dias_seguridad + 7) + a["StockSeguridad"]).apply(math.ceil)
    inv = inventario.copy()
    inv["Clave"] = inv["CodigoBarras"].astype(str).str.strip()
    inv["Clave"] = inv["Clave"].where(inv["Clave"] != "", inv["CodigoProducto"].astype(str).str.strip())
    inv = inv.groupby("Clave", as_index=False).agg(StockActual=("StockSistema", "sum"), CostoUnitario=("CostoUnitario", "mean"))
    a = a.merge(inv, on="Clave", how="left", indicator="VinculoInventario")
    a["VinculadoInventario"] = a["VinculoInventario"].eq("both")
    a["StockActual"] = a["StockActual"].fillna(0)
    a["CostoUnitario"] = a["CostoUnitario"].fillna(0)
    a["DiasCobertura"] = a["StockActual"] / a["DemandaDiaria"].replace(0, float("nan"))
    a["CompraSugerida"] = (a["StockObjetivo"] - a["StockActual"]).clip(lower=0).apply(math.ceil)
    a.loc[a["StockActual"] > a["PuntoPedido"], "CompraSugerida"] = 0
    a["InversionSugerida"] = a["CompraSugerida"] * a["CostoUnitario"]
    a["Estado"] = "Adecuado"
    a.loc[a["StockActual"] <= a["PuntoPedido"], "Estado"] = "Reponer"
    a.loc[a["StockActual"] <= 0, "Estado"] = "Sin stock"
    a.loc[a["DiasCobertura"] > 60, "Estado"] = "Sobrestock posible"
    a.loc[~a["VinculadoInventario"], "Estado"] = "Sin vincular inventario"
    a.loc[~a["VinculadoInventario"], "CompraSugerida"] = 0
    a.loc[~a["VinculadoInventario"], "InversionSugerida"] = 0
    return a.sort_values(["Estado", "InversionSugerida"], ascending=[True, False])


def _leer_reporte_excel(archivo):
    bruto = pd.read_excel(archivo, sheet_name="ventas_productos", header=0, dtype=str)
    bruto.columns = [str(c).strip() for c in bruto.columns]
    if not all(c in bruto.columns for c in VENTAS_COLUMNAS):
        bruto = pd.read_excel(archivo, sheet_name="ventas_productos", header=1, dtype=str)
        bruto.columns = [str(c).strip() for c in bruto.columns]
    faltan = [c for c in VENTAS_COLUMNAS if c not in bruto.columns]
    if faltan:
        raise ValueError("Faltan encabezados del archivo: " + ", ".join(faltan))
    return bruto[VENTAS_COLUMNAS].fillna("").astype(str)


def pantalla_compras_inteligentes():
    header("Compras Inteligentes", "Ventas, rotación, quiebres de stock y capital inmovilizado")
    if str(st.session_state.usuario.get("Rol", "")).upper() != "ADMIN":
        st.error("Vista reservada para administración.")
        return
    tab1, tab2, tab3 = st.tabs(["📊 Demanda y reposición", "📥 Cargar ventas", "🛡️ Calidad de datos"])
    with tab2:
        st.markdown("### Carga diaria desde el sistema de ventas")
        st.info("La hoja VentasProductos utiliza los 25 encabezados de tu Excel, desde N hasta TOTAL. Pega los encabezados en la fila 1 de Google Sheets y los registros desde la fila 2. No copies notas ni títulos generales.")
        st.caption("El importador permite cargar el Excel directamente, pero no modifica el inventario ni las ventas originales.")
        try:
            ws = hoja_ventas()
            st.success("Hoja VentasProductos disponible en BD_Inventario_PremiumMarket.")
        except Exception as exc:
            st.error(f"No se pudo preparar VentasProductos: {exc}")
            return
        archivo = st.file_uploader("Selecciona el Excel de ventas", type=["xlsx"], key="ventas_excel_etapa5")
        if archivo is not None:
            try:
                nuevo = _leer_reporte_excel(archivo)
                st.write(f"Filas del archivo: {len(nuevo):,}")
                st.dataframe(nuevo.head(12), use_container_width=True, hide_index=True)
                if st.button("Agregar únicamente registros no importados", type="primary", key="ventas_importar"):
                    existente = cargar_ventas()
                    # Identidad multiconjunto: mantiene líneas idénticas repetidas dentro
                    # de una misma exportación y evita reimportarlas al repetir el archivo.
                    columnas_id = ["FECHA/HORA", "COMPROBANTE", "CÓDIGO DE BARRA", "PRODUCTO", "SKU", "COSTO*", "PRECIO PROMEDIO", "CANTIDAD", "TOTAL"]
                    def llaves_con_ocurrencia(frame):
                        if frame.empty: return []
                        b = frame[columnas_id].fillna("").astype(str).apply(lambda r: "\x1f".join(r), axis=1)
                        return list(zip(b, b.groupby(b).cumcount()))
                    previos = set(llaves_con_ocurrencia(existente))
                    claves = llaves_con_ocurrencia(nuevo)
                    filas = [list(fila) for i, fila in enumerate(nuevo.itertuples(index=False, name=None)) if claves[i] not in previos]
                    if filas:
                        ws.append_rows(filas, value_input_option="RAW")
                    cargar_ventas.clear()
                    registrar_auditoria("IMPORTACION_VENTAS", f"{len(filas)} filas nuevas; archivo {archivo.name}")
                    st.success(f"Importadas {len(filas)} filas nuevas. {len(nuevo)-len(filas)} filas ya estaban registradas.")
            except Exception as exc:
                st.error(f"No se pudo leer/importar el Excel: {exc}")
    try:
        ventas = preparar_ventas(cargar_ventas())
    except Exception as exc:
        st.error(f"Error al leer ventas: {exc}")
        return
    n, validas, sin_cantidad = diagnostico_ventas(ventas)
    with tab3:
        k1,k2,k3=st.columns(3)
        k1.metric("Líneas de venta",f"{n:,}")
        k2.metric("Con cantidad válida",f"{validas:,}")
        k3.metric("Sin cantidad confiable",f"{sin_cantidad:,}")
        if n:
            st.write("Período:",ventas["Dia"].min().strftime("%d/%m/%Y"),"a",ventas["Dia"].max().strftime("%d/%m/%Y"))
            st.write("Días con ventas:",ventas["Dia"].nunique())
            if sin_cantidad:
                st.warning("CANTIDAD está vacía, es cero o inválida en parte de los datos. No se generarán pedidos automáticos con cantidades incompletas.")
                st.dataframe(ventas.loc[~ventas["CantidadValida"], ["FECHA/HORA", "COMPROBANTE", "PRODUCTO", "CANTIDAD"]].head(100),use_container_width=True,hide_index=True)
    with tab1:
        if not n:
            st.info("Primero carga ventas en la hoja VentasProductos o importa el Excel desde la pestaña Cargar ventas.")
            return
        if sin_cantidad:
            st.error(f"Hay {sin_cantidad:,} líneas sin CANTIDAD válida. Corrige esos registros antes de generar recomendaciones de compra.")
            st.dataframe(ventas.loc[~ventas["CantidadValida"], ["FECHA/HORA", "PRODUCTO", "CANTIDAD"]].head(80), hide_index=True, use_container_width=True)
            return

        fecha_ultima = ventas["Dia"].max()
        fecha_primera = ventas["Dia"].min()
        dias_periodo = (fecha_ultima - fecha_primera).days + 1
        dias_con_ventas = ventas["Dia"].nunique()
        st.markdown("### Panel ejecutivo de abastecimiento")
        if dias_con_ventas < dias_periodo:
            st.warning(f"Hay {dias_periodo - dias_con_ventas} días sin registros entre {fecha_primera:%d/%m/%Y} y {fecha_ultima:%d/%m/%Y}. Verifica que las ventas diarias estén completas: los días ausentes reducen las estimaciones.")
        if (pd.Timestamp.today().normalize() - fecha_ultima).days > 2:
            st.warning(f"Última venta cargada: {fecha_ultima:%d/%m/%Y}. Actualiza la hoja antes de tomar decisiones de compra.")

        c1,c2,c3,c4=st.columns(4)
        ventana=c1.selectbox("Histórico de demanda",[7,14,30,60,90],index=2,format_func=lambda v:f"Últimos {v} días",key="ci_ventana")
        entrega=c2.number_input("Entrega proveedor · días",min_value=1,max_value=90,value=3,key="ci_entrega")
        seguridad=c3.number_input("Colchón · días",min_value=0,max_value=60,value=4,key="ci_colchon")
        servicio=c4.selectbox("Nivel de servicio",[90,95,98,99],index=1,format_func=lambda v:f"{v}%",key="ci_servicio")
        inventario=cargar_inventario()
        resumen=resumen_demanda(ventas,inventario,int(entrega),int(seguridad),int(ventana),int(servicio))
        if resumen.empty:
            st.info("No hay ventas válidas en el período.")
            return
        if (~resumen["VinculadoInventario"]).any():
            st.warning(f"{int((~resumen['VinculadoInventario']).sum())} productos vendidos no coinciden con el inventario por código de barras/SKU. No se recomienda compra para ellos.")
        st.caption("El stock mostrado procede de la hoja Inventario (stock registrado), no de una lectura física en tiempo real. Las recomendaciones son orientativas y requieren validar existencias, compras en tránsito y tiempos de proveedor.")
        k1,k2,k3,k4=st.columns(4)
        k1.metric("Productos vendidos",f"{resumen['Clave'].nunique():,}")
        k2.metric("Unidades · período",f"{resumen['Unidades'].sum():,.0f}")
        k3.metric("En riesgo de reposición",f"{int(((resumen['CompraSugerida']>0)&resumen['VinculadoInventario']).sum()):,}")
        k4.metric("Compra orientativa",formato_soles(resumen["InversionSugerida"].sum()))

        st.divider()
        st.markdown("### Explorador de productos")
        st.caption("Busca por nombre, código de barras o SKU. Las gráficas se calculan con CANTIDAD, agregada por día.")
        buscar=st.text_input("Buscar producto",placeholder="Ej.: Coca Cola, Sporade, 775...",key="ci_buscar")
        opciones=resumen.copy()
        if buscar.strip():
            patron=re.escape(buscar.strip())
            opciones=opciones[opciones["Producto"].astype(str).str.contains(patron,case=False,na=False,regex=True)|opciones["Clave"].astype(str).str.contains(patron,case=False,na=False,regex=True)]
        if opciones.empty:
            st.info("No hay productos vendidos que coincidan con la búsqueda en el período elegido.")
        else:
            opciones=opciones.sort_values("Unidades",ascending=False)
            etiquetas={str(r.Clave):f"{r.Producto}  ·  {r.Clave}" for r in opciones.itertuples()}
            clave=st.selectbox("Producto a analizar",list(etiquetas),format_func=lambda k:etiquetas[k],key="ci_producto")
            p=resumen[resumen["Clave"].astype(str)==clave].iloc[0]
            pc1,pc2,pc3,pc4,pc5=st.columns(5)
            pc1.metric("Stock registrado",f"{p['StockActual']:,.0f}" if p["VinculadoInventario"] else "Sin vínculo")
            pc2.metric("Demanda diaria",f"{p['DemandaDiaria']:.2f} und")
            pc3.metric("Cobertura actual",f"{p['DiasCobertura']:.1f} días" if pd.notna(p["DiasCobertura"]) else "—")
            pc4.metric("Punto de pedido",f"{p['PuntoPedido']:,.0f} und")
            pc5.metric("Compra sugerida",f"{p['CompraSugerida']:,.0f} und" if p["VinculadoInventario"] else "No disponible")
            st.markdown(f"**Estado:** {p['Estado']}  ·  **Stock de seguridad:** {p['StockSeguridad']:,.0f} und  ·  **Stock objetivo:** {p['StockObjetivo']:,.0f} und")
            periodo_inicio=fecha_ultima-pd.Timedelta(days=int(ventana)-1)
            fechas=pd.date_range(max(fecha_primera,periodo_inicio),fecha_ultima,freq="D")
            vprod=ventas[(ventas["Clave"].astype(str)==clave)&(ventas["Dia"]>=fechas.min())].copy()
            serie=vprod.groupby("Dia")["Cantidad"].sum().reindex(fechas,fill_value=0)
            serie.index.name="Día"
            izq,der=st.columns([1.5,1])
            with izq:
                st.markdown("**Ventas diarias · unidades**")
                st.bar_chart(serie.rename("Unidades vendidas"),color="#00A959",use_container_width=True)
            with der:
                st.markdown("**Proyección de existencias**")
                horizonte=max(14,int(entrega)+int(seguridad)+7)
                dias=list(range(horizonte+1))
                proy=pd.DataFrame({"Día":dias,"Stock proyectado sin reposición":[max(0,float(p["StockActual"])-float(p["DemandaDiaria"])*d) for d in dias],"Punto de pedido":[float(p["PuntoPedido"])]*len(dias)}).set_index("Día")
                st.line_chart(proy,use_container_width=True)
                st.caption("Escenario lineal con demanda promedio constante; no descuenta pedidos en tránsito ni predice cambios de temporada.")
            v1,v2,v3=st.columns(3)
            v1.metric("Ventas del producto",formato_soles(p["VentaTotal"]))
            v2.metric("Margen bruto",formato_soles(p["MargenTotal"]))
            v3.metric("Inversión estimada",formato_soles(p["InversionSugerida"]))

        st.divider()
        st.markdown("### Productos de mayor rotación")
        st.caption("Ranking por unidades vendidas en el período. Los productos con distinta presentación o código se muestran por separado.")
        top=resumen.sort_values("Unidades",ascending=False).head(15).copy()
        top["Etiqueta"]=(top["Producto"].astype(str).str.slice(0,36)+" · "+top["Clave"].astype(str).str.slice(-6))
        top_graf=top.set_index("Etiqueta")["Unidades"].sort_values()
        st.bar_chart(top_graf,color="#EC3237",horizontal=True,use_container_width=True)
        st.dataframe(top[["Producto","Clave","Unidades","DemandaDiaria","StockActual","DiasCobertura","VentaTotal","MargenTotal","Estado"]],hide_index=True,use_container_width=True)

        st.divider()
        st.markdown("### Prioridades de compra y capital inmovilizado")
        t1,t2,t3=st.tabs(["Reponer ahora","Baja rotación y sobrestock","Plan completo"])
        with t1:
            urg=resumen[(resumen["VinculadoInventario"])&(resumen["CompraSugerida"]>0)].sort_values(["DiasCobertura","InversionSugerida"],ascending=[True,False])
            st.dataframe(urg[["Producto","Clave","StockActual","DemandaDiaria","DiasCobertura","PuntoPedido","CompraSugerida","CostoUnitario","InversionSugerida","Estado"]],hide_index=True,use_container_width=True)
            st.caption("Revisa manualmente cada propuesta antes de emitir una orden de compra.")
        with t2:
            st.caption("Productos del catálogo sin ventas en la ventana o con cobertura elevada. No se asume que no hayan vendido históricamente.")
            inv=inventario.copy()
            inv["Clave"] = inv["CodigoBarras"].astype(str).str.strip()
            inv["Clave"] = inv["Clave"].where(inv["Clave"]!="",inv["CodigoProducto"].astype(str).str.strip())
            invg=inv.groupby("Clave",as_index=False).agg(Producto=("Producto","first"),StockActual=("StockSistema","sum"),CostoUnitario=("CostoUnitario","mean"))
            invg=invg.merge(resumen[["Clave","DemandaDiaria","DiasCobertura","Unidades"]],on="Clave",how="left")
            invg["ValorStock"]=invg["StockActual"].clip(lower=0)*invg["CostoUnitario"].fillna(0)
            invg["Diagnostico"]="Revisar"
            invg.loc[invg["Unidades"].isna(),"Diagnostico"]="Sin ventas en ventana"
            invg.loc[invg["DiasCobertura"]>60,"Diagnostico"]="Cobertura mayor a 60 días"
            lentos=invg[(invg["StockActual"]>0)&(invg["Diagnostico"]!="Revisar")].sort_values("ValorStock",ascending=False)
            a1,a2=st.columns(2)
            a1.metric("Referencias para revisar",f"{len(lentos):,}")
            a2.metric("Capital a costo en revisión",formato_soles(lentos["ValorStock"].sum()))
            st.dataframe(lentos[["Producto","Clave","StockActual","Unidades","DiasCobertura","CostoUnitario","ValorStock","Diagnostico"]],hide_index=True,use_container_width=True)
            st.caption("Antes de reducir compras verifica estacionalidad, productos nuevos y días faltantes en el histórico.")
        with t3:
            columnas=["Producto","Clave","Categoria","Unidades","VentaTotal","CostoTotal","MargenTotal","MargenPorcentaje","DemandaDiaria","StockActual","DiasCobertura","PuntoPedido","StockSeguridad","StockObjetivo","CompraSugerida","InversionSugerida","Estado"]
            st.dataframe(resumen[columnas],hide_index=True,use_container_width=True)
            st.download_button("Descargar análisis de compras (Excel)",exportar_excel({"Plan de compras":resumen[columnas],"Top rotacion":top[["Producto","Clave","Unidades","DemandaDiaria","VentaTotal"]],"Capital inmovilizado":lentos if 'lentos' in locals() else pd.DataFrame()}),file_name="compras_inteligentes_premium.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)


# ================================================================
# PREMIUM STOCK INTELLIGENCE — Motor analítico (integrado en app.py)
# ================================================================
import numpy as np
from scipy.stats import norm
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

_P_COLORS = {'red':'#EC3237','green':'#00A959','blue':'#2777BC','navy':'#1D2A44','muted':'#7787A0','gray':'#F4F6F9'}


def _p_plot(fig, height=350):
    # Etiquetas legibles sin necesidad de hover.
    fig.update_layout(uniformtext_minsize=10, uniformtext_mode='show')
    fig.update_layout(template='plotly_white', height=height, margin=dict(l=12,r=12,t=30,b=15),
        paper_bgcolor='white', plot_bgcolor='white', font=dict(color='#334155',size=12,family='Montserrat, sans-serif'),
        hovermode='x unified', legend=dict(orientation='h',y=-0.22),
        xaxis=dict(showgrid=False), yaxis=dict(gridcolor='#E3E6EC'))
    fig.update_yaxes(automargin=True)
    st.plotly_chart(fig, use_container_width=True, config={'displaylogo':False,'scrollZoom':False,'toImageButtonOptions':{'format':'png','scale':2}})


def _p_inventory(inv):
    d=inv.copy()
    d['Clave']=d['CodigoBarras'].fillna('').astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
    d['Clave']=d['Clave'].mask(d['Clave'].eq(''), d['CodigoProducto'].fillna('').astype(str).str.strip())
    for c in ['StockSistema','CostoUnitario']:
        d[c]=pd.to_numeric(d[c],errors='coerce').fillna(0)
    d['CostoStock']=d['StockSistema'].clip(lower=0)*d['CostoUnitario']
    g=d.groupby('Clave',as_index=False).agg(Stock=('StockSistema','sum'),Capital=('CostoStock','sum'),ProductoInv=('Producto','first'))
    g['CostoUnitario']=np.where(g['Stock']>0,g['Capital']/g['Stock'],0)
    # Para existencias cero, conservar el costo registrado si existe.
    fallback=d.groupby('Clave')['CostoUnitario'].mean()
    g['CostoUnitario']=np.where(g['CostoUnitario']>0,g['CostoUnitario'],g['Clave'].map(fallback).fillna(0))
    return g


def _p_daily(ventas, days=None):
    d=ventas.loc[ventas['CantidadValida']].copy()
    if d.empty: return d, pd.DatetimeIndex([]), pd.DataFrame()
    d['Clave']=d['Clave'].astype(str).str.strip().str.replace(r'\.0$','',regex=True)
    d=d[d['Clave'].ne('')]
    last=d['Dia'].max()
    first=d['Dia'].min()
    if days: first=max(first,last-pd.Timedelta(days=days-1))
    d=d[d['Dia']>=first]
    calendar=pd.date_range(first,last,freq='D')
    grouped=d.groupby(['Clave','Dia'],as_index=False)['Cantidad'].sum()
    return d,calendar,grouped


def _p_forecast_candidates(series, horizon, allow_advanced=True):
    """Validación temporal holdout: no barajar fechas ni entrenar con el futuro."""
    y=np.asarray(series,dtype=float)
    n=len(y)
    hold=max(3,min(21,n//5)) if n>=21 else 0
    def forecast(name, train, steps):
        train=np.asarray(train,dtype=float)
        steps=int(steps)
        if name=='Media móvil 7d':
            return np.full(steps,max(0,float(np.mean(train[-min(7,len(train)):]))))
        if name=='Media ponderada 28d':
            s=train[-min(28,len(train)):]
            w=np.arange(1,len(s)+1,dtype=float)
            return np.full(steps,max(0,float(np.dot(s,w)/w.sum())))
        if name=='Estacional semanal':
            if len(train)<21: return np.full(steps,float(np.mean(train)))
            return np.maximum(0,np.array([np.mean(train[max(0,len(train)-28):][np.arange(max(0,len(train)-28),len(train))%7==(len(train)+i)%7]) for i in range(steps)]))
        if name=='Suavizamiento ETS':
            from statsmodels.tsa.holtwinters import ExponentialSmoothing
            seasonal='add' if len(train)>=42 else None
            fit=ExponentialSmoothing(train,trend=None,seasonal=seasonal,seasonal_periods=7 if seasonal else None,
                 initialization_method='estimated').fit(optimized=True)
            return np.maximum(0,np.asarray(fit.forecast(steps),dtype=float))
        if name=='StatsForecast AutoTheta':
            from statsforecast import StatsForecast
            from statsforecast.models import AutoTheta
            df_sf=pd.DataFrame({'unique_id':'producto','ds':pd.date_range('2024-01-01',periods=len(train),freq='D'),'y':train})
            model=StatsForecast(models=[AutoTheta(season_length=7)],freq='D',n_jobs=1)
            out=model.forecast(df=df_sf,h=steps)
            return np.maximum(0,out['AutoTheta'].to_numpy(dtype=float))
        if name=='LightGBM':
            import lightgbm as lgb
            if len(train)<70: raise ValueError('historial insuficiente')
            # Predicción recursiva: las características de rezago se generan exclusivamente
            # con datos pasados y pronósticos ya generados.
            def feats(arr,t):
                return [arr[t-1],arr[t-7],np.mean(arr[t-7:t]),np.mean(arr[t-14:t]),
                    np.std(arr[t-14:t]), t%7]
            X=np.array([feats(train,t) for t in range(14,len(train))]); Y=train[14:]
            m=lgb.LGBMRegressor(n_estimators=90,max_depth=3,num_leaves=7,learning_rate=.055,
                 min_child_samples=12,verbosity=-1,random_state=42,n_jobs=1)
            m.fit(X,Y)
            history=list(train); out=[]
            for _ in range(steps):
                pred=max(0,float(m.predict(np.array(feats(np.asarray(history),len(history))).reshape(1,-1))[0]))
                out.append(pred); history.append(pred)
            return np.array(out)
        raise ValueError(name)
    candidates=['Media móvil 7d','Media ponderada 28d']
    if n>=21: candidates.append('Estacional semanal')
    if allow_advanced and n>=28: candidates.append('Suavizamiento ETS')
    if allow_advanced and n>=42: candidates.append('StatsForecast AutoTheta')
    if allow_advanced and n>=90: candidates.append('LightGBM')
    scores=[]
    for name in candidates:
        try:
            if hold:
                pred=forecast(name,y[:-hold],hold)
                mae=float(np.mean(np.abs(y[-hold:]-pred)))
                bias=float(np.mean(pred-y[-hold:]))
            else:
                mae=np.nan; bias=np.nan
            scores.append((name,mae,bias))
        except Exception:
            continue
    if not scores: scores=[('Media móvil 7d',np.nan,np.nan)]
    winner=min(scores,key=lambda v:v[1] if np.isfinite(v[1]) else 1e20)[0]
    try: pred=forecast(winner,y,horizon)
    except Exception: pred=np.full(horizon,float(np.mean(y[-min(7,n):])))
    # Incertidumbre: aproximación empírica basada en error de validación temporal
    # y dispersión diaria. No equivale a un intervalo calibrado de demanda.
    best_mae=next((r[1] for r in scores if r[0]==winner),np.nan)
    sigma=max(float(np.std(y[-min(n,56):])),float(best_mae)*1.253 if np.isfinite(best_mae) else 0,0.25)
    widening=np.sqrt(1+np.arange(horizon)/7)
    low=np.maximum(0,pred-1.645*sigma*widening)
    high=np.maximum(pred,pred+1.645*sigma*widening)
    return {'modelo':winner,'pronostico':pred,'inferior':low,'superior':high,'sigma':sigma,
            'scores':pd.DataFrame(scores,columns=['Modelo','MAE validación','Sesgo validación']), 'holdout':hold}


def _p_metrics(ventas, inv, window, lead, review, service, budget, min_history):
    d,dates,grouped=_p_daily(ventas,window)
    if d.empty: return pd.DataFrame(),dates,grouped
    n=len(dates)
    z=float(norm.ppf(service/100))
    agg=d.groupby('Clave',as_index=False).agg(Producto=('PRODUCTO','first'),Categoria=('CATEGORÍA','first'),
        Unidades=('Cantidad','sum'),Venta=('VentaTotal','sum'),CostoVenta=('CostoTotal','sum'),
        UltimaVenta=('Dia','max'),DiasConVenta=('Dia','nunique'))
    sums=grouped.groupby('Clave')['Cantidad'].agg(lambda x:float(np.sum(np.asarray(x,dtype=float)**2)))
    agg['Demanda']=agg['Unidades']/max(1,n)
    agg['Sigma']=np.sqrt((agg['Clave'].map(sums).fillna(0)/max(1,n)-agg['Demanda']**2).clip(lower=0))
    agg['Margen']=agg['Venta']-agg['CostoVenta']
    agg['MargenPct']=np.where(agg['Venta']>0,agg['Margen']/agg['Venta']*100,0)
    agg=agg.merge(_p_inventory(inv),on='Clave',how='outer',indicator=True)
    agg['Vinculado']=agg['_merge'].ne('left_only') & agg['Stock'].notna()
    agg['Producto']=agg['Producto'].fillna(agg['ProductoInv']).fillna('Sin nombre')
    for col in ['Unidades','Venta','CostoVenta','Margen','MargenPct','Demanda','Sigma','Stock','Capital','CostoUnitario','DiasConVenta']:
        agg[col]=pd.to_numeric(agg[col],errors='coerce').fillna(0)
    agg['UltimaVenta']=pd.to_datetime(agg['UltimaVenta'])
    agg['DiasSinVenta']=(dates[-1]-agg['UltimaVenta']).dt.days if len(dates) else np.nan
    agg['Cobertura']=np.where(agg['Demanda']>0,agg['Stock']/agg['Demanda'],np.nan)
    agg['Seguridad']=np.ceil(z*agg['Sigma']*np.sqrt(max(1,lead)))
    agg['PuntoPedido']=np.ceil(agg['Demanda']*lead+agg['Seguridad'])
    agg['Objetivo']=np.ceil(agg['Demanda']*(lead+review)+agg['Seguridad'])
    agg['Sugerencia']=np.maximum(0,agg['Objetivo']-agg['Stock']).astype(int)
    agg.loc[(agg['Stock']>agg['PuntoPedido']) | (~agg['Vinculado']) | (agg['Demanda']<=0),'Sugerencia']=0
    agg['Inversion']=agg['Sugerencia']*agg['CostoUnitario']
    agg['Riesgo']=np.select([~agg['Vinculado'],(agg['Stock']<=0)&(agg['Demanda']>0),
       (agg['Cobertura']<=lead)&(agg['Demanda']>0),agg['Stock']<=agg['PuntoPedido'],
       agg['Cobertura']>60,(agg['Demanda']==0)&(agg['Stock']>0)],
       ['Sin vínculo','Agotado','Quiebre probable','Reponer','Sobrestock','Sin ventas'],default='Adecuado')
    agg['CapitalLento']=np.where(agg['Riesgo'].isin(['Sobrestock','Sin ventas']),agg['Capital'],0)
    agg['Prioridad']=np.where(agg['Riesgo'].eq('Agotado'),5,np.where(agg['Riesgo'].eq('Quiebre probable'),4,
       np.where(agg['Riesgo'].eq('Reponer'),3,0)))
    agg['Prioridad']=agg['Prioridad']*(1+np.maximum(agg['MargenPct'],0)/100)
    agg['Calidad']=np.where(n<min_history,'Historial corto',np.where(agg['DiasConVenta']<3,'Ventas esporádicas','Orientativa'))
    return agg,dates,grouped


def _p_scenario_plot(stock,forecast,lower,upper,dates,lead,point):
    f=np.asarray(forecast)
    expected=np.maximum(0,stock-np.cumsum(f))
    optimistic=np.maximum(0,stock-np.cumsum(lower))
    pessimistic=np.maximum(0,stock-np.cumsum(upper))
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=list(dates)+list(dates[::-1]),y=list(optimistic)+list(pessimistic[::-1]),
         fill='toself',fillcolor='rgba(39,119,188,.12)',line=dict(color='rgba(0,0,0,0)'),name='Escenarios bajo/alto'))
    fig.add_trace(go.Scatter(x=dates,y=expected,name='Stock esperado',mode='lines+markers+text',text=[f'{v:.1f}' for v in expected],textposition='top center',textfont=dict(size=10,color=_P_COLORS['blue']),cliponaxis=False,line=dict(color=_P_COLORS['blue'],width=3)))
    fig.add_hline(y=point,line_dash='dot',line_color=_P_COLORS['red'],annotation_text='Punto de pedido')
    if lead<len(dates): fig.add_vline(x=dates[lead].timestamp()*1000,line_dash='dash',line_color=_P_COLORS['green'])
    _p_plot(fig,390)


def _p_excel(sheets):
    output=io.BytesIO()
    with pd.ExcelWriter(output,engine='openpyxl') as writer:
        for name,data in sheets.items():
            safe=data.copy().replace([np.inf,-np.inf],np.nan)
            for c in safe.columns:
                if pd.api.types.is_datetime64_any_dtype(safe[c]):
                    safe[c]=safe[c].dt.tz_localize(None) if getattr(safe[c].dt,'tz',None) else safe[c]
            safe.to_excel(writer,sheet_name=name[:31],index=False)
    return output.getvalue()


def _psi_manager_purchase_view(summary, dates, grouped, ventas, lead, service):
    """Vista gerencial: propuesta de compra para 14 días desde recepción."""
    from zoneinfo import ZoneInfo
    st.markdown('### Plan de compra · 14 días desde la recepción')
    st.caption('Responde tres preguntas: ¿qué se está vendiendo?, ¿cuánto pedir? y ¿cuánto dinero comprometer?')
    today=pd.Timestamp.now(tz=ZoneInfo('America/Lima')).normalize().tz_localize(None)
    saturday=today+pd.Timedelta(days=(5-today.weekday())%7)
    a,b,c=st.columns([1,1,1])
    with a: arrival=st.date_input('Fecha estimada de llegada',value=saturday.date(),key='psi_mgr_arrival')
    with b: duration=st.number_input('Días que debe durar el pedido',min_value=1,max_value=90,value=14,key='psi_mgr_duration')
    with c: reserve=st.selectbox('Protección ante ventas mayores a lo normal',[90,95,97,99],index=1,key='psi_mgr_service')
    st.caption('La cobertura empieza al recibir la mercadería, no al realizar el pedido. Se considera el stock disponible proyectado a la llegada.')
    st.markdown('**¿Qué productos deseas abastecer?**')
    scope=st.radio('Selección', ['Cervezas y licores','Todas las categorías','Buscar productos'],horizontal=True,key='psi_mgr_scope')
    x=summary.copy()
    x=x[x['Unidades'].gt(0) & x['Vinculado']].copy()
    alcohol_terms=r'cerveza|licor|whisk|vodka|ron\b|pisco|vino\b|espumante|gin\b|tequila|brandy|aguardiente|champagne|sidra|anisado|alcoh[oó]lic'
    if scope=='Cervezas y licores':
        x=x[x['Categoria'].fillna('').str.contains(alcohol_terms,case=False,regex=True)|x['Producto'].fillna('').str.contains(alcohol_terms,case=False,regex=True)]
        st.info('Selección basada en categoría y nombre del producto. Revisa la lista: la clasificación automática puede omitir artículos o incluir otros por coincidencia de palabras.')
    elif scope=='Buscar productos':
        q=st.text_input('Buscar por producto o código',key='psi_mgr_query')
        if q: x=x[x['Producto'].str.contains(re.escape(q),case=False,na=False)|x['Clave'].str.contains(re.escape(q),case=False,na=False)]
    if x.empty:
        st.warning('No hay productos con ventas históricas vinculados al inventario para esta selección. No se generan compras sin evidencia de demanda.')
        return
    days_until=max(0,(pd.Timestamp(arrival)-today).days)
    if pd.Timestamp(arrival)<today: st.warning('La llegada elegida ya pasó; se asume recepción inmediata para el cálculo.')
    if (pd.Timestamp(arrival)-today).days>30: st.info('Plazo largo: confirma disponibilidad del proveedor y la vigencia de las estimaciones.')
    last_date=dates[-1]
    if (today-last_date).days>2:
        st.warning(f'Últimas ventas registradas: {last_date:%d/%m/%Y}. Si faltan días de carga, la demanda puede estar subestimada.')
    from scipy.stats import norm as _norm
    z=float(_norm.ppf(int(reserve)/100))
    rows=[]
    for r in x.itertuples(index=False):
        key=str(r.Clave)
        hist=grouped[grouped['Clave'].eq(key)].set_index('Dia')['Cantidad'].reindex(dates,fill_value=0).to_numpy(dtype=float)
        if len(hist)==0: continue
        # Pronóstico estable para operación: combina promedio reciente y patrón semanal
        recent=hist[-min(56,len(hist)):]
        mean=float(recent.mean())
        if len(hist)>=28:
            weekday=np.array([np.mean(hist[-28:][np.arange(len(hist)-28,len(hist))%7==j]) for j in range(7)])
            # Suavizado para evitar sobreajuste de apenas 4 observaciones por día.
            weekday=.55*weekday+.45*float(np.mean(hist[-28:]))
        else: weekday=np.full(7,mean)
        n_total=days_until+int(duration)
        future=pd.date_range(today+pd.Timedelta(days=1),periods=max(n_total,1),freq='D')
        forecast=np.maximum(0,np.array([weekday[(d-dates[0]).days%7] if len(hist)>=28 else mean for d in future]))
        before=float(forecast[:days_until].sum())
        after=float(forecast[days_until:days_until+int(duration)].sum())
        # Reserva estadística orientativa: dispersión diaria * sqrt(horizonte)
        sigma=float(np.std(recent,ddof=1)) if len(recent)>1 else 0
        safety=int(np.ceil(z*sigma*np.sqrt(int(duration))))
        stock=float(r.Stock)
        arrival_stock=max(0,stock-before)
        need=max(0,int(np.ceil(after+safety-arrival_stock)))
        cost=float(r.CostoUnitario)
        rows.append({'Producto':r.Producto,'Código':key,'Categoría':r.Categoria,
                     'Stock hoy':round(stock,1),'Venta diaria':round(mean,2),
                     'Venta estimada 14d':round(after,1),'Reserva':safety,
                     'Stock al recibir':round(arrival_stock,1),'Comprar (und)':need,
                     'Costo unitario':round(cost,2),'Inversión S/':round(need*cost,2),
                     'Días sin venta':int(r.DiasSinVenta) if pd.notna(r.DiasSinVenta) else None,
                     'Cobertura hoy':round(stock/mean,1) if mean>0 else None,
                     'Riesgo previo a entrega':'Sin stock' if stock<=0 else ('Puede agotarse' if before>=stock else 'Con cobertura'),
                     '_demanda':after,'_before':before})
    plan=pd.DataFrame(rows)
    if plan.empty: st.info('No se pudieron estimar cantidades.');return
    plan=plan.sort_values(['Comprar (und)','Inversión S/'],ascending=False)
    total=int(plan['Comprar (und)'].sum()); investment=float(plan['Inversión S/'].sum())
    no_stock=int((plan['Stock hoy']<=0).sum()); at_risk=int(plan['Riesgo previo a entrega'].ne('Con cobertura').sum())
    m=st.columns(4)
    m[0].metric('Productos a comprar',f"{int((plan['Comprar (und)']>0).sum()):,}")
    m[1].metric('Unidades sugeridas',f'{total:,}')
    m[2].metric('Inversión estimada',formato_soles(investment))
    m[3].metric('Sin stock hoy',str(no_stock))
    st.markdown(f'**Lectura para gerencia:** para cubrir **{int(duration)} días desde el {pd.Timestamp(arrival):%d/%m/%Y}**, se estiman **{total:,} unidades** por **{formato_soles(investment)}**, incluyendo una reserva de servicio del **{reserve}%**. Hay **{at_risk} referencias** agotadas o con riesgo de agotarse antes de recibir el pedido.')
    if no_stock:
        st.warning(f'{no_stock} productos tienen stock registrado cero. Sus ventas recientes podrían subestimar la demanda real si llevan días agotados; revisa el pedido antes de confirmarlo.')
    st.markdown('#### Prioridades de compra')
    st.caption('Comprar (und) = ventas esperadas durante el periodo + reserva − stock estimado al recibir. Las cantidades son orientativas, no pedidos automáticos.')
    show=plan[['Producto','Stock hoy','Venta diaria','Venta estimada 14d','Reserva','Stock al recibir','Comprar (und)','Inversión S/','Riesgo previo a entrega']]
    st.dataframe(show,hide_index=True,use_container_width=True,height=390)
    left,right=st.columns([1.35,1])
    with left:
        st.markdown('**¿Qué productos concentran la compra?**')
        top=plan.nlargest(12,'Inversión S/').sort_values('Inversión S/')
        fig=go.Figure(go.Bar(x=top['Inversión S/'],y=top['Producto'].str.slice(0,42),orientation='h',marker_color='#00A959',text=[f'S/ {v:,.0f}' for v in top['Inversión S/']],textposition='outside',cliponaxis=False))
        fig.update_xaxes(title='Inversión sugerida (S/)')
        _p_plot(fig,400)
    with right:
        st.markdown('**Cómo se calcula**')
        st.markdown('**1.** Se estiman las unidades que se venderían hasta la llegada.\n\n**2.** Se proyecta cuánto stock quedará al recibir.\n\n**3.** Se estima la venta de los siguientes 14 días.\n\n**4.** Se añade una reserva por variabilidad y se resta el stock disponible.')
        st.caption('Se usa un promedio reciente con patrón semanal suavizado cuando hay al menos 28 días. Es una estimación inicial; no sustituye la validación temporal de modelos ni corrige automáticamente ventas perdidas por quiebres.')
    st.download_button('📥 Descargar propuesta de compra (Excel)',_p_excel({'Plan de compra':plan.drop(columns=['_demanda','_before'])}),file_name='Premium_Plan_Compra_14_Dias.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True,key='psi_mgr_export')
    st.caption('No incluye pedidos en tránsito, mínimos de compra, múltiplos por caja, vencimientos ni condiciones de proveedor. Costo unitario cero significa que la inversión puede estar incompleta.')


def pantalla_stock_intelligence():
    """Una sola pantalla de decisión: qué comprar, cuánto y por qué."""
    from zoneinfo import ZoneInfo
    header('Plan de Compras | Tiendas Premium', 'Decisiones de abastecimiento basadas en stock disponible y comportamiento de ventas')
    if str(st.session_state.usuario.get('Rol','')).upper()!='ADMIN':
        st.error('Acceso exclusivo para administración.'); return
    try:
        ventas=preparar_ventas(cargar_ventas())
        inventario=cargar_inventario()
    except Exception as exc:
        st.error(f'No se pudieron cargar las ventas o el inventario: {exc}'); return
    if ventas.empty:
        st.info('Todavía no hay ventas cargadas. Abre «Actualizar ventas» al final de la página.')
    elif (~ventas['CantidadValida']).any():
        st.error(f"Hay {int((~ventas['CantidadValida']).sum())} filas con CANTIDAD inválida. Revisa las ventas antes de generar compras.")
    else:
        today=pd.Timestamp.now(tz=ZoneInfo('America/Lima')).normalize().tz_localize(None)
        last=ventas['Dia'].max()
        default_arrival=today+pd.Timedelta(days=(5-today.weekday())%7)
        st.markdown('<div class="psi-section"><span class="psi-index">01</span> Configura el abastecimiento</div>',unsafe_allow_html=True)
        c1,c2,c3=st.columns([1.1,1,1])
        with c1: arrival=st.date_input('¿Cuándo llegará?',value=default_arrival.date(),min_value=today.date(),key='psi_simple_arrival')
        with c2: duration=st.selectbox('¿Para cuántos días?',options=[7,14,21,30],index=1,format_func=lambda x:f'{x} días desde la llegada',key='psi_simple_days')
        with c3: service=st.selectbox('Reserva de seguridad',options=[90,95,97,99],index=1,format_func=lambda x:f'{x}% de protección',key='psi_simple_service')
        col1,col2=st.columns([1,1.6])
        with col1: window=st.selectbox('Historial para estimar ventas',[30,60,90,180,365],index=2,format_func=lambda x:f'Últimos {x} días',key='psi_simple_window')
        with col2: search=st.text_input('Filtrar productos o categoría',placeholder='Ej.: cerveza, Coca-Cola, snacks, código de barras',key='psi_simple_search')
        summary,dates,grouped=_p_metrics(ventas,inventario,int(window),3,7,int(service),0,28)
        if summary.empty:
            st.info('No hay datos suficientes para calcular un pedido.'); return
        x=summary[(summary['Unidades']>0)&(summary['Vinculado'])].copy()
        if search.strip():
            pattern=re.escape(search.strip())
            x=x[x['Producto'].str.contains(pattern,case=False,na=False)|x['Categoria'].fillna('').str.contains(pattern,case=False,na=False)|x['Clave'].str.contains(pattern,case=False,na=False)]
        if x.empty:
            st.info('No hay productos con ventas históricas vinculados al inventario para este filtro.');
        else:
            days_until=max(0,(pd.Timestamp(arrival)-today).days)
            z=float(norm.ppf(int(service)/100))
            future=pd.date_range(today+pd.Timedelta(days=1),periods=max(1,days_until+duration),freq='D')
            rows=[]
            for r in x.itertuples(index=False):
                hist=grouped[grouped['Clave'].eq(str(r.Clave))].set_index('Dia')['Cantidad'].reindex(dates,fill_value=0).to_numpy(dtype=float)
                if not len(hist): continue
                recent=hist[-min(56,len(hist)):]
                avg=float(recent.mean())
                if len(hist)>=28:
                    tail=hist[-28:]
                    weekly=np.array([tail[np.arange(len(tail))%7==j].mean() for j in range(7)])
                    weekly=.55*weekly+.45*float(tail.mean())
                    # Alinear los días de la semana con la fecha del último registro.
                    start_weekday=(dates[-28].weekday() if len(dates)>=28 else dates[0].weekday())
                    demand=np.maximum(0,np.array([weekly[(d.weekday()-start_weekday)%7] for d in future]))
                else:
                    demand=np.full(len(future),avg)
                before=float(demand[:days_until].sum())
                after=float(demand[days_until:days_until+duration].sum())
                sigma=float(np.std(recent,ddof=1)) if len(recent)>1 else 0
                reserve=int(np.ceil(z*sigma*np.sqrt(duration)))
                stock=max(0,float(r.Stock))
                arrival_stock=max(0,stock-before)
                qty=max(0,int(np.ceil(after+reserve-arrival_stock)))
                cost=max(0,float(r.CostoUnitario))
                risk='Agotado' if stock<=0 else ('Puede agotarse antes de recibir' if stock<=before else 'Con stock hasta entrega')
                if qty==0: status='No comprar'
                elif risk!='Con stock hasta entrega': status='Urgente'
                else: status='Programar'
                explanation=(f'Vende aprox. {avg:.1f} und/día; al recibir quedarían {arrival_stock:.0f} und. '
                             f'Se estiman {after:.0f} und para {duration} días y {reserve} und de reserva.')
                rows.append({'Producto':r.Producto,'Código':str(r.Clave),'Categoría':r.Categoria,
                             'Stock actual':int(round(stock)),'Venta diaria':round(avg,2),
                             'Stock al recibir':round(arrival_stock,1),'Venta esperada':round(after,1),
                             'Reserva':reserve,'Comprar':qty,'Costo unitario':round(cost,2),
                             'Inversión S/':round(qty*cost,2),'Prioridad':status,'Motivo':explanation,
                             'Riesgo':risk,'Cobertura (días)':round(stock/avg,1) if avg>0 else None})
            plan=pd.DataFrame(rows)
            if not plan.empty:
                order={'Urgente':0,'Programar':1,'No comprar':2}
                plan['_orden']=plan['Prioridad'].map(order)
                plan=plan.sort_values(['_orden','Comprar'],ascending=[True,False]).drop(columns='_orden')
                buy=plan[plan['Comprar']>0]
                st.markdown('<div class="psi-section"><span class="psi-index">02</span> Resumen ejecutivo</div>',unsafe_allow_html=True)
                k1,k2,k3=st.columns(3)
                k1.metric('Productos a comprar',f'{len(buy):,}')
                k2.metric('Unidades a pedir',f"{int(buy['Comprar'].sum()):,}")
                k3.metric('Inversión estimada',formato_soles(buy['Inversión S/'].sum()))
                urgent=int((plan['Prioridad']=='Urgente').sum())
                from html import escape as _psi_escape
                no_buy=int((plan['Prioridad']=='No comprar').sum())
                total_cost=float(buy['Inversión S/'].sum())
                text_summary=(f'Para cubrir {duration} días desde la llegada del {pd.Timestamp(arrival):%d/%m/%Y}, '
                              f'se propone adquirir {int(buy["Comprar"].sum()):,} unidades de {len(buy)} productos '
                              f'con una inversión estimada de S/ {total_cost:,.2f}. '
                              f'{urgent} productos requieren atención urgente y {no_buy} no necesitan compra en este escenario.')
                st.markdown(f'<div class="psi-executive"><h3>Decisión recomendada</h3><p>{_psi_escape(text_summary)}</p></div>',unsafe_allow_html=True)
                b1,b2,b3=st.columns(3)
                b1.metric('Atención urgente',f'{urgent} productos')
                b2.metric('Compra programada',f'{int((plan["Prioridad"]=="Programar").sum())} productos')
                b3.metric('No comprar',f'{no_buy} productos')
                if (today-last).days>2:
                    st.warning(f'Última venta cargada: {last:%d/%m/%Y}. Faltan días recientes; las compras sugeridas podrían estar subestimadas.')
                if len(dates)<28:
                    st.warning('Historial corto: las recomendaciones son preliminares.')
                if (plan['Costo unitario'].eq(0)&plan['Comprar'].gt(0)).any():
                    st.warning('Hay productos sin costo válido. La inversión total puede estar incompleta.')
                st.caption('Stock actual = hoja Inventario. La recomendación NO incluye pedidos en tránsito ni reconstruye ventas perdidas durante quiebres de stock.')
                st.markdown('<div class="psi-section"><span class="psi-index">03</span> Prioridades de compra</div>',unsafe_allow_html=True)
                view=st.radio('Mostrar',['Solo comprar','Todos los productos','Urgentes'],horizontal=True,key='psi_simple_filter')
                visible=buy if view=='Solo comprar' else (plan[plan['Prioridad']=='Urgente'] if view=='Urgentes' else plan)
                st.caption('Ordenado por prioridad. Selecciona «Todos los productos» para revisar también los que no necesitan reposición.')
                view_cols=['Producto','Stock actual','Venta diaria','Cobertura (días)','Comprar','Inversión S/','Prioridad','Motivo']
                st.dataframe(visible[view_cols],hide_index=True,use_container_width=True,height=min(500,max(180,55+len(visible)*36)),column_config={
                    'Producto':st.column_config.TextColumn('Producto',width='large'),
                    'Stock actual':st.column_config.NumberColumn('Stock',format='%d und'),
                    'Venta diaria':st.column_config.NumberColumn('Venta/día',format='%.2f'),
                    'Cobertura (días)':st.column_config.NumberColumn('Días restantes',format='%.1f'),
                    'Comprar':st.column_config.NumberColumn('Pedir',format='%d und'),
                    'Inversión S/':st.column_config.NumberColumn('Inversión',format='S/ %.2f'),
                    'Prioridad':st.column_config.TextColumn('Decisión',width='small'),
                    'Motivo':st.column_config.TextColumn('Fundamento',width='large')})
                if len(buy)>0:
                    import plotly.graph_objects as _psi_go
                    st.markdown('**¿Dónde se concentra la inversión?**')
                    chart=buy.nlargest(8,'Inversión S/').sort_values('Inversión S/')
                    fig_inv=_psi_go.Figure(_psi_go.Bar(x=chart['Inversión S/'],y=chart['Producto'].str.slice(0,34),orientation='h',marker_color='#00A959',text=[f'S/ {v:,.0f}' for v in chart['Inversión S/']],textposition='outside',cliponaxis=False))
                    fig_inv.update_layout(margin=dict(l=10,r=55,t=12,b=18),height=max(220,40*len(chart)+75),paper_bgcolor='white',plot_bgcolor='white',showlegend=False,font=dict(color='#42536b',size=12),xaxis=dict(title='Inversión sugerida (S/)',showgrid=True,gridcolor='#eef1f5'),yaxis=dict(title=''))
                    st.plotly_chart(fig_inv,use_container_width=True,config={'displayModeBar':False})
                st.download_button('📥 Descargar lista de compra (Excel)',data=_p_excel({'Compra recomendada':plan}),file_name='TiendasPremium_Plan_de_Compras.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',key='psi_simple_export')
                st.markdown('<div class="psi-section"><span class="psi-index">04</span> Explicación de un producto</div>',unsafe_allow_html=True)
                product_names=[f"{r.Producto} · {r.Código}" for r in plan.itertuples(index=False)]
                chosen=st.selectbox('Producto para revisar',options=range(len(plan)),format_func=lambda i:product_names[i],key='psi_simple_selected')
                item=plan.iloc[chosen]
                st.markdown(f'<div class="psi-executive"><h3>{_psi_escape(str(item["Producto"]))} · {_psi_escape(str(item["Prioridad"]))}</h3><p>{_psi_escape(str(item["Motivo"]))}</p></div>',unsafe_allow_html=True)
                c1,c2,c3=st.columns(3)
                c1.metric('Stock actual',f"{item['Stock actual']} und")
                c2.metric('Cobertura estimada',f"{item['Cobertura (días)']} días" if pd.notna(item['Cobertura (días)']) else 'Sin demanda')
                c3.metric('Comprar',f"{item['Comprar']} und")
                key=item['Código']
                historical=grouped[grouped['Clave'].eq(key)].set_index('Dia')['Cantidad'].reindex(dates,fill_value=0)
                daily=historical.tail(14)
                fig=go.Figure(go.Bar(x=daily.index,y=daily.values,marker_color='#00A959',text=[f'{v:.0f}' for v in daily.values],textposition='outside',cliponaxis=False,name='Unidades'))
                fig.update_layout(title='Ventas de los últimos 14 días',showlegend=False,yaxis_title='Unidades')
                _p_plot(fig,290)
                st.caption('Unidades vendidas por día. Un cero solo equivale a ausencia de ventas si el registro de ese día está completo.')
                if float(item['Venta diaria'])>0:
                    days=int(max(1,round(float(item['Cobertura (días)'])))) if pd.notna(item['Cobertura (días)']) else 0
                    if days and days<=7:
                        st.warning(f'Con el stock registrado, este producto podría agotarse en unos {days} días si continúa su ritmo de ventas.')
                else:
                    st.info('No hay demanda observada suficiente para calcular días de cobertura. Revisar disponibilidad e historial.')
                with st.expander('Ver cálculo y limitaciones',expanded=False):
                    st.write(f"Stock al recibir: {item['Stock al recibir']} und · Ventas previstas: {item['Venta esperada']} und · Reserva: {item['Reserva']} und")
                    st.write('Compra = máximo entre 0 y (ventas previstas durante el periodo + reserva − stock estimado al recibir), redondeado hacia arriba.')
                    st.write('Las cantidades son estimaciones y requieren revisión antes de realizar un pedido. Sin historial de disponibilidad, las ventas observadas pueden subestimar la demanda cuando hubo quiebres.')
    with st.expander('📥 Actualizar ventas desde Excel',expanded=False):
        st.caption('Importa el Excel con los 25 encabezados originales. Se conservan las filas existentes.')
        archivo=st.file_uploader('Archivo de ventas (.xlsx)',type=['xlsx'],key='psi_simple_upload')
        if archivo is not None:
            try:
                nuevo=_leer_reporte_excel(archivo)
                st.write(f'Registros detectados: {len(nuevo):,}')
                st.dataframe(nuevo.head(5),hide_index=True,use_container_width=True)
                if st.button('Agregar ventas nuevas',key='psi_simple_import',type='primary'):
                    ws=hoja_ventas(); existing=cargar_ventas()
                    cols=['FECHA/HORA','COMPROBANTE','CÓDIGO DE BARRA','PRODUCTO','SKU','COSTO*','PRECIO PROMEDIO','CANTIDAD','TOTAL']
                    def occurrences(frame):
                        if frame.empty: return []
                        b=frame[cols].fillna('').astype(str).apply(lambda r:'\x1f'.join(r),axis=1)
                        return list(zip(b,b.groupby(b).cumcount()))
                    seen=set(occurrences(existing)); keys=occurrences(nuevo)
                    rows=[list(r) for i,r in enumerate(nuevo.itertuples(index=False,name=None)) if keys[i] not in seen]
                    if rows: ws.append_rows(rows,value_input_option='RAW')
                    cargar_ventas.clear()
                    registrar_auditoria('IMPORTACION_VENTAS',f'{len(rows)} filas; {archivo.name}')
                    st.success(f'{len(rows)} filas agregadas; {len(nuevo)-len(rows)} ya existentes.')
            except Exception as exc:
                st.error(f'No se pudo procesar el Excel: {exc}')

def pantalla_seguridad_y_respaldo():
    header("Seguridad y respaldos", "Resguardo de datos y control de accesos")
    if str(st.session_state.usuario.get("Rol", "")).upper() != "ADMIN":
        st.error("Solo administración puede acceder.")
        return
    st.markdown("### Copia de seguridad de Google Sheets")
    st.caption("Genera un respaldo descargable de las hojas operativas. No incluye contraseñas de Usuarios por seguridad.")
    if st.button("Preparar respaldo", key="e5_preparar_respaldo"):
        try:
            libro=conectar_google()
            nombres=[x.title for x in libro.worksheets() if x.title != "Usuarios"]
            contenido={}
            for nombre in nombres:
                filas=libro.worksheet(nombre).get_all_values()
                if filas:
                    ancho=max(len(x) for x in filas)
                    contenido[nombre]=pd.DataFrame([r+[""]*(ancho-len(r)) for r in filas[1:]],columns=[f"{v or 'Col'+str(i)}" for i,v in enumerate(filas[0]+[""]*(ancho-len(filas[0])))] )
            st.session_state["respaldo_e5"] = exportar_excel(contenido)
            registrar_auditoria("RESPALDO_GENERADO",f"Hojas: {len(contenido)}")
            st.success("Respaldo generado. Descárgalo y guárdalo en un lugar seguro.")
        except Exception as exc:
            st.error(f"No se pudo generar el respaldo: {exc}")
    if st.session_state.get("respaldo_e5"):
        st.download_button("Descargar respaldo XLSX",st.session_state["respaldo_e5"],file_name=f"respaldo_premium_{datetime.now():%Y%m%d_%H%M}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.info("La recuperación debe realizarse con supervisión administrativa, restaurando primero una copia de la hoja. Esta versión no sobrescribe automáticamente datos productivos.")
    st.markdown("### Estado de la plataforma")
    st.write("Autenticación: PBKDF2 para contraseñas nuevas; acceso compatible con credenciales anteriores.")
    st.write("Auditoría: registro de operaciones principales en la hoja Auditoria.")
    st.warning("La prevención absoluta de conflictos entre dos usuarios simultáneos no es transaccional en Google Sheets. Para garantizarla será necesario migrar los registros críticos a PostgreSQL.")
    st.markdown("### Ruta de migración a PostgreSQL")
    st.caption("1. Definir tablas normalizadas de productos, sesiones, conteos, zonas, ventas y usuarios. 2. Importar y validar históricos. 3. Aplicar restricciones únicas y transacciones. 4. Migrar operaciones de escritura con pruebas paralelas. 5. Activar backups automáticos y restauración verificada.")


# =========================================================
# SIDEBAR (misma estructura que Asistencia)
# Marca · tarjeta de usuario · aviso · búsqueda · menú · accesos · cerrar sesión
# =========================================================

_CLAVES_SESION = [
    "autenticado", "usuario", "pagina", "nav_menu", "reconteo_activo", "sesion_actual", "codigo_pendiente",
    "producto_pendiente", "modo_inventario", "ultimo_codigo_scan", "zona_activa", "precio_producto", "precio_modo",
    "precio_ultimo_codigo_scan", "login_timestamp", "ultima_actividad", "gs_q", "_pg_prev", "_pg_n", "_menu_opciones",
]


def _cerrar_sesion(motivo=""):
    """Limpia la sesión del usuario. Si hay motivo (cierre automático), el login lo muestra."""
    for key in _CLAVES_SESION:
        st.session_state.pop(key, None)
    if motivo:
        st.session_state["_sesion_expirada"] = motivo


def _cambio_menu():
    """Callback del menú lateral: se ejecuta ANTES del rerun, por lo que la
    página queda actualizada con un solo clic."""
    st.session_state.pagina = st.session_state.get("nav_menu", "Inicio")
    st.session_state["gs_q"] = ""


def render_busqueda_inv(q, opciones):
    """Búsqueda global (solo lectura): secciones del menú y productos del inventario."""
    header("Resultados de búsqueda", f"Coincidencias para «{q}»")
    qn = _norm_txt(q)
    secs = [o for o in opciones if qn in _norm_txt(o)]
    if secs:
        st.markdown(f'<div class="tp-note-t" style="margin:6px 0 10px">Secciones · {len(secs)}</div>', unsafe_allow_html=True)
        cols = st.columns(min(len(secs), 4))
        for i, s in enumerate(secs):
            with cols[i % len(cols)]:
                st.button(s, key=f"gs_sec_{i}", use_container_width=True, on_click=_ir_a, args=(s,))
    try:
        prods = buscar_productos(q)
    except Exception:
        prods = pd.DataFrame()
    n = len(prods)
    st.markdown(f'<div class="tp-note-t" style="margin:22px 0 10px">Productos · {n}{"+" if n >= 100 else ""}</div>', unsafe_allow_html=True)
    if prods.empty:
        ui_callout("No encontré productos con ese nombre, código, categoría o marca. Prueba con otra palabra.")
        return
    filas = ""
    for _, r in prods.head(25).iterrows():
        stock = limpiar_numero(r.get("StockSistema", 0))
        detalle = " · ".join(
            x for x in [
                f"Cód. {safe_text(r.get('CodigoProducto', ''))}" if str(r.get("CodigoProducto", "")).strip() else "",
                safe_text(r.get("Categoria", "")) if str(r.get("Categoria", "")).strip() else "",
                safe_text(r.get("Marca", "")) if str(r.get("Marca", "")).strip() else "",
            ] if x
        ) or "Sin detalle"
        chips = ui_chip(f"Stock {stock:,.0f}", "ok" if stock > 0 else "bad") + ui_chip(formato_soles(limpiar_numero(r.get("PrecioVenta", 0))), "neutral")
        filas += f'<div class="tp-row"><div class="tp-row-main"><b>{safe_text(r.get("Producto", ""))}</b><span>{detalle}</span></div><div class="tp-chips">{chips}</div></div>'
    st.markdown(filas, unsafe_allow_html=True)
    if n > 25:
        st.caption(f"Mostrando 25 de {n}{'+' if n >= 100 else ''} coincidencias. Afina la búsqueda para ver menos resultados.")


def sidebar():
    usuario = st.session_state.usuario
    rol = str(usuario.get("Rol", "CONTADOR")).upper()
    nombre_usuario = str(usuario.get("NombreCompleto", "")).strip()
    login_usuario = str(usuario.get("Usuario", "")).strip()

    st.sidebar.markdown(f'<div style="text-align:center; padding: 8px 0 14px 0;">{logo_tag(58)}</div>', unsafe_allow_html=True)
    st.sidebar.markdown('<div class="tp-brand"><div class="tp-brand-name">Tiendas <span>Premium</span></div><div class="tp-brand-sub">Sistema de inventario</div></div>', unsafe_allow_html=True)
    st.sidebar.markdown(f"""
        <div class="tp-user">
            {ui_avatar(nombre_usuario or login_usuario)}
            <div><b>{safe_text(nombre_usuario or login_usuario)}</b><span>{safe_text(rol.capitalize())} · {safe_text(login_usuario)}</span></div>
        </div>
    """, unsafe_allow_html=True)

    # Aviso de sesiones de conteo abiertas (mismo recurso visual que los avisos de Asistencia)
    try:
        _ses = cargar_sesiones()
        _abiertas = int((_ses["Estado"].astype(str).str.upper() == "ABIERTA").sum()) if not _ses.empty else 0
    except Exception:
        _abiertas = 0
    if _abiertas:
        st.sidebar.markdown(f'<div class="tp-notif"><span>Inventarios en curso</span><span>{_abiertas}</span></div>', unsafe_allow_html=True)

    opciones = ["Inicio", "Precios", "Sesión", "Zonas", "Inventario", "Resultados", "Análisis"]
    if rol == "ADMIN":
        opciones += ["Compras Inteligentes", "Seguridad y respaldos", "Administración"]
    st.session_state["_menu_opciones"] = opciones

    st.sidebar.text_input("Buscar", key="gs_q", placeholder="Buscar productos, secciones…", label_visibility="collapsed")

    # Sincroniza el menú con la página actual (por ejemplo, cuando un botón
    # de la pantalla cambia de página). Se hace ANTES de crear el radio.
    actual = st.session_state.get("pagina", "Inicio")
    if actual not in opciones:
        actual = "Inicio"
        st.session_state.pagina = actual
    if st.session_state.get("nav_menu") != actual:
        st.session_state["nav_menu"] = actual

    seleccion = st.sidebar.radio("Navegación", opciones, key="nav_menu", on_change=_cambio_menu)
    st.session_state.pagina = seleccion

    # Barra inferior de navegación (solo se ve en celular; en PC la oculta el CSS)
    _nav_items = [("Inicio", "Inicio", ":material/dashboard:"), ("Precios", "Precios", ":material/sell:"),
                  ("Inventario", "Contar", ":material/qr_code_scanner:"), ("Resultados", "Resultados", ":material/bar_chart:")]
    try:
        with st.container(key="tp_bottomnav"):
            for _col, (_dest, _lbl, _ico) in zip(st.columns(len(_nav_items)), _nav_items):
                with _col:
                    st.button(_lbl, key=f"bn_{_dest}", icon=_ico, use_container_width=True,
                              type="primary" if seleccion == _dest else "secondary", on_click=_ir_a, args=(_dest,))
    except Exception:
        pass  # versiones antiguas de Streamlit: se usa solo el menú lateral

    st.sidebar.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
    if st.sidebar.button("Actualizar Datos", use_container_width=True, key="sb_actualizar_datos"):
        actualizar_datos()
        st.rerun()

    st.sidebar.markdown('<div class="btn-logout">', unsafe_allow_html=True)
    st.sidebar.markdown(
        f'<a class="tp-negosy" href="{NEGOSY_URL}" target="_blank" rel="noopener noreferrer"><span><span class="tp-negosy-t">Negosy</span><span class="tp-negosy-s">Sistema de ventas</span></span>'
        "<svg width='18' height='18' viewBox='0 0 24 24' fill='none' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M7 17L17 7M9 7h8v8'/></svg></a>",
        unsafe_allow_html=True)
    if ASISTENCIA_URL:
        st.sidebar.markdown(
            f'<a class="tp-negosy" href="{ASISTENCIA_URL}" target="_blank" rel="noopener noreferrer"><span><span class="tp-negosy-t">Asistencia</span><span class="tp-negosy-s">Control de personal</span></span>'
            "<svg width='18' height='18' viewBox='0 0 24 24' fill='none' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M7 17L17 7M9 7h8v8'/></svg></a>",
            unsafe_allow_html=True)
    ui_guia_instalar(st.sidebar)
    if st.sidebar.button("Cerrar Sesión", use_container_width=True, key="sb_cerrar_sesion"):
        registrar_auditoria("LOGOUT", "Cierre de sesión")
        _cerrar_sesion()
        st.rerun()
    st.sidebar.markdown('</div>', unsafe_allow_html=True)



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
    "gs_q": "",
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

ui_pwa_inyectar()

if not st.session_state.autenticado:
    try:
        pantalla_login()
    except Exception as exc:
        mostrar_error_google(exc, "carga de login")
    st.stop()

# --- CONTROL DE EXPIRACIÓN DE SESIÓN (igual que Asistencia) ---
# Máximo 10 horas desde el login y cierre automático tras 30 minutos de inactividad.
_ahora_ses = time.time()
if "login_timestamp" not in st.session_state:
    st.session_state.login_timestamp = _ahora_ses
if "ultima_actividad" not in st.session_state:
    st.session_state.ultima_actividad = _ahora_ses
_desde_login = _ahora_ses - st.session_state.login_timestamp
_inactivo = _ahora_ses - st.session_state.ultima_actividad
if _desde_login > SESION_MAX_SEGUNDOS or _inactivo > INACTIVIDAD_MAX_SEGUNDOS:
    _motivo_cierre = "duración máxima (10 horas)" if _desde_login > SESION_MAX_SEGUNDOS else "inactividad (30 minutos)"
    registrar_auditoria("LOGOUT_AUTOMATICO", f"Sesión cerrada por {_motivo_cierre}")
    _cerrar_sesion(_motivo_cierre)
    st.rerun()
st.session_state.ultima_actividad = _ahora_ses

sidebar()

# Transición suave entre secciones y búsqueda global (misma mecánica que Asistencia)
_gq = str(st.session_state.get("gs_q", "")).strip()
_pid = str(st.session_state.get("pagina", "Inicio")) + ("|buscar" if len(_gq) >= 2 else "")
if st.session_state.get("_pg_prev") != _pid:
    st.session_state["_pg_prev"] = _pid
    st.session_state["_pg_n"] = st.session_state.get("_pg_n", 0) + 1
st.markdown(f'<div class="tp-pg-{"a" if st.session_state["_pg_n"] % 2 == 0 else "b"}"></div>', unsafe_allow_html=True)

if len(_gq) >= 2:
    try:
        render_busqueda_inv(_gq, st.session_state.get("_menu_opciones", []))
    except Exception as exc:
        mostrar_error_google(exc, "búsqueda")
    footer()
    st.stop()

try:
    pagina = st.session_state.get("pagina", "Inicio")
    if pagina == "Inicio":
        pantalla_inicio()
    elif pagina == "Precios":
        pantalla_precios()
    elif pagina == "Sesión":
        pantalla_sesion()
    elif pagina == "Zonas":
        pantalla_zonas()
    elif pagina == "Inventario":
        pantalla_inventario()
    elif pagina == "Resultados":
        pantalla_resultados()
    elif pagina == "Análisis":
        pantalla_analisis()
    elif pagina == "Compras Inteligentes":
        pantalla_stock_intelligence()
    elif pagina == "Seguridad y respaldos":
        pantalla_seguridad_y_respaldo()
    elif pagina == "Administración":
        if str(st.session_state.usuario.get("Rol", "")).upper() == "ADMIN":
            pantalla_admin()
        else:
            st.error("No tienes permisos para acceder a Administración.")
    footer()
except Exception as exc:
    mostrar_error_google(exc, "carga de la pantalla")
    footer()

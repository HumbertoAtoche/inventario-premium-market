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
# ESTILO VISUAL COMPLETO — REFERENCIA APP ASISTENCIA
# Se superpone al tema previo; no altera procesos ni conexiones.
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

    .cal-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 14px;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02);
    }
    .cal-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: #1f2937;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .cal-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 3px;
        font-size: 0.75rem;
    }
    .cal-table th {
        background-color: #f8fafc;
        color: #64748b;
        font-weight: 600;
        padding: 6px 2px;
        text-align: center;
        border-radius: 4px;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .cal-table td {
        height: 36px;
        text-align: center;
        vertical-align: middle;
        border-radius: 6px;
        font-weight: 600;
        color: #334155;
        background-color: #ffffff;
        border: 1px solid #f1f5f9;
        transition: all 0.15s ease;
    }
    
    .cal-day-num {
        font-size: 0.82rem;
        line-height: 1;
    }
    .cal-sub {
        font-size: 0.6rem;
        font-weight: 500;
        margin-top: 2px;
        display: block;
        opacity: 0.9;
    }

    .bg-asistio {
        background-color: #dcfce7 !important;
        color: #15803d !important;
        border: 1px solid #bbf7d0 !important;
    }
    .bg-falta {
        background-color: #fee2e2 !important;
        color: #b91c1c !important;
        border: 1px solid #fca5a5 !important;
    }
    .bg-permiso {
        background-color: #ede9fe !important;
        color: #6d28d9 !important;
        border: 1px solid #c4b5fd !important;
    }
    .bg-permiso-pendiente {
        background-color: #fef3c7 !important;
        color: #92400e !important;
        border: 1px solid #fcd34d !important;
    }
    .bg-recuperacion {
        background-color: #cffafe !important;
        color: #0e7490 !important;
        border: 1px solid #67e8f9 !important;
    }
    .bg-extra {
        background-color: #fef9c3 !important;
        color: #a16207 !important;
        border: 1px solid #fef08a !important;
    }
    .bg-descanso {
        background-color: #f3f4f6 !important;
        color: #6b7280 !important;
        border: 1px solid #e5e7eb !important;
    }
    .bg-inicio {
        background-color: #e0f2fe !important;
        color: #0369a1 !important;
        border: 1px solid #bae6fd !important;
    }
    .bg-cese {
        background-color: #f3e8ff !important;
        color: #6b21a8 !important;
        border: 1px solid #e9d5ff !important;
    }
    .bg-vacio {
        background-color: transparent !important;
        border: none !important;
    }
    .bg-futuro {
        background-color: #ffffff !important;
        color: #94a3b8 !important;
        border: 1px dashed #e2e8f0 !important;
    }
    .bg-permiso-salud {
        background-color: #fce7f3 !important;
        color: #be185d !important;
        border: 1px solid #f9a8d4 !important;
    }
    .bg-recuperacion-salud {
        background-color: #e0e7ff !important;
        color: #4338ca !important;
        border: 1px solid #c7d2fe !important;
    }
    .bg-domingo-voluntario {
        background-color: #ccfbf1 !important;
        color: #0f766e !important;
        border: 1px solid #5eead4 !important;
    }

    .legend-container {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin-bottom: 16px;
        background: #ffffff;
        padding: 10px 14px;
        border-radius: 8px;
        border: 1px solid #e5e7eb;
    }
    .legend-item {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 0.78rem;
        font-weight: 500;
        color: #4b5563;
    }
    .legend-badge {
        width: 12px;
        height: 12px;
        border-radius: 3px;
        display: inline-block;
    }

    .profile-name {
        font-weight: 700;
        font-size: 1.05rem;
        color: #111827;
    }
    .profile-role {
        font-size: 0.82rem;
        color: #4B5563;
        margin-bottom: 6px;
    }
    .profile-field {
        font-size: 0.68rem;
        font-weight: 700;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 6px;
    }
    .profile-val {
        font-size: 0.85rem;
        font-weight: 500;
        color: #111827;
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
    /* ESTILOS DE BOLETA DE PAGO EN HTML */
    .boleta-container {
        background-color: #ffffff;
        border: 2px solid #111827;
        padding: 24px;
        border-radius: 6px;
        max-width: 850px;
        margin: 0 auto 20px auto;
        color: #111827;
        font-family: 'Montserrat', sans-serif;
    }
    .boleta-header-title {
        text-align: center;
        font-size: 1.2rem;
        font-weight: 800;
        letter-spacing: 1px;
        border-bottom: 2px solid #111827;
        padding-bottom: 8px;
        margin-bottom: 15px;
    }
    .boleta-table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 12px;
        font-size: 0.82rem;
    }
    .boleta-table th, .boleta-table td {
        border: 1px solid #000;
        padding: 6px 8px;
        text-align: left;
    }
    .boleta-table th {
        background-color: #f3f4f6;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)
st.markdown("<style>" + '\n/* Inventario: componentes específicos, armonizados con Asistencia */\n:root { --red:#EC3237; --green:#00A959; --blue:#1071B8; --text:#111827; --muted:#6B7280; --bg:#FAFAFA; --card:#FFFFFF; --border:#E5E7EB; }\n.premium-header,.market-header {background:#fff!important;border:1px solid #E5E7EB!important;border-left:4px solid #EC3237!important;border-radius:8px!important;padding:20px 24px!important;margin-bottom:24px!important;box-shadow:none!important;}\n.premium-header h1,.market-header h1 {color:#111827!important;font-size:1.3rem!important;font-weight:600!important;}\n.premium-header p,.market-header p {color:#6B7280!important;font-size:.85rem!important;}\n.info-card,.card,.kpi-card,.product-card,.price-info-item,.stock-box,.price-hero {background:#fff!important;border:1px solid #E5E7EB!important;border-radius:8px!important;box-shadow:none!important;color:#111827!important;}\n.info-card,.card,.kpi-card {padding:18px 20px!important;margin-bottom:15px!important;}\n.product-card {border-top:3px solid #1071B8!important;padding:18px 20px!important;}\n.info-label,.kpi-label,.stock-label,.price-label {color:#6B7280!important;font-size:.72rem!important;font-weight:600!important;letter-spacing:.5px!important;}\n.info-value,.kpi-value,.stock-number,.price-value {color:#111827!important;font-weight:700!important;}\n.price-hero {padding:24px 20px!important;text-align:center!important;}\n.price-info-grid {display:flex;flex-wrap:wrap;gap:10px;}\n.price-info-item {flex:1 1 120px;padding:12px!important;text-align:center;}\n.badge {display:inline-block;padding:4px 10px;border-radius:999px;font-size:.72rem;font-weight:600;}\n.badge-ok,.badge-sobrante {background:#DCFCE7;color:#15803D;}\n.badge-faltante {background:#FEE2E2;color:#B91C1C;}\n.badge-abierta {background:#DBEAFE;color:#1D4ED8;}\n.badge-cerrada {background:#F3F4F6;color:#4B5563;}\n[data-testid="stSidebar"] [role="radiogroup"] label {border-radius:6px!important;padding:8px 10px!important;}\n[data-testid="stSidebar"] [role="radiogroup"] label:hover {background:#1F2937!important;}\n[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {background:#263445!important;border-left:3px solid #EC3237!important;}\n.stButton>button[kind="primary"],div[data-testid="stFormSubmitButton"] button[kind="primary"] {background:#EC3237!important;color:#fff!important;}\n.stButton>button[kind="primary"]:hover {background:#D02429!important;}\n[data-testid="stDataFrame"], [data-testid="stDataEditor"] {border-radius:8px!important;overflow:hidden;}\n[data-testid="stTabs"] button[aria-selected="true"] {color:#EC3237!important;border-bottom-color:#EC3237!important;}\n[data-testid="stMetric"] {background:#fff;border:1px solid #E5E7EB;border-radius:8px;padding:14px 16px;}\n[data-testid="stMetricValue"] {color:#111827!important;}\n[data-testid="stFileUploader"] {background:#fff;border-radius:8px;}\n.stTextInput input,.stNumberInput input,.stTextArea textarea {border-radius:6px!important;}\n.app-footer {text-align:center;padding:24px 10px 12px;margin-top:40px;border-top:1px solid #E5E7EB;color:#6B7280;font-size:.8rem;}\n@media(max-width:768px) {\n .block-container {padding-left:.65rem!important;padding-right:.65rem!important;padding-bottom:4rem!important;}\n .premium-header,.market-header {padding:16px!important;margin-bottom:16px!important;}\n .premium-header h1,.market-header h1 {font-size:1.13rem!important;}\n .info-card,.card,.kpi-card,.product-card {padding:13px!important;}\n .kpi-value,.info-value {font-size:1.25rem!important;}\n .price-hero .price-value {font-size:2.25rem!important;}\n .stButton>button,div[data-testid="stFormSubmitButton"] button {min-height:46px!important;height:auto!important;}\n [data-testid="stHorizontalBlock"] {gap:.65rem!important;}\n .app-footer {font-size:.72rem;}\n}\n' + "</style>", unsafe_allow_html=True)

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

    sesion_actual = obtener_sesion_abierta()
    if sesion_actual:
        m = metricas_cobertura(sesion_actual["IdSesion"], sesion_actual["Sucursal"])
        st.progress(m["cobertura"]/100 if m["total"] else 0, text=f"Inventario activo · Cobertura {m['cobertura']:.1f}% · {m['pendientes']} pendientes · Exactitud {m['exactitud']:.1f}%")
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
                st.markdown("<div class='section-title'>🕒 Últimos escaneados</div>", unsafe_allow_html=True)
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

    st.markdown("<div class='section-title'>📥 Listas de faltantes y sobrantes (para tu sistema de ventas)</div>", unsafe_allow_html=True)
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

    st.markdown("<div class='section-title'>📈 Exactitud por sesión</div>", unsafe_allow_html=True)
    graf = t.set_index("Etiqueta")[["ExactitudInventario"]].rename(columns={"ExactitudInventario": "Exactitud %"})
    graf["Meta"] = META_EXACTITUD
    st.line_chart(graf)

    st.markdown("<div class='section-title'>💸 Desfase neto por sesión</div>", unsafe_allow_html=True)
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
# IDENTIDAD VISUAL PREMIUM — TEMA CLARO UNIFICADO
# Referencia: dashboard de asistencia de Tiendas Premium.
# Solo presentación: no modifica lógica ni Google Sheets.
# =========================================================
st.markdown("""
<style>
:root {color-scheme:light;--tp-ink:#152238;--tp-muted:#7889A3;--tp-red:#EC3237;--tp-green:#00A959;--tp-line:#E1E6EE;--tp-page:#F3F5F8;}
html,body,.stApp,[data-testid="stAppViewContainer"] {background:#F3F5F8!important;color:#152238!important;}
[data-testid="stMain"], [data-testid="stMainBlockContainer"] {background:transparent!important;}
[data-testid="stSidebar"],section[data-testid="stSidebar"]>div {background:#FFFFFF!important;border-right:1px solid #E1E6EE!important;}
[data-testid="stSidebar"] * {color:#26374F!important;}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {color:#26374F!important;}
[data-testid="stSidebar"] [role="radiogroup"] label {border-radius:13px!important;border:0!important;padding:11px 13px!important;transition:background .15s ease;}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {background:#F3F5F8!important;}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {background:#FDE9EA!important;border-left:4px solid #EC3237!important;}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) * {color:#CC252C!important;font-weight:700!important;}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {color:#7889A3!important;}
.market-header,.premium-header {background:#FFFFFF!important;border:1px solid #E1E6EE!important;border-left:1px solid #E1E6EE!important;border-radius:18px!important;padding:28px 30px!important;box-shadow:0 5px 16px rgba(30,50,80,.035)!important;position:relative;overflow:hidden;}
.market-header:before,.premium-header:before {content:"";position:absolute;top:0;left:30px;width:42px;height:4px;border-radius:0 0 5px 5px;background:#EC3237;}
.market-header h1,.premium-header h1 {font-size:1.55rem!important;font-weight:700!important;color:#152238!important;}
.market-header p,.premium-header p {color:#7889A3!important;font-size:.9rem!important;}
.card,.info-card,.kpi-card,.product-card,.stock-box,.price-hero,.price-info-item,.cal-card,div[data-testid="stForm"],div[data-testid="stExpander"],[data-testid="stMetric"] {background:#FFFFFF!important;border:1px solid #E1E6EE!important;border-radius:16px!important;box-shadow:0 2px 5px rgba(30,50,80,.035)!important;}
.kpi-card,[data-testid="stMetric"] {border-left:4px solid #00A959!important;}
.info-label,.kpi-label,.stock-label,.price-label {color:#7889A3!important;}
.info-value,.kpi-value,.stock-number,.price-value,[data-testid="stMetricValue"] {color:#152238!important;}
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp h5,.stApp h6 {color:#152238!important;}
.stApp p,.stApp label,.stApp li {color:#34435B;}
.stButton>button,div[data-testid="stFormSubmitButton"] button,div[data-testid="stDownloadButton"] button {background:#FFFFFF!important;color:#26374F!important;border:1px solid #DDE3EC!important;border-radius:10px!important;box-shadow:none!important;font-weight:600!important;}
.stButton>button:hover,div[data-testid="stFormSubmitButton"] button:hover,div[data-testid="stDownloadButton"] button:hover {background:#FDE9EA!important;color:#C7262D!important;border-color:#F3B9BC!important;}
.stButton>button[kind="primary"],div[data-testid="stFormSubmitButton"] button[kind="primary"] {background:#EC3237!important;color:#FFFFFF!important;border-color:#EC3237!important;}
.stButton>button[kind="primary"] *,div[data-testid="stFormSubmitButton"] button[kind="primary"] * {color:#FFFFFF!important;}
.stButton>button[kind="primary"]:hover,div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {background:#D92A30!important;border-color:#D92A30!important;}
[data-testid="stSidebar"] .stButton>button {background:#FFFFFF!important;color:#26374F!important;border:1px solid #DDE3EC!important;}
[data-testid="stSidebar"] .stButton>button:hover {background:#FDE9EA!important;color:#C7262D!important;}
[data-testid="stSidebar"] .btn-logout>button {background:#FFFFFF!important;color:#C7262D!important;border:1px solid #F3B9BC!important;}
[data-testid="stTabs"] button[aria-selected="true"] {color:#EC3237!important;border-bottom-color:#EC3237!important;}
[data-testid="stDataFrame"],[data-testid="stDataEditor"],div[data-baseweb="select"]>div,div[data-baseweb="input"]>div,textarea {background:#FFFFFF!important;border-color:#E1E6EE!important;border-radius:10px!important;color:#26374F!important;}
[data-testid="stAlert"] {border-radius:12px!important;}
[data-testid="stProgress"] [role="progressbar"]>div {background:#00A959!important;}
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] * {color:#26374F!important;}
.app-footer {border-top:1px solid #E1E6EE!important;color:#7889A3!important;}
.app-footer strong {color:#26374F!important;}
@media(max-width:768px){.market-header,.premium-header{padding:20px 16px!important;border-radius:13px!important}.market-header h1,.premium-header h1{font-size:1.2rem!important}.card,.info-card,.kpi-card,.product-card{border-radius:12px!important}}
</style>
""",unsafe_allow_html=True)


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
            st.info("Primero importa el reporte en Cargar ventas o pega las ventas en Google Sheets.")
            return
        k1,k2,k3=st.columns(3)
        k1.metric("Registros",f"{n:,}")
        k2.metric("Productos vendidos",f"{ventas['Clave'].nunique():,}")
        k3.metric("Días registrados",f"{ventas['Dia'].nunique():,}")
        if sin_cantidad:
            st.warning(f"Hay {sin_cantidad:,} registros sin cantidad vendida confiable. Se muestra el ranking de frecuencia, pero se bloquean las recomendaciones numéricas de compra para evitar pedidos incorrectos.")
            frecuencia=ventas.groupby(["Clave","PRODUCTO"],as_index=False).size().rename(columns={"size":"Líneas de venta"}).sort_values("Líneas de venta",ascending=False)
            st.dataframe(frecuencia.head(100),use_container_width=True,hide_index=True)
            st.download_button("Descargar frecuencia (Excel)",exportar_excel({"Frecuencia":frecuencia}),file_name="frecuencia_ventas.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            return
        c1,c2,c3,c4=st.columns(4)
        ventana=c1.selectbox("Ventana de demanda (días)",[7,14,30,60,90],index=2)
        entrega=c2.number_input("Plazo proveedor (días)",min_value=1,max_value=90,value=3)
        seguridad=c3.number_input("Días de colchón",min_value=0,max_value=60,value=4)
        servicio=c4.selectbox("Nivel de servicio",[90,95,98,99],index=1)
        st.caption("Parámetros generales iniciales. En una versión posterior se podrán configurar por proveedor y producto.")
        inventario=cargar_inventario()
        resumen=resumen_demanda(ventas,inventario,int(entrega),int(seguridad),int(ventana),int(servicio))
        if resumen.empty:
            st.info("No hay ventas válidas en la ventana seleccionada.")
            return
        if (~resumen["VinculadoInventario"]).any():
            st.warning(f"{int((~resumen['VinculadoInventario']).sum())} productos vendidos no se vincularon al inventario por código de barras/SKU. No se sugieren compras para ellos hasta revisar la correspondencia.")
        st.warning("Proyección orientativa: confirma que cada día esté cargado. CANTIDAD representa las unidades vendidas; CANTIDAD EQUIVALENCIA no se usa como cantidad base. Los días sin registro se consideran dentro del período; si faltan exportaciones, la demanda quedará subestimada.")
        c1,c2,c3=st.columns(3)
        c1.metric("Productos a revisar",int((resumen["CompraSugerida"]>0).sum()))
        c2.metric("Sin stock",int((resumen["StockActual"]<=0).sum()))
        c3.metric("Inversión sugerida",formato_soles(resumen["InversionSugerida"].sum()))
        ver=resumen[["Producto","Categoria","Unidades","VentaTotal","CostoTotal","MargenTotal","MargenPorcentaje","DemandaDiaria","StockActual","DiasCobertura","PuntoPedido","StockSeguridad","StockObjetivo","CompraSugerida","InversionSugerida","Estado"]].copy()
        st.dataframe(ver,use_container_width=True,hide_index=True)
        st.download_button("Descargar plan de reposición (Excel)",exportar_excel({"Reposicion":ver}),file_name="plan_reposicion.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


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
            <div style='font-size: 0.85rem; font-weight: 700; letter-spacing: 1px; color: #152238;'>
                TIENDAS <span style='color: #EC3237;'>PREMIUM</span>
            </div>
            <div style='font-size: 0.7rem; color: #6B7280; margin-top:2px;'>Sistema de Inventario</div>
        </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown(f"""
        <div style='background-color: #F4F6F9; border: 1px solid #E1E6EE; padding: 12px 14px; border-radius: 14px; margin-bottom: 16px;'>
            <div style='font-size: 0.8rem; font-weight: 600; color: #152238;'>{nombre_usuario}</div>
            <div style='font-size: 0.68rem; color: #9CA3AF; text-transform: uppercase;'>{safe_text(rol)} • USUARIO {login_usuario}</div>
        </div>
    """, unsafe_allow_html=True)

    opciones = ["Inicio", "Precios", "Sesión", "Zonas", "Inventario", "Resultados", "Análisis"]
    if rol == "ADMIN":
        opciones += ["Compras Inteligentes", "Seguridad y respaldos"]
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
        for key in ["autenticado", "usuario", "pagina", "nav_menu", "reconteo_activo", "sesion_actual", "codigo_pendiente", "producto_pendiente", "modo_inventario", "ultimo_codigo_scan", "zona_activa", "precio_producto", "precio_modo", "precio_ultimo_codigo_scan"]:
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
    elif pagina == "Zonas":
        pantalla_zonas()
    elif pagina == "Inventario":
        pantalla_inventario()
    elif pagina == "Resultados":
        pantalla_resultados()
    elif pagina == "Análisis":
        pantalla_analisis()
    elif pagina == "Compras Inteligentes":
        pantalla_compras_inteligentes()
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

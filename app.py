"""Punto de entrada.  Ejecutar con:  streamlit run app.py"""
import os
import time

import streamlit as st

from inventario.contexto import _estatica, BASE_DIR, backend, cfg, empresa_id, refrescar_conexion

# La configuración de página debe ser lo primero; usa solo la configuración estática (no requiere conexión).
_est = _estatica(empresa_id())
_icono = next((os.path.join(BASE_DIR, r) for r in (_est.favicon_ruta, _est.logo_ruta) if os.path.isfile(os.path.join(BASE_DIR, r))), "📦")
try:
    st.set_page_config(page_title=f"{_est.app_titulo} | {_est.nombre}", page_icon=_icono, layout="wide", initial_sidebar_state="expanded")
except Exception:
    pass

from inventario.navegacion import _cerrar_sesion, render_busqueda_inv, sidebar
from inventario.nucleo import errores, permisos
from inventario.pantallas.acceso import asistente_inicial, necesita_asistente, pantalla_login
from inventario.pantallas.admin import pantalla_admin
from inventario.pantallas.compras_ia import pantalla_stock_intelligence
from inventario.pantallas.configuracion import pantalla_configuracion
from inventario.pantallas.conteo import pantalla_inventario, pantalla_sesion, pantalla_zonas
from inventario.pantallas.importar import pantalla_importar
from inventario.pantallas.inicio import pantalla_inicio
from inventario.pantallas.movimientos import pantalla_movimientos
from inventario.pantallas.ordenes import pantalla_ordenes
from inventario.pantallas.precios import pantalla_precios
from inventario.pantallas.resultados import pantalla_analisis, pantalla_resultados
from inventario.pantallas.seguridad import pantalla_seguridad_y_respaldo
from inventario.pantallas.vencimientos import pantalla_vencimientos
from inventario.ui.componentes import footer, header, ui_pwa_inyectar
from inventario.ui.estilos import inyectar_estilos
from inventario.utilidades import mostrar_error_google

PAGINAS_FUNCIONES = {
    "Inicio": pantalla_inicio, "Precios": pantalla_precios, "Sesión": pantalla_sesion, "Zonas": pantalla_zonas, "Inventario": pantalla_inventario,
    "Movimientos": pantalla_movimientos, "Vencimientos": pantalla_vencimientos, "Órdenes de Compra": pantalla_ordenes,
    "Resultados": pantalla_resultados, "Análisis": pantalla_analisis, "Compras Inteligentes": pantalla_stock_intelligence,
    "Importar datos": pantalla_importar, "Seguridad y respaldos": pantalla_seguridad_y_respaldo, "Configuración": pantalla_configuracion,
    "Administración": pantalla_admin,
}

for _k, _v in {"autenticado": False, "usuario": None, "pagina": "Inicio", "gs_q": ""}.items():
    st.session_state.setdefault(_k, _v)

# --- conexión y configuración ---
try:
    backend()
    c = cfg()
except Exception as exc:
    header("No se pudo conectar", "Revisa la configuración de datos")
    codigo = errores.registrar_error("conexión inicial", exc)
    st.error(f"No se pudo abrir el almacenamiento de datos. Código de error: ERR-{codigo}.")
    st.info("Revisa que el archivo de datos exista y esté compartido con la cuenta de servicio, o la dirección de la base de datos en la configuración.")
    if st.button("Reintentar"):
        refrescar_conexion()
        st.rerun()
    st.stop()

inyectar_estilos()
ui_pwa_inyectar()

# --- primera vez ---
try:
    if necesita_asistente():
        asistente_inicial()
except Exception as exc:
    mostrar_error_google(exc, "la configuración inicial")
    st.stop()

# --- acceso ---
if not st.session_state.autenticado:
    try:
        pantalla_login()
    except Exception as exc:
        mostrar_error_google(exc, "el inicio de sesión")
    st.stop()

# --- control de sesión: duración máxima e inactividad ---
_ahora = time.time()
st.session_state.setdefault("login_timestamp", _ahora)
st.session_state.setdefault("ultima_actividad", _ahora)
_desde, _inactivo = _ahora - st.session_state.login_timestamp, _ahora - st.session_state.ultima_actividad
if _desde > c.sesion_max_horas * 3600 or _inactivo > c.inactividad_min * 60:
    _motivo = f"duración máxima ({c.sesion_max_horas} horas)" if _desde > c.sesion_max_horas * 3600 else f"inactividad ({c.inactividad_min} minutos)"
    from inventario.servicios import registrar_auditoria
    registrar_auditoria("LOGOUT_AUTOMATICO", f"Sesión cerrada por {_motivo}")
    _cerrar_sesion(_motivo)
    st.rerun()
st.session_state.ultima_actividad = _ahora

sidebar()

# --- transición entre secciones y búsqueda global ---
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
        mostrar_error_google(exc, "la búsqueda")
    footer()
    st.stop()

# --- pantalla actual (solo si el rol y los módulos lo permiten) ---
try:
    pagina = st.session_state.get("pagina", "Inicio")
    if pagina not in permisos.paginas_para(st.session_state.usuario, c):
        st.error("No tienes acceso a esta sección.")
    else:
        PAGINAS_FUNCIONES[pagina]()
    footer()
except Exception as exc:
    mostrar_error_google(exc, "la carga de la pantalla")
    footer()

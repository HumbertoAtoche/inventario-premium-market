"""Contexto de ejecución (une el núcleo con Streamlit): empresa activa, configuración, datos y servicios.

Nada aquí conoce pantallas. Todo lo que cambia entre empresas (hoja de datos, moneda, zona horaria,
umbrales…) se obtiene de `cfg()`; los datos, de `datos()`/`tabla()`."""
import functools
import os
import streamlit as st
from inventario.nucleo import config as _config, permisos, tiempo
from inventario.nucleo.ajustes import Ajustes
from inventario.nucleo.backend import crear_backend
from inventario.nucleo.compras import Compras
from inventario.nucleo.datos import Datos
from inventario.nucleo.esquemas import TABLAS
from inventario.nucleo.kardex import Kardex


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # raíz del proyecto (donde está app.py)


# ---------- empresa ----------
def empresas_disponibles():
    return _config.listar_empresas(BASE_DIR)


def empresa_id():
    return st.session_state.get("empresa_id") or empresas_disponibles()[0]["id"]


def _secretos(eid):
    """Bloque opcional [empresas.<id>] o [empresa] de los secretos de Streamlit."""
    try:
        if "empresas" in st.secrets and eid in st.secrets["empresas"]:
            return dict(st.secrets["empresas"][eid])
        if "empresa" in st.secrets:
            return dict(st.secrets["empresa"])
    except Exception:
        pass
    return {}


@st.cache_resource(show_spinner=False)
def _estatica(eid):
    return _config.cargar_estatica(BASE_DIR, eid, _secretos(eid))


@st.cache_resource(show_spinner=False)
def _backend(eid):
    """Una conexión por empresa y por proceso. Crea las tablas que falten si `datos_autocrear` está activo."""
    c = _estatica(eid)
    cred = None
    if c.datos_backend == "sheets":
        cred = st.secrets[c.datos_credenciales] if c.datos_credenciales in st.secrets else st.secrets["gcp_service_account"]
    b = crear_backend(c, cred)
    if c.datos_autocrear:
        b.asegurar_esquema()
    else:
        faltan = [TABLAS[k][0] for k in ("inventario", "conteos", "sesiones", "resumen", "usuarios") if not b.existe(TABLAS[k][0])]
        if faltan:
            raise RuntimeError("Faltan estas tablas en los datos: " + ", ".join(faltan))
    return b


def backend():
    return _backend(empresa_id())


@st.cache_resource(show_spinner=False)
def _servicio_config(eid):
    return _config.ServicioConfig(_estatica(eid), lambda: _backend(eid).tabla(TABLAS["configuracion"][0], TABLAS["configuracion"][1]))


def servicio_config():
    return _servicio_config(empresa_id())


def cfg():
    """Configuración efectiva de la empresa activa (y fija su zona horaria para esta ejecución)."""
    return servicio_config().efectiva()


def refrescar_conexion():
    _backend.clear()
    _servicio_config.clear()
    _estatica.clear()


# ---------- datos y servicios ----------
def datos():
    return Datos(backend())


def tabla(clave):
    return datos().t(clave)


def obtener_hoja(clave):
    return tabla(clave)


def hoja_control(nombre, encabezados):
    return backend().tabla(nombre, list(encabezados))


def kardex():
    return Kardex(datos(), cfg(), tiempo.ahora)


def compras():
    return Compras(datos(), kardex(), tiempo.ahora)


def ajustes():
    return Ajustes(datos(), kardex(), tiempo.ahora)


def permiso(nombre):
    return permisos.tiene(st.session_state.get("usuario"), nombre)


def simbolo():
    return cfg().moneda_simbolo


def moneda_fmt():
    c = cfg()
    return f"{c.moneda_simbolo} %.{int(c.moneda_decimales)}f"


# ---------- caché que NO mezcla empresas ni usuarios ----------
def cache_empresa(ttl=60, sucursal=False):
    """Como st.cache_data, pero la clave incluye la empresa. Con sucursal=True, además recorta el
    resultado a las sucursales a las que tiene acceso el usuario actual (la caché guarda todo)."""
    def deco(fn):
        @st.cache_data(ttl=ttl, show_spinner=False)
        def _interno(eid, nombre, *a, **k):
            return fn(*a, **k)

        @functools.wraps(fn)
        def envoltura(*a, **k):
            r = _interno(empresa_id(), fn.__qualname__, *a, **k)
            return permisos.filtrar_sucursales(r, st.session_state.get("usuario")) if sucursal else r
        envoltura.clear = _interno.clear
        return envoltura
    return deco

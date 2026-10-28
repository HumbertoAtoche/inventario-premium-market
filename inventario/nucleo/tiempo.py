"""Hora de la empresa.

Streamlit Cloud corre en UTC: `datetime.now()` daba hora equivocada (5 h en Perú).
Aquí todo sale en la zona horaria configurada. Se usa un ContextVar para que dos
sesiones con zonas distintas no se pisen.
"""
import contextvars
from datetime import datetime
from zoneinfo import ZoneInfo

_ZONA = contextvars.ContextVar("zona_empresa", default="America/Lima")


def usar_zona(nombre):
    """Fija la zona horaria de la sesión actual. Si es inválida, conserva la anterior."""
    try:
        ZoneInfo(nombre)
    except Exception:
        return False
    _ZONA.set(nombre)
    return True


def zona():
    return ZoneInfo(_ZONA.get())


def ahora():
    """Fecha/hora local de la empresa SIN tzinfo (compatible con los datos guardados como texto)."""
    return datetime.now(zona()).replace(tzinfo=None)


def ahora_str():
    return ahora().strftime("%Y-%m-%d %H:%M:%S")


def hoy_str():
    return ahora().strftime("%Y-%m-%d")


def saludo(hora=None):
    h = ahora().hour if hora is None else hora
    return "Buenos días" if h < 12 else ("Buenas tardes" if h < 19 else "Buenas noches")

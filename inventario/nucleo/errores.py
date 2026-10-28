"""Registro de errores: cada fallo recibe un código corto para encontrarlo luego en el log."""
import logging
import traceback
import uuid

logger = logging.getLogger("inventario")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)


def registrar_error(contexto, exc):
    """Escribe el error completo en el log y devuelve un código corto para mostrar al usuario."""
    codigo = uuid.uuid4().hex[:8].upper()
    logger.error("ERR-%s · %s · %s\n%s", codigo, contexto, exc, "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    return codigo


def clasificar(exc):
    """Tipo de problema de datos: cuota | permiso | no_encontrado | otro."""
    t = str(exc).lower()
    if "429" in t or "quota exceeded" in t:
        return "cuota"
    if "403" in t or "permission" in t:
        return "permiso"
    if "404" in t or "not found" in t:
        return "no_encontrado"
    return "otro"

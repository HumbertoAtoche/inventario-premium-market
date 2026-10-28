"""Utilidades numéricas y de códigos, sin dependencias de la interfaz."""
import re
import uuid


def limpiar_codigo(valor):
    if valor is None:
        return ""
    try:
        if valor != valor:      # NaN
            return ""
    except Exception:
        pass
    texto = str(valor).strip()
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto


def num(valor, default=0.0):
    """Número tolerante: '1,234.50', '1.234,50', 'S/ 12', 12, '' -> float."""
    if valor is None or (isinstance(valor, float) and valor != valor):
        return default
    if isinstance(valor, (int, float)):
        return float(valor)
    t = re.sub(r"[^\d,.\-]", "", str(valor).strip())
    if t in ("", "-", ".", ","):
        return default
    if "," in t and "." in t:
        t = t.replace(",", "") if t.rfind(".") > t.rfind(",") else t.replace(".", "").replace(",", ".")
    elif "," in t:
        partes = t.split(",")
        t = t.replace(",", ".") if len(partes) == 2 and len(partes[1]) in (1, 2) else t.replace(",", "")
    try:
        return float(t)
    except ValueError:
        return default


def nuevo_id(prefijo, ahora):
    return f"{prefijo}-{ahora.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"


def misma(a, b):
    return str(a).strip().casefold() == str(b).strip().casefold()

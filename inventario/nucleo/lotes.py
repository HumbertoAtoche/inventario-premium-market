"""Lotes y vencimientos (módulo opcional). FEFO: primero en vencer, primero en salir."""
from datetime import datetime, date
import pandas as pd

from .backend import buscar_filas, actualizar_donde, agregar_dict
from .esquemas import HEADERS_LOTES
from .util import num, limpiar_codigo, misma

_FORMATOS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d")


def parsear_fecha(txt):
    t = str(txt or "").strip()[:10]
    for f in _FORMATOS:
        try:
            return datetime.strptime(t, f).date()
        except ValueError:
            continue
    return None


def _crit(codigo, sucursal, lote=None):
    c = {"CodigoProducto": limpiar_codigo(codigo), "Sucursal": sucursal}
    if lote is not None:
        c["Lote"] = lote
    return c


def registrar_ingreso(datos, ahora, codigo, sucursal, lote, vence, cantidad):
    """Suma `cantidad` al lote (lo crea si no existe)."""
    if not str(lote).strip():
        raise ValueError("Indica el número de lote.")
    f = parsear_fecha(vence)
    if vence and f is None:
        raise ValueError("Fecha de vencimiento no válida (usa AAAA-MM-DD).")
    t = datos.t("lotes")
    hallado = buscar_filas(t, _crit(codigo, sucursal, str(lote).strip()))
    if hallado:
        _, reg = hallado[-1]
        actualizar_donde(t, _crit(codigo, sucursal, str(lote).strip()),
                         {"Cantidad": num(reg["Cantidad"]) + float(cantidad), "FechaVencimiento": f.isoformat() if f else reg["FechaVencimiento"]})
    else:
        agregar_dict(t, HEADERS_LOTES, {"CodigoProducto": limpiar_codigo(codigo), "Sucursal": sucursal, "Lote": str(lote).strip(),
                                        "FechaVencimiento": f.isoformat() if f else "", "Cantidad": float(cantidad),
                                        "FechaIngreso": ahora.strftime("%Y-%m-%d")})


def saldo_lotes(datos, codigo, sucursal):
    """Lotes con saldo > 0 ordenados FEFO (sin fecha al final)."""
    filas = [reg for _, reg in buscar_filas(datos.t("lotes"), _crit(codigo, sucursal)) if num(reg["Cantidad"]) > 0]
    filas.sort(key=lambda r: (parsear_fecha(r["FechaVencimiento"]) is None, parsear_fecha(r["FechaVencimiento"]) or date.max))
    return filas


def consumir(datos, codigo, sucursal, cantidad, lote=None):
    """Descuenta de un lote concreto o por FEFO. Devuelve ([(lote, cantidad)], sin_lote).
    `sin_lote` es lo que no pudo cubrirse con lotes (stock sin lote registrado)."""
    t = datos.t("lotes")
    restante, asignado = float(cantidad), []
    candidatos = ([r for r in saldo_lotes(datos, codigo, sucursal) if misma(r["Lote"], lote)] if lote else saldo_lotes(datos, codigo, sucursal))
    for r in candidatos:
        if restante <= 1e-9:
            break
        toma = min(restante, num(r["Cantidad"]))
        actualizar_donde(t, _crit(codigo, sucursal, r["Lote"]), {"Cantidad": num(r["Cantidad"]) - toma})
        asignado.append((str(r["Lote"]), toma))
        restante -= toma
    return asignado, max(0.0, restante)


def alertas(df_lotes, hoy, dias=(30, 60)):
    """Lotes con saldo y su estado de vencimiento."""
    cols = ["CodigoProducto", "Sucursal", "Lote", "FechaVencimiento", "Cantidad", "DiasParaVencer", "Estado"]
    if df_lotes is None or df_lotes.empty:
        return pd.DataFrame(columns=cols)
    d = df_lotes.copy()
    d["Cantidad"] = d["Cantidad"].map(num)
    d = d[d["Cantidad"] > 0]
    d["_f"] = d["FechaVencimiento"].map(parsear_fecha)
    d = d[d["_f"].notna()].copy()
    d["DiasParaVencer"] = d["_f"].map(lambda f: (f - hoy).days)
    d1, d2 = (sorted(dias) + [60, 90])[:2] if len(dias) < 2 else sorted(dias)[:2]

    def estado(x):
        return "VENCIDO" if x < 0 else (f"≤{d1} días" if x <= d1 else (f"≤{d2} días" if x <= d2 else "OK"))
    d["Estado"] = d["DiasParaVencer"].map(estado)
    return d.sort_values("DiasParaVencer")[cols].reset_index(drop=True)

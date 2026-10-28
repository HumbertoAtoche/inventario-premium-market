"""Importación de productos y ventas desde Excel/CSV, con detección de columnas y validación.

Sirve a cualquier empresa: no exige un formato fijo; se *mapean* las columnas del archivo
a los campos que usa el sistema (y el mapeo se puede guardar para la próxima vez).
"""
import csv
import difflib
import io
import re
import unicodedata

import pandas as pd

from .esquemas import HEADERS_INVENTARIO, VENTAS_COLUMNAS
from .util import num, limpiar_codigo

CAMPOS_PRODUCTO = {
    "CodigoBarras": ["codigo de barras", "codigo barras", "barras", "ean", "upc", "gtin", "cod barras", "codbarras", "codigo de barra"],
    "CodigoProducto": ["codigo", "codigo producto", "cod", "sku", "item", "id producto", "codigo interno", "referencia", "cod producto"],
    "Producto": ["producto", "nombre", "nombre producto", "articulo", "nombre del producto", "descripcion producto"],
    "Descripcion": ["descripcion", "detalle", "observacion", "presentacion"],
    "Categoria": ["categoria", "rubro", "familia", "linea", "grupo", "tipo"],
    "Marca": ["marca", "fabricante", "brand"],
    "Unidad": ["unidad", "um", "u m", "unidad de medida", "medida", "und"],
    "Sucursal": ["sucursal", "tienda", "almacen", "local", "bodega", "sede"],
    "StockSistema": ["stock", "stock sistema", "existencia", "existencias", "cantidad", "saldo", "stock actual", "inventario"],
    "CostoUnitario": ["costo", "costo unitario", "costo unit", "precio costo", "costo promedio", "costo compra", "costo*"],
    "PrecioVenta": ["precio", "p venta", "pv", "precio venta", "precio de venta", "pvp", "precio publico", "precio unitario"],
    "Estado": ["estado", "activo", "status"],
    "StockMinimo": ["stock minimo", "minimo", "stock min", "punto de reposicion", "min"],
}
OBLIGATORIOS_PRODUCTO = ["Producto"]          # además: CodigoProducto o CodigoBarras

CAMPOS_VENTA = {
    "Fecha": ["fecha", "fecha hora", "fecha/hora", "fecha de venta", "date", "fecha emision"],
    "CodigoBarras": ["codigo de barras", "codigo de barra", "barras", "ean", "codigo barras"],
    "SKU": ["sku", "codigo", "codigo producto", "cod", "item"],
    "Producto": ["producto", "nombre", "articulo", "descripcion"],
    "Cantidad": ["cantidad", "cant", "unidades", "qty", "cantidad vendida"],
    "Total": ["total", "importe", "venta", "monto", "subtotal", "valor venta"],
    "Costo": ["costo", "costo total", "costo*"],
    "Categoria": ["categoria", "rubro", "familia", "linea"],
    "Comprobante": ["comprobante", "documento", "boleta", "factura", "nro comprobante", "ticket"],
}


def _norm(s):
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9*]+", " ", s)).strip()


# ---------- lectura ----------
def _detectar_separador(texto):
    """Elige el separador que aparece igual de seguido en más líneas (ignora comas decimales y títulos)."""
    lineas = [l for l in texto.splitlines() if l.strip()][:30]
    mejor, mejor_p = ",", 0
    for sep in (";", "\t", "|", ","):                      # en empate gana el primero
        cuentas = [l.count(sep) for l in lineas if l.count(sep) > 0]
        if not cuentas:
            continue
        moda = max(set(cuentas), key=cuentas.count)
        puntaje = cuentas.count(moda) * moda
        if puntaje > mejor_p:
            mejor, mejor_p = sep, puntaje
    return mejor


def detectar_encabezado(raw):
    """Índice de la fila que parece ser el encabezado (salta títulos generales del reporte)."""
    muestra = raw.head(12)
    cuentas = [(i, sum(1 for v in muestra.iloc[i] if str(v).strip())) for i in range(len(muestra))]
    if not cuentas:
        return 0
    maximo = max(c for _, c in cuentas)
    for i, c in cuentas:
        if c >= max(2, int(maximo * 0.6)):
            return i
    return 0


def leer_archivo(contenido, nombre, hoja=0, fila_encabezado=None):
    """Devuelve (DataFrame de textos, fila_encabezado_usada)."""
    ext = nombre.lower().rsplit(".", 1)[-1]
    if ext in ("xlsx", "xlsm", "xls"):
        raw = pd.read_excel(io.BytesIO(contenido), sheet_name=hoja, header=None, dtype=str).fillna("")
    else:
        texto = None
        for enc in ("utf-8-sig", "latin-1"):
            try:
                texto = contenido.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        sep = _detectar_separador(texto)
        filas = list(csv.reader(io.StringIO(texto), delimiter=sep))       # tolera filas de título con menos columnas
        ancho = max((len(f) for f in filas), default=0)
        raw = pd.DataFrame([f + [""] * (ancho - len(f)) for f in filas], dtype=str)
    raw = raw.astype(str)
    h = detectar_encabezado(raw) if fila_encabezado is None else int(fila_encabezado)
    df = raw.iloc[h + 1:].copy()
    df.columns = [str(c).strip() or f"columna_{i}" for i, c in enumerate(raw.iloc[h])]
    df = df.loc[:, ~df.columns.duplicated()]
    df = df[(df.apply(lambda r: any(str(v).strip() for v in r), axis=1))].reset_index(drop=True)
    return df, h


# ---------- mapeo ----------
def sugerir_mapeo(columnas, campos):
    """{campo: columna_del_archivo | None}."""
    libres = {c: _norm(c) for c in columnas}
    res = {k: None for k in campos}
    for campo, alias in campos.items():                     # 1) coincidencia exacta con un alias
        al = {_norm(campo)} | {_norm(a) for a in alias}
        for c, n in list(libres.items()):
            if n in al:
                res[campo] = c
                libres.pop(c)
                break
    for campo, alias in campos.items():                     # 2) parecido
        if res[campo] or not libres:
            continue
        al = [_norm(campo)] + [_norm(a) for a in alias]
        mejor, puntaje = None, 0.0
        for c, n in libres.items():
            p = max(difflib.SequenceMatcher(None, n, a).ratio() for a in al)
            if p > puntaje:
                mejor, puntaje = c, p
        if mejor and puntaje >= 0.86:
            res[campo] = mejor
            libres.pop(mejor)
    return res


# ---------- productos ----------
def _clave(sucursal, barras, codigo):
    return (str(sucursal).strip().casefold(), limpiar_codigo(barras) or limpiar_codigo(codigo))


def _numero(v):
    """(valor, válido). Vacío = 0 válido."""
    if str(v).strip() == "":
        return 0.0, True
    r = num(v, default=None)
    return (0.0, False) if r is None else (r, True)


def convertir_productos(df, mapeo, sucursal_defecto="Principal", offset=2):
    """-> (DataFrame con HEADERS_INVENTARIO, errores [{'fila','problema'}], advertencias [str])."""
    errores, adv, filas, vistos = [], [], [], set()
    g = lambda r, campo: str(r[mapeo[campo]]).strip() if mapeo.get(campo) and mapeo[campo] in r.index else ""
    if not mapeo.get("Producto"):
        return pd.DataFrame(columns=HEADERS_INVENTARIO), [{"fila": 0, "problema": "Falta indicar la columna del nombre del producto."}], []
    if not (mapeo.get("CodigoProducto") or mapeo.get("CodigoBarras")):
        return pd.DataFrame(columns=HEADERS_INVENTARIO), [{"fila": 0, "problema": "Indica al menos la columna de código de producto o de código de barras."}], []
    for i, r in df.iterrows():
        n = i + offset            # número de fila en el archivo original (offset = fila del encabezado + 2)
        reg = {c: g(r, c) for c in HEADERS_INVENTARIO}
        reg["CodigoBarras"], reg["CodigoProducto"] = limpiar_codigo(reg["CodigoBarras"]), limpiar_codigo(reg["CodigoProducto"])
        if not reg["Producto"]:
            errores.append({"fila": n, "problema": "Sin nombre de producto"}); continue
        if not (reg["CodigoBarras"] or reg["CodigoProducto"]):
            errores.append({"fila": n, "problema": "Sin código"}); continue
        malo = False
        for c in ("StockSistema", "CostoUnitario", "PrecioVenta", "StockMinimo"):
            v, ok = _numero(reg[c])
            if not ok:
                errores.append({"fila": n, "problema": f"{c} no es un número: «{reg[c]}»"}); malo = True; break
            if c != "StockSistema" and v < 0:
                errores.append({"fila": n, "problema": f"{c} negativo"}); malo = True; break
            reg[c] = v
        if malo:
            continue
        if reg["StockSistema"] < 0:
            adv.append(f"Fila {n}: stock negativo ({reg['StockSistema']:g}) en «{reg['Producto']}».")
        reg["Sucursal"] = reg["Sucursal"] or sucursal_defecto
        reg["Unidad"] = reg["Unidad"] or "UND"
        reg["Estado"] = reg["Estado"] or "ACTIVO"
        k = _clave(reg["Sucursal"], reg["CodigoBarras"], reg["CodigoProducto"])
        if k in vistos:
            errores.append({"fila": n, "problema": "Duplicado (se conserva la primera fila)"}); continue
        vistos.add(k)
        filas.append(reg)
    return pd.DataFrame(filas, columns=HEADERS_INVENTARIO), errores, adv


def escribir_productos(datos, df, modo="agregar_nuevos"):
    """modo: agregar_nuevos | actualizar | reemplazar. Devuelve {'nuevos','actualizados','omitidos'}."""
    t = datos.t("inventario")
    grid = t.get_all_values()
    head = [str(h).strip() for h in grid[0]] if grid else list(HEADERS_INVENTARIO)
    fila_de = lambda reg: [reg.get(h, "") for h in head]
    if modo == "reemplazar":
        t.reemplazar_todo([head] + [fila_de(r) for r in df.to_dict("records")])
        return {"nuevos": len(df), "actualizados": 0, "omitidos": 0}
    pos = {h: i for i, h in enumerate(head)}
    existentes = {}
    for idx, r in enumerate(grid[1:], 1):
        cel = lambda c: r[pos[c]] if c in pos and pos[c] < len(r) else ""
        existentes[_clave(cel("Sucursal"), cel("CodigoBarras"), cel("CodigoProducto"))] = idx
    nuevos, actualizados, omitidos = [], 0, 0
    for reg in df.to_dict("records"):
        k = _clave(reg["Sucursal"], reg["CodigoBarras"], reg["CodigoProducto"])
        if k in existentes:
            if modo == "actualizar":
                fila = grid[existentes[k]]
                fila += [""] * (len(head) - len(fila))
                for h in head:
                    if h in reg:
                        fila[pos[h]] = str(reg[h])
                actualizados += 1
            else:
                omitidos += 1
        else:
            nuevos.append(fila_de(reg))
    if actualizados:
        t.reemplazar_todo(grid + nuevos)
    elif nuevos:
        t.append_rows(nuevos, value_input_option="RAW")
    return {"nuevos": len(nuevos), "actualizados": actualizados, "omitidos": omitidos}


# ---------- ventas ----------
def convertir_ventas(df, mapeo, offset=2):
    """-> (DataFrame con VENTAS_COLUMNAS, errores, advertencias)."""
    if all(c in df.columns for c in VENTAS_COLUMNAS):                       # ya viene en el formato del reporte
        out = df[VENTAS_COLUMNAS].astype(str).copy()
        return out.reset_index(drop=True), [], ["El archivo ya tiene las 25 columnas del reporte: se usó tal cual."]
    if not mapeo.get("Fecha") or not mapeo.get("Cantidad") or not (mapeo.get("Producto") or mapeo.get("SKU") or mapeo.get("CodigoBarras")):
        return pd.DataFrame(columns=VENTAS_COLUMNAS), [{"fila": 0, "problema": "Indica al menos las columnas de fecha, cantidad y producto/código."}], []
    g = lambda r, c: str(r[mapeo[c]]).strip() if mapeo.get(c) and mapeo[c] in r.index else ""
    fechas = pd.to_datetime(df[mapeo["Fecha"]].astype(str).str.strip(), dayfirst=True, errors="coerce", format="mixed")
    errores, filas = [], []
    for i, r in df.iterrows():
        n = i + offset            # número de fila en el archivo original (offset = fila del encabezado + 2)
        if pd.isna(fechas.iloc[i]):
            errores.append({"fila": n, "problema": f"Fecha no válida: «{r[mapeo['Fecha']]}»"}); continue
        cant, ok = _numero(g(r, "Cantidad"))
        if not ok or cant <= 0:
            errores.append({"fila": n, "problema": f"Cantidad no válida: «{g(r, 'Cantidad')}»"}); continue
        fila = {c: "" for c in VENTAS_COLUMNAS}
        fila.update({"N": str(len(filas) + 1), "FECHA/HORA": fechas.iloc[i].strftime("%d-%m-%Y %H:%M"), "COMPROBANTE": g(r, "Comprobante"),
                     "CÓDIGO DE BARRA": limpiar_codigo(g(r, "CodigoBarras")), "SKU": limpiar_codigo(g(r, "SKU")), "PRODUCTO": g(r, "Producto"),
                     "CATEGORÍA": g(r, "Categoria"), "CANTIDAD": f"{cant:g}", "TOTAL": f"{num(g(r, 'Total')):.2f}", "COSTO*": f"{num(g(r, 'Costo')):.2f}"})
        filas.append(fila)
    return pd.DataFrame(filas, columns=VENTAS_COLUMNAS), errores, []


def _clave_venta(r):
    return (str(r["FECHA/HORA"]).strip(), limpiar_codigo(r["CÓDIGO DE BARRA"]), limpiar_codigo(r["SKU"]), str(r["PRODUCTO"]).strip().casefold(),
            round(num(r["CANTIDAD"]), 4), round(num(r["TOTAL"]), 2), str(r["COMPROBANTE"]).strip())


def escribir_ventas(datos, df, modo="agregar"):
    """modo: agregar (omite lo ya registrado) | reemplazar. Devuelve {'nuevos','omitidos'}."""
    t = datos.t("ventas")
    if modo == "reemplazar":
        t.reemplazar_todo([VENTAS_COLUMNAS] + df[VENTAS_COLUMNAS].astype(str).values.tolist())
        return {"nuevos": len(df), "omitidos": 0}
    g = t.get_all_values()
    existentes = set()
    for r in g[1:]:
        r = (r + [""] * len(VENTAS_COLUMNAS))[:len(VENTAS_COLUMNAS)]
        existentes.add(_clave_venta(dict(zip(VENTAS_COLUMNAS, r))))
    nuevas = [r for r in df[VENTAS_COLUMNAS].astype(str).to_dict("records") if _clave_venta(r) not in existentes]
    if nuevas:
        t.append_rows([[r[c] for c in VENTAS_COLUMNAS] for r in nuevas], value_input_option="RAW")
    return {"nuevos": len(nuevas), "omitidos": len(df) - len(nuevas)}

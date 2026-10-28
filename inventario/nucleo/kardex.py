"""Movimientos de inventario (kardex): entradas, salidas, mermas, devoluciones, transferencias y ajustes.

Cada movimiento queda registrado con el stock antes y después, y actualiza `StockSistema`.
Nota de concurrencia: con Google Sheets la lectura-escritura del stock no es atómica; si dos
personas mueven el MISMO producto en el mismo segundo, uno podría pisar al otro. Con un backend
SQL real conviene mover esto a un UPDATE atómico (ver README).
"""
import pandas as pd

from . import lotes as _lotes
from .backend import buscar_filas, actualizar_donde, agregar_dict
from .esquemas import HEADERS_MOVIMIENTOS, HEADERS_INVENTARIO
from .util import num, limpiar_codigo, nuevo_id, misma

SIGNO = {
    "ENTRADA": 1, "DEVOLUCION_CLIENTE": 1, "AJUSTE_POSITIVO": 1, "TRANSFERENCIA_ENTRADA": 1,
    "SALIDA": -1, "MERMA": -1, "DEVOLUCION_PROVEEDOR": -1, "AJUSTE_NEGATIVO": -1, "TRANSFERENCIA_SALIDA": -1,
}
MANUALES = ["ENTRADA", "SALIDA", "MERMA", "DEVOLUCION_CLIENTE", "DEVOLUCION_PROVEEDOR"]
ETIQUETAS = {
    "ENTRADA": "Entrada (compra / ingreso)", "SALIDA": "Salida (consumo / baja)", "MERMA": "Merma (rotura, vencimiento, pérdida)",
    "DEVOLUCION_CLIENTE": "Devolución de cliente", "DEVOLUCION_PROVEEDOR": "Devolución a proveedor",
}


class Kardex:
    def __init__(self, datos, cfg, ahora):
        """`ahora`: función sin argumentos que devuelve la hora local (naive)."""
        self.datos, self.cfg, self.ahora = datos, cfg, ahora

    # ---------- búsqueda ----------
    def buscar_producto(self, codigo, sucursal):
        t = self.datos.t("inventario")
        c = limpiar_codigo(codigo)
        for campo in ("CodigoProducto", "CodigoBarras"):
            r = buscar_filas(t, {campo: c, "Sucursal": sucursal})
            if r:
                return r[-1]
        return None

    def _fijar_stock(self, fila, reg, nuevo):
        t = self.datos.t("inventario")
        col = list(reg).index("StockSistema") + 1
        t.update_cell(fila, col, nuevo)

    # ---------- registro ----------
    def registrar(self, usuario, tipo, codigo, sucursal, cantidad, costo=None, lote="", vence="",
                  referencia="", motivo="", permitir_negativo=None):
        tipo = str(tipo).upper()
        if tipo not in SIGNO:
            raise ValueError(f"Tipo de movimiento no válido: {tipo}")
        cant = num(cantidad, 0.0)
        if cant <= 0:
            raise ValueError("La cantidad debe ser mayor que cero.")
        if permitir_negativo is None:
            permitir_negativo = bool(self.cfg.permitir_stock_negativo)
        hallado = self.buscar_producto(codigo, sucursal)
        if not hallado:
            raise ValueError(f"No existe el producto «{codigo}» en la sucursal «{sucursal}».")
        fila, reg = hallado
        antes = num(reg["StockSistema"])
        delta = SIGNO[tipo] * cant
        despues = antes + delta
        if despues < -1e-9 and not permitir_negativo:
            raise ValueError(f"Stock insuficiente: hay {antes:g} y se intenta sacar {cant:g}.")
        usa_lotes = self.cfg.modulo("lotes")
        partes = [(str(lote).strip(), cant)]
        if usa_lotes and SIGNO[tipo] > 0 and str(lote).strip():
            _lotes.registrar_ingreso(self.datos, self.ahora(), reg["CodigoProducto"] or codigo, sucursal, lote, vence, cant)
        elif usa_lotes and SIGNO[tipo] < 0:
            asignado, sin_lote = _lotes.consumir(self.datos, reg["CodigoProducto"] or codigo, sucursal, cant, str(lote).strip() or None)
            partes = [(l, c) for l, c in asignado] + ([("", sin_lote)] if sin_lote > 1e-9 else [])
        self._fijar_stock(fila, reg, despues)
        costo_u = num(costo, num(reg["CostoUnitario"])) if costo not in (None, "") else num(reg["CostoUnitario"])
        t = self.datos.t("movimientos")
        ids, corriente = [], antes
        for lote_i, cant_i in partes:
            nuevo = corriente + SIGNO[tipo] * cant_i
            idm = nuevo_id("MOV", self.ahora())
            agregar_dict(t, HEADERS_MOVIMIENTOS, {
                "IdMov": idm, "FechaHora": self.ahora().strftime("%Y-%m-%d %H:%M:%S"), "Usuario": usuario, "Tipo": tipo,
                "Sucursal": sucursal, "CodigoProducto": reg["CodigoProducto"], "CodigoBarras": reg["CodigoBarras"],
                "Producto": reg["Producto"], "Cantidad": SIGNO[tipo] * cant_i, "CostoUnitario": costo_u, "Lote": lote_i,
                "Referencia": referencia, "Motivo": motivo, "StockAntes": corriente, "StockDespues": nuevo})
            ids.append(idm)
            corriente = nuevo
        return {"ids": ids, "producto": reg["Producto"], "stock_antes": antes, "stock_despues": despues}

    def transferir(self, usuario, codigo, origen, destino, cantidad, motivo=""):
        if misma(origen, destino):
            raise ValueError("El origen y el destino deben ser distintos.")
        h = self.buscar_producto(codigo, origen)
        if not h:
            raise ValueError(f"No existe el producto «{codigo}» en «{origen}».")
        if num(cantidad) > num(h[1]["StockSistema"]) + 1e-9 and not self.cfg.permitir_stock_negativo:
            raise ValueError(f"Stock insuficiente en «{origen}»: hay {num(h[1]['StockSistema']):g}.")
        if not self.buscar_producto(codigo, destino):        # el producto aún no existe en el destino: se crea con stock 0
            nuevo = {k: h[1].get(k, "") for k in HEADERS_INVENTARIO}
            nuevo.update({"Sucursal": destino, "StockSistema": 0})
            agregar_dict(self.datos.t("inventario"), HEADERS_INVENTARIO, nuevo)
        ref = nuevo_id("TRF", self.ahora())
        a = self.registrar(usuario, "TRANSFERENCIA_SALIDA", codigo, origen, cantidad, referencia=ref, motivo=motivo or f"Hacia {destino}")
        b = self.registrar(usuario, "TRANSFERENCIA_ENTRADA", codigo, destino, cantidad, referencia=ref, motivo=motivo or f"Desde {origen}",
                           costo=h[1].get("CostoUnitario"))
        return {"referencia": ref, "salida": a, "entrada": b}

    # ---------- consulta ----------
    def historial(self, sucursal=None, tipo=None, desde=None, hasta=None, texto=""):
        df = self.datos.df("movimientos")
        if df.empty:
            return df
        if sucursal and sucursal != "Todas":
            df = df[df["Sucursal"].astype(str) == sucursal]
        if tipo and tipo != "Todos":
            df = df[df["Tipo"].astype(str) == tipo]
        f = pd.to_datetime(df["FechaHora"], errors="coerce")
        mask = pd.Series(True, index=df.index)
        if desde is not None:
            mask &= f >= pd.Timestamp(desde)
        if hasta is not None:
            mask &= f < pd.Timestamp(hasta) + pd.Timedelta(days=1)
        df = df[mask]
        if texto:
            t = str(texto).strip().casefold()
            m = df[["Producto", "CodigoProducto", "CodigoBarras", "Referencia", "Motivo"]].astype(str).apply(lambda c: c.str.casefold().str.contains(t, regex=False)).any(axis=1)
            df = df[m]
        return df.sort_values("FechaHora", ascending=False)

    def kardex_producto(self, codigo, sucursal):
        """Movimientos de un producto en orden cronológico con su saldo."""
        df = self.datos.df("movimientos")
        if df.empty:
            return df
        c = limpiar_codigo(codigo)
        m = ((df["CodigoProducto"].astype(str) == c) | (df["CodigoBarras"].astype(str) == c)) & (df["Sucursal"].astype(str).str.casefold() == str(sucursal).casefold())
        return df[m].sort_values("FechaHora")

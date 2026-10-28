"""Proveedores y órdenes de compra, con recepción (total o parcial) que alimenta el kardex."""
import pandas as pd

from .backend import buscar_filas, actualizar_donde, agregar_dict
from .esquemas import HEADERS_PROVEEDORES, HEADERS_OC, HEADERS_OC_DET
from .util import num, limpiar_codigo, nuevo_id

ESTADOS_OC = ["BORRADOR", "ENVIADA", "RECIBIDA_PARCIAL", "RECIBIDA", "ANULADA"]


class Compras:
    def __init__(self, datos, kardex, ahora):
        self.datos, self.kardex, self.ahora = datos, kardex, ahora

    # ---------- proveedores ----------
    def crear_proveedor(self, nombre, id_fiscal="", contacto="", telefono="", email="", plazo_dias=0):
        if not str(nombre).strip():
            raise ValueError("El nombre del proveedor es obligatorio.")
        df = self.datos.df("proveedores")
        if not df.empty and (df["Nombre"].astype(str).str.strip().str.casefold() == str(nombre).strip().casefold()).any():
            raise ValueError("Ya existe un proveedor con ese nombre.")
        idp = nuevo_id("PRV", self.ahora())
        agregar_dict(self.datos.t("proveedores"), HEADERS_PROVEEDORES, {
            "IdProveedor": idp, "Nombre": str(nombre).strip(), "IdFiscal": id_fiscal, "Contacto": contacto, "Telefono": telefono,
            "Email": email, "PlazoEntregaDias": int(num(plazo_dias)), "Estado": "ACTIVO"})
        return idp

    def proveedores(self, solo_activos=True):
        df = self.datos.df("proveedores")
        if solo_activos and not df.empty:
            df = df[df["Estado"].astype(str).str.upper() == "ACTIVO"]
        return df

    def cambiar_estado_proveedor(self, id_proveedor, estado):
        return actualizar_donde(self.datos.t("proveedores"), {"IdProveedor": id_proveedor}, {"Estado": estado})

    # ---------- órdenes ----------
    def crear_oc(self, usuario, id_proveedor, sucursal, items, observacion=""):
        items = [i for i in items if num(i.get("cantidad")) > 0]
        if not items:
            raise ValueError("Agrega al menos un producto con cantidad mayor que cero.")
        prov = buscar_filas(self.datos.t("proveedores"), {"IdProveedor": id_proveedor})
        if not prov:
            raise ValueError("Proveedor no encontrado.")
        ido = nuevo_id("OC", self.ahora())
        total = sum(num(i["cantidad"]) * num(i.get("costo")) for i in items)
        agregar_dict(self.datos.t("ordenes_compra"), HEADERS_OC, {
            "IdOC": ido, "Fecha": self.ahora().strftime("%Y-%m-%d"), "IdProveedor": id_proveedor, "Proveedor": prov[-1][1]["Nombre"],
            "Sucursal": sucursal, "Estado": "BORRADOR", "Total": round(total, 2), "Usuario": usuario, "Observacion": observacion, "FechaRecepcion": ""})
        det = self.datos.t("ordenes_compra_det")
        for i in items:
            agregar_dict(det, HEADERS_OC_DET, {"IdOC": ido, "CodigoProducto": limpiar_codigo(i["codigo"]), "Producto": i.get("producto", ""),
                                               "Cantidad": num(i["cantidad"]), "CostoUnitario": num(i.get("costo")), "CantidadRecibida": 0})
        return ido

    def ordenes(self):
        return self.datos.df("ordenes_compra")

    def detalle(self, id_oc):
        df = self.datos.df("ordenes_compra_det")
        if df.empty:
            return df
        d = df[df["IdOC"].astype(str) == str(id_oc)].copy()
        d["Cantidad"] = d["Cantidad"].map(num)
        d["CantidadRecibida"] = d["CantidadRecibida"].map(num)
        d["Pendiente"] = (d["Cantidad"] - d["CantidadRecibida"]).clip(lower=0)
        return d

    def _oc(self, id_oc):
        r = buscar_filas(self.datos.t("ordenes_compra"), {"IdOC": id_oc})
        if not r:
            raise ValueError("Orden de compra no encontrada.")
        return r[-1][1]

    def cambiar_estado(self, id_oc, estado):
        oc = self._oc(id_oc)
        actual = str(oc["Estado"]).upper()
        validas = {"BORRADOR": {"ENVIADA", "ANULADA"}, "ENVIADA": {"ANULADA"}}
        if estado not in validas.get(actual, set()):
            raise ValueError(f"No se puede pasar de {actual} a {estado}.")
        if estado == "ANULADA" and self.detalle(id_oc)["CantidadRecibida"].sum() > 0:
            raise ValueError("La orden ya tiene mercadería recibida: no se puede anular.")
        actualizar_donde(self.datos.t("ordenes_compra"), {"IdOC": id_oc}, {"Estado": estado})

    def recibir(self, usuario, id_oc, recepciones, lotes=None, permitir_exceso=False):
        """recepciones: {CodigoProducto: cantidad que llega ahora}. lotes: {CodigoProducto: (lote, vence)}.
        Cada recepción genera una ENTRADA en el kardex con Referencia = IdOC."""
        oc = self._oc(id_oc)
        if str(oc["Estado"]).upper() not in ("ENVIADA", "RECIBIDA_PARCIAL"):
            raise ValueError("Solo se puede recibir una orden ENVIADA o parcialmente recibida.")
        det = self.detalle(id_oc)
        pendientes = {str(r["CodigoProducto"]): r for _, r in det.iterrows()}
        for cod, cant in recepciones.items():           # validar todo ANTES de mover stock
            if num(cant) <= 0:
                continue
            if str(cod) not in pendientes:
                raise ValueError(f"El producto {cod} no está en la orden.")
            if num(cant) > pendientes[str(cod)]["Pendiente"] + 1e-9 and not permitir_exceso:
                raise ValueError(f"{pendientes[str(cod)]['Producto']}: llegan {num(cant):g} y solo faltan {pendientes[str(cod)]['Pendiente']:g}.")
        recibidos = 0
        for cod, cant in recepciones.items():
            if num(cant) <= 0:
                continue
            fila = pendientes[str(cod)]
            lote, vence = (lotes or {}).get(str(cod), ("", ""))
            self.kardex.registrar(usuario, "ENTRADA", cod, oc["Sucursal"], cant, costo=fila["CostoUnitario"], lote=lote, vence=vence,
                                  referencia=id_oc, motivo=f"Recepción OC {id_oc}")
            actualizar_donde(self.datos.t("ordenes_compra_det"), {"IdOC": id_oc, "CodigoProducto": cod},
                             {"CantidadRecibida": fila["CantidadRecibida"] + num(cant)})
            recibidos += 1
        if not recibidos:
            raise ValueError("No indicaste ninguna cantidad recibida.")
        completo = (self.detalle(id_oc)["Pendiente"] <= 1e-9).all()
        actualizar_donde(self.datos.t("ordenes_compra"), {"IdOC": id_oc},
                         {"Estado": "RECIBIDA" if completo else "RECIBIDA_PARCIAL", "FechaRecepcion": self.ahora().strftime("%Y-%m-%d")})
        return "RECIBIDA" if completo else "RECIBIDA_PARCIAL"

    # ---------- sugerencias ----------
    @staticmethod
    def sugerir_reposicion(inv, factor=2.0):
        """Productos bajo su stock mínimo. Sugerido = (mínimo × factor) − stock."""
        cols = ["CodigoProducto", "Producto", "Sucursal", "StockSistema", "StockMinimo", "Sugerido", "CostoUnitario"]
        if inv is None or inv.empty or "StockMinimo" not in inv.columns:
            return pd.DataFrame(columns=cols)
        d = inv.copy()
        d["StockSistema"] = d["StockSistema"].map(num)
        d["StockMinimo"] = d["StockMinimo"].map(num)
        d = d[(d["StockMinimo"] > 0) & (d["StockSistema"] <= d["StockMinimo"])].copy()
        d["Sugerido"] = (d["StockMinimo"] * factor - d["StockSistema"]).clip(lower=1).round(0)
        d["CostoUnitario"] = d["CostoUnitario"].map(num)
        return d[cols].sort_values("StockSistema").reset_index(drop=True)

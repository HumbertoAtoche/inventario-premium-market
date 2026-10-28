"""Ajustes de stock tras un conteo, con flujo de aprobación.

Un conteo detecta diferencias; un ajuste las lleva al stock del sistema. Para que nadie
"arregle" faltantes sin control, el ajuste se PROPONE, un responsable lo APRUEBA y recién
entonces se aplica como movimiento en el kardex.
"""
from .backend import buscar_filas, actualizar_donde, agregar_dict
from .esquemas import HEADERS_AJUSTES
from .util import num, limpiar_codigo, nuevo_id, misma


class Ajustes:
    def __init__(self, datos, kardex, ahora):
        self.datos, self.kardex, self.ahora = datos, kardex, ahora

    def proponer(self, usuario, id_sesion, df_diferencias, auto_aplicar=False):
        """df_diferencias: columnas CodigoProducto, CodigoBarras, Producto, Sucursal, StockSistema, StockFisico, CostoUnitario.
        Omite lo que ya fue propuesto para esa sesión. Devuelve (creados, omitidos)."""
        t = self.datos.t("ajustes")
        existentes = {(str(r["IdSesion"]), limpiar_codigo(r["CodigoProducto"]) or limpiar_codigo(r["CodigoBarras"]), str(r["Sucursal"]).casefold())
                      for _, r in self.datos.df("ajustes").iterrows() if str(r["Estado"]).upper() != "RECHAZADO"}
        creados, omitidos = [], 0
        for _, r in df_diferencias.iterrows():
            dif = num(r["StockFisico"]) - num(r["StockSistema"])
            if abs(dif) < 1e-9:
                continue
            clave = (str(id_sesion), limpiar_codigo(r.get("CodigoProducto", "")) or limpiar_codigo(r.get("CodigoBarras", "")), str(r["Sucursal"]).casefold())
            if clave in existentes:
                omitidos += 1
                continue
            ida = nuevo_id("AJU", self.ahora())
            agregar_dict(t, HEADERS_AJUSTES, {
                "IdAjuste": ida, "IdSesion": id_sesion, "FechaHora": self.ahora().strftime("%Y-%m-%d %H:%M:%S"),
                "CodigoProducto": limpiar_codigo(r.get("CodigoProducto", "")), "CodigoBarras": limpiar_codigo(r.get("CodigoBarras", "")),
                "Producto": r.get("Producto", ""), "Sucursal": r["Sucursal"], "StockSistema": num(r["StockSistema"]),
                "StockFisico": num(r["StockFisico"]), "Diferencia": dif, "CostoUnitario": num(r.get("CostoUnitario")),
                "Impacto": round(dif * num(r.get("CostoUnitario")), 2), "Estado": "PENDIENTE", "SolicitadoPor": usuario,
                "ResueltoPor": "", "FechaResolucion": "", "Comentario": ""})
            creados.append(ida)
        if auto_aplicar:
            for ida in creados:
                self.resolver(usuario, ida, True, "Aplicación automática (la empresa no exige aprobación)", permitir_propio=True)
        return creados, omitidos

    def lista(self, estado=None):
        df = self.datos.df("ajustes")
        if estado and not df.empty:
            df = df[df["Estado"].astype(str).str.upper() == estado]
        return df

    def resolver(self, usuario, id_ajuste, aprobar, comentario="", permitir_propio=False):
        r = buscar_filas(self.datos.t("ajustes"), {"IdAjuste": id_ajuste})
        if not r:
            raise ValueError("Ajuste no encontrado.")
        reg = r[-1][1]
        if str(reg["Estado"]).upper() != "PENDIENTE":
            raise ValueError("Este ajuste ya fue resuelto.")
        if aprobar and misma(reg["SolicitadoPor"], usuario) and not permitir_propio:
            raise ValueError("Otra persona con permiso debe aprobar un ajuste que tú propusiste.")
        estado = "RECHAZADO"
        if aprobar:
            dif = num(reg["Diferencia"])
            self.kardex.registrar(usuario, "AJUSTE_POSITIVO" if dif > 0 else "AJUSTE_NEGATIVO", reg["CodigoProducto"] or reg["CodigoBarras"],
                                  reg["Sucursal"], abs(dif), costo=reg["CostoUnitario"], referencia=id_ajuste,
                                  motivo=f"Ajuste por conteo {reg['IdSesion']}")
            estado = "APLICADO"
        actualizar_donde(self.datos.t("ajustes"), {"IdAjuste": id_ajuste},
                         {"Estado": estado, "ResueltoPor": usuario, "FechaResolucion": self.ahora().strftime("%Y-%m-%d %H:%M:%S"), "Comentario": comentario})
        return estado

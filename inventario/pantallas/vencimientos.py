"""Lotes y vencimientos (FEFO)."""
import streamlit as st
from inventario.contexto import cfg, datos, kardex, moneda_fmt, permiso
from inventario.nucleo import lotes as lotes_mod, permisos, tiempo
from inventario.nucleo.util import num
from inventario.servicios import actualizar_datos, cargar_inventario, registrar_auditoria
from inventario.ui.componentes import header, kpi, ui_callout, ui_seccion
from inventario.utilidades import formato_soles, mostrar_error_google


def pantalla_vencimientos():
    header("Vencimientos", "Lotes por vencer y vencidos · FEFO: primero en vencer, primero en salir")
    c = cfg()
    dias = sorted(int(d) for d in (c.dias_alerta_vencimiento or [30, 60]))[:2] or [30, 60]
    try:
        df = permisos.filtrar_sucursales(datos().df("lotes"), st.session_state.get("usuario"))
        inv = cargar_inventario()
    except Exception as exc:
        mostrar_error_google(exc, "los lotes")
        return
    al = lotes_mod.alertas(df, tiempo.ahora().date(), tuple(dias))
    if al.empty:
        ui_callout("Todavía no hay lotes con saldo y fecha de vencimiento. Se crean al registrar una ENTRADA con lote y vencimiento (en Movimientos o al recibir una orden de compra).")
        return
    nombre = {(str(r["CodigoProducto"]), str(r["Sucursal"]).casefold()): (r["Producto"], num(r["CostoUnitario"])) for _, r in inv.iterrows()} if not inv.empty else {}
    al["Producto"] = [nombre.get((str(r.CodigoProducto), str(r.Sucursal).casefold()), ("(no está en el inventario)", 0))[0] for r in al.itertuples()]
    al["Valor"] = [num(r.Cantidad) * nombre.get((str(r.CodigoProducto), str(r.Sucursal).casefold()), ("", 0))[1] for r in al.itertuples()]
    venc = al[al["Estado"] == "VENCIDO"]
    prox = al[al["Estado"] == f"≤{dias[0]} días"]
    a, b, c_, d = st.columns(4)
    with a: kpi("Vencidos", f"{len(venc)}", f"{venc['Cantidad'].sum():g} unidades · {formato_soles(venc['Valor'].sum())}")
    with b: kpi(f"Vencen en ≤{dias[0]} días", f"{len(prox)}", f"{prox['Cantidad'].sum():g} unidades · {formato_soles(prox['Valor'].sum())}")
    with c_: kpi(f"Vencen en ≤{dias[1]} días", f"{(al['Estado'] == f'≤{dias[1]} días').sum()}")
    with d: kpi("Lotes con saldo", f"{len(al)}")
    f1, f2 = st.columns(2)
    with f1: est = st.selectbox("Estado", ["Todos", "VENCIDO", f"≤{dias[0]} días", f"≤{dias[1]} días", "OK"], key="ven_est")
    with f2: suc = st.selectbox("Sucursal", ["Todas"] + sorted(al["Sucursal"].astype(str).unique()), key="ven_suc")
    vista = al[(al["Estado"] == est) | (est == "Todos")]
    vista = vista[(vista["Sucursal"].astype(str) == suc) | (suc == "Todas")]
    st.dataframe(vista[["Producto", "Sucursal", "Lote", "FechaVencimiento", "DiasParaVencer", "Cantidad", "Valor", "Estado"]], use_container_width=True, hide_index=True,
                 column_config={"Valor": st.column_config.NumberColumn(format=moneda_fmt()), "DiasParaVencer": "Días"})
    if len(venc) and permiso("movimientos_registrar"):
        ui_seccion("Dar de baja lo vencido", "Genera una MERMA por cada lote vencido y lo descuenta del stock")
        ok = st.checkbox(f"Confirmo dar de baja {len(venc)} lotes vencidos ({venc['Cantidad'].sum():g} unidades)", key="ven_conf")
        if st.button("Dar de baja lotes vencidos", disabled=not ok, key="ven_baja"):
            k, hechos, fallos = kardex(), 0, []
            for r in venc.itertuples():
                try:
                    k.registrar(str(st.session_state.usuario.get("Usuario", "")), "MERMA", r.CodigoProducto, r.Sucursal, r.Cantidad, lote=r.Lote,
                                motivo=f"Vencimiento del lote {r.Lote} ({r.FechaVencimiento})")
                    hechos += 1
                except Exception as exc:
                    fallos.append(f"{r.Producto} · lote {r.Lote}: {exc}")
            registrar_auditoria("BAJA_VENCIDOS", f"{hechos} lotes dados de baja")
            actualizar_datos()
            st.success(f"{hechos} lotes dados de baja.")
            for f in fallos:
                st.warning(f)

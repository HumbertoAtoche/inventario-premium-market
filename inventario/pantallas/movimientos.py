"""Movimientos de inventario (kardex) y ajustes con aprobación."""
import pandas as pd
import streamlit as st
from inventario.contexto import ajustes, cfg, kardex, moneda_fmt, permiso
from inventario.nucleo import permisos, tiempo
from inventario.nucleo.kardex import ETIQUETAS, MANUALES
from inventario.nucleo.util import num
from inventario.servicios import actualizar_datos, buscar_productos, cargar_conteos, cargar_inventario, cargar_sesiones, conteos_vigentes, registrar_auditoria
from inventario.ui.componentes import header, kpi, ui_callout, ui_seccion
from inventario.utilidades import exportar_excel, limpiar_numero, mostrar_error_google, safe_text


def _usuario():
    return str(st.session_state.get("usuario", {}).get("Usuario", ""))


def _sucursales_visibles(inv):
    s = sorted({str(x).strip() for x in inv["Sucursal"] if str(x).strip()}) if not inv.empty else []
    return s or list(cfg().sucursales)


def _elegir_producto(prefijo, sucursal=None):
    """Buscador (código, código de barras o nombre) + lista de resultados. Devuelve el producto elegido o None."""
    inv = cargar_inventario()
    if sucursal and not inv.empty:
        inv = inv[inv["Sucursal"].astype(str).str.casefold() == str(sucursal).casefold()]
    txt = st.text_input("Buscar producto (código, código de barras o nombre)", key=f"{prefijo}_q")
    if not txt.strip():
        st.caption("Escribe o escanea un código para buscar.")
        return None
    res = buscar_productos(txt, inv)
    if res.empty:
        st.warning("No encontré productos con ese dato en esta sucursal.")
        return None
    etiqueta = lambda i: f"{res.loc[i, 'Producto']} · {res.loc[i, 'CodigoProducto'] or res.loc[i, 'CodigoBarras']} · stock {limpiar_numero(res.loc[i, 'StockSistema']):g}"
    i = st.selectbox("Producto", list(res.index), format_func=etiqueta, key=f"{prefijo}_sel")
    return res.loc[i].to_dict()


def _tab_registrar(k):
    c = cfg()
    if not permiso("movimientos_registrar"):
        ui_callout("Tu rol puede consultar movimientos, pero no registrarlos.")
        return
    inv = cargar_inventario()
    sucs = _sucursales_visibles(inv)
    tipos = list(MANUALES) + (["TRANSFERENCIA"] if len(sucs) > 1 else [])
    tipo = st.radio("Tipo de movimiento", tipos, format_func=lambda t: ETIQUETAS.get(t, "Transferencia entre sucursales"), key="mov_tipo")
    origen = destino = suc = None
    if tipo == "TRANSFERENCIA":
        a, b = st.columns(2)
        with a: origen = st.selectbox("Origen", sucs, key="mov_origen")
        with b: destino = st.selectbox("Destino", [s for s in sucs if s != origen], key="mov_destino")
        prod = _elegir_producto("mov", origen)
    else:
        suc = st.selectbox("Sucursal", sucs, key="mov_suc")
        prod = _elegir_producto("mov", suc)
    if not prod:
        return
    st.markdown(f'<div class="product-card"><div class="product-name">{safe_text(prod["Producto"])}</div>'
                f'<div class="product-meta">{safe_text(prod["CodigoProducto"] or prod["CodigoBarras"])} · Stock actual <b>{limpiar_numero(prod["StockSistema"]):g}</b> {safe_text(prod["Unidad"])}</div></div>',
                unsafe_allow_html=True)
    lotes_on = c.modulo("lotes")
    with st.form("mov_form", clear_on_submit=True):
        f1, f2 = st.columns(2)
        with f1:
            cantidad = st.number_input("Cantidad", min_value=0.0, value=1.0, step=1.0, format="%g")
        with f2:
            costo = st.number_input("Costo unitario", min_value=0.0, value=float(limpiar_numero(prod["CostoUnitario"])), step=0.1, disabled=tipo == "TRANSFERENCIA")
        lote = vence = ""
        if lotes_on and tipo != "TRANSFERENCIA":
            l1, l2 = st.columns(2)
            ingreso = tipo in ("ENTRADA", "DEVOLUCION_CLIENTE")
            with l1: lote = st.text_input("Lote" + ("" if ingreso else " (vacío = el que vence primero)"))
            with l2: vence = st.text_input("Vencimiento (AAAA-MM-DD)", disabled=not ingreso)
        r1, r2 = st.columns(2)
        with r1: referencia = st.text_input("Referencia (factura, guía…)", disabled=tipo == "TRANSFERENCIA")
        with r2: motivo = st.text_input("Motivo" + (" (obligatorio)" if tipo in ("MERMA", "SALIDA") else ""))
        enviar = st.form_submit_button("Registrar movimiento", type="primary", use_container_width=True)
    if not enviar:
        return
    if tipo in ("MERMA", "SALIDA") and not motivo.strip():
        st.error("Indica el motivo: queda en la auditoría.")
        return
    codigo = prod["CodigoProducto"] or prod["CodigoBarras"]
    try:
        if tipo == "TRANSFERENCIA":
            k.transferir(_usuario(), codigo, origen, destino, cantidad, motivo)
            msg = f"Transferidas {cantidad:g} unidades de {origen} a {destino}."
        else:
            r = k.registrar(_usuario(), tipo, codigo, suc, cantidad, costo=costo, lote=lote, vence=vence, referencia=referencia, motivo=motivo)
            msg = f"{ETIQUETAS[tipo].split(' (')[0]} registrada. Stock: {r['stock_antes']:g} → {r['stock_despues']:g}."
        registrar_auditoria("MOVIMIENTO", f"{tipo} {cantidad:g} · {prod['Producto']}")
        actualizar_datos()
        st.success(msg)
    except ValueError as exc:
        st.error(str(exc))
    except Exception as exc:
        mostrar_error_google(exc, "el registro del movimiento")


def _tab_kardex(k):
    sucs = _sucursales_visibles(cargar_inventario())
    suc = st.selectbox("Sucursal", sucs, key="kdx_suc")
    prod = _elegir_producto("kdx", suc)
    if not prod:
        return
    h = k.kardex_producto(prod["CodigoProducto"] or prod["CodigoBarras"], suc)
    if h.empty:
        ui_callout("Este producto todavía no tiene movimientos registrados.")
        return
    cant = h["Cantidad"].map(num)
    a, b, c_ = st.columns(3)
    with a: kpi("Entradas", f"{cant[cant > 0].sum():g}", "unidades")
    with b: kpi("Salidas", f"{-cant[cant < 0].sum():g}", "unidades")
    with c_: kpi("Stock actual", f"{limpiar_numero(prod['StockSistema']):g}", "según el sistema")
    vista = h[["FechaHora", "Tipo", "Cantidad", "Lote", "Referencia", "Motivo", "Usuario", "StockDespues"]].rename(columns={"FechaHora": "Fecha", "StockDespues": "Saldo"})
    st.dataframe(vista, use_container_width=True, hide_index=True)


def _tab_historial(k):
    inv = cargar_inventario()
    f1, f2, f3, f4 = st.columns(4)
    with f1: suc = st.selectbox("Sucursal", ["Todas"] + _sucursales_visibles(inv), key="his_suc")
    with f2: tipo = st.selectbox("Tipo", ["Todos"] + list(ETIQUETAS) + ["TRANSFERENCIA_ENTRADA", "TRANSFERENCIA_SALIDA", "AJUSTE_POSITIVO", "AJUSTE_NEGATIVO"], key="his_tipo")
    hoy = tiempo.ahora().date()
    with f3: desde = st.date_input("Desde", value=hoy - pd.Timedelta(days=30), key="his_desde")
    with f4: hasta = st.date_input("Hasta", value=hoy, key="his_hasta")
    texto = st.text_input("Texto (producto, referencia, motivo)", key="his_txt")
    h = k.historial(suc, tipo, desde, hasta, texto)
    permitidas = permisos.sucursales_usuario(st.session_state.get("usuario"))
    if permitidas is not None:
        h = permisos.filtrar_sucursales(h, st.session_state.get("usuario"))
    st.caption(f"{len(h):,} movimientos")
    if h.empty:
        return
    st.dataframe(h.drop(columns=["IdMov"]).head(500), use_container_width=True, hide_index=True)
    st.download_button("Descargar en Excel", exportar_excel({"Movimientos": h}), file_name=f"movimientos_{tiempo.hoy_str()}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="his_xlsx")


def _tab_ajustes(k):
    c = cfg()
    aj = ajustes()
    usuario = st.session_state.usuario
    ui_seccion("Proponer ajustes desde un conteo", "Las diferencias detectadas se convierten en ajustes pendientes de aprobación" if c.ajustes_requieren_aprobacion else "Se aplicarán de inmediato")
    sesiones = cargar_sesiones()
    if sesiones.empty:
        ui_callout("Aún no hay sesiones de inventario.")
    elif permiso("ajustes_aprobar") or permiso("movimientos_registrar"):
        etiqueta = {r["IdSesion"]: f"{r['NombreSesion']} · {r['Estado']} · {r['FechaInicio']}" for _, r in sesiones.iterrows()}
        ids = list(etiqueta)
        sel = st.selectbox("Sesión de inventario", ids[::-1], format_func=etiqueta.get, key="aj_sesion")
        dc = conteos_vigentes(cargar_conteos().query("IdSesion == @sel"))
        if dc is None or dc.empty:
            ui_callout("Esta sesión no tiene conteos.")
        else:
            dif = dc.copy()
            dif["StockSistema"] = dif["StockSistema"].map(limpiar_numero)
            dif["StockFisico"] = dif["StockFisico"].map(limpiar_numero)
            dif = dif[(dif["StockFisico"] - dif["StockSistema"]).abs() > 1e-9]
            st.caption(f"{len(dif)} productos con diferencia en esta sesión.")
            if len(dif) and st.button(f"Proponer {len(dif)} ajustes", key="aj_proponer"):
                try:
                    creados, omitidos = aj.proponer(_usuario(), sel, dif, auto_aplicar=not c.ajustes_requieren_aprobacion)
                    registrar_auditoria("AJUSTES_PROPUESTOS", f"{len(creados)} ajustes de la sesión {sel}", sel)
                    actualizar_datos()
                    st.success(f"{len(creados)} ajustes creados" + (f" ({omitidos} ya estaban propuestos)." if omitidos else "."))
                except Exception as exc:
                    mostrar_error_google(exc, "la creación de ajustes")
    ui_seccion("Ajustes pendientes")
    pend = aj.lista("PENDIENTE")
    if pend.empty:
        ui_callout("No hay ajustes pendientes.", "ok")
    else:
        st.dataframe(pend[["IdAjuste", "Producto", "Sucursal", "StockSistema", "StockFisico", "Diferencia", "Impacto", "SolicitadoPor"]], use_container_width=True, hide_index=True,
                     column_config={"Impacto": st.column_config.NumberColumn(format=moneda_fmt())})
        if permiso("ajustes_aprobar"):
            ida = st.selectbox("Ajuste a resolver", list(pend["IdAjuste"]), format_func=lambda i: f"{pend.set_index('IdAjuste').loc[i, 'Producto']} · {pend.set_index('IdAjuste').loc[i, 'Diferencia']}", key="aj_sel")
            comentario = st.text_input("Comentario (opcional)", key="aj_com")
            b1, b2 = st.columns(2)
            for col, aprobar, etiq in ((b1, True, "Aprobar y aplicar"), (b2, False, "Rechazar")):
                with col:
                    if st.button(etiq, key=f"aj_{'ok' if aprobar else 'no'}", type="primary" if aprobar else "secondary", use_container_width=True):
                        try:
                            estado = aj.resolver(_usuario(), ida, aprobar, comentario, permitir_propio=permisos.rol_de(usuario) == "ADMIN")
                            registrar_auditoria("AJUSTE_" + estado, ida)
                            actualizar_datos()
                            st.success(f"Ajuste {estado.lower()}.")
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
                        except Exception as exc:
                            mostrar_error_google(exc, "la resolución del ajuste")
        else:
            ui_callout("Un supervisor o administrador debe aprobar estos ajustes.")
    with st.expander("Ajustes resueltos"):
        res = aj.lista()
        res = res[res["Estado"].astype(str).str.upper() != "PENDIENTE"] if not res.empty else res
        st.dataframe(res.tail(100), use_container_width=True, hide_index=True)


def pantalla_movimientos():
    header("Movimientos", "Entradas, salidas, mermas, transferencias y ajustes con historial completo")
    k = kardex()
    try:
        mov = k.historial()
        hoy = tiempo.hoy_str()
        hoy_df = mov[mov["FechaHora"].astype(str).str.startswith(hoy)] if not mov.empty else mov
        cant = hoy_df["Cantidad"].map(num) if not hoy_df.empty else pd.Series(dtype=float)
        pend = len(ajustes().lista("PENDIENTE"))
    except Exception as exc:
        mostrar_error_google(exc, "los movimientos")
        return
    a, b, c_, d = st.columns(4)
    with a: kpi("Movimientos hoy", f"{len(hoy_df):,}")
    with b: kpi("Entradas hoy", f"{cant[cant > 0].sum():g}", "unidades")
    with c_: kpi("Salidas hoy", f"{-cant[cant < 0].sum():g}", "unidades")
    with d: kpi("Ajustes pendientes", f"{pend}", "esperan aprobación" if pend else "al día")
    t1, t2, t3, t4 = st.tabs(["Registrar", "Kardex por producto", "Historial", "Ajustes"])
    with t1: _tab_registrar(k)
    with t2: _tab_kardex(k)
    with t3: _tab_historial(k)
    with t4: _tab_ajustes(k)

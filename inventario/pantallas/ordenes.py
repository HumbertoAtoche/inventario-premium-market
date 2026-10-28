"""Proveedores y órdenes de compra con recepción (total o parcial) que actualiza el stock."""
import pandas as pd
import streamlit as st
from inventario.contexto import cfg, compras, moneda_fmt, permiso
from inventario.nucleo import permisos
from inventario.nucleo.compras import Compras
from inventario.nucleo.util import num
from inventario.servicios import actualizar_datos, buscar_productos, cargar_inventario, registrar_auditoria
from inventario.ui.componentes import header, ui_callout, ui_seccion
from inventario.utilidades import formato_soles, limpiar_numero, mostrar_error_google, safe_text


def _usuario():
    return str(st.session_state.get("usuario", {}).get("Usuario", ""))


def _tab_ordenes(co):
    oc = co.ordenes()
    if oc.empty:
        ui_callout("Aún no hay órdenes de compra. Crea la primera en la pestaña «Nueva orden».")
        return
    oc = permisos.filtrar_sucursales(oc, st.session_state.get("usuario"))
    estados = ["Todos"] + sorted(oc["Estado"].astype(str).unique())
    est = st.selectbox("Estado", estados, key="oc_f_est")
    vista = oc if est == "Todos" else oc[oc["Estado"].astype(str) == est]
    st.dataframe(vista.sort_values("Fecha", ascending=False), use_container_width=True, hide_index=True,
                 column_config={"Total": st.column_config.NumberColumn(format=moneda_fmt())})
    if vista.empty:
        return
    ido = st.selectbox("Ver detalle de la orden", list(vista["IdOC"]), key="oc_det")
    det = co.detalle(ido)
    st.dataframe(det[["CodigoProducto", "Producto", "Cantidad", "CostoUnitario", "CantidadRecibida", "Pendiente"]], use_container_width=True, hide_index=True)
    estado = str(vista.set_index("IdOC").loc[ido, "Estado"]).upper()
    if permiso("compras"):
        a, b = st.columns(2)
        with a:
            if estado == "BORRADOR" and st.button("Marcar como ENVIADA", key="oc_env", type="primary", use_container_width=True):
                try:
                    co.cambiar_estado(ido, "ENVIADA"); registrar_auditoria("OC_ENVIADA", ido); st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        with b:
            if estado in ("BORRADOR", "ENVIADA") and st.button("Anular orden", key="oc_anu", use_container_width=True):
                try:
                    co.cambiar_estado(ido, "ANULADA"); registrar_auditoria("OC_ANULADA", ido); st.rerun()
                except ValueError as exc:
                    st.error(str(exc))


def _tab_nueva(co):
    if not permiso("compras"):
        ui_callout("Tu rol no puede crear órdenes de compra.")
        return
    prov = co.proveedores()
    if prov.empty:
        ui_callout("Primero registra un proveedor en la pestaña «Proveedores».", "warn")
        return
    inv = cargar_inventario()
    sucs = sorted({str(s) for s in inv["Sucursal"] if str(s).strip()}) or list(cfg().sucursales)
    a, b = st.columns(2)
    with a: idp = st.selectbox("Proveedor", list(prov["IdProveedor"]), format_func=lambda i: prov.set_index("IdProveedor").loc[i, "Nombre"], key="oc_prov")
    with b: suc = st.selectbox("Sucursal de destino", sucs, key="oc_suc")
    items = st.session_state.setdefault("oc_items", [])
    ui_seccion("Productos de la orden")
    sug = Compras.sugerir_reposicion(inv[inv["Sucursal"].astype(str) == suc]) if not inv.empty else pd.DataFrame()
    if len(sug) and st.button(f"Cargar {len(sug)} productos bajo su stock mínimo", key="oc_sug"):
        st.session_state["oc_items"] = [{"codigo": r.CodigoProducto, "producto": r.Producto, "cantidad": float(r.Sugerido), "costo": float(r.CostoUnitario)} for r in sug.itertuples()]
        st.rerun()
    q = st.text_input("Buscar producto para agregar", key="oc_q")
    if q.strip():
        res = buscar_productos(q, inv[inv["Sucursal"].astype(str) == suc])
        if res.empty:
            st.caption("Sin coincidencias.")
        else:
            i = st.selectbox("Producto", list(res.index), format_func=lambda i: f"{res.loc[i, 'Producto']} · {res.loc[i, 'CodigoProducto'] or res.loc[i, 'CodigoBarras']}", key="oc_sel")
            c1, c2, c3 = st.columns([1, 1, 1])
            with c1: cant = st.number_input("Cantidad", min_value=0.0, value=1.0, step=1.0, format="%g", key="oc_cant")
            with c2: costo = st.number_input("Costo unitario", min_value=0.0, value=float(limpiar_numero(res.loc[i, "CostoUnitario"])), step=0.1, key="oc_costo")
            with c3:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("Agregar a la orden", key="oc_add", use_container_width=True):
                    st.session_state["oc_items"].append({"codigo": res.loc[i, "CodigoProducto"] or res.loc[i, "CodigoBarras"], "producto": res.loc[i, "Producto"], "cantidad": cant, "costo": costo})
                    st.rerun()
    if not items:
        ui_callout("La orden está vacía. Busca productos arriba o carga los que están bajo su stock mínimo.")
        return
    tabla_items = pd.DataFrame(items)
    editado = st.data_editor(tabla_items.rename(columns={"codigo": "Código", "producto": "Producto", "cantidad": "Cantidad", "costo": "Costo"}), hide_index=True,
                             use_container_width=True, disabled=["Código", "Producto"], num_rows="dynamic", key="oc_editor")
    items_ok = [{"codigo": r["Código"], "producto": r["Producto"], "cantidad": r["Cantidad"], "costo": r["Costo"]} for r in editado.to_dict("records") if r.get("Código")]
    total = sum(num(i["cantidad"]) * num(i["costo"]) for i in items_ok)
    st.markdown(f"**Total estimado: {formato_soles(total)}** · {len(items_ok)} productos")
    obs = st.text_input("Observación", key="oc_obs")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("Crear orden (borrador)", type="primary", use_container_width=True, key="oc_crear"):
            try:
                ido = co.crear_oc(_usuario(), idp, suc, items_ok, obs)
                registrar_auditoria("OC_CREADA", f"{ido} · {len(items_ok)} productos · {formato_soles(total)}")
                st.session_state["oc_items"] = []
                st.success(f"Orden {ido} creada como BORRADOR.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                mostrar_error_google(exc, "la orden de compra")
    with b2:
        if st.button("Vaciar", use_container_width=True, key="oc_vaciar"):
            st.session_state["oc_items"] = []
            st.rerun()


def _tab_recepcion(co):
    if not permiso("movimientos_registrar") and not permiso("compras"):
        ui_callout("Tu rol no puede registrar recepciones.")
        return
    oc = co.ordenes()
    abiertas = oc[oc["Estado"].astype(str).isin(["ENVIADA", "RECIBIDA_PARCIAL"])] if not oc.empty else oc
    abiertas = permisos.filtrar_sucursales(abiertas, st.session_state.get("usuario"))
    if abiertas.empty:
        ui_callout("No hay órdenes esperando mercadería. Marca una orden como ENVIADA para poder recibirla.")
        return
    ido = st.selectbox("Orden a recibir", list(abiertas["IdOC"]), format_func=lambda i: f"{i} · {abiertas.set_index('IdOC').loc[i, 'Proveedor']} · {abiertas.set_index('IdOC').loc[i, 'Estado']}", key="rec_oc")
    det = co.detalle(ido)
    det = det[det["Pendiente"] > 0]
    lotes_on = cfg().modulo("lotes")
    with st.form(f"rec_form_{ido}"):
        recibido, lotes = {}, {}
        for r in det.itertuples():
            c1, c2, c3 = st.columns([3, 1.3, 2]) if lotes_on else (*st.columns([3, 1.3]), None)
            with c1: st.markdown(f"**{safe_text(r.Producto)}** · pendiente {r.Pendiente:g} de {r.Cantidad:g}")
            with c2: recibido[str(r.CodigoProducto)] = st.number_input("Llega ahora", min_value=0.0, max_value=float(r.Pendiente), value=float(r.Pendiente), step=1.0, format="%g", key=f"rec_{ido}_{r.CodigoProducto}")
            if lotes_on and c3 is not None:
                with c3:
                    l = st.text_input("Lote", key=f"rec_l_{ido}_{r.CodigoProducto}", label_visibility="collapsed", placeholder="Lote")
                    v = st.text_input("Vence", key=f"rec_v_{ido}_{r.CodigoProducto}", label_visibility="collapsed", placeholder="AAAA-MM-DD")
                    lotes[str(r.CodigoProducto)] = (l, v)
        enviar = st.form_submit_button("Registrar recepción", type="primary", use_container_width=True)
    if enviar:
        try:
            estado = co.recibir(_usuario(), ido, recibido, lotes)
            registrar_auditoria("OC_RECEPCION", f"{ido} → {estado}")
            actualizar_datos()
            st.success(f"Recepción registrada. La orden quedó {estado}. El stock ya se actualizó.")
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            mostrar_error_google(exc, "la recepción")


def _tab_proveedores(co):
    if permiso("compras"):
        with st.form("prov_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1: nombre = st.text_input("Nombre del proveedor")
            with c2: idf = st.text_input(f"{cfg().id_fiscal_etiqueta}")
            with c3: plazo = st.number_input("Plazo de entrega (días)", min_value=0, value=3)
            c4, c5, c6 = st.columns(3)
            with c4: contacto = st.text_input("Contacto")
            with c5: tel = st.text_input("Teléfono")
            with c6: mail = st.text_input("Correo")
            if st.form_submit_button("Agregar proveedor", type="primary"):
                try:
                    co.crear_proveedor(nombre, idf, contacto, tel, mail, plazo)
                    registrar_auditoria("PROVEEDOR_CREADO", nombre)
                    st.success("Proveedor agregado.")
                except ValueError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    mostrar_error_google(exc, "el proveedor")
    df = co.proveedores(solo_activos=False)
    if df.empty:
        ui_callout("Aún no hay proveedores.")
        return
    st.dataframe(df.drop(columns=["IdProveedor"]), use_container_width=True, hide_index=True)
    if permiso("compras"):
        idp = st.selectbox("Activar / desactivar", list(df["IdProveedor"]), format_func=lambda i: f"{df.set_index('IdProveedor').loc[i, 'Nombre']} ({df.set_index('IdProveedor').loc[i, 'Estado']})", key="prov_est")
        actual = str(df.set_index("IdProveedor").loc[idp, "Estado"]).upper()
        if st.button("Desactivar" if actual == "ACTIVO" else "Activar", key="prov_btn"):
            co.cambiar_estado_proveedor(idp, "INACTIVO" if actual == "ACTIVO" else "ACTIVO")
            st.rerun()


def pantalla_ordenes():
    header("Órdenes de Compra", "Proveedores, órdenes y recepción de mercadería")
    co = compras()
    try:
        t1, t2, t3, t4 = st.tabs(["Órdenes", "Nueva orden", "Recepción", "Proveedores"])
        with t1: _tab_ordenes(co)
        with t2: _tab_nueva(co)
        with t3: _tab_recepcion(co)
        with t4: _tab_proveedores(co)
    except Exception as exc:
        mostrar_error_google(exc, "las órdenes de compra")

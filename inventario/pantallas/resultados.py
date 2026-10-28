"""Resultados y análisis de conteos."""
import pandas as pd
import re
import streamlit as st
from inventario.contexto import cfg, moneda_fmt
from inventario.nucleo import permisos
from inventario.nucleo.esquemas import HEADERS_CONTEO
from inventario.servicios import buscar_por_codigo, calcular_resumen, cargar_conteos, cargar_inventario, cargar_resumenes, cargar_sesiones, cargar_universo, clasificar_abc, clave_producto, conteos_vigentes, diagnosticar_inventario, es_diferencia_critica, estado_cobertura, generar_ajustes, lista_diferencias, metricas_cobertura, obtener_sesion_abierta, productividad_contadores, tendencia_sesiones
from inventario.ui.componentes import header, kpi, ui_seccion
from inventario.utilidades import exportar_excel, formato_soles


def pantalla_resultados():
    header("Resultados y dashboard ejecutivo", "Analiza exactitud, faltantes, sobrantes e impacto económico")
    sesiones = cargar_sesiones()
    conteos = cargar_conteos()

    if sesiones.empty:
        st.info("No existen sesiones registradas.")
        return

    opciones = sesiones.sort_values("FechaInicio", ascending=False)["IdSesion"].astype(str).tolist()
    seleccionado = st.selectbox("Seleccionar sesión", opciones, format_func=lambda x: (
        str(sesiones.loc[sesiones["IdSesion"].astype(str) == x, "NombreSesion"].iloc[0])
        if (sesiones["IdSesion"].astype(str) == x).any() else x
    ))

    resumen = calcular_resumen(seleccionado)
    dc_hist = conteos[conteos["IdSesion"].astype(str) == str(seleccionado)].copy() if not conteos.empty else pd.DataFrame()
    dc = conteos_vigentes(dc_hist)  # último conteo de cada producto (respeta reconteos)
    ajustes = generar_ajustes(dc)
    sesion_fila = sesiones[sesiones["IdSesion"].astype(str) == seleccionado].iloc[0]
    cobertura_det = estado_cobertura(seleccionado, sesion_fila["Sucursal"])
    m = metricas_cobertura(seleccionado, sesion_fila["Sucursal"])
    st.progress(m["cobertura"]/100 if m["total"] else 0, text=f"Cobertura {m['cobertura']:.1f}% · {m['pendientes']} pendientes · {m['ceros']} ceros verificados")
    st.caption(f"Exactitud de los productos verificados: {m['exactitud']:.1f}% · No localizados: {m['no_localizados']}")
    k1, k2, k3, k4 = st.columns(4)
    if resumen["ProductosContados"]:
        nota_exactitud = f"Meta {cfg().meta_exactitud:.0f}% · " + ("✅ cumple" if resumen["ExactitudInventario"] >= cfg().meta_exactitud else "⚠️ bajo la meta")
    else:
        nota_exactitud = f"Meta {cfg().meta_exactitud:.0f}%"
    with k1: kpi("Exactitud", f"{resumen['ExactitudInventario']:.1f}%", nota_exactitud)
    with k2: kpi("Faltantes", formato_soles(resumen["ValorFaltantes"]), f"{resumen['UnidadesFaltantes']:,.0f} unidades")
    with k3: kpi("Sobrantes", formato_soles(resumen["ValorSobrantes"]), f"{resumen['UnidadesSobrantes']:,.0f} unidades")
    with k4: kpi("Desfase neto", formato_soles(resumen["DesfaseNeto"]), "pérdida neta valorizada")

    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi("Contados", f"{resumen['ProductosContados']:,}", f"de {resumen['ProductosSistema']:,}")
    with c2: kpi("OK", f"{resumen['ProductosOK']:,}", "sin diferencia")
    with c3: kpi("Faltantes", f"{resumen['ProductosFaltantes']:,}", "productos")
    with c4: kpi("Sobrantes", f"{resumen['ProductosSobrantes']:,}", "productos")

    ui_seccion("Principales faltantes")
    if dc.empty:
        st.info("No hay conteos para esta sesión.")
    else:
        falt = dc[dc["TipoDiferencia"] == "FALTANTE"].copy().sort_values("ValorFaltante", ascending=False).head(10)
        if falt.empty:
            st.success("No existen faltantes en esta sesión.")
        else:
            fshow = falt[["Producto", "CodigoProducto", "StockSistema", "StockFisico", "Diferencia", "CostoUnitario", "ValorFaltante", "NombreUsuario"]].copy()
            fshow.columns = ["Producto", "Código", "Sistema", "Físico", "Dif.", "Costo", "Faltante", "Usuario"]
            st.dataframe(fshow, use_container_width=True, hide_index=True, column_config={
                "Costo": st.column_config.NumberColumn(format=moneda_fmt()),
                "Faltante": st.column_config.NumberColumn(format=moneda_fmt()),
            })

    ui_seccion("Principales sobrantes")
    if not dc.empty:
        sobr = dc[dc["TipoDiferencia"] == "SOBRANTE"].copy().sort_values("ValorSobrante", ascending=False).head(10)
        if sobr.empty:
            st.info("No existen sobrantes en esta sesión.")
        else:
            sshow = sobr[["Producto", "CodigoProducto", "StockSistema", "StockFisico", "Diferencia", "CostoUnitario", "ValorSobrante", "NombreUsuario"]].copy()
            sshow.columns = ["Producto", "Código", "Sistema", "Físico", "Dif.", "Costo", "Sobrante", "Usuario"]
            st.dataframe(sshow, use_container_width=True, hide_index=True, column_config={
                "Costo": st.column_config.NumberColumn(format=moneda_fmt()),
                "Sobrante": st.column_config.NumberColumn(format=moneda_fmt()),
            })

    if not dc.empty:
        ui_seccion("Valor de faltantes por categoría")
        por_categoria = (
            dc[dc["TipoDiferencia"] == "FALTANTE"]
            .groupby("Categoria")["ValorFaltante"]
            .sum()
            .sort_values(ascending=False)
        )
        if por_categoria.empty:
            st.info("No hay faltantes registrados por categoría en esta sesión.")
        else:
            st.bar_chart(por_categoria)

    if not dc.empty:
        ui_seccion("Diferencias significativas a revisar")
        criticos = dc[dc.apply(lambda r: es_diferencia_critica(r["StockSistema"], r["StockFisico"], r["CostoUnitario"]), axis=1)].copy()
        if criticos.empty:
            st.success("No hay diferencias significativas que requieran reconteo.")
        else:
            cshow = criticos[["Producto", "CodigoProducto", "StockSistema", "StockFisico", "Diferencia", "CostoDiferencia", "NombreUsuario"]].copy()
            cshow.columns = ["Producto", "Código", "Sistema", "Físico", "Dif.", "Impacto", "Usuario"]
            st.dataframe(cshow, use_container_width=True, hide_index=True, column_config={
                "Impacto": st.column_config.NumberColumn(format=moneda_fmt()),
            })
            sesion_abierta = obtener_sesion_abierta()
            if sesion_abierta and str(sesion_abierta["IdSesion"]) == str(seleccionado):
                idx_rec = st.selectbox(
                    "Producto a recontar",
                    list(criticos.index),
                    format_func=lambda i: f"{criticos.loc[i, 'Producto']} · {criticos.loc[i, 'CodigoProducto']} ({criticos.loc[i, 'Diferencia']:+,.0f})",
                )
                if st.button("🔁 Iniciar reconteo", use_container_width=True):
                    fila_rec = criticos.loc[idx_rec]
                    prod_rec = buscar_por_codigo(fila_rec["CodigoBarras"]) or buscar_por_codigo(fila_rec["CodigoProducto"])
                    if prod_rec:
                        st.session_state.producto_pendiente = prod_rec
                        st.session_state.codigo_pendiente = ""
                        st.session_state.reconteo_activo = True
                        st.session_state.modo_inventario = "scanner"
                        st.session_state.pagina = "Inventario"
                        st.rerun()
                    else:
                        st.error("No se encontró el producto en el inventario actual.")
            else:
                st.caption("El reconteo solo está disponible mientras la sesión esté abierta.")

    ui_seccion("Listas de faltantes y sobrantes (para tu sistema de ventas)")
    if dc.empty:
        st.info("No hay conteos para generar listas en esta sesión.")
    else:
        lista_falt = lista_diferencias(dc, "FALTANTE")
        lista_sobr = lista_diferencias(dc, "SOBRANTE")
        st.caption("Listas completas (no solo las 10 principales), con las cantidades en positivo. Usan el último conteo de cada producto.")
        xlsx_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        tab_f, tab_s = st.tabs([f"🔴 Faltantes ({len(lista_falt)})", f"🟢 Sobrantes ({len(lista_sobr)})"])
        for tab, lista, nombre, hoja, col_valor in (
            (tab_f, lista_falt, "faltantes", "Faltantes", "ValorFaltante"),
            (tab_s, lista_sobr, "sobrantes", "Sobrantes", "ValorSobrante"),
        ):
            with tab:
                if lista.empty:
                    st.info(f"No existen {nombre} en esta sesión.")
                    continue
                st.dataframe(lista, use_container_width=True, hide_index=True, column_config={
                    "CostoUnitario": st.column_config.NumberColumn("Costo", format=moneda_fmt()),
                    col_valor: st.column_config.NumberColumn("Valor", format=moneda_fmt()),
                })
                b1, b2 = st.columns(2)
                with b1:
                    try:
                        st.download_button(
                            f"📊 Descargar {nombre} (Excel)",
                            data=exportar_excel({hoja: lista}),
                            file_name=f"{nombre}_{seleccionado}.xlsx",
                            mime=xlsx_mime,
                            use_container_width=True,
                            key=f"dl_{nombre}_xlsx",
                        )
                    except Exception:
                        st.caption("Instala `openpyxl` en requirements.txt para exportar a Excel.")
                with b2:
                    st.download_button(
                        f"📥 Descargar {nombre} (CSV)",
                        data=lista.to_csv(index=False).encode("utf-8-sig"),
                        file_name=f"{nombre}_{seleccionado}.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key=f"dl_{nombre}_csv",
                    )

    ui_seccion("Ajustes sugeridos de stock")
    if ajustes.empty:
        st.info("No hay diferencias que ajustar en esta sesión.")
    else:
        st.caption("Lista lista para cargar en tu sistema contable/ERP. Ajuste positivo = entrada, negativo = salida. Considera el último conteo de cada producto.")
        st.dataframe(ajustes, use_container_width=True, hide_index=True, column_config={
            "CostoUnitario": st.column_config.NumberColumn("Costo", format=moneda_fmt()),
            "ImpactoSoles": st.column_config.NumberColumn("Impacto", format=moneda_fmt()),
        })
        st.download_button(
            "📥 Descargar ajustes sugeridos (CSV)",
            data=ajustes.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"ajustes_{seleccionado}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    ui_seccion("Detalle completo")
    if not dc_hist.empty:
        st.caption("Los resultados usan el último conteo de cada producto; este detalle conserva todo el historial, incluidos los reconteos.")
        detalle = dc_hist.copy()
        st.dataframe(detalle, use_container_width=True, hide_index=True)

        csv = detalle.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 Descargar detalle CSV",
            data=csv,
            file_name=f"inventario_{seleccionado}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    resumen_csv = pd.DataFrame([resumen]).to_csv(index=False).encode("utf-8-sig")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "📥 Descargar resumen CSV",
            data=resumen_csv,
            file_name=f"resumen_{seleccionado}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with c2:
        try:
            excel_bytes = exportar_excel({
                "Detalle": dc_hist if not dc_hist.empty else pd.DataFrame(columns=HEADERS_CONTEO),
                "Resumen": pd.DataFrame([resumen]),
                "Ajustes": ajustes,
                "Faltantes": lista_diferencias(dc, "FALTANTE"),
                "Sobrantes": lista_diferencias(dc, "SOBRANTE"),
                "Pendientes": cobertura_det[cobertura_det["EstadoVerificacion"].isin(["PENDIENTE", "NO LOCALIZADO"])],
                "Cobertura": cobertura_det,
            })
            st.download_button(
                "📊 Descargar todo en Excel",
                data=excel_bytes,
                file_name=f"inventario_{seleccionado}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception:
            st.caption("Instala `openpyxl` en requirements.txt para habilitar la exportación a Excel.")


def _tab_pendientes():
    sesiones = cargar_sesiones()
    if sesiones.empty:
        st.info("Todavía no existen sesiones.")
        return
    ids = sesiones["IdSesion"].astype(str).iloc[::-1].tolist()
    seleccion = st.selectbox("Sesión a revisar (abierta o histórica)", ids, key="pend_sesion")
    ses = sesiones[sesiones["IdSesion"].astype(str) == seleccion].iloc[0]
    d = estado_cobertura(seleccion, ses["Sucursal"])
    m = metricas_cobertura(seleccion, ses["Sucursal"])
    st.progress(m["cobertura"]/100 if m["total"] else 0, text=f"Cobertura: {m['cobertura']:.1f}%")
    c1,c2,c3,c4 = st.columns(4)
    with c1: kpi("Esperados", str(m["total"]))
    with c2: kpi("Verificados", str(m["contados"]))
    with c3: kpi("Pendientes", str(m["pendientes"]))
    with c4: kpi("Exactitud", f"{m['exactitud']:.1f}%")
    if not d.empty:
        st.caption(f"Ceros verificados: {m['ceros']} · No localizados: {m['no_localizados']} (continúan pendientes)")
        filtro_estado = st.multiselect("Estados", sorted(d["EstadoVerificacion"].unique()), default=["PENDIENTE", "NO LOCALIZADO"])
        texto = st.text_input("Buscar nombre, código, marca o categoría", key="buscar_pendientes")
        cats = sorted([str(x) for x in d["Categoria"].dropna().unique() if str(x).strip()])
        categorias = st.multiselect("Categorías", cats, key="cats_pendientes")
        solo_cero = st.checkbox("Solo productos con stock sistema cero", value=False)
        vista = d[d["EstadoVerificacion"].isin(filtro_estado)] if filtro_estado else d.iloc[0:0]
        if categorias: vista = vista[vista["Categoria"].isin(categorias)]
        if solo_cero: vista = vista[vista["StockSistema"] == 0]
        if texto.strip():
            mask = pd.Series(False, index=vista.index)
            for col in ["Producto", "CodigoProducto", "CodigoBarras", "Marca", "Categoria"]:
                mask |= vista[col].astype(str).str.contains(re.escape(texto.strip()), case=False, na=False)
            vista = vista[mask]
        columnas = ["Producto", "CodigoProducto", "CodigoBarras", "Categoria", "Marca", "Sucursal", "StockSistema", "EstadoVerificacion"]
        st.caption(f"Mostrando {len(vista):,} productos · No se ocultan los de stock cero")
        st.dataframe(vista[columnas], use_container_width=True, hide_index=True)
        st.download_button("📊 Descargar lista filtrada (Excel)", data=exportar_excel({"Cobertura":vista[columnas]}), file_name=f"cobertura_{seleccion}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        pendientes = d[d["EstadoVerificacion"].isin(["PENDIENTE", "NO LOCALIZADO"])]
        st.download_button("📊 Descargar TODOS los pendientes (Excel)", data=exportar_excel({"Pendientes":pendientes[columnas]}), file_name=f"pendientes_completos_{seleccion}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    if cargar_universo()["IdSesion"].astype(str).eq(seleccion).sum() == 0:
        st.warning("Sesión anterior a esta actualización: cobertura estimada con el catálogo actual; no existe fotografía histórica.")


def _tab_abc():
    abc = clasificar_abc(cargar_inventario())
    if abc.empty:
        st.info("No hay productos con stock y costo para clasificar.")
        return
    st.caption(
        "Clasificación Pareto por valor de inventario a costo: **A** concentra el 80 % del valor, "
        "**B** el siguiente 15 % y **C** el último 5 %. Prioriza el conteo y el control en la clase A."
    )
    columnas = st.columns(3)
    for columna, clase in zip(columnas, ["A", "B", "C"]):
        sub = abc[abc["Clase"] == clase]
        with columna:
            kpi(f"Clase {clase}", f"{len(sub):,} productos", f"{sub['% Valor'].sum():.1f}% del valor")

    st.bar_chart(abc.groupby("Clase")["Valor"].sum())

    clase_sel = st.selectbox("Ver clase", ["Todas", "A", "B", "C"])
    vista = abc if clase_sel == "Todas" else abc[abc["Clase"] == clase_sel]
    st.dataframe(
        vista.head(300),
        use_container_width=True,
        hide_index=True,
        column_config={
            "StockSistema": st.column_config.NumberColumn("Stock", format="%.0f"),
            "CostoUnitario": st.column_config.NumberColumn("Costo", format=moneda_fmt()),
            "Valor": st.column_config.NumberColumn(format=moneda_fmt()),
            "% Valor": st.column_config.NumberColumn(format="%.2f%%"),
            "% Acumulado": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )
    st.download_button(
        "📥 Descargar clasificación ABC (CSV)",
        data=abc.to_csv(index=False).encode("utf-8-sig"),
        file_name="clasificacion_abc.csv",
        mime="text/csv",
        use_container_width=True,
    )


def _tab_salud():
    inv = cargar_inventario()
    if inv.empty:
        st.info("No hay productos en el inventario.")
        return
    hallazgos = diagnosticar_inventario(inv)
    afectados = set()
    for _, sev, d in hallazgos:
        if sev in ("Alta", "Media"):
            afectados.update(d.index)
    calidad = (1 - len(afectados) / len(inv)) * 100
    altas = sum(len(d) for _, sev, d in hallazgos if sev == "Alta")

    k1, k2, k3 = st.columns(3)
    with k1: kpi("Calidad de datos", f"{calidad:.1f}%", "productos sin alertas altas/medias")
    with k2: kpi("Hallazgos críticos", f"{altas:,}", "severidad alta")
    with k3: kpi("Productos revisados", f"{len(inv):,}", "en el inventario")

    resumen = pd.DataFrame([{"Regla": n, "Severidad": s, "Productos": len(d)} for n, s, d in hallazgos])
    st.dataframe(resumen, use_container_width=True, hide_index=True)

    con_datos = [(n, d) for n, s, d in hallazgos if not d.empty]
    if not con_datos:
        st.success("No se encontraron problemas en los datos del inventario.")
        return
    nombres = [n for n, _ in con_datos]
    regla_sel = st.selectbox("Ver detalle de", nombres)
    detalle = dict(con_datos)[regla_sel]
    cols = ["Producto", "CodigoProducto", "CodigoBarras", "Categoria", "Sucursal", "StockSistema", "CostoUnitario", "PrecioVenta"]
    st.dataframe(detalle[cols].head(300), use_container_width=True, hide_index=True)
    try:
        st.download_button(
            "📊 Descargar todos los hallazgos (Excel)",
            data=exportar_excel({n: d for n, d in con_datos}),
            file_name="salud_datos_inventario.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except Exception:
        st.caption("Instala `openpyxl` para exportar a Excel.")


def _tab_productividad():
    conteos = cargar_conteos()
    sesiones = cargar_sesiones()
    if conteos.empty:
        st.info("Todavía no hay conteos registrados.")
        return
    todas = "Todas las sesiones"
    ids = sesiones.sort_values("FechaInicio", ascending=False)["IdSesion"].astype(str).tolist() if not sesiones.empty else []
    nombres = {
        str(r["IdSesion"]): f"{r['NombreSesion']} ({str(r['FechaInicio'])[:10]})"
        for _, r in sesiones.iterrows()
    } if not sesiones.empty else {}
    sel = st.selectbox("Sesión", [todas] + ids, format_func=lambda x: x if x == todas else nombres.get(x, x))
    df = productividad_contadores(conteos, None if sel == todas else sel)
    if df.empty:
        st.info("No hay conteos para la sesión seleccionada.")
        return

    ritmo_max = df["Conteos/hora"].max()
    k1, k2, k3 = st.columns(3)
    with k1: kpi("Conteos", f"{int(df['Conteos'].sum()):,}", "registros")
    with k2: kpi("Contadores activos", f"{len(df):,}", "personas")
    with k3: kpi("Mejor ritmo", f"{ritmo_max:,.0f}/h" if ritmo_max == ritmo_max else "—", "por sesión seleccionada")

    st.bar_chart(df.set_index("Contador")["Conteos"])
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("La exactitud del contador mide qué porcentaje de sus conteos coincidió con el sistema en la primera pasada.")
    st.download_button(
        "📥 Descargar productividad (CSV)",
        data=df.to_csv(index=False).encode("utf-8-sig"),
        file_name="productividad_contadores.csv",
        mime="text/csv",
        use_container_width=True,
    )


def _tab_tendencia():
    t = tendencia_sesiones(cargar_resumenes())
    if t.empty:
        st.info("Cierra al menos una sesión para ver la tendencia de exactitud y desfase.")
        return

    ultima = t.iloc[-1]
    variacion = (ultima["ExactitudInventario"] - t.iloc[-2]["ExactitudInventario"]) if len(t) > 1 else None
    k1, k2, k3 = st.columns(3)
    with k1: kpi("Última exactitud", f"{ultima['ExactitudInventario']:.1f}%", f"Meta {cfg().meta_exactitud:.0f}%")
    with k2: kpi("Variación", f"{variacion:+.1f} pp" if variacion is not None else "—", "frente a la sesión anterior")
    with k3: kpi("Último desfase neto", formato_soles(ultima["DesfaseNeto"]), str(ultima["NombreSesion"]))

    ui_seccion("Exactitud por sesión")
    graf = t.set_index("Etiqueta")[["ExactitudInventario"]].rename(columns={"ExactitudInventario": "Exactitud %"})
    graf["Meta"] = cfg().meta_exactitud
    st.line_chart(graf)

    ui_seccion("Desfase neto por sesión")
    st.bar_chart(t.set_index("Etiqueta")["DesfaseNeto"])

    vista = t[["Fecha", "NombreSesion", "Sucursal", "ProductosContados", "ExactitudInventario", "ValorFaltantes", "ValorSobrantes", "DesfaseNeto"]]
    st.dataframe(vista, use_container_width=True, hide_index=True)


def _e4_sesiones_cerradas(sucursal="Todas"):
    ses = cargar_sesiones().copy()
    if ses.empty:
        return ses
    ses = ses[ses["Estado"].astype(str).str.upper() == "CERRADA"].copy()
    if sucursal != "Todas":
        ses = ses[ses["Sucursal"].astype(str) == sucursal]
    return ses.drop_duplicates("IdSesion", keep="last")


def _e4_conteos_historicos(sesiones):
    """Una observación por producto/sesión; respeta los reconteos y las zonas."""
    if sesiones.empty:
        return pd.DataFrame()
    todos = cargar_conteos()
    if todos.empty:
        return pd.DataFrame()
    d = todos[todos["IdSesion"].astype(str).isin(set(sesiones["IdSesion"].astype(str)))].copy()
    if d.empty:
        return d
    d = conteos_vigentes(d)
    # Se usa la misma consolidación que en resultados: los conteos por zona
    # están reflejados en ConteoInventario por el mecanismo de consolidación.
    d["_ProductoClave"] = clave_producto(d)
    d["_SesionClave"] = d["IdSesion"].astype(str)
    for col in ["StockSistema", "StockFisico", "Diferencia", "CostoUnitario", "ValorFaltante", "ValorSobrante"]:
        d[col] = pd.to_numeric(d[col], errors="coerce").fillna(0)
    d = d.merge(sesiones[["IdSesion", "NombreSesion", "FechaFin"]].astype(str), on="IdSesion", how="left")
    return d


def _e4_resumen_historico(sesiones):
    if sesiones.empty:
        return pd.DataFrame()
    r = cargar_resumenes().copy()
    if r.empty:
        return r
    r = r[r["IdSesion"].astype(str).isin(set(sesiones["IdSesion"].astype(str)))].copy()
    if r.empty:
        return r
    r = r.drop_duplicates("IdSesion", keep="last")
    for col in ["CoberturaInventario", "ExactitudInventario", "ValorFaltantes", "ValorSobrantes", "DesfaseNeto", "ProductosPendientes"]:
        r[col] = pd.to_numeric(r[col], errors="coerce")
    r = r.merge(sesiones[["IdSesion", "FechaFin"]].astype(str), on="IdSesion", how="left")
    r["OrdenFecha"] = pd.to_datetime(r["FechaFin"], errors="coerce")
    r = r.sort_values(["OrdenFecha", "IdSesion"], kind="stable")
    r["Sesión"] = r["NombreSesion"].astype(str) + " · " + r["IdSesion"].astype(str).str[-6:]
    return r


def _e4_recurrencias(conteos, minimo=2):
    if conteos.empty:
        return pd.DataFrame()
    d = conteos[conteos["Diferencia"].abs() > 0.000001].copy()
    if d.empty:
        return pd.DataFrame()
    d["PerdidaSoles"] = d["ValorFaltante"].clip(lower=0)
    d["SobranteSoles"] = d["ValorSobrante"].clip(lower=0)
    agrupado = d.groupby("_ProductoClave", as_index=False).agg(
        Producto=("Producto", "last"), Categoria=("Categoria", "last"),
        Sucursal=("Sucursal", "last"), SesionesConDiferencia=("IdSesion", "nunique"),
        PerdidaAcumulada=("PerdidaSoles", "sum"), SobranteAcumulado=("SobranteSoles", "sum"),
        UltimaFecha=("FechaFin", "max"),
    )
    return agrupado[agrupado["SesionesConDiferencia"] >= minimo].sort_values(
        ["SesionesConDiferencia", "PerdidaAcumulada"], ascending=False)


def _e4_criticidad(inventario, recurrencias):
    """Criticidad de control, no pronóstico de demanda: ABC valor + recurrencia."""
    abc = clasificar_abc(inventario)
    if abc.empty:
        return abc
    d = abc.copy()
    # Vincular por código de producto dentro de sucursal cuando esté disponible.
    # Si no existe coincidencia fiable, no se imputa recurrencia.
    d["SesionesConDiferencia"] = 0
    if not recurrencias.empty and "CodigoProducto" in d.columns:
        # El ABC actual no incluye sucursal; evitar atribuir recurrencias
        # entre sucursales usando un código que podría estar repetido.
        pass
    d["Criticidad"] = d["Clase"].map({"A": "ALTA", "B": "MEDIA", "C": "BAJA"}).fillna("SIN CLASE")
    return d


def _e4_alertas_stock(inv):
    """Alertas descriptivas, sin inventar rotación ni puntos de reposición."""
    if inv.empty:
        return pd.DataFrame()
    d = inv.copy()
    d["StockSistema"] = pd.to_numeric(d["StockSistema"], errors="coerce").fillna(0)
    d["CostoUnitario"] = pd.to_numeric(d["CostoUnitario"], errors="coerce").fillna(0)
    d["Alerta"] = d["StockSistema"].apply(lambda x: "STOCK NEGATIVO" if x < 0 else ("SIN STOCK" if x == 0 else ""))
    d.loc[(d["CostoUnitario"] <= 0) & (d["Alerta"] == ""), "Alerta"] = "SIN COSTO"
    return d[d["Alerta"] != ""][["Sucursal", "CodigoProducto", "Producto", "Categoria", "StockSistema", "CostoUnitario", "Alerta"]]


def _tab_inteligencia():
    st.markdown("### Inteligencia de inventarios")
    st.caption("Histórico de sesiones cerradas. Los productos pendientes o no localizados NO se clasifican como pérdidas.")
    sesiones_all = cargar_sesiones()
    if sesiones_all.empty:
        st.info("Todavía no hay sesiones para analizar.")
        return
    sucursales = sorted([str(x) for x in sesiones_all["Sucursal"].dropna().unique() if str(x).strip()])
    suc = st.selectbox("Sucursal", ["Todas"] + sucursales, key="e4_sucursal")
    ses = _e4_sesiones_cerradas(suc)
    if ses.empty:
        st.info("No existen sesiones cerradas para esta sucursal.")
        return
    resumen = _e4_resumen_historico(ses)
    conteos = _e4_conteos_historicos(ses)
    tabs = st.tabs(["📊 Ejecutivo", "🔁 Recurrentes", "💸 Pérdidas", "🅰️ ABC y criticidad", "🚨 Stock y reposición"])
    with tabs[0]:
        if resumen.empty:
            st.warning("No hay resúmenes históricos guardados. Cierra sesiones nuevas para alimentar las tendencias.")
        else:
            ultimo = resumen.iloc[-1]
            c1, c2, c3, c4 = st.columns(4)
            with c1: kpi("Sesiones cerradas", str(len(resumen)), "histórico filtrado")
            with c2: kpi("Cobertura final", f"{ultimo['CoberturaInventario']:.1f}%" if pd.notna(ultimo["CoberturaInventario"]) else "—", "última sesión")
            with c3: kpi("Exactitud final", f"{ultimo['ExactitudInventario']:.1f}%" if pd.notna(ultimo["ExactitudInventario"]) else "—", "solo productos verificados")
            with c4: kpi("Pérdida bruta", formato_soles(resumen["ValorFaltantes"].sum()), "suma histórica de faltantes")
            graf = resumen.set_index("Sesión")[["CoberturaInventario", "ExactitudInventario"]].rename(columns={"CoberturaInventario":"Cobertura %", "ExactitudInventario":"Exactitud %"})
            st.markdown("#### Evolución de cobertura y exactitud")
            st.line_chart(graf)
            st.markdown("#### Diferencias valorizadas por sesión")
            st.bar_chart(resumen.set_index("Sesión")[["ValorFaltantes", "ValorSobrantes"]].rename(columns={"ValorFaltantes":"Faltantes", "ValorSobrantes":"Sobrantes"}))
            st.dataframe(resumen[["Fecha", "NombreSesion", "Sucursal", "CoberturaInventario", "ExactitudInventario", "ProductosPendientes", "ValorFaltantes", "ValorSobrantes"]], use_container_width=True, hide_index=True)
            st.download_button("📥 Exportar histórico ejecutivo (Excel)", exportar_excel({"Tendencias":resumen.drop(columns=["OrdenFecha"])}), file_name="inteligencia_historico.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="e4_xls_hist")
    with tabs[1]:
        umbral = st.number_input("Mínimo de sesiones con diferencias", min_value=2, max_value=max(2, len(ses)), value=2, key="e4_recur_min")
        rec = _e4_recurrencias(conteos, umbral) if not conteos.empty else pd.DataFrame()
        if rec.empty:
            st.info("No se identifican diferencias recurrentes con el criterio seleccionado.")
        else:
            st.dataframe(rec.drop(columns=["_ProductoClave"]), use_container_width=True, hide_index=True)
            st.download_button("📥 Exportar recurrencias (Excel)", exportar_excel({"Recurrentes":rec.drop(columns=["_ProductoClave"])}), file_name="productos_recurrentes.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="e4_xls_rec")
        st.caption("Se cuenta una vez por producto y sesión, incluso si hubo varios reconteos.")
    with tabs[2]:
        if conteos.empty:
            st.info("No existen conteos históricos para valorizar.")
        else:
            perd = conteos[conteos["ValorFaltante"] > 0].copy()
            if perd.empty:
                st.success("No hay faltantes valorizados en las sesiones cerradas seleccionadas.")
            else:
                ranking = perd.groupby("_ProductoClave", as_index=False).agg(Producto=("Producto", "last"), Categoria=("Categoria", "last"), Sucursal=("Sucursal", "last"), Sesiones=("IdSesion", "nunique"), UnidadesFaltantes=("Diferencia", lambda v: float(-v[v < 0].sum())), PerdidaSoles=("ValorFaltante", "sum")).sort_values("PerdidaSoles", ascending=False)
                c1,c2=st.columns(2)
                with c1: kpi("Pérdida bruta histórica", formato_soles(perd["ValorFaltante"].sum()), "sin descontar sobrantes")
                with c2: kpi("Productos con pérdida", f"{len(ranking):,}", "productos distintos")
                st.bar_chart(ranking.head(15).set_index("Producto")["PerdidaSoles"])
                st.dataframe(ranking.drop(columns=["_ProductoClave"]), use_container_width=True, hide_index=True)
                st.download_button("📥 Exportar ranking de pérdidas (Excel)", exportar_excel({"Perdidas":ranking.drop(columns=["_ProductoClave"])}), file_name="ranking_perdidas.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="e4_xls_perd")
    with tabs[3]:
        inv = cargar_inventario()
        if suc != "Todas":
            inv = inv[inv["Sucursal"].astype(str) == suc].copy()
        abc = _e4_criticidad(inv, pd.DataFrame())
        if abc.empty:
            st.info("No hay stock valorizado suficiente para calcular ABC.")
        else:
            st.caption("ABC por valor actual a costo: A hasta 80 %, B hasta 95 %, C restante. Criticidad inicial basada en ABC, no en ventas.")
            st.dataframe(abc, use_container_width=True, hide_index=True)
            st.download_button("📥 Exportar ABC y criticidad (Excel)", exportar_excel({"ABC_Criticidad":abc}), file_name="abc_criticidad.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="e4_xls_abc")
    with tabs[4]:
        inv = cargar_inventario()
        if suc != "Todas":
            inv = inv[inv["Sucursal"].astype(str) == suc].copy()
        alertas = _e4_alertas_stock(inv)
        if alertas.empty:
            st.success("Sin alertas básicas de stock negativo, stock cero o costo faltante.")
        else:
            st.dataframe(alertas, use_container_width=True, hide_index=True)
            st.download_button("📥 Exportar alertas (Excel)", exportar_excel({"Alertas":alertas}), file_name="alertas_stock.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="e4_xls_alertas")
        st.info("Las sugerencias de cantidad a reponer, punto de pedido y días de cobertura se habilitarán cuando existan movimientos/ventas con fecha, producto, sucursal y unidades. No se estimará demanda a partir de conteos físicos.")


def pantalla_analisis():
    header("Análisis de inventario", "Prioriza el conteo, detecta problemas en los datos y mide el desempeño")
    es_admin = permisos.es_supervision(st.session_state.usuario)
    etiquetas = ["🎯 Pendientes", "🅰️ Análisis ABC"]
    if es_admin:
        etiquetas += ["🩺 Salud de datos", "👥 Productividad", "📈 Tendencia", "🧠 Inteligencia"]
    tabs = st.tabs(etiquetas)
    with tabs[0]:
        _tab_pendientes()
    with tabs[1]:
        _tab_abc()
    if es_admin:
        with tabs[2]:
            _tab_salud()
        with tabs[3]:
            _tab_productividad()
        with tabs[4]:
            _tab_tendencia()
        with tabs[5]:
            _tab_inteligencia()

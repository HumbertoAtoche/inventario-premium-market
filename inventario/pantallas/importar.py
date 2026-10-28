"""Importación de productos y ventas desde Excel/CSV con detección de columnas y validación previa."""
import pandas as pd
import streamlit as st
from inventario.contexto import cfg, datos, permiso, servicio_config
from inventario.nucleo import importadores as imp
from inventario.servicios import actualizar_datos, registrar_auditoria
from inventario.ui.componentes import header, kpi, ui_callout, ui_seccion
from inventario.utilidades import mostrar_error_google


def _plantilla_productos():
    ejemplo = pd.DataFrame([{"CodigoProducto": "P001", "CodigoBarras": "7750000000011", "Producto": "Producto de ejemplo", "Categoria": "General",
                             "Marca": "Genérica", "Unidad": "UND", "Sucursal": "", "StockSistema": 10, "CostoUnitario": 5.5, "PrecioVenta": 9.9, "StockMinimo": 3}])
    return ejemplo.to_csv(index=False).encode("utf-8-sig")


def _selector_mapeo(prefijo, columnas, campos, sugerido, etiquetas=None):
    """Una lista desplegable por campo del sistema -> columna del archivo."""
    opciones = ["(no usar)"] + list(columnas)
    mapeo, cols = {}, st.columns(3)
    for i, campo in enumerate(campos):
        previo = sugerido.get(campo)
        idx = opciones.index(previo) if previo in opciones else 0
        with cols[i % 3]:
            elegido = st.selectbox((etiquetas or {}).get(campo, campo), opciones, index=idx, key=f"{prefijo}_map_{campo}")
        mapeo[campo] = None if elegido == "(no usar)" else elegido
    return mapeo


def _tabla_errores(errores):
    if errores:
        with st.expander(f"Ver las {len(errores)} filas con problemas (no se importarán)"):
            st.dataframe(pd.DataFrame(errores).rename(columns={"fila": "Fila del archivo", "problema": "Problema"}), use_container_width=True, hide_index=True)


def bloque_importar_productos(prefijo="imp_p", sucursal_defecto=None, permitir_reemplazar=True):
    """Devuelve el resumen de la importación realizada (o None)."""
    c = cfg()
    st.download_button("Descargar plantilla de ejemplo (CSV)", _plantilla_productos(), file_name="plantilla_productos.csv", mime="text/csv", key=f"{prefijo}_plantilla")
    archivo = st.file_uploader("Archivo de productos (Excel o CSV)", type=["xlsx", "xls", "csv"], key=f"{prefijo}_archivo")
    if not archivo:
        ui_callout("Una fila por producto. Como mínimo: el nombre y un código (de producto o de barras). No hace falta que las columnas se llamen igual: "
                   "el sistema las detecta y tú puedes corregirlas.")
        return None
    try:
        df0, h0 = imp.leer_archivo(archivo.getvalue(), archivo.name)
    except Exception as exc:
        st.error(f"No pude leer el archivo: {exc}")
        return None
    fila_enc = st.number_input("Fila donde están los encabezados", min_value=1, value=int(h0) + 1, step=1, key=f"{prefijo}_fila_enc",
                               help="Si tu archivo tiene títulos arriba, indica en qué fila empiezan las columnas.")
    try:
        df, h = imp.leer_archivo(archivo.getvalue(), archivo.name, fila_encabezado=int(fila_enc) - 1)
    except Exception as exc:
        st.error(f"No pude leer el archivo con esa fila de encabezados: {exc}")
        return None
    if df.empty:
        st.warning("No hay filas de datos debajo de los encabezados.")
        return None
    ui_seccion("Correspondencia de columnas", "Revisa que cada campo apunte a la columna correcta")
    mapeo = _selector_mapeo(prefijo, df.columns, imp.CAMPOS_PRODUCTO, imp.sugerir_mapeo(df.columns, imp.CAMPOS_PRODUCTO))
    suc_def = sucursal_defecto or (c.sucursales[0] if c.sucursales else "Principal")
    if not mapeo.get("Sucursal"):
        opciones = list(c.sucursales) or [suc_def]
        suc_def = st.selectbox("Sucursal de estos productos", opciones, index=opciones.index(suc_def) if suc_def in opciones else 0, key=f"{prefijo}_suc")
    out, errores, adv = imp.convertir_productos(df, mapeo, suc_def, offset=h + 2)
    k1, k2, k3 = st.columns(3)
    with k1: kpi("Filas leídas", f"{len(df):,}")
    with k2: kpi("Listas para importar", f"{len(out):,}")
    with k3: kpi("Con problemas", f"{len(errores):,}", "no se importarán" if errores else "todo en orden")
    _tabla_errores(errores)
    for a in adv[:5]:
        st.caption("⚠ " + a)
    if len(adv) > 5:
        st.caption(f"… y {len(adv) - 5} advertencias más.")
    if out.empty:
        return None
    st.dataframe(out.head(15), use_container_width=True, hide_index=True)
    modos = {"agregar_nuevos": "Agregar solo los productos nuevos (no toca los existentes)",
             "actualizar": "Agregar nuevos y actualizar los existentes (incluye el stock)"}
    if permitir_reemplazar:
        modos["reemplazar"] = "Reemplazar TODO el inventario por este archivo"
    modo = st.radio("¿Cómo importar?", list(modos), format_func=modos.get, key=f"{prefijo}_modo")
    confirmado = True
    if modo == "reemplazar":
        confirmado = st.checkbox("Entiendo que esto borra el inventario actual y no se puede deshacer.", key=f"{prefijo}_conf")
    if st.button(f"Importar {len(out):,} productos", type="primary", disabled=not confirmado or not len(out), key=f"{prefijo}_go"):
        try:
            res = imp.escribir_productos(datos(), out, modo)
            registrar_auditoria("IMPORTACION_PRODUCTOS", f"{modo}: {res} · archivo {archivo.name}")
            actualizar_datos()
            st.success(f"Listo: {res['nuevos']} nuevos, {res['actualizados']} actualizados, {res['omitidos']} omitidos.")
            return res
        except Exception as exc:
            mostrar_error_google(exc, "la importación de productos")
    return None


def bloque_importar_ventas(prefijo="imp_v"):
    c = cfg()
    archivo = st.file_uploader("Reporte de ventas (Excel o CSV)", type=["xlsx", "xls", "csv"], key=f"{prefijo}_archivo")
    if not archivo:
        ui_callout("Sirve el reporte de cualquier sistema de ventas. Necesita fecha, cantidad y producto (o código). Si lo importas de nuevo, "
                   "no se duplican las ventas ya registradas. Las ventas alimentan el plan de compras inteligente.")
        return
    try:
        df0, h0 = imp.leer_archivo(archivo.getvalue(), archivo.name)
        fila_enc = st.number_input("Fila donde están los encabezados", min_value=1, value=int(h0) + 1, step=1, key=f"{prefijo}_fila_enc")
        df, h = imp.leer_archivo(archivo.getvalue(), archivo.name, fila_encabezado=int(fila_enc) - 1)
    except Exception as exc:
        st.error(f"No pude leer el archivo: {exc}")
        return
    guardado = {k: v for k, v in (c.ventas_mapeo or {}).items() if v in df.columns}
    sugerido = {**imp.sugerir_mapeo(df.columns, imp.CAMPOS_VENTA), **guardado}
    ui_seccion("Correspondencia de columnas", "Se recuerda para la próxima importación" if guardado else "Revisa que cada campo apunte a la columna correcta")
    etiquetas = {"Fecha": "Fecha (obligatoria)", "Cantidad": "Cantidad (obligatoria)", "CodigoBarras": "Código de barras", "SKU": "Código / SKU"}
    mapeo = _selector_mapeo(prefijo, df.columns, imp.CAMPOS_VENTA, sugerido, etiquetas)
    out, errores, adv = imp.convertir_ventas(df, mapeo, offset=h + 2)
    k1, k2, k3 = st.columns(3)
    with k1: kpi("Filas leídas", f"{len(df):,}")
    with k2: kpi("Listas para importar", f"{len(out):,}")
    with k3: kpi("Con problemas", f"{len(errores):,}", "no se importarán" if errores else "todo en orden")
    _tabla_errores(errores)
    for a in adv:
        ui_callout(a)
    if out.empty:
        return
    st.dataframe(out[["FECHA/HORA", "PRODUCTO", "CÓDIGO DE BARRA", "SKU", "CANTIDAD", "TOTAL", "COSTO*"]].head(15), use_container_width=True, hide_index=True)
    modo = st.radio("¿Cómo importar?", ["agregar", "reemplazar"], format_func=lambda m: "Agregar (omite lo ya registrado)" if m == "agregar" else "Reemplazar TODAS las ventas", key=f"{prefijo}_modo")
    confirmado = modo == "agregar" or st.checkbox("Entiendo que esto borra las ventas actuales.", key=f"{prefijo}_conf")
    if st.button(f"Importar {len(out):,} ventas", type="primary", disabled=not confirmado, key=f"{prefijo}_go"):
        try:
            res = imp.escribir_ventas(datos(), out, modo)
            if any(mapeo.values()) and mapeo != guardado:
                servicio_config().guardar({"ventas_mapeo": {k: v for k, v in mapeo.items() if v}}, st.session_state.get("usuario", {}).get("Usuario", ""))
            registrar_auditoria("IMPORTACION_VENTAS", f"{modo}: {res} · archivo {archivo.name}")
            actualizar_datos()
            st.success(f"Listo: {res['nuevos']} ventas nuevas, {res['omitidos']} ya estaban registradas.")
        except Exception as exc:
            mostrar_error_google(exc, "la importación de ventas")


def pantalla_importar():
    header("Importar datos", "Carga productos y ventas desde Excel o CSV")
    if not permiso("importar"):
        st.error("No tienes permiso para importar datos.")
        return
    t1, t2 = st.tabs(["Productos", "Ventas"])
    with t1:
        bloque_importar_productos()
    with t2:
        bloque_importar_ventas()

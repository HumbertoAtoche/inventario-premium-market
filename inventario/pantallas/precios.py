"""Consulta de precios."""
import streamlit as st
from inventario.servicios import buscar_por_codigo, buscar_productos
from inventario.ui.componentes import header
from inventario.utilidades import formato_soles, limpiar_codigo, limpiar_numero, safe_text, sonido_confirmacion


def tarjeta_precio(producto):
    nombre = producto.get("Producto", "Producto sin nombre")
    precio = limpiar_numero(producto.get("PrecioVenta", 0))
    stock = limpiar_numero(producto.get("StockSistema", 0))
    unidad = producto.get("Unidad", "") or "unidad"

    st.markdown(
        f"""
        <div class='price-hero'>
            <div class='price-label'>{safe_text(nombre)}</div>
            <div class='price-value'>{formato_soles(precio)}</div>
            <div class='price-sub'>Precio de venta al público</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class='price-info-grid'>
            <div class='price-info-item'><div class='lbl'>Código</div><div class='val'>{safe_text(producto.get('CodigoProducto','') or '—')}</div></div>
            <div class='price-info-item'><div class='lbl'>Marca</div><div class='val'>{safe_text(producto.get('Marca','') or '—')}</div></div>
            <div class='price-info-item'><div class='lbl'>Categoría</div><div class='val'>{safe_text(producto.get('Categoria','') or '—')}</div></div>
            <div class='price-info-item'><div class='lbl'>Stock</div><div class='val'>{stock:,.0f} {safe_text(unidad)}</div></div>
            <div class='price-info-item'><div class='lbl'>Sucursal</div><div class='val'>{safe_text(producto.get('Sucursal','') or '—')}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if stock <= 0:
        st.warning("⚠️ El sistema no registra stock disponible para este producto.")

    if st.button("🔎 Consultar otro producto", type="primary", use_container_width=True):
        st.session_state.precio_producto = None
        st.session_state.precio_ultimo_codigo_scan = ""
        st.rerun()


def pantalla_precios():
    header("Consulta de precios", "Escanea o busca un producto para informar su precio al instante")

    if st.session_state.get("precio_producto"):
        tarjeta_precio(st.session_state.precio_producto)
        return

    modo = st.session_state.get("precio_modo", "scanner")
    a1, a2 = st.columns(2)
    with a1:
        if st.button("📷 Escanear código", use_container_width=True, type="primary" if modo == "scanner" else "secondary"):
            st.session_state.precio_modo = "scanner"
            st.rerun()
    with a2:
        if st.button("🔎 Buscar por nombre", use_container_width=True, type="primary" if modo == "busqueda" else "secondary"):
            st.session_state.precio_modo = "busqueda"
            st.rerun()

    st.divider()

    if modo == "busqueda":
        texto = st.text_input("Buscar producto", placeholder="Ej. Inca Kola, 775..., Coca...", key="precio_texto_busqueda")
        df = buscar_productos(texto)
        if df.empty:
            st.info("Escribe un nombre, marca o código para ver resultados.")
        else:
            st.caption(f"Mostrando {len(df):,} resultado(s).")
            for idx, producto in df.iterrows():
                nombre = str(producto.get("Producto", "Sin nombre"))
                precio = formato_soles(producto.get("PrecioVenta", 0))
                st.markdown(
                    f"<div class='card'><b>{safe_text(nombre)}</b> — <span style='color:#1071b8;font-weight:800'>{precio}</span>"
                    f"<br><span style='color:#6b7280;font-size:.8rem'>Código: {safe_text(producto.get('CodigoProducto',''))}</span></div>",
                    unsafe_allow_html=True,
                )
                if st.button("Ver precio", key=f"precio_sel_{idx}", use_container_width=True):
                    st.session_state.precio_producto = producto.to_dict()
                    st.rerun()
        return

    st.markdown(
        "<div class='mobile-note'>📱 Apunta la cámara al código de barras. Ideal para responder consultas de precio en caja sin usar el conteo físico.</div>",
        unsafe_allow_html=True,
    )
    try:
        from streamlit_qrcode_scanner import qrcode_scanner
        codigo = qrcode_scanner(key="precio_barcode_scanner")
        if codigo:
            codigo = limpiar_codigo(codigo)
            if codigo and codigo != st.session_state.get("precio_ultimo_codigo_scan", ""):
                st.session_state.precio_ultimo_codigo_scan = codigo
                producto = buscar_por_codigo(codigo)
                if producto:
                    st.session_state.precio_producto = producto
                    sonido_confirmacion()
                    st.rerun()
                else:
                    st.error(f"No encontramos el código **{codigo}** en el inventario.")
    except ImportError:
        st.warning("El escáner no está instalado. Agrega `streamlit-qrcode-scanner` a requirements.txt.")
    except Exception as exc:
        st.warning("No se pudo iniciar la cámara. Usa la búsqueda por nombre.")
        with st.expander("Detalle técnico"):
            st.code(str(exc))

    st.divider()
    with st.form("form_codigo_precio", clear_on_submit=True):
        codigo_manual = st.text_input(
            "Código de barras / código de producto",
            placeholder="Escanea con un lector físico o escribe el código y presiona Enter",
        )
        buscar = st.form_submit_button("🔎 Consultar precio", use_container_width=True)
    if buscar and codigo_manual.strip():
        producto = buscar_por_codigo(codigo_manual)
        if producto:
            st.session_state.precio_producto = producto
            st.rerun()
        else:
            st.error(f"No encontramos el código **{limpiar_codigo(codigo_manual)}** en el inventario.")

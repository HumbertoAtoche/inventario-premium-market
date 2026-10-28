"""Barra lateral, búsqueda global y navegación móvil."""
import pandas as pd
import streamlit as st
from inventario.contexto import cfg
from inventario.nucleo import permisos
from inventario.servicios import actualizar_datos, buscar_productos, cargar_sesiones, registrar_auditoria
from inventario.ui.componentes import _html, _ir_a, _norm_txt, header, logo_tag, ui_avatar, ui_callout, ui_chip, ui_guia_instalar
from inventario.utilidades import formato_soles, limpiar_numero, safe_text


# =========================================================
# SIDEBAR (misma estructura que Asistencia)
# Marca · tarjeta de usuario · aviso · búsqueda · menú · accesos · cerrar sesión
# =========================================================

_CLAVES_SESION = [
    "autenticado", "usuario", "pagina", "nav_menu", "reconteo_activo", "sesion_actual", "codigo_pendiente",
    "producto_pendiente", "modo_inventario", "ultimo_codigo_scan", "zona_activa", "precio_producto", "precio_modo",
    "precio_ultimo_codigo_scan", "login_timestamp", "ultima_actividad", "gs_q", "_pg_prev", "_pg_n", "_menu_opciones", "cfg_cache",
]


def _cerrar_sesion(motivo=""):
    """Limpia la sesión del usuario. Si hay motivo (cierre automático), el login lo muestra."""
    for key in _CLAVES_SESION:
        st.session_state.pop(key, None)
    if motivo:
        st.session_state["_sesion_expirada"] = motivo


def _cambio_menu():
    """Callback del menú lateral: se ejecuta ANTES del rerun, por lo que la
    página queda actualizada con un solo clic."""
    st.session_state.pagina = st.session_state.get("nav_menu", "Inicio")
    st.session_state["gs_q"] = ""


def render_busqueda_inv(q, opciones):
    """Búsqueda global (solo lectura): secciones del menú y productos del inventario."""
    header("Resultados de búsqueda", f"Coincidencias para «{q}»")
    qn = _norm_txt(q)
    secs = [o for o in opciones if qn in _norm_txt(o)]
    if secs:
        st.markdown(f'<div class="tp-note-t" style="margin:6px 0 10px">Secciones · {len(secs)}</div>', unsafe_allow_html=True)
        cols = st.columns(min(len(secs), 4))
        for i, s in enumerate(secs):
            with cols[i % len(cols)]:
                st.button(s, key=f"gs_sec_{i}", use_container_width=True, on_click=_ir_a, args=(s,))
    try:
        prods = buscar_productos(q)
    except Exception:
        prods = pd.DataFrame()
    n = len(prods)
    st.markdown(f'<div class="tp-note-t" style="margin:22px 0 10px">Productos · {n}{"+" if n >= 100 else ""}</div>', unsafe_allow_html=True)
    if prods.empty:
        ui_callout("No encontré productos con ese nombre, código, categoría o marca. Prueba con otra palabra.")
        return
    filas = ""
    for _, r in prods.head(25).iterrows():
        stock = limpiar_numero(r.get("StockSistema", 0))
        detalle = " · ".join(
            x for x in [
                f"Cód. {safe_text(r.get('CodigoProducto', ''))}" if str(r.get("CodigoProducto", "")).strip() else "",
                safe_text(r.get("Categoria", "")) if str(r.get("Categoria", "")).strip() else "",
                safe_text(r.get("Marca", "")) if str(r.get("Marca", "")).strip() else "",
            ] if x
        ) or "Sin detalle"
        chips = ui_chip(f"Stock {stock:,.0f}", "ok" if stock > 0 else "bad") + ui_chip(formato_soles(limpiar_numero(r.get("PrecioVenta", 0))), "neutral")
        filas += f'<div class="tp-row"><div class="tp-row-main"><b>{safe_text(r.get("Producto", ""))}</b><span>{detalle}</span></div><div class="tp-chips">{chips}</div></div>'
    st.markdown(filas, unsafe_allow_html=True)
    if n > 25:
        st.caption(f"Mostrando 25 de {n}{'+' if n >= 100 else ''} coincidencias. Afina la búsqueda para ver menos resultados.")


def sidebar():
    usuario = st.session_state.usuario
    rol = permisos.rol_de(usuario)
    nombre_usuario = str(usuario.get("NombreCompleto", "")).strip()
    login_usuario = str(usuario.get("Usuario", "")).strip()

    st.sidebar.markdown(f'<div style="text-align:center; padding: 8px 0 14px 0;">{logo_tag(58)}</div>', unsafe_allow_html=True)
    _pal = cfg().nombre.split()
    _marca = (" ".join(_pal[:-1]) + f" <span>{_html.escape(_pal[-1])}</span>") if len(_pal) > 1 else f"<span>{_html.escape(cfg().nombre)}</span>"
    st.sidebar.markdown(f'<div class="tp-brand"><div class="tp-brand-name">{_marca}</div><div class="tp-brand-sub">{_html.escape(cfg().sistema_subtitulo)}</div></div>', unsafe_allow_html=True)
    st.sidebar.markdown(f"""
        <div class="tp-user">
            {ui_avatar(nombre_usuario or login_usuario)}
            <div><b>{safe_text(nombre_usuario or login_usuario)}</b><span>{safe_text(rol.capitalize())} · {safe_text(login_usuario)}</span></div>
        </div>
    """, unsafe_allow_html=True)

    # Aviso de sesiones de conteo abiertas (mismo recurso visual que los avisos de Asistencia)
    try:
        _ses = cargar_sesiones()
        _abiertas = int((_ses["Estado"].astype(str).str.upper() == "ABIERTA").sum()) if not _ses.empty else 0
    except Exception:
        _abiertas = 0
    if _abiertas:
        st.sidebar.markdown(f'<div class="tp-notif"><span>Inventarios en curso</span><span>{_abiertas}</span></div>', unsafe_allow_html=True)

    opciones = permisos.paginas_para(usuario, cfg())
    st.session_state["_menu_opciones"] = opciones

    st.sidebar.text_input("Buscar", key="gs_q", placeholder="Buscar productos, secciones…", label_visibility="collapsed")

    # Sincroniza el menú con la página actual (por ejemplo, cuando un botón
    # de la pantalla cambia de página). Se hace ANTES de crear el radio.
    actual = st.session_state.get("pagina", "Inicio")
    if actual not in opciones:
        actual = "Inicio"
        st.session_state.pagina = actual
    if st.session_state.get("nav_menu") != actual:
        st.session_state["nav_menu"] = actual

    seleccion = st.sidebar.radio("Navegación", opciones, key="nav_menu", on_change=_cambio_menu)
    st.session_state.pagina = seleccion

    # Barra inferior de navegación (solo se ve en celular; en PC la oculta el CSS)
    _nav_items = [("Inicio", "Inicio", ":material/dashboard:"), ("Precios", "Precios", ":material/sell:"),
                  ("Inventario", "Contar", ":material/qr_code_scanner:"), ("Resultados", "Resultados", ":material/bar_chart:")]
    _nav_items = [i for i in _nav_items if i[0] in opciones]
    try:
        with st.container(key="tp_bottomnav"):
            for _col, (_dest, _lbl, _ico) in zip(st.columns(len(_nav_items)), _nav_items):
                with _col:
                    st.button(_lbl, key=f"bn_{_dest}", icon=_ico, use_container_width=True,
                              type="primary" if seleccion == _dest else "secondary", on_click=_ir_a, args=(_dest,))
    except Exception:
        pass  # versiones antiguas de Streamlit: se usa solo el menú lateral

    st.sidebar.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
    if st.sidebar.button("Actualizar Datos", use_container_width=True, key="sb_actualizar_datos"):
        actualizar_datos()
        st.rerun()

    st.sidebar.markdown('<div class="btn-logout">', unsafe_allow_html=True)
    for _e in cfg().enlaces:
        _url = str(_e.get("url", ""))
        if _url.startswith(("http://", "https://")):
            st.sidebar.markdown(
                f'<a class="tp-negosy" href="{_html.escape(_url, quote=True)}" target="_blank" rel="noopener noreferrer"><span><span class="tp-negosy-t">{_html.escape(str(_e.get("nombre", "")))}</span>'
                f'<span class="tp-negosy-s">{_html.escape(str(_e.get("detalle", "")))}</span></span>'
                "<svg width='18' height='18' viewBox='0 0 24 24' fill='none' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M7 17L17 7M9 7h8v8'/></svg></a>",
                unsafe_allow_html=True)
    ui_guia_instalar(st.sidebar)
    if st.sidebar.button("Cerrar Sesión", use_container_width=True, key="sb_cerrar_sesion"):
        registrar_auditoria("LOGOUT", "Cierre de sesión")
        _cerrar_sesion()
        st.rerun()
    st.sidebar.markdown('</div>', unsafe_allow_html=True)

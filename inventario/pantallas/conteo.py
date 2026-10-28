"""Sesiones, zonas, escáner y conteo por producto."""
import streamlit as st
from inventario.constantes import HOJA_ZONAS
from inventario.contexto import cfg, hoja_control
from inventario.nucleo import permisos
from inventario.nucleo.esquemas import HEADERS_ZONAS
from inventario.servicios import buscar_por_codigo, buscar_productos, calcular_resumen, cargar_conteos, cargar_conteos_zona, cargar_inventario, cargar_usuarios, cargar_zonas, cerrar_sesion, contar_productos_sesion, conteo_ciego_usuario, crear_sesion, crear_zonas_iniciales, es_diferencia_critica, guardar_conteo, guardar_conteo_zona, guardar_resumen, guardar_zona_estado, metricas_cobertura, obtener_sesion_abierta, pendientes_anteriores, registrar_no_localizado, solicitar_reconteo, solicitud_pendiente, ultimo_conteo_producto, ultimo_conteo_zona, zona_usuario, zonas_sesion
from inventario.ui.componentes import badge, header, kpi, ui_seccion
from inventario.utilidades import exportar_excel, formato_soles, limpiar_codigo, limpiar_numero, mostrar_error_google, safe_text, sonido_confirmacion


def pantalla_zonas():
    header("Zonas de inventario", "Asigna góndolas y áreas sin registrar productos previamente")
    sesion = obtener_sesion_abierta()
    if not sesion:
        st.info("Abre una sesión de inventario para gestionar zonas.")
        return
    usuario = st.session_state.usuario
    admin = permisos.es_supervision(usuario)
    d = zonas_sesion(sesion["IdSesion"])
    if d.empty:
        st.info("Esta sesión todavía no tiene zonas configuradas. Puede seguir usándose el inventario general.")
        if admin and st.button(f"Crear las {len(cfg().zonas)} zonas de {cfg().nombre}", type="primary"):
            crear_zonas_iniciales(sesion)
            st.rerun()
        return
    d["Conteos"] = 0
    cz = cargar_conteos_zona()
    cz = cz[cz["IdSesion"].astype(str) == str(sesion["IdSesion"])]
    if not cz.empty:
        cz = cz.drop_duplicates(["Zona", "CodigoBarras", "CodigoProducto"], keep="last")
        d["Conteos"] = d["Zona"].map(cz.groupby("Zona").size()).fillna(0).astype(int)
    st.dataframe(d[["Zona","Responsable","Estado","Conteos","FechaInicio","FechaFin"]], hide_index=True, use_container_width=True)
    st.caption("Las zonas finalizadas quedan bloqueadas. El avance global se mide por productos únicos; no se inventa un porcentaje por zona.")
    if admin:
        with st.expander("Administrar zonas y responsables", expanded=True):
            usuarios = cargar_usuarios()
            nombres = [str(u) for u in usuarios["Usuario"].tolist()] if not usuarios.empty else []
            zona = st.selectbox("Zona", d["Zona"].tolist(), key="adm_zona")
            actual = d[d["Zona"] == zona].iloc[-1]
            resp = st.selectbox("Responsable", [""] + nombres, index=([""]+nombres).index(actual["Responsable"]) if actual["Responsable"] in nombres else 0)
            estado = st.selectbox("Estado", ["PENDIENTE", "EN PROCESO", "FINALIZADA"], index=["PENDIENTE", "EN PROCESO", "FINALIZADA"].index(actual["Estado"]) if actual["Estado"] in ["PENDIENTE", "EN PROCESO", "FINALIZADA"] else 0)
            if st.button("Guardar asignación / estado", type="primary"):
                guardar_zona_estado(sesion["IdSesion"], zona, resp, estado, usuario["Usuario"])
                st.rerun()
            nueva = st.text_input("Agregar otra zona (opcional)")
            if st.button("Agregar zona") and nueva.strip():
                if nueva.strip().casefold() in d["Zona"].astype(str).str.casefold().tolist():
                    st.warning("La zona ya existe.")
                else:
                    hoja_control(HOJA_ZONAS, HEADERS_ZONAS).append_row([sesion["IdSesion"], nueva.strip(), "", "PENDIENTE", "", "", usuario["Usuario"]], value_input_option="RAW")
                    cargar_zonas.clear()
                    st.rerun()
    mias = d[(d["Responsable"].astype(str).str.casefold() == str(usuario["Usuario"]).casefold()) | admin]
    if not mias.empty:
        st.subheader("Mis zonas")
        zona_elegida = st.selectbox("Selecciona la zona de conteo", ["— Sin zona (inventario general) —"] + mias[mias["Estado"] != "FINALIZADA"]["Zona"].tolist())
        if st.button("Trabajar en esta zona", type="primary"):
            if not zona_elegida.startswith("—"):
                rz = d[d["Zona"] == zona_elegida].iloc[-1]
                if rz["Estado"] == "PENDIENTE":
                    guardar_zona_estado(sesion["IdSesion"], zona_elegida, rz["Responsable"], "EN PROCESO", usuario["Usuario"])
            st.session_state.zona_activa = "" if zona_elegida.startswith("—") else zona_elegida
            st.session_state.producto_pendiente = None
            st.session_state.pagina = "Inventario"
            st.rerun()
        zfinal = st.selectbox("Finalizar una de mis zonas", ["—"] + mias[mias["Estado"] != "FINALIZADA"]["Zona"].tolist())
        if zfinal != "—" and st.checkbox("Confirmo que terminé de revisar esta zona") and st.button("Finalizar zona"):
            r = d[d["Zona"] == zfinal].iloc[-1]
            guardar_zona_estado(sesion["IdSesion"], zfinal, r["Responsable"], "FINALIZADA", usuario["Usuario"])
            if st.session_state.get("zona_activa") == zfinal:
                st.session_state.zona_activa = ""
            st.rerun()


def pantalla_sesion():
    header("Sesiones de inventario", "Abre, controla y cierra jornadas de conteo")
    usuario = st.session_state.usuario
    sesion = obtener_sesion_abierta()

    if sesion:
        st.markdown(
            f"<div class='card'><b>🟢 Sesión activa</b><br><br><b>{safe_text(sesion['NombreSesion'])}</b><br>" \
            f"ID: {safe_text(sesion['IdSesion'])}<br>Sucursal: {safe_text(sesion['Sucursal'])}<br>" \
            f"Inicio: {safe_text(sesion['FechaInicio'])}<br>{badge('ABIERTA')}</div>",
            unsafe_allow_html=True,
        )
        conteos = cargar_conteos()
        total = contar_productos_sesion(conteos, sesion["IdSesion"])
        c1, c2 = st.columns(2)
        with c1: kpi("Productos contados", f"{total:,}", "en esta sesión")
        with c2:
            resumen = calcular_resumen(sesion["IdSesion"])
            kpi("Desfase neto", formato_soles(resumen["DesfaseNeto"]), "faltantes - sobrantes")

        m = metricas_cobertura(sesion["IdSesion"], sesion["Sucursal"])
        st.progress(m["cobertura"] / 100, text=f"Cobertura {m['cobertura']:.1f}% · {m['contados']:,}/{m['total']:,} verificados")
        a, b, c = st.columns(3)
        with a: kpi("Pendientes", f"{m['pendientes']:,}", "sin conteo físico")
        with b: kpi("Ceros verificados", f"{m['ceros']:,}", "comprobados")
        with c: kpi("Exactitud", f"{m['exactitud']:.1f}%", "de los contados")
        if m["pendientes"]:
            st.warning(f"Se puede cerrar parcialmente, pero {m['pendientes']:,} productos quedarán pendientes, no como faltantes.")
        observacion_cierre = st.text_area("Observación de cierre", placeholder="Motivo del cierre parcial", key=f"obs_cierre_{sesion['IdSesion']}")
        confirmar_cierre = st.checkbox("Confirmo el cierre y el registro de los productos pendientes", key=f"confirmar_cierre_{sesion['IdSesion']}")
        a1, a2 = st.columns(2)
        with a1:
            if st.button("📷 Continuar inventario", use_container_width=True):
                st.session_state.pagina = "Inventario"
                st.rerun()
        with a2:
            if st.button("🔒 Cerrar sesión", use_container_width=True, disabled=not confirmar_cierre):
                if m["pendientes"] and not observacion_cierre.strip():
                    st.error("Para un cierre parcial debes indicar el motivo.")
                else:
                    try:
                        resumen = calcular_resumen(sesion["IdSesion"])
                        resumen["ObservacionCierre"] = observacion_cierre.strip()
                        detalle_cierre = f"Cobertura {m['cobertura']:.1f}% · pendientes {m['pendientes']} · {observacion_cierre.strip()}"
                        if not cerrar_sesion(sesion["IdSesion"], detalle_cierre):
                            st.error("No se encontró la sesión para cerrar.")
                        else:
                            resumen["Estado"] = "CERRADA"
                            guardar_resumen(resumen)
                            st.success("Sesión cerrada; pendientes conservados en el universo de la sesión.")
                            st.rerun()
                    except Exception as exc:
                        mostrar_error_google(exc, "cierre de sesión")
    else:
        st.markdown("<div class='card'><b>ℹ️ No hay una sesión abierta.</b><br>Crea una para comenzar el conteo físico.</div>", unsafe_allow_html=True)
        with st.form("crear_sesion"):
            nombre = st.text_input("Nombre de la sesión", placeholder="Ej. Inventario general septiembre")
            c1, c2 = st.columns(2)
            sucursal = c1.text_input("Sucursal", placeholder="Ej. Tarapoto")
            observacion = c2.text_input("Observación", placeholder="Opcional")
            crear = st.form_submit_button("➕ Crear sesión", use_container_width=True)
            if crear:
                if not nombre.strip() or not sucursal.strip():
                    st.error("Ingresa nombre de sesión y sucursal.")
                else:
                    try:
                        crear_sesion(nombre, sucursal, usuario, observacion)
                        st.success("Sesión creada correctamente.")
                        st.rerun()
                    except Exception as exc:
                        mostrar_error_google(exc, "creación de sesión")


def pantalla_scanner(sesion=None):
    header("Escanear producto", "Usa la cámara del celular o ingresa el código manualmente")

    c_mode, c_stats = st.columns([2, 1])
    with c_mode:
        st.markdown(
            "<div class='mobile-note'>📱 Permite el acceso a la cámara. Apunta al código de barras "
            "dentro del recuadro — el sonido y la vibración confirman una lectura correcta.</div>",
            unsafe_allow_html=True,
        )
    if sesion:
        conteos = cargar_conteos()
        n = contar_productos_sesion(conteos, sesion["IdSesion"])
        with c_stats:
            kpi("Contados", f"{n:,}", "en esta sesión")

    try:
        from streamlit_qrcode_scanner import qrcode_scanner
        codigo = qrcode_scanner(key="premium_barcode_scanner")
        if codigo:
            codigo = limpiar_codigo(codigo)
            if codigo and codigo != st.session_state.get("ultimo_codigo_scan", ""):
                st.session_state.ultimo_codigo_scan = codigo
                st.session_state.codigo_pendiente = codigo
                sonido_confirmacion()
                st.rerun()
    except ImportError:
        st.warning("El escáner no está instalado. Agrega `streamlit-qrcode-scanner` a requirements.txt.")
    except Exception as exc:
        st.warning("No se pudo iniciar la cámara. Puedes utilizar la búsqueda manual.")
        with st.expander("💡 ¿Problemas con la cámara?"):
            st.markdown(
                "- Asegúrate de estar usando **HTTPS** (obligatorio para acceder a la cámara).\n"
                "- Revisa que el navegador tenga **permiso de cámara** habilitado para este sitio.\n"
                "- En iPhone, usa **Safari**; en Android, **Chrome** funciona mejor.\n"
                "- Si la cámara está siendo usada por otra app, ciérrala e intenta de nuevo."
            )
            st.code(str(exc))

    st.divider()
    with st.form("form_codigo_manual", clear_on_submit=True):
        codigo_manual = st.text_input(
            "Código de barras / código de producto",
            placeholder="Escanea o escribe el código y presiona Enter",
        )
        buscar = st.form_submit_button("🔎 Buscar código", use_container_width=True)
    if buscar and codigo_manual.strip():
        st.session_state.codigo_pendiente = limpiar_codigo(codigo_manual)
        st.rerun()

    if st.button("🔎 No puedo escanear — buscar por nombre", use_container_width=True):
        st.session_state.modo_inventario = "busqueda"
        st.session_state.codigo_pendiente = ""
        st.rerun()

    if sesion:
        conteos = cargar_conteos()
        if not conteos.empty:
            propios = conteos[conteos["IdSesion"].astype(str) == str(sesion["IdSesion"])].tail(5).iloc[::-1]
            if not propios.empty:
                ui_seccion("Últimos escaneados")
                for _, fila in propios.iterrows():
                    st.markdown(
                        f"<div class='card' style='padding:10px 14px;margin-bottom:8px;display:flex;"
                        f"justify-content:space-between;align-items:center;'>"
                        f"<span><b>{safe_text(fila['Producto'])}</b> "
                        f"<span style='color:#6b7280;font-size:.78rem'>({safe_text(fila['FechaHora'])})</span></span>"
                        f"{'' if conteo_ciego_usuario(st.session_state.usuario) else badge(fila['TipoDiferencia'])}</div>",
                        unsafe_allow_html=True,
                    )


def pantalla_producto(producto, sesion):
    codigo = limpiar_codigo(producto.get("CodigoBarras", "")) or limpiar_codigo(producto.get("CodigoProducto", "")) or str(producto.get("Producto", ""))
    zona = st.session_state.get("zona_activa", "")
    zona_habilitada = zona_usuario(sesion, st.session_state.usuario) if zona else None
    if zona and zona_habilitada is None:
        st.error("La zona seleccionada está finalizada o no te corresponde. Ve a Zonas.")
        return
    previo_zona = ultimo_conteo_zona(sesion["IdSesion"], zona, producto) if zona_habilitada else None
    ya_contado = (previo_zona is not None) if zona_habilitada else (ultimo_conteo_producto(sesion["IdSesion"], producto) is not None)
    # El reconteo solo aplica a productos ya contados (evita etiquetar mal si la bandera quedó activa).
    es_reconteo = bool(st.session_state.get("reconteo_activo", False)) and ya_contado
    previo = previo_zona if zona_habilitada else ultimo_conteo_producto(sesion["IdSesion"], producto)

    if zona_habilitada:
        st.info(f"📍 Conteo en: **{zona}** · Las cantidades de distintas zonas se sumarán.")
    if ya_contado and not es_reconteo:
        st.warning("⚠️ Este producto ya fue contado en esta sesión.")
        if previo and not conteo_ciego_usuario(st.session_state.usuario):
            st.info(
                f"Último conteo: {limpiar_numero(previo.get('StockFisico', 0)):,.0f} unidades "
                f"por {previo.get('NombreUsuario', '')} · {previo.get('FechaHora', '')}."
            )
        critico = es_diferencia_critica(previo.get("StockSistema", 0), previo.get("StockFisico", 0), previo.get("CostoUnitario", 0)) if previo else False
        if critico and not conteo_ciego_usuario(st.session_state.usuario):
            st.error("Diferencia significativa: se recomienda reconteo independiente.")
            if not solicitud_pendiente(sesion["IdSesion"], producto):
                if st.button("Solicitar reconteo por diferencia", key=f"solicitud_{codigo}"):
                    solicitar_reconteo(sesion, producto, st.session_state.usuario, "Diferencia crítica detectada")
                    st.rerun()
            else:
                st.warning("Reconteo pendiente de resolución.")
        c_re, c_back = st.columns(2)
        with c_re:
            if st.button("🔁 Hacer reconteo", type="primary", use_container_width=True):
                st.session_state.reconteo_activo = True
                st.rerun()
        with c_back:
            if st.button("↩️ Volver al escáner", use_container_width=True):
                st.session_state.producto_pendiente = None
                st.session_state.codigo_pendiente = ""
                st.rerun()
        return

    if es_reconteo:
        header("Reconteo físico", "Verifica nuevamente la cantidad: el último conteo será reemplazado en los resultados")
        if previo and not conteo_ciego_usuario(st.session_state.usuario):
            st.info(
                f"Conteo anterior: {limpiar_numero(previo.get('StockFisico', 0)):,.0f} unidades "
                f"por {previo.get('NombreUsuario', '')} · {previo.get('FechaHora', '')}. "
                "El historial se conserva en el detalle."
            )
    else:
        header("Conteo físico", "Compara el stock del sistema con el conteo real")
    st.markdown(
        f"""
        <div class='product-card'>
            <div class='product-name'>{safe_text(producto.get('Producto','Producto sin nombre'))}</div>
            <div class='product-meta'>Código: {safe_text(producto.get('CodigoProducto',''))} · Barras: {safe_text(codigo)}</div>
            <div class='product-meta'>Categoría: {safe_text(producto.get('Categoria',''))} · Marca: {safe_text(producto.get('Marca',''))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    ciego = conteo_ciego_usuario(st.session_state.usuario)
    stock_txt = "🔒 Oculto" if ciego else f"{limpiar_numero(producto.get('StockSistema',0)):,.0f}"
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"<div class='stock-box'><div class='stock-label'>Stock sistema</div><div class='stock-number'>{stock_txt}</div></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='stock-box'><div class='stock-label'>Costo unitario</div><div class='stock-number'>{formato_soles(producto.get('CostoUnitario',0))}</div></div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div class='stock-box'><div class='stock-label'>Sucursal</div><div class='stock-number' style='font-size:1rem'>{safe_text(producto.get('Sucursal',''))}</div></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    fisico = st.number_input(
        "Cantidad física encontrada",
        min_value=0.0,
        value=0.0,
        step=1.0,
        key=f"fisico_{codigo}_{sesion['IdSesion']}",
    )
    diferencia = fisico - limpiar_numero(producto.get("StockSistema", 0))
    costo = limpiar_numero(producto.get("CostoUnitario", 0))

    if zona_habilitada:
        st.caption("El faltante o sobrante se calcula al consolidar todas las zonas; aquí registras solo lo encontrado en esta zona.")
    if diferencia < 0:
        tipo = "FALTANTE"
        if not ciego and not zona_habilitada:
            st.error(f"🔴 Faltante: {abs(diferencia):,.0f} unidades · {formato_soles(abs(diferencia) * costo)}")
    elif diferencia > 0:
        tipo = "SOBRANTE"
        if not ciego and not zona_habilitada:
            st.success(f"🟢 Sobrante: {diferencia:,.0f} unidades · {formato_soles(diferencia * costo)}")
    else:
        tipo = "OK"
        if not ciego and not zona_habilitada:
            st.success("🟢 Stock exacto: no existe diferencia.")
    if ciego:
        st.info("🔒 Conteo ciego: el resultado se calculará al guardar.")

    confirmado = True
    if not ciego and not zona_habilitada and es_diferencia_critica(producto.get("StockSistema", 0), fisico, costo):
        st.warning(
            "⚠️ La cantidad difiere de forma significativa del sistema. Revisa estantes, almacén y otras "
            "ubicaciones, y verifica que el producto sea el correcto antes de guardar."
        )
        confirmado = st.checkbox(
            "Confirmo que el conteo es correcto",
            key=f"confirma_dif_{codigo}_{sesion['IdSesion']}",
        )

    verificacion = st.checkbox("He verificado físicamente este producto y confirmo la cantidad indicada (incluido cero).", key=f"verificado_{sesion['IdSesion']}_{codigo}")
    metodo = st.selectbox("Método de conteo", ["Escáner", "Búsqueda manual", "Código manual"])
    observacion = st.text_area("Observación", placeholder="Opcional")

    if not ya_contado:
        with st.expander("🔎 No encuentro este producto"):
            motivo_no_localizado = st.text_area("Dónde se buscó / motivo", key=f"motivo_nl_{sesion['IdSesion']}_{codigo}")
            if st.button("Registrar como no localizado", key=f"nl_{sesion['IdSesion']}_{codigo}"):
                try:
                    registrar_no_localizado(sesion, producto, motivo_no_localizado)
                    st.session_state.producto_pendiente = None
                    st.session_state.codigo_pendiente = ""
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
    c1, c2 = st.columns(2)
    with c1:
        motivo_valido = (not es_reconteo) or bool(observacion.strip())
        if es_reconteo and not motivo_valido:
            st.caption("El motivo de corrección es obligatorio para un reconteo.")
        if st.button("💾 Guardar conteo", type="primary", use_container_width=True, disabled=not (confirmado and verificacion and motivo_valido)):
            try:
                if zona_habilitada:
                    guardar_conteo_zona(sesion, st.session_state.usuario, producto, fisico, metodo, observacion, es_reconteo)
                else:
                    guardar_conteo(sesion, st.session_state.usuario, producto, fisico, metodo, observacion, es_reconteo)
                st.success("Cantidad guardada en la zona." if zona_habilitada else (f"{'Reconteo' if es_reconteo else 'Conteo'} guardado correctamente" if ciego else f"{'Reconteo' if es_reconteo else 'Conteo'} guardado: {tipo}"))
                sonido_confirmacion()
                st.session_state.reconteo_activo = False
                st.session_state.producto_pendiente = None
                st.session_state.codigo_pendiente = ""
                st.session_state.ultimo_codigo_scan = ""
                st.rerun()
            except Exception as exc:
                if isinstance(exc, ValueError):
                    st.error(str(exc))
                else:
                    mostrar_error_google(exc, "guardar conteo")
    with c2:
        if st.button("↩️ Cancelar", use_container_width=True):
            st.session_state.reconteo_activo = False
            st.session_state.producto_pendiente = None
            st.session_state.codigo_pendiente = ""
            st.rerun()


def pantalla_busqueda(sesion):
    header("Buscar producto", "Encuentra el producto por nombre, código, descripción o marca")
    texto = st.text_input("Buscar", placeholder="Ej. Inca Kola, 775..., Coca...")

    inv_completo = cargar_inventario()
    c1, c2 = st.columns(2)
    with c1:
        categorias = ["Todas"] + sorted([c for c in inv_completo["Categoria"].unique() if c]) if not inv_completo.empty else ["Todas"]
        cat_sel = st.selectbox("Filtrar por categoría", categorias)
    with c2:
        sucursales = ["Todas"] + sorted([s for s in inv_completo["Sucursal"].unique() if s]) if not inv_completo.empty else ["Todas"]
        suc_sel = st.selectbox("Filtrar por sucursal", sucursales)

    df = buscar_productos(texto)
    if cat_sel != "Todas":
        df = df[df["Categoria"] == cat_sel]
    if suc_sel != "Todas":
        df = df[df["Sucursal"] == suc_sel]

    if df.empty:
        st.info("No se encontraron productos.")
    else:
        st.caption(f"Mostrando {len(df):,} resultado(s).")
        for idx, producto in df.iterrows():
            codigo = limpiar_codigo(producto.get("CodigoBarras", ""))
            nombre = str(producto.get("Producto", "Sin nombre"))
            st.markdown(
                f"<div class='card'><b>{safe_text(nombre)}</b><br><span style='color:#6b7280;font-size:.8rem'>Código: {safe_text(producto.get('CodigoProducto',''))} · Barras: {safe_text(codigo)} · Stock: {"Oculto" if conteo_ciego_usuario(st.session_state.usuario) else f"{limpiar_numero(producto.get('StockSistema',0)):,.0f}"}</span></div>",
                unsafe_allow_html=True,
            )
            if st.button("Seleccionar", key=f"sel_prod_{idx}_{codigo}", use_container_width=True):
                st.session_state.producto_pendiente = producto.to_dict()
                st.session_state.codigo_pendiente = codigo
                st.session_state.modo_inventario = "producto"
                st.rerun()

    if st.button("📷 Volver al escáner", use_container_width=True):
        st.session_state.modo_inventario = "scanner"
        st.rerun()


def pantalla_inventario():
    sesion = obtener_sesion_abierta()
    if not sesion:
        header("Inventario físico", "Primero debes abrir una sesión")
        st.warning("No existe una sesión abierta.")
        if st.button("🧾 Ir a Sesión", use_container_width=True):
            st.session_state.pagina = "Sesión"
            st.rerun()
        return

    zona_actual = st.session_state.get("zona_activa", "")
    if zona_actual:
        st.info(f"📍 Zona activa: **{zona_actual}**")
        if st.button("Cambiar de zona"):
            st.session_state.pagina = "Zonas"
            st.rerun()
    elif not zonas_sesion(sesion["IdSesion"]).empty:
        st.warning("Estás en modo general (sin zona). Para registrar cantidades por góndola, selecciona una zona en el menú Zonas.")
    m = metricas_cobertura(sesion["IdSesion"], sesion["Sucursal"])
    contados, total, porcentaje = m["contados"], m["total"], m["cobertura"]

    st.markdown(
        f"<div class='mobile-note'>🧾 <b>{safe_text(sesion['NombreSesion'])}</b> · {safe_text(sesion['Sucursal'])} · {contados:,}/{total:,} productos · {porcentaje:.1f}%</div>",
        unsafe_allow_html=True,
    )
    st.progress(min(porcentaje / 100, 1.0))
    with st.expander("⭐ Prioridad: pendientes del inventario anterior"):
        try:
            previos = pendientes_anteriores(sesion)
            if previos.empty:
                st.info("No hay pendientes históricos aplicables, o ya fueron verificados.")
            else:
                st.caption(f"{len(previos)} productos pendientes del inventario anterior, aún sin verificar en esta sesión.")
                columnas_prioridad = ["Producto", "CodigoProducto", "CodigoBarras", "Categoria", "EstadoVerificacion"]
                if not conteo_ciego_usuario(st.session_state.usuario):
                    columnas_prioridad.insert(4, "StockSistema")
                st.dataframe(previos[columnas_prioridad], hide_index=True, use_container_width=True)
                st.download_button("Descargar prioridades (Excel)", data=exportar_excel({"Prioridad":previos[columnas_prioridad]}), file_name=f"prioridades_{sesion['IdSesion']}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except Exception as exc:
            st.warning(f"No fue posible cargar las prioridades históricas: {exc}")

    if st.session_state.get("producto_pendiente"):
        pantalla_producto(st.session_state.producto_pendiente, sesion)
        return

    codigo = st.session_state.get("codigo_pendiente", "")
    if codigo:
        producto = buscar_por_codigo(codigo)
        if producto:
            st.session_state.producto_pendiente = producto
            st.rerun()
        else:
            st.error(f"No encontramos el código **{codigo}** en el inventario.")
            if st.button("🔎 Buscar por nombre", use_container_width=True):
                st.session_state.modo_inventario = "busqueda"
                st.session_state.codigo_pendiente = ""
                st.rerun()
            if st.button("↩️ Volver", use_container_width=True):
                st.session_state.codigo_pendiente = ""
                st.rerun()
            return

    modo = st.session_state.get("modo_inventario", "scanner")
    if modo == "busqueda":
        pantalla_busqueda(sesion)
    else:
        pantalla_scanner(sesion)

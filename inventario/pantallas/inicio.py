"""Dashboard de inicio."""
import streamlit as st
import streamlit.components.v1 as components
from inventario.contexto import cfg, moneda_fmt
from inventario.servicios import actualizar_datos, alertas_operativas, cargar_conteos, cargar_inventario, cargar_sesiones, metricas_cobertura, obtener_sesion_abierta
from inventario.ui.componentes import _ir_a, header, kpi, ui_avatar, ui_callout, ui_chip, ui_seccion
from inventario.utilidades import formato_soles, safe_text, saludo_actual


def pantalla_inicio():
    usuario = st.session_state.usuario
    nombre = str(usuario.get("NombreCompleto", "")).strip() or str(usuario.get("Usuario", ""))
    primer_nombre = nombre.split()[0] if nombre.split() else ""
    header("Dashboard de Inventario", f"{saludo_actual()}, {nombre} · Resumen de existencias, conteos y compras")

    inv = cargar_inventario()
    conteos = cargar_conteos()
    sesiones = cargar_sesiones()

    sesion_actual = obtener_sesion_abierta()
    estado_txt, estado_chip, pct, val_prog = "Sin inventario activo", "neutral", 0, "—"
    if sesion_actual:
        m = metricas_cobertura(sesion_actual["IdSesion"], sesion_actual["Sucursal"])
        pct = int(max(0, min(100, m["cobertura"]))) if m["total"] else 0
        estado_txt = f"Inventario en curso · {safe_text(sesion_actual['NombreSesion'])}"
        estado_chip = "ok"
        val_prog = f"{m['cobertura']:.1f}% · {m['pendientes']} pendientes · Exactitud {m['exactitud']:.1f}%"

    hc1, hc2 = st.columns([1.5, 1])
    with hc1:
        st.markdown(
            f'<div class="tp-hero"><div class="tp-hero-top">{ui_avatar(nombre, 54)}<div>'
            f'<div class="tp-hero-hi">Hola, {safe_text(primer_nombre)}</div>{ui_chip(estado_txt, estado_chip)}</div></div>'
            f'<div class="tp-prog-lbl"><span>Cobertura del inventario</span><span>{val_prog}</span></div>'
            f'<div class="tp-prog"><i style="width:{pct}%"></i></div></div>',
            unsafe_allow_html=True,
        )
    with hc2:
        components.html("""<body style="margin:0;font-family:Montserrat,Arial,sans-serif"><div style="box-sizing:border-box;height:132px;background:#fff;border:1px solid #E3E6EC;border-radius:20px;display:flex;flex-direction:column;align-items:center;justify-content:center;box-shadow:0 1px 3px rgba(15,23,42,.05)"><div id="t" style="font-size:2.3rem;font-weight:700;color:#0F172A;font-variant-numeric:tabular-nums">--:--:--</div><div id="d" style="font-size:.8rem;color:#64748B;font-weight:600;text-transform:capitalize"></div></div><script>function u(){var n=new Date();document.getElementById("t").textContent=n.toLocaleTimeString("es-PE",{timeZone:"America/Lima",hour12:false});document.getElementById("d").textContent=n.toLocaleDateString("es-PE",{timeZone:"America/Lima",weekday:"long",day:"numeric",month:"long"})}u();setInterval(u,1000)</script></body>""".replace("America/Lima", cfg().zona_horaria).replace("es-PE", cfg().locale), height=134)
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    stock_total = float(inv["StockSistema"].sum()) if not inv.empty else 0
    valor_inventario = float((inv["StockSistema"] * inv["CostoUnitario"]).sum()) if not inv.empty else 0
    activos = int((inv["Estado"].str.upper().isin(["ACTIVO", "ACTIVA", "1", "SI", "SÍ"])).sum()) if not inv.empty else len(inv)
    sesiones_abiertas = int((sesiones["Estado"].str.upper() == "ABIERTA").sum()) if not sesiones.empty else 0

    k1, k2, k3, k4 = st.columns(4)
    with k1: kpi("Productos", f"{len(inv):,}", f"{activos:,} activos")
    with k2: kpi("Stock sistema", f"{stock_total:,.0f}", "unidades")
    with k3: kpi("Valor inventario", formato_soles(valor_inventario), "a costo")
    with k4: kpi("Sesiones abiertas", str(sesiones_abiertas), "en curso")
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    c_refresh, c_info = st.columns([1, 3])
    with c_refresh:
        if st.button("Actualizar datos", use_container_width=True, key="inicio_actualizar"):
            actualizar_datos()
            st.rerun()
    with c_info:
        ui_callout("Los datos se mantienen en caché para reducir lecturas a Google Sheets. Actualiza manualmente cuando necesites información reciente.")

    alertas = alertas_operativas(inv, sesiones)
    if alertas:
        ui_seccion("Alertas", "Puntos que requieren tu atención")
        for texto_alerta in alertas:
            ui_callout(texto_alerta, "warn")

    ui_seccion("Acciones rápidas", "Atajos a las tareas más frecuentes")
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        st.button("Nueva sesión", use_container_width=True, key="qa_sesion", on_click=_ir_a, args=("Sesión",))
    with a2:
        st.button("Iniciar inventario", use_container_width=True, key="qa_inventario", type="primary", on_click=_ir_a, args=("Inventario",))
    with a3:
        st.button("Ver resultados", use_container_width=True, key="qa_resultados", on_click=_ir_a, args=("Resultados",))
    with a4:
        st.button("Consultar precio", use_container_width=True, key="qa_precios", on_click=_ir_a, args=("Precios",))

    ui_seccion("Últimos conteos", "Los 10 registros más recientes")
    if conteos.empty:
        st.info("Todavía no existen conteos registrados.")
    else:
        ult = conteos.tail(10).iloc[::-1].copy()
        mostrar = ult[["FechaHora", "NombreUsuario", "Producto", "StockSistema", "StockFisico", "Diferencia", "TipoDiferencia", "CostoDiferencia"]].copy()
        mostrar.columns = ["Fecha", "Usuario", "Producto", "Sistema", "Físico", "Dif.", "Resultado", "Impacto"]
        st.dataframe(
            mostrar,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Impacto": st.column_config.NumberColumn(format=moneda_fmt()),
                "Sistema": st.column_config.NumberColumn(format="%.0f"),
                "Físico": st.column_config.NumberColumn(format="%.0f"),
                "Dif.": st.column_config.NumberColumn(format="%.0f"),
            },
        )

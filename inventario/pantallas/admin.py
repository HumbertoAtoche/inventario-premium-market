"""Administración de usuarios, auditoría y conteo ciego."""
import streamlit as st
from inventario.servicios import cargar_auditoria, cargar_control_reconteos, cargar_inventario, cargar_sesiones, cargar_usuarios, configurar_conteo_ciego, conteo_ciego_usuario, crear_usuario
from inventario.ui.componentes import header, kpi
from inventario.utilidades import exportar_excel, formato_soles, mostrar_error_google


def pantalla_admin():
    header("Administración", "Usuarios, inventario y control de sesiones")
    tab1, tab2, tab3, tab4 = st.tabs(["👤 Usuarios", "📦 Inventario", "🧾 Sesiones", "🛡️ Auditoría"])

    with tab1:
        st.markdown("### Conteo ciego por usuario")
        st.caption("Los contadores configurados no verán stock de sistema, diferencia ni conteos anteriores durante la captura. Los administradores conservan acceso de supervisión.")
        usuarios_cfg = cargar_usuarios()
        if not usuarios_cfg.empty:
            candidatos = usuarios_cfg[~usuarios_cfg["Rol"].astype(str).str.upper().isin(["ADMIN", "SUPERVISOR"])]["Usuario"].astype(str).tolist()
            if candidatos:
                seleccionado_cfg = st.selectbox("Contador", candidatos, key="cfg_contador")
                actual_cfg = conteo_ciego_usuario({"Usuario":seleccionado_cfg,"Rol":"CONTADOR"})
                habilitar_cfg = st.checkbox("Habilitar conteo ciego", value=actual_cfg, key=f"cfg_ciego_{seleccionado_cfg}")
                if st.button("Guardar configuración de conteo ciego"):
                    try:
                        configurar_conteo_ciego(seleccionado_cfg, habilitar_cfg, st.session_state.usuario.get("Usuario", ""))
                        st.success("Configuración guardada.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
        st.divider()
        usuarios = cargar_usuarios()
        if usuarios.empty:
            st.info("No existen usuarios.")
        else:
            vista = usuarios[["Usuario", "NombreCompleto", "Rol", "Estado"]].copy()
            st.dataframe(vista, use_container_width=True, hide_index=True)

        st.markdown("### Crear usuario")
        with st.form("crear_usuario_admin"):
            c1, c2 = st.columns(2)
            usuario = c1.text_input("Usuario")
            nombre = c2.text_input("Nombre completo")
            c3, c4 = st.columns(2)
            rol = c3.selectbox("Rol", ["CONTADOR", "ADMIN"])
            password = c4.text_input("Contraseña", type="password")
            confirmar = st.text_input("Confirmar contraseña", type="password")
            if st.form_submit_button("➕ Crear usuario", use_container_width=True):
                if not usuario.strip() or not nombre.strip() or not password:
                    st.error("Completa todos los campos.")
                elif password != confirmar:
                    st.error("Las contraseñas no coinciden.")
                elif len(password) < 10:
                    st.error("La contraseña debe tener al menos 10 caracteres.")
                else:
                    try:
                        crear_usuario(usuario, nombre, rol, password)
                        st.success("Usuario creado correctamente.")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
                    except Exception as exc:
                        mostrar_error_google(exc, "creación de usuario")

    with tab2:
        inv = cargar_inventario()
        k1, k2, k3 = st.columns(3)
        with k1: kpi("Productos", f"{len(inv):,}", "registros")
        with k2: kpi("Stock", f"{float(inv['StockSistema'].sum()) if not inv.empty else 0:,.0f}", "unidades")
        with k3: kpi("Valor", formato_soles((inv["StockSistema"] * inv["CostoUnitario"]).sum() if not inv.empty else 0), "a costo")
        if not inv.empty:
            st.dataframe(inv, use_container_width=True, hide_index=True)
            colcsv, colxlsx = st.columns(2)
            with colcsv:
                st.download_button(
                    "📥 Exportar inventario (CSV)",
                    data=inv.to_csv(index=False).encode("utf-8-sig"),
                    file_name="inventario_completo.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with colxlsx:
                try:
                    st.download_button(
                        "📊 Exportar inventario (Excel)",
                        data=exportar_excel({"Inventario": inv}),
                        file_name="inventario_completo.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                except Exception:
                    st.caption("Instala `openpyxl` para exportar a Excel.")

    with tab3:
        st.markdown("### Solicitudes de reconteo")
        solicitudes = cargar_control_reconteos()
        if solicitudes.empty:
            st.caption("Sin solicitudes de reconteo registradas.")
        else:
            st.dataframe(solicitudes.sort_values("FechaSolicitud", ascending=False), hide_index=True, use_container_width=True)
        st.divider()
        sesiones = cargar_sesiones()
        if sesiones.empty:
            st.info("No existen sesiones.")
        else:
            st.dataframe(sesiones.sort_values("FechaInicio", ascending=False), use_container_width=True, hide_index=True)

    with tab4:
        aud = cargar_auditoria()
        if aud.empty:
            st.info("Aún no hay eventos registrados. La bitácora guarda inicios de sesión, creación y cierre de sesiones, reconteos y altas de usuarios.")
        else:
            aud = aud.sort_values("FechaHora", ascending=False)
            acciones = ["Todas"] + sorted([a for a in aud["Accion"].astype(str).unique() if a])
            accion_sel = st.selectbox("Filtrar por acción", acciones)
            if accion_sel != "Todas":
                aud = aud[aud["Accion"].astype(str) == accion_sel]
            st.dataframe(aud.head(500), use_container_width=True, hide_index=True)
            st.download_button(
                "📥 Descargar bitácora (CSV)",
                data=aud.to_csv(index=False).encode("utf-8-sig"),
                file_name="auditoria_inventario.csv",
                mime="text/csv",
                use_container_width=True,
            )

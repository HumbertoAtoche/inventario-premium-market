"""Respaldos (descarga y restauración), permisos por rol y estado de la plataforma."""
import pandas as pd
import streamlit as st
from inventario.contexto import backend, cfg, permiso
from inventario.nucleo import permisos, tiempo
from inventario.nucleo.esquemas import TABLAS
from inventario.servicios import actualizar_datos, registrar_auditoria
from inventario.ui.componentes import header, ui_callout, ui_seccion
from inventario.utilidades import exportar_excel, mostrar_error_google


def _exportar_todo():
    b, contenido = backend(), {}
    for clave, (nombre, cols) in TABLAS.items():
        if not b.existe(nombre):
            continue
        filas = b.tabla(nombre).get_all_values()
        if not filas:
            continue
        ancho = max(len(x) for x in filas)
        df = pd.DataFrame([r + [""] * (ancho - len(r)) for r in filas[1:]], columns=[(v or f"Col{i}") for i, v in enumerate(filas[0] + [""] * (ancho - len(filas[0])))])
        if clave == "usuarios" and "Password" in df.columns:
            df = df.drop(columns=["Password"])          # las contraseñas nunca salen del sistema
        contenido[nombre] = df
    return contenido


def _restaurar(archivo):
    """Restaura tablas desde un respaldo XLSX (reemplaza el contenido de cada tabla incluida). Usuarios nunca se restaura."""
    libro = pd.read_excel(archivo, sheet_name=None, dtype=str)
    por_nombre = {n: (k, cols) for k, (n, cols) in TABLAS.items()}
    aplicadas = []
    for hoja, df in libro.items():
        if hoja not in por_nombre or por_nombre[hoja][0] == "usuarios":
            continue
        df = df.fillna("")
        backend().tabla(hoja, por_nombre[hoja][1]).reemplazar_todo([list(df.columns)] + df.values.tolist())
        aplicadas.append(f"{hoja} ({len(df)} filas)")
    return aplicadas


def pantalla_seguridad_y_respaldo():
    header("Seguridad y respaldos", "Resguardo de datos y control de accesos")
    if not permiso("seguridad"):
        st.error("Solo administración puede acceder.")
        return
    ui_seccion("Copia de seguridad", "Descarga todas las tablas en un Excel. No incluye contraseñas.")
    if st.button("Preparar respaldo", key="seg_preparar"):
        try:
            contenido = _exportar_todo()
            st.session_state["respaldo_xlsx"] = exportar_excel(contenido)
            registrar_auditoria("RESPALDO_GENERADO", f"Tablas: {len(contenido)}")
            st.success("Respaldo generado. Descárgalo y guárdalo en un lugar seguro.")
        except Exception as exc:
            mostrar_error_google(exc, "el respaldo")
    if st.session_state.get("respaldo_xlsx"):
        st.download_button("Descargar respaldo XLSX", st.session_state["respaldo_xlsx"], file_name=f"respaldo_{cfg().empresa_id}_{tiempo.ahora():%Y%m%d_%H%M}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="seg_descargar")
    ui_seccion("Restaurar o migrar", "Carga un respaldo para recuperar datos o para llevarlos a otro almacenamiento (por ejemplo, de Google Sheets a una base de datos)")
    ui_callout("Restaurar REEMPLAZA el contenido de cada tabla incluida en el archivo. Los usuarios no se restauran (el respaldo no lleva contraseñas). Haz antes un respaldo del estado actual.", "warn")
    arch = st.file_uploader("Respaldo (.xlsx) generado por esta aplicación", type=["xlsx"], key="seg_restaurar_archivo")
    if arch is not None:
        try:
            nombres = [h for h in pd.ExcelFile(arch).sheet_names if h in {n for n, _ in TABLAS.values()} and h != TABLAS["usuarios"][0]]
        except Exception as exc:
            st.error(f"No pude leer el archivo: {exc}")
            nombres = []
        if nombres:
            st.write("Tablas que se restaurarán: " + ", ".join(nombres))
            frase = st.text_input("Escribe RESTAURAR para confirmar", key="seg_confirmar")
            if st.button("Restaurar ahora", disabled=frase.strip() != "RESTAURAR", key="seg_restaurar_go"):
                try:
                    aplicadas = _restaurar(arch)
                    registrar_auditoria("RESTAURACION", "; ".join(aplicadas))
                    actualizar_datos()
                    st.success("Restauración completa: " + "; ".join(aplicadas))
                except Exception as exc:
                    mostrar_error_google(exc, "la restauración")
        elif arch is not None:
            st.warning("El archivo no contiene tablas reconocibles.")
    ui_seccion("Roles y permisos")
    filas = [{"Permiso": desc, **{r: ("✔" if p in perms else "") for r, perms in permisos.ROLES.items()}} for p, desc in permisos.PERMISOS.items()]
    st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)
    ui_seccion("Estado de la plataforma")
    c = cfg()
    st.write(f"Autenticación: PBKDF2; bloqueo tras {c.max_intentos_login} intentos por {c.bloqueo_login_seg // 60} min (en el servidor). Sesión máxima {c.sesion_max_horas} h, cierre tras {c.inactividad_min} min sin actividad.")
    st.write("Auditoría: operaciones principales en la tabla Auditoria; cada error recibe un código ERR-XXXXXXXX en el registro del servidor.")
    if backend().nombre == "sheets":
        st.warning("Google Sheets no es transaccional: si dos personas modifican el MISMO producto en el mismo instante, una escritura puede pisar a la otra. "
                   "Para operaciones muy concurrentes, configura `datos_backend: sql` (PostgreSQL).")
    else:
        st.info(f"Almacenamiento activo: {backend().nombre}.")

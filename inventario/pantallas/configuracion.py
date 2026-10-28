"""Configuración de la empresa: marca, moneda, zona horaria, sucursales, umbrales, módulos y seguridad."""
import re
import streamlit as st
from inventario.contexto import backend, cfg, permiso, servicio_config
from inventario.nucleo import imagenes
from inventario.nucleo.esquemas import TABLAS
from inventario.servicios import registrar_auditoria
from inventario.ui.componentes import header, ui_callout, ui_seccion
from inventario.utilidades import mostrar_error_google
from zoneinfo import available_timezones


def _lineas(txt):
    vistos, res = set(), []
    for l in str(txt).splitlines():
        l = l.strip()
        if l and l.casefold() not in vistos:
            vistos.add(l.casefold())
            res.append(l)
    return res


def _guardar(cambios, titulo):
    try:
        guardados = servicio_config().guardar(cambios, str(st.session_state.get("usuario", {}).get("Usuario", "SISTEMA")))
        registrar_auditoria("CONFIGURACION", f"{titulo}: {', '.join(guardados)}")
        st.success("Configuración guardada.")
        st.rerun()
    except Exception as exc:
        mostrar_error_google(exc, "la configuración")


def _tab_empresa(c):
    with st.form("cfg_empresa"):
        a, b = st.columns(2)
        with a:
            nombre = st.text_input("Nombre comercial", c.nombre)
            razon = st.text_input("Razón social", c.razon_social)
            app_titulo = st.text_input("Nombre de la app (pestaña y celular)", c.app_titulo)
            subt = st.text_input("Subtítulo del menú lateral", c.sistema_subtitulo)
        with b:
            etq = st.text_input("Etiqueta del identificador fiscal (RUC, NIT, RFC, CUIT…)", c.id_fiscal_etiqueta)
            idf = st.text_input("Identificador fiscal", c.id_fiscal)
            dev = st.text_input("Desarrollado por (pie de página)", c.desarrollado_por)
            color = st.color_picker("Color de la marca", c.color_primario)
        logo = st.file_uploader("Logo (PNG, JPG o WEBP; se reduce automáticamente)", type=["png", "jpg", "jpeg", "webp"])
        quitar = st.checkbox("Quitar el logo subido (usar el de la carpeta assets)", value=False) if c.logo_b64 else False
        st.markdown("**Pantalla de ingreso**")
        t1 = st.text_input("Título", c.login_titulo)
        t2 = st.text_input("Parte destacada del título", c.login_titulo_resaltado)
        t3 = st.text_area("Subtítulo", c.login_subtitulo, height=70)
        frases = st.text_area("Frases del día (una por línea)", "\n".join(c.frases), height=120)
        if st.form_submit_button("Guardar", type="primary"):
            cambios = {"nombre": nombre.strip() or c.nombre, "razon_social": razon, "app_titulo": app_titulo.strip() or c.app_titulo, "sistema_subtitulo": subt,
                       "id_fiscal_etiqueta": etq, "id_fiscal": idf, "desarrollado_por": dev, "color_primario": color, "login_titulo": t1,
                       "login_titulo_resaltado": t2, "login_subtitulo": t3, "frases": _lineas(frases) or c.frases}
            try:
                if logo is not None:
                    cambios["logo_b64"] = imagenes.logo_a_data_uri(logo.getvalue())
                elif quitar:
                    cambios["logo_b64"] = ""
            except Exception as exc:
                st.error(f"No pude usar esa imagen: {exc}")
                return
            _guardar(cambios, "empresa y marca")
    ui_seccion("Accesos directos del menú lateral", "Enlaces a otras aplicaciones de la empresa (ventas, asistencia…)")
    enlaces = st.data_editor(c.enlaces or [{"nombre": "", "detalle": "", "url": ""}], num_rows="dynamic", use_container_width=True, key="cfg_enlaces",
                             column_config={"nombre": "Nombre", "detalle": "Descripción", "url": "Dirección (https://…)"})
    if st.button("Guardar accesos directos", key="cfg_enlaces_ok"):
        validos = [{"nombre": str(e.get("nombre", "")).strip(), "detalle": str(e.get("detalle", "")).strip(), "url": str(e.get("url", "")).strip()}
                   for e in enlaces if str(e.get("url", "")).strip().startswith(("http://", "https://"))]
        _guardar({"enlaces": validos}, "enlaces")


def _tab_regional(c):
    zonas = sorted(available_timezones())
    locales = ["es-PE", "es-MX", "es-CO", "es-AR", "es-CL", "es-EC", "es-BO", "es-UY", "es-ES", "en-US", "pt-BR"]
    with st.form("cfg_regional"):
        a, b, c3 = st.columns(3)
        with a: simbolo = st.text_input("Símbolo de moneda", c.moneda_simbolo, max_chars=5)
        with b: codigo = st.text_input("Código de moneda (ISO)", c.moneda_codigo, max_chars=3)
        with c3: dec = st.number_input("Decimales", 0, 4, int(c.moneda_decimales))
        d, e = st.columns(2)
        with d: tz = st.selectbox("Zona horaria", zonas, index=zonas.index(c.zona_horaria) if c.zona_horaria in zonas else 0)
        with e: loc = st.selectbox("Formato regional", locales, index=locales.index(c.locale) if c.locale in locales else 0)
        if st.form_submit_button("Guardar", type="primary"):
            _guardar({"moneda_simbolo": simbolo.strip() or c.moneda_simbolo, "moneda_codigo": codigo.strip().upper(), "moneda_decimales": int(dec),
                      "zona_horaria": tz, "locale": loc}, "regional")


def _tab_operacion(c):
    with st.form("cfg_operacion"):
        a, b = st.columns(2)
        with a: sucursales = st.text_area("Sucursales (una por línea)", "\n".join(c.sucursales), height=120)
        with b: zonas = st.text_area("Zonas de conteo (una por línea)", "\n".join(c.zonas), height=120, help="Secciones físicas del local: góndola 1, almacén, etc.")
        ui_seccion("Umbrales de control")
        u1, u2, u3, u4 = st.columns(4)
        with u1: meta = st.number_input("Meta de exactitud (%)", 0.0, 100.0, float(c.meta_exactitud), step=0.5)
        with u2: monto = st.number_input(f"Diferencia que exige confirmar ({c.moneda_simbolo})", 0.0, value=float(c.umbral_dif_monto), step=10.0)
        with u3: unid = st.number_input("… o en unidades", 0, value=int(c.umbral_dif_unidades))
        with u4: pct = st.number_input("… o en %", 0.0, 100.0, float(c.umbral_dif_pct), step=1.0)
        v1, v2 = st.columns(2)
        with v1: horas = st.number_input("Alertar sesiones abiertas más de (horas)", 1, 720, int(c.horas_sesion_alerta))
        with v2: venc = st.text_input("Días de alerta de vencimiento (dos valores)", ", ".join(str(d) for d in c.dias_alerta_vencimiento))
        ui_seccion("Reglas")
        r1, r2, r3 = st.columns(3)
        with r1: ciego = st.checkbox("Conteo ciego por defecto", c.conteo_ciego, help="El contador no ve el stock del sistema mientras cuenta.")
        with r2: neg = st.checkbox("Permitir stock negativo", c.permitir_stock_negativo)
        with r3: aprob = st.checkbox("Los ajustes requieren aprobación", c.ajustes_requieren_aprobacion)
        ui_seccion("Módulos activos", "Muestran u ocultan secciones del menú")
        m1, m2, m3, m4 = st.columns(4)
        with m1: mov = st.checkbox("Movimientos (kardex)", c.modulo("movimientos"))
        with m2: lot = st.checkbox("Lotes y vencimientos", c.modulo("lotes"))
        with m3: oc = st.checkbox("Órdenes de compra", c.modulo("ordenes_compra"))
        with m4: imp = st.checkbox("Importador", c.modulo("importador"))
        if st.form_submit_button("Guardar", type="primary"):
            dias = [int(x) for x in re.findall(r"\d+", venc)][:2]
            if len(dias) != 2:
                st.error("Escribe dos números para los días de alerta de vencimiento, por ejemplo: 30, 60")
                return
            if not _lineas(sucursales):
                st.error("Debe existir al menos una sucursal.")
                return
            _guardar({"sucursales": _lineas(sucursales), "zonas": _lineas(zonas) or c.zonas, "meta_exactitud": meta, "umbral_dif_monto": monto,
                      "umbral_dif_unidades": unid, "umbral_dif_pct": pct, "horas_sesion_alerta": horas, "dias_alerta_vencimiento": sorted(dias),
                      "conteo_ciego": ciego, "permitir_stock_negativo": neg, "ajustes_requieren_aprobacion": aprob,
                      "modulos": {"movimientos": mov, "lotes": lot, "ordenes_compra": oc, "importador": imp}}, "operación")


def _tab_seguridad(c):
    with st.form("cfg_seguridad"):
        a, b, c3 = st.columns(3)
        with a: intentos = st.number_input("Intentos fallidos antes del bloqueo", 3, 20, int(c.max_intentos_login))
        with b: bloqueo = st.number_input("Duración del bloqueo (segundos)", 30, 3600, int(c.bloqueo_login_seg), step=30)
        with c3: largo = st.number_input("Largo mínimo de contraseña", 6, 64, int(c.min_largo_password))
        d, e = st.columns(2)
        with d: sesion = st.number_input("Duración máxima de la sesión (horas)", 1, 72, int(c.sesion_max_horas))
        with e: inact = st.number_input("Cierre por inactividad (minutos)", 5, 480, int(c.inactividad_min))
        nombre = st.checkbox("Mostrar el nombre del usuario al escribir su usuario en el ingreso", c.login_mostrar_nombre,
                             help="Apágalo si no quieres que un extraño pueda saber qué usuarios existen.")
        if st.form_submit_button("Guardar", type="primary"):
            _guardar({"max_intentos_login": intentos, "bloqueo_login_seg": bloqueo, "min_largo_password": largo, "sesion_max_horas": sesion,
                      "inactividad_min": inact, "login_mostrar_nombre": nombre}, "seguridad")


def _tab_datos(c):
    b = backend()
    ui_seccion("Origen de los datos", "Se define en el archivo de configuración o en los secretos, no desde aquí")
    st.markdown(f"- **Tipo:** `{b.nombre}`" + (f"\n- **Archivo:** `{c.datos_hoja_id or c.datos_hoja_nombre}`" if b.nombre == "sheets" else "")
                + f"\n- **Empresa:** `{c.empresa_id}`")
    faltan = [n for n, _ in TABLAS.values() if not b.existe(n)]
    if faltan:
        ui_callout("Faltan estas tablas: " + ", ".join(faltan), "warn")
        if st.button("Crear las tablas que faltan", type="primary", key="cfg_crear_tablas"):
            creadas = b.asegurar_esquema()
            registrar_auditoria("TABLAS_CREADAS", ", ".join(creadas))
            st.success(f"Se crearon {len(creadas)} tablas.")
            st.rerun()
    else:
        ui_callout("Todas las tablas existen.", "ok")
    ui_seccion("Datos de ejemplo")
    st.caption("Importa productos y ventas desde «Importar datos» en el menú.")


def pantalla_configuracion():
    header("Configuración", "Todo lo que cambia de una empresa a otra, sin tocar el código")
    if not permiso("configurar"):
        st.error("Solo administración puede cambiar la configuración.")
        return
    c = cfg()
    t = st.tabs(["Empresa y marca", "Regional", "Operación", "Seguridad", "Datos"])
    with t[0]: _tab_empresa(c)
    with t[1]: _tab_regional(c)
    with t[2]: _tab_operacion(c)
    with t[3]: _tab_seguridad(c)
    with t[4]: _tab_datos(c)

"""Acceso: inicio de sesión y asistente de configuración inicial (primera vez)."""
import streamlit as st
import time
from inventario.contexto import cfg, empresas_disponibles, servicio_config
from inventario.nucleo import imagenes, seguridad as seg, tiempo
from inventario.pantallas.importar import bloque_importar_productos
from inventario.servicios import autenticar, cargar_usuarios, crear_usuario, registrar_auditoria
from inventario.ui.componentes import _html, footer, header, logo_tag, ui_avatar, ui_callout, ui_card_container, ui_guia_instalar, ui_seccion
from inventario.ui.estilos import inyectar_estilos_login
from inventario.utilidades import mostrar_error_google
from zoneinfo import available_timezones


def _selector_empresa():
    """Solo aparece si hay varias empresas configuradas."""
    emps = empresas_disponibles()
    if len(emps) < 2:
        return
    ids = [e["id"] for e in emps]
    actual = st.session_state.get("empresa_id", ids[0])
    _, centro, _ = st.columns([1, 1.2, 1])
    with centro:
        elegido = st.selectbox("Empresa", ids, index=ids.index(actual) if actual in ids else 0, key="login_empresa",
                               format_func=lambda i: next(e["nombre"] for e in emps if e["id"] == i))
    if elegido != st.session_state.get("empresa_id"):
        st.session_state["empresa_id"] = elegido
        st.rerun()


def pantalla_login():
    _selector_empresa()
    c = cfg()
    usuarios = cargar_usuarios()
    inyectar_estilos_login()
    guarda = seg.guarda_de(c.empresa_id)
    guarda.configurar(c.max_intentos_login, c.bloqueo_login_seg)

    _ico = lambda d: f'<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{d}</svg>'
    _i1 = _ico("<rect x='3' y='7' width='18' height='14' rx='2'/><path d='M3 11h18M8 7V3h8v4'/>")
    _i2 = _ico("<path d='M4 20V10M10 20V4M16 20v-8M22 20V7'/>")
    _i3 = _ico("<path d='M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z'/><path d='M9 12l2 2 4-4'/>")
    _lock = _ico("<rect x='5' y='11' width='14' height='9' rx='2'/><path d='M8 11V8a4 4 0 018 0v3'/>")
    frases = c.frases or ["Bienvenido."]
    frase = frases[tiempo.ahora().toordinal() % len(frases)]
    resaltado = f" <em>{_html.escape(c.login_titulo_resaltado)}</em>" if c.login_titulo_resaltado else ""
    hero = (f'<div class="tp-lg-hero"><div><span class="tp-lg-logo">{logo_tag(40)}</span>'
            f'<div class="tp-lg-k">{tiempo.saludo()}, equipo {_html.escape(c.nombre)}</div>'
            f'<div class="tp-lg-h">{_html.escape(c.login_titulo)}{resaltado}</div>'
            f'<p class="tp-lg-p">{_html.escape(c.login_subtitulo)}</p>'
            f'<div class="tp-lg-feat"><div><i>{_i1}</i>Inventario y conteos por producto</div>'
            f'<div><i>{_i2}</i>Movimientos, compras y reposición inteligente</div>'
            f'<div><i>{_i3}</i>Acceso protegido con cierre automático de sesión</div></div></div>'
            f'<div class="tp-lg-quote"><small>Frase del día</small><p>{_html.escape(frase)}</p></div></div>')
    c_hero, c_form = st.columns([1.15, 1], gap="large")
    with c_hero:
        st.markdown(hero, unsafe_allow_html=True)
    with c_form:
        st.markdown('<div class="tp-lg-spacer"></div>', unsafe_allow_html=True)
        with ui_card_container("login_form"):
            motivo = st.session_state.pop("_sesion_expirada", "")
            if motivo:
                ui_callout(f"Tu sesión se cerró automáticamente por {motivo}. Por favor, vuelve a iniciar sesión.", "warn")
            saludo = st.empty()
            usuario = st.text_input("Usuario", placeholder="Tu usuario", key="tp_inv_login_user")
            password = st.text_input("Contraseña", type="password", placeholder="Tu contraseña", key="tp_inv_login_pass")
            u_key = usuario.strip().lower()
            fila_u = usuarios[usuarios["Usuario"].astype(str).str.lower() == u_key] if u_key else usuarios.iloc[0:0]
            if not fila_u.empty and c.login_mostrar_nombre:
                nom = str(fila_u.iloc[0]["NombreCompleto"]).strip() or str(fila_u.iloc[0]["Usuario"])
                saludo.markdown(f'<div class="tp-lg-who">{ui_avatar(nom, 96)}<div class="tp-lg-t">Hola, {_html.escape(nom.split()[0])}</div><div class="tp-lg-s">Ingresa tu contraseña para continuar</div></div>', unsafe_allow_html=True)
            else:
                saludo.markdown(f'<div class="tp-lg-who"><div class="tp-lg-lock">{_lock}</div><div class="tp-lg-t">Bienvenido</div><div class="tp-lg-s">Ingresa con tu usuario y tu contraseña</div></div>', unsafe_allow_html=True)
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            clave = f"{c.empresa_id}|{u_key}"
            bloqueo = guarda.segundos_bloqueado(clave) if u_key else 0
            if bloqueo > 0:
                st.error(f"Demasiados intentos fallidos. Por seguridad, espera {bloqueo // 60 + 1} minuto(s) e inténtalo de nuevo.")
            clic = st.button("Ingresar al sistema", use_container_width=True, key="login_btn", disabled=bloqueo > 0)
            if bloqueo <= 0 and u_key and (clic or password):
                intento = (u_key, password)
                if st.session_state.get("login_ult_intento") == intento and st.session_state.get("login_ult_msg"):
                    st.error(st.session_state["login_ult_msg"])       # mismo intento repetido: no cuenta otra vez
                else:
                    try:
                        registro = autenticar(usuario, password)
                        if registro:
                            guarda.limpiar(clave)
                            st.session_state.update(autenticado=True, usuario=registro, pagina="Inicio", codigo_pendiente="", producto_pendiente=None,
                                                    modo_inventario="scanner", login_timestamp=time.time(), ultima_actividad=time.time())
                            st.session_state.pop("login_ult_intento", None)
                            st.session_state.pop("login_ult_msg", None)
                            registrar_auditoria("LOGIN", "Inicio de sesión")
                            st.rerun()
                        else:
                            bloqueado, quedan = guarda.registrar_fallo(clave)
                            if bloqueado:
                                registrar_auditoria("LOGIN_BLOQUEADO", f"Usuario ingresado: {usuario.strip()}")
                                msg = f"Demasiados intentos fallidos. Acceso bloqueado por {c.bloqueo_login_seg // 60 or 1} minutos."
                                st.session_state.pop("login_ult_intento", None)
                                st.session_state.pop("login_ult_msg", None)
                            else:
                                msg = f"Usuario o contraseña incorrectos. Te quedan {quedan} intento(s) antes de un bloqueo temporal."
                                st.session_state["login_ult_intento"], st.session_state["login_ult_msg"] = intento, msg
                            st.error(msg)
                    except Exception as exc:
                        mostrar_error_google(exc, "el inicio de sesión")
            st.markdown(f'<div class="tp-lg-note">Conexión protegida · La sesión se cierra tras {c.inactividad_min} min de inactividad</div>', unsafe_allow_html=True)
        ui_guia_instalar(st)
    st.stop()


# ======================= Asistente de configuración inicial =======================
def necesita_asistente():
    """Empresa nueva: sin configuración terminada Y sin ningún usuario. Las instalaciones existentes no lo ven."""
    return (not cfg().setup_completo) and cargar_usuarios().empty


def _paso(n, total, titulo):
    st.markdown(f'<div class="tp-sec"><div><div class="tp-sec-title">Paso {n} de {total} · {titulo}</div></div></div>', unsafe_allow_html=True)
    st.progress(n / total)


def asistente_inicial():
    inyectar_estilos_login()
    header("Configuración inicial", "Unos minutos y tu inventario queda listo para usarse")
    w = st.session_state.setdefault("wiz", {"paso": 1, "d": {}})
    d, paso, total = w["d"], w["paso"], 5
    _, centro, _ = st.columns([0.4, 3, 0.4])
    with centro:
        if paso == 1:
            _paso(1, total, "Tu empresa")
            d["nombre"] = st.text_input("Nombre comercial", d.get("nombre", ""))
            d["razon_social"] = st.text_input("Razón social (opcional)", d.get("razon_social", ""))
            a, b = st.columns(2)
            with a: d["id_fiscal_etiqueta"] = st.text_input("Identificador fiscal (RUC, NIT, RFC…)", d.get("id_fiscal_etiqueta", "RUC"))
            with b: d["id_fiscal"] = st.text_input("Número", d.get("id_fiscal", ""))
            d["color_primario"] = st.color_picker("Color de tu marca", d.get("color_primario", "#EC3237"))
            logo = st.file_uploader("Logo (opcional)", type=["png", "jpg", "jpeg", "webp"])
            if logo is not None:
                try:
                    d["logo_b64"] = imagenes.logo_a_data_uri(logo.getvalue())
                    st.caption("Logo cargado.")
                except Exception as exc:
                    st.error(f"No pude usar esa imagen: {exc}")
            if st.button("Siguiente", type="primary", key="w1"):
                if not d["nombre"].strip():
                    st.error("Escribe el nombre de tu empresa.")
                else:
                    w["paso"] = 2; st.rerun()
        elif paso == 2:
            _paso(2, total, "Moneda y hora")
            zonas = sorted(available_timezones())
            a, b, c3 = st.columns(3)
            with a: d["moneda_simbolo"] = st.text_input("Símbolo de moneda", d.get("moneda_simbolo", "S/"), max_chars=5)
            with b: d["moneda_codigo"] = st.text_input("Código (PEN, USD, MXN…)", d.get("moneda_codigo", "PEN"), max_chars=3).upper()
            with c3: d["moneda_decimales"] = st.number_input("Decimales", 0, 4, int(d.get("moneda_decimales", 2)))
            d["zona_horaria"] = st.selectbox("Zona horaria", zonas, index=zonas.index(d.get("zona_horaria", "America/Lima")))
            x, y = st.columns(2)
            with x:
                if st.button("Atrás", key="w2a"): w["paso"] = 1; st.rerun()
            with y:
                if st.button("Siguiente", type="primary", key="w2"): w["paso"] = 3; st.rerun()
        elif paso == 3:
            _paso(3, total, "Cómo trabajas")
            d["sucursales_txt"] = st.text_area("Sucursales o locales (uno por línea)", d.get("sucursales_txt", "Principal"), height=100)
            d["zonas_txt"] = st.text_area("Zonas de conteo (una por línea)", d.get("zonas_txt", "General"), height=100, help="Secciones físicas: góndola, almacén, vitrina…")
            m = d.setdefault("modulos", {"movimientos": True, "lotes": False, "ordenes_compra": True, "importador": True})
            ui_seccion("Funciones que quieres usar")
            m["movimientos"] = st.checkbox("Movimientos de inventario (entradas, salidas, mermas, transferencias)", m["movimientos"])
            m["lotes"] = st.checkbox("Lotes y fechas de vencimiento", m["lotes"])
            m["ordenes_compra"] = st.checkbox("Proveedores y órdenes de compra", m["ordenes_compra"])
            d["conteo_ciego"] = st.checkbox("Conteo ciego (el contador no ve el stock del sistema)", d.get("conteo_ciego", False))
            x, y = st.columns(2)
            with x:
                if st.button("Atrás", key="w3a"): w["paso"] = 2; st.rerun()
            with y:
                if st.button("Siguiente", type="primary", key="w3"):
                    if not [s for s in d["sucursales_txt"].splitlines() if s.strip()]:
                        st.error("Indica al menos una sucursal.")
                    else:
                        w["paso"] = 4; st.rerun()
        elif paso == 4:
            _paso(4, total, "Administrador")
            ui_callout("Será la persona que gestiona usuarios y configuración. Podrás crear más usuarios después.")
            d["adm_usuario"] = st.text_input("Usuario", d.get("adm_usuario", ""))
            d["adm_nombre"] = st.text_input("Nombre completo", d.get("adm_nombre", ""))
            p1 = st.text_input("Contraseña", type="password", key="w_p1")
            p2 = st.text_input("Repite la contraseña", type="password", key="w_p2")
            x, y = st.columns(2)
            with x:
                if st.button("Atrás", key="w4a"): w["paso"] = 3; st.rerun()
            with y:
                if st.button("Siguiente", type="primary", key="w4"):
                    problemas = seg.validar_password(p1, d["adm_usuario"], cfg().min_largo_password)
                    if not d["adm_usuario"].strip() or not d["adm_nombre"].strip():
                        st.error("Completa el usuario y el nombre.")
                    elif problemas:
                        st.error(" ".join(problemas))
                    elif p1 != p2:
                        st.error("Las contraseñas no coinciden.")
                    else:
                        d["adm_clave"] = p1; w["paso"] = 5; st.rerun()
        else:
            _paso(5, total, "Tus productos")
            ui_callout("Puedes cargar tu lista de productos ahora desde Excel o CSV, o hacerlo después desde «Importar datos».")
            sucs = [s.strip() for s in d["sucursales_txt"].splitlines() if s.strip()]
            bloque_importar_productos("wiz_p", sucs[0], permitir_reemplazar=False)
            x, y = st.columns(2)
            with x:
                if st.button("Atrás", key="w5a"): w["paso"] = 4; st.rerun()
            with y:
                if st.button("Terminar configuración", type="primary", key="w5"):
                    try:
                        crear_usuario(d["adm_usuario"].strip(), d["adm_nombre"].strip(), "ADMIN", d["adm_clave"])
                        cambios = {k: d[k] for k in ("nombre", "razon_social", "id_fiscal_etiqueta", "id_fiscal", "color_primario", "moneda_simbolo", "moneda_codigo",
                                                     "moneda_decimales", "zona_horaria", "modulos", "conteo_ciego") if k in d}
                        if d.get("logo_b64"): cambios["logo_b64"] = d["logo_b64"]
                        cambios["app_titulo"] = "Inventario"
                        cambios["sucursales"] = sucs
                        cambios["zonas"] = [z.strip() for z in d["zonas_txt"].splitlines() if z.strip()] or ["General"]
                        cambios["setup_completo"] = True
                        servicio_config().guardar(cambios, d["adm_usuario"].strip())
                        cargar_usuarios.clear()
                        st.session_state.pop("wiz", None)
                        st.success("¡Listo! Ya puedes iniciar sesión con el usuario administrador.")
                        st.rerun()
                    except Exception as exc:
                        mostrar_error_google(exc, "la configuración inicial")
    footer()
    st.stop()

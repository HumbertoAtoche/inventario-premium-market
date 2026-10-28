"""Componentes visuales reutilizables: encabezados, KPIs, chips, tarjetas, marca e instalación en celular."""
import base64
import html
import io
import mimetypes
import os
import re
import streamlit as st
import streamlit.components.v1 as components
from inventario.contexto import BASE_DIR, cfg
from inventario.utilidades import safe_text


# ---------- marca (logo / favicon desde la configuración) ----------
def _ruta(rel):
    return rel if os.path.isabs(rel) else os.path.join(BASE_DIR, rel)


def ruta_logo():
    r = _ruta(cfg().logo_ruta)
    return r if os.path.isfile(r) else ""


def ruta_favicon():
    r = _ruta(cfg().favicon_ruta)
    return r if os.path.isfile(r) else ""


def favicon_pagina():
    return ruta_favicon() or ruta_logo() or "📦"


@st.cache_data(show_spinner=False)
def _archivo_b64(ruta):
    with open(ruta, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def logo_b64_mime():
    """(base64, mime) del logo: el subido en el asistente (guardado en la configuración) o el archivo de assets."""
    c = cfg()
    if c.logo_b64:
        cab, _, dato = c.logo_b64.rpartition(",")
        mime = cab.split(":")[1].split(";")[0] if cab.startswith("data:") else "image/png"
        return dato, mime
    r = ruta_logo()
    if r:
        try:
            return _archivo_b64(r), mimetypes.guess_type(r)[0] or "image/png"
        except OSError:
            pass
    return "", ""


def logo_tag(height=52, fallback_emoji="📦"):
    """<img> del logo incrustado en base64 (sin depender de internet) o un emoji si no hay logo."""
    b64, mime = logo_b64_mime()
    if not b64:
        return f'<span style="font-size:{height}px;line-height:1;">{fallback_emoji}</span>'
    return (f'<img src="data:{mime};base64,{b64}" alt="logo" '
            f'style="height:{height}px;max-width:100%;object-fit:contain;vertical-align:middle;">')


def abrir_logo_pil():
    """Imagen PIL del ícono de la app (favicon > logo). Lanza FileNotFoundError si no hay ninguna."""
    from PIL import Image
    c = cfg()
    if c.logo_b64:
        return Image.open(io.BytesIO(base64.b64decode(c.logo_b64.rpartition(",")[2]))).convert("RGBA")
    ruta = ruta_favicon() or ruta_logo()
    if not ruta:
        raise FileNotFoundError("sin logo")
    return Image.open(ruta).convert("RGBA")


def footer():
    st.markdown(f'<div class="app-footer">{cfg().pie()}</div>', unsafe_allow_html=True)


_html = html


def header(titulo, subtitulo=""):
    sub = f"<p>{safe_text(subtitulo)}</p>" if subtitulo else ""
    st.markdown(
        f'<div class="market-header"><h1>{safe_text(titulo)}</h1>{sub}</div>',
        unsafe_allow_html=True,
    )


def kpi(label, value, note=""):
    st.markdown(ui_kpi(safe_text(label), safe_text(value), safe_text(note)), unsafe_allow_html=True)


def badge(tipo):
    clase = {
        "OK": "ok",
        "FALTANTE": "bad",
        "SOBRANTE": "ok",
        "ABIERTA": "info",
        "CERRADA": "neutral",
    }.get(str(tipo).upper(), "neutral")
    return ui_chip(safe_text(tipo), clase)


def ui_iniciales(nombre):
    p = [x for x in str(nombre).split() if x]
    return (p[0][0] + (p[1][0] if len(p) > 1 else "")).upper() if p else "?"


def ui_avatar(nombre, size=46):
    dim = f"width:{size}px;height:{size}px;font-size:{max(12, int(size * 0.34))}px;"
    return f'<span class="tp-avatar" style="{dim}">{_html.escape(ui_iniciales(nombre))}</span>'


def ui_chip(texto, tipo="neutral"):
    """tipo: ok | warn | bad | info | neutral"""
    return f'<span class="tp-chip {tipo}">{texto}</span>'


def ui_kpi(etiqueta, valor, detalle=""):
    sub = f'<div class="tp-kpi-sub">{detalle}</div>' if detalle else ""
    return f'<div class="tp-kpi"><div class="tp-kpi-lbl">{etiqueta}</div><div class="tp-kpi-val">{valor}</div>{sub}</div>'


def ui_card_container(key):
    """Contenedor que ES la tarjeta blanca (todo el contenido dentro del mismo fondo)."""
    try:
        return st.container(key=f"tpc_{key}")
    except TypeError:
        return st.container(border=True)


def ui_callout(texto, tono="info"):
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", _html.escape(str(texto)))
    ic = {"info": "i", "ok": "✓", "warn": "!"}[tono]
    st.markdown(f'<div class="tp-callout {tono}"><i>{ic}</i><div>{t}</div></div>', unsafe_allow_html=True)


def ui_seccion(titulo, sub=""):
    s = f'<div class="tp-sec-sub">{_html.escape(sub)}</div>' if sub else ""
    st.markdown(f'<div class="tp-sec"><div><div class="tp-sec-title">{_html.escape(titulo)}</div>{s}</div></div>', unsafe_allow_html=True)


def ui_icono_app():
    """Ícono cuadrado con fondo blanco y el logo centrado (180 px iPhone, 512 px Android)."""
    from PIL import Image, ImageDraw, ImageFont

    def _icono(sz):
        im = Image.new("RGBA", (sz, sz), (255, 255, 255, 255))
        try:
            lg = abrir_logo_pil()
            lg.thumbnail((int(sz * 0.74), int(sz * 0.74)), Image.LANCZOS)
            im.paste(lg, ((sz - lg.width) // 2, (sz - lg.height) // 2), lg)
        except Exception:
            d = ImageDraw.Draw(im)
            d.rounded_rectangle((sz * .12, sz * .12, sz * .88, sz * .88), radius=sz * .2, fill=(236, 50, 55, 255))
            try:
                d.text((sz * .5, sz * .5), "P", fill="white", anchor="mm", font=ImageFont.load_default(size=int(sz * .5)))
            except Exception:
                pass
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    return _icono(180), _icono(512)


def ui_pwa_inyectar():
    """Pide al celular: ícono propio, nombre corto, color de marca y pantalla completa al añadir a inicio."""
    try:
        i180, i512 = ui_icono_app()
    except Exception:
        return
    js = """<script>(function(){try{
var d=window.parent.document,h=d.head;
function meta(n,c){var m=d.querySelector('meta[name="'+n+'"]');if(!m){m=d.createElement('meta');m.name=n;h.appendChild(m);}m.content=c;}
d.querySelectorAll('link[rel="apple-touch-icon"],link[rel="manifest"]').forEach(function(e){e.remove();});
var a=d.createElement('link');a.rel='apple-touch-icon';a.setAttribute('sizes','180x180');a.href='__I180__';h.appendChild(a);
meta('apple-mobile-web-app-capable','yes');meta('mobile-web-app-capable','yes');
meta('apple-mobile-web-app-title','__APP__');meta('application-name','__APP__');
meta('apple-mobile-web-app-status-bar-style','default');meta('theme-color','__COLOR__');
var L=window.parent.location,mf={name:'__APPFULL__',short_name:'__APP__',start_url:L.origin+L.pathname,scope:L.origin+'/',display:'standalone',
background_color:'#FFFFFF',theme_color:'__COLOR__',icons:[{src:'__I512__',sizes:'512x512',type:'image/png',purpose:'any'}]};
var m=d.createElement('link');m.rel='manifest';m.href='data:application/manifest+json,'+encodeURIComponent(JSON.stringify(mf));h.appendChild(m);
}catch(e){}})();</script>"""
    components.html(js.replace("__I180__", i180).replace("__I512__", i512).replace("__APPFULL__", f"{cfg().app_titulo} · {cfg().nombre}").replace("__APP__", cfg().app_titulo).replace("__COLOR__", cfg().color_primario), height=0)


def ui_guia_instalar(cont):
    ua = ""
    try:
        ua = str(st.context.headers.get("User-Agent", ""))
    except Exception:
        pass
    es_ios, es_and = any(x in ua for x in ("iPhone", "iPad", "iPod")), "Android" in ua
    ios = ('<div class="tp-steps-t">iPhone · Safari ' + (ui_chip("Tu dispositivo", "ok") if es_ios else "") + '</div><ol class="tp-steps">'
           '<li>Abre esta página en <b>Safari</b>.</li><li>Toca el botón <b>Compartir</b> (cuadro con flecha hacia arriba).</li>'
           '<li>Elige <b>Añadir a pantalla de inicio</b>.</li><li>Toca <b>Añadir</b>. Listo: aparece el ícono de la app.</li></ol>')
    andr = ('<div class="tp-steps-t">Android · Chrome ' + (ui_chip("Tu dispositivo", "ok") if es_and else "") + '</div><ol class="tp-steps">'
            '<li>Abre esta página en <b>Chrome</b>.</li><li>Toca el menú <b>⋮</b> (arriba a la derecha).</li>'
            '<li>Elige <b>Instalar app</b> o <b>Añadir a pantalla de inicio</b>.</li><li>Confirma con <b>Instalar</b>.</li></ol>')
    with cont.expander("Instalar en tu celular"):
        st.markdown((andr + ios) if es_and else (ios + andr), unsafe_allow_html=True)
        st.caption("Cada vez que abras la app te pedirá tu usuario y contraseña por seguridad.")


def _norm_txt(x):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(x).lower()) if unicodedata.category(c) != "Mn")


def _ir_a(destino):
    """Navega a una sección y limpia la búsqueda (se usa en botones con on_click)."""
    st.session_state["pagina"] = destino
    st.session_state["gs_q"] = ""


def _limpiar_busqueda():
    st.session_state["gs_q"] = ""

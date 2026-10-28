"""Utilidades generales (hora de la empresa, formato, errores)."""
import base64
import html
import io
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from inventario.contexto import cfg
from inventario.nucleo import errores, tiempo


def ahora():
    """Fecha y hora de la empresa como texto (formato que se guarda en las tablas)."""
    return tiempo.ahora_str()


def fecha_actual():
    return tiempo.hoy_str()


def generar_id_sesion():
    return tiempo.ahora().strftime("INV-%Y%m%d-%H%M%S-%f")


def generar_id_usuario():
    return tiempo.ahora().strftime("USR-%Y%m%d%H%M%S%f")


def saludo_actual():
    return tiempo.saludo()


def formato_soles(valor):
    """Formato de moneda de la empresa (el nombre se conserva por compatibilidad)."""
    return cfg().moneda(valor)


def mostrar_error_google(exc, contexto="los datos"):
    """Mensaje claro + código de error para soporte. El detalle técnico solo lo ve supervisión."""
    from inventario.nucleo import permisos
    codigo = errores.registrar_error(contexto, exc)
    tipo = errores.clasificar(exc)
    if tipo == "cuota":
        st.error("⚠️ El servicio de datos alcanzó temporalmente su límite de lecturas.")
        st.info("La aplicación no se desconectó. Espera unos segundos y usa **Actualizar datos**.")
    elif tipo == "permiso":
        st.error("🔒 El servicio de datos rechazó el acceso.")
        st.info("Revisa que la cuenta de servicio tenga acceso al archivo de datos.")
    elif tipo == "no_encontrado":
        st.error("📄 No se encontró el archivo o una de las tablas configuradas.")
    else:
        st.error(f"⚠️ No se pudo completar la operación con {contexto}.")
    st.caption(f"Código de error: ERR-{codigo}. Compártelo con soporte para ubicar el detalle.")
    if permisos.es_supervision(st.session_state.get("usuario")):
        with st.expander("Detalle técnico"):
            st.code(str(exc))


def limpiar_codigo(valor):
    if pd.isna(valor):
        return ""
    texto = str(valor).strip()
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto


def limpiar_numero(valor, default=0):
    try:
        if pd.isna(valor):
            return default
        texto = str(valor).strip().replace(",", "")
        if texto == "":
            return default
        return float(texto)
    except Exception:
        return default


def exportar_excel(hojas: dict):
    """Genera un archivo .xlsx en memoria a partir de un diccionario {nombre_hoja: DataFrame}."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for nombre, df in hojas.items():
            df.to_excel(writer, sheet_name=nombre[:31], index=False)
    buffer.seek(0)
    return buffer.getvalue()


def safe_text(valor):
    return html.escape(str(valor))


def normalizar_df(df, headers):
    if df is None or df.empty:
        return pd.DataFrame(columns=headers)
    df = df.copy()
    for col in headers:
        if col not in df.columns:
            df[col] = ""
    return df[headers + [c for c in df.columns if c not in headers]]


@st.cache_data(show_spinner=False)
def _beep_wav_base64(frecuencia=1500, duracion_ms=110, volumen=0.35):
    """Genera un beep corto en WAV (sin dependencias externas) y lo devuelve en Base64."""
    import struct
    import wave
    import math

    tasa = 22050
    n_muestras = int(tasa * duracion_ms / 1000)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(tasa)
        for i in range(n_muestras):
            valor = int(volumen * 32767 * math.sin(2 * math.pi * frecuencia * i / tasa))
            wav.writeframes(struct.pack("<h", valor))
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def sonido_confirmacion():
    """Reproduce un beep + vibración corta al confirmar un escaneo exitoso."""
    audio_b64 = _beep_wav_base64()
    components.html(
        f"""
        <audio id="beep_ok" autoplay>
            <source src="data:audio/wav;base64,{audio_b64}" type="audio/wav">
        </audio>
        <script>
            try {{ if (navigator.vibrate) {{ navigator.vibrate(70); }} }} catch (e) {{}}
        </script>
        """,
        height=0,
    )

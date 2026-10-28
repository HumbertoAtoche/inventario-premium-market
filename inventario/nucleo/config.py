"""Configuración por empresa.

Capas (la última gana):
  1. Valores por defecto de esta clase (empresa genérica).
  2. Archivo `empresas/<id>.json` (o `config.json` si solo hay una empresa).
  3. Bloque `[empresa]` de los secretos de Streamlit (opcional).
  4. Hoja/tabla `Configuracion`: lo que el administrador edita desde la app.

Las claves de conexión a los datos (`datos_*`) solo salen de las capas 2 y 3: no se
pueden cambiar desde la app, para que nadie se quede sin acceso por error.
"""
import json
import os
from dataclasses import dataclass, field, fields, asdict

from . import tiempo
from .esquemas import nombre_tabla, columnas

_FRASES = [
    "Un inventario preciso ayuda a tomar mejores decisiones.",
    "Lo que se cuenta bien hoy, se vende mejor mañana.",
    "Comprar con información es cuidar el capital del negocio.",
    "Un equipo organizado logra mejores resultados.",
    "Cada producto en su lugar es una venta que no se pierde.",
    "Contar con cuidado es la mejor forma de evitar sorpresas.",
]


@dataclass
class Config:
    # --- Identidad ---
    empresa_id: str = "default"
    nombre: str = "Mi Empresa"
    razon_social: str = ""
    id_fiscal_etiqueta: str = "RUC"
    id_fiscal: str = ""
    desarrollado_por: str = ""
    sistema_subtitulo: str = "Sistema de inventario"
    app_titulo: str = "Inventario"
    # --- Marca ---
    color_primario: str = "#EC3237"
    logo_ruta: str = "assets/logo.png"
    favicon_ruta: str = "assets/favicon.png"
    logo_b64: str = ""
    login_titulo: str = "Tu inventario y tus compras,"
    login_titulo_resaltado: str = "en un solo lugar."
    login_subtitulo: str = "Control de existencias, conteos y compras, con información clara y al instante."
    frases: list = field(default_factory=lambda: list(_FRASES))
    enlaces: list = field(default_factory=list)          # [{"nombre","detalle","url"}]
    # --- Regional ---
    moneda_simbolo: str = "S/"
    moneda_codigo: str = "PEN"
    moneda_decimales: int = 2
    zona_horaria: str = "America/Lima"
    locale: str = "es-PE"
    # --- Operación ---
    sucursales: list = field(default_factory=lambda: ["Principal"])
    zonas: list = field(default_factory=lambda: ["General"])
    meta_exactitud: float = 98.0
    umbral_dif_monto: float = 200.0
    umbral_dif_unidades: int = 10
    umbral_dif_pct: float = 30.0
    conteo_ciego: bool = False
    horas_sesion_alerta: int = 24
    permitir_stock_negativo: bool = False
    ajustes_requieren_aprobacion: bool = True
    dias_alerta_vencimiento: list = field(default_factory=lambda: [30, 60])
    modulos: dict = field(default_factory=lambda: {"movimientos": True, "lotes": False, "ordenes_compra": True, "importador": True})
    ventas_mapeo: dict = field(default_factory=dict)      # columna del reporte de ventas -> campo estándar
    # --- Seguridad ---
    max_intentos_login: int = 5
    bloqueo_login_seg: int = 300
    sesion_max_horas: int = 10
    inactividad_min: int = 30
    min_largo_password: int = 10
    login_mostrar_nombre: bool = True
    # --- Estado de la configuración inicial ---
    setup_completo: bool = False
    # --- Conexión a los datos (solo archivo/secretos) ---
    datos_backend: str = "sheets"                         # sheets | sql | memoria
    datos_hoja_nombre: str = "BD_Inventario"
    datos_hoja_id: str = ""
    datos_credenciales: str = "gcp_service_account"       # clave en st.secrets
    datos_sql_url: str = ""                                # sqlite:///ruta.db  |  postgresql://...
    datos_autocrear: bool = True

    # ----- utilidades -----
    def modulo(self, nombre):
        return bool(self.modulos.get(nombre, False))

    def to_dict(self):
        return asdict(self)

    def moneda(self, valor):
        try:
            return f"{self.moneda_simbolo} {float(valor):,.{int(self.moneda_decimales)}f}"
        except Exception:
            return f"{self.moneda_simbolo} {0:,.{int(self.moneda_decimales)}f}"

    def pie(self):
        partes = []
        if self.desarrollado_por:
            partes.append(f"Desarrollado por <strong>{_esc(self.desarrollado_por)}</strong>")
        linea = f"<strong>{_esc(self.razon_social or self.nombre)}</strong>"
        if self.id_fiscal:
            linea += f" • {_esc(self.id_fiscal_etiqueta)} {_esc(self.id_fiscal)}"
        partes.append(linea)
        partes.append("Todos los derechos reservados")
        return "<br>".join(partes)


def _esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_TIPOS = {f.name: f for f in fields(Config)}
SOLO_ARCHIVO = {"empresa_id", "datos_backend", "datos_hoja_nombre", "datos_hoja_id", "datos_credenciales", "datos_sql_url", "datos_autocrear"}
EDITABLES = set(_TIPOS) - SOLO_ARCHIVO


def _coercer(valor, muestra):
    """Convierte `valor` al tipo de `muestra` (el default del campo). Lanza ValueError si no se puede."""
    if isinstance(muestra, bool):
        if isinstance(valor, str):
            return valor.strip().lower() in ("1", "true", "si", "sí", "yes", "on")
        return bool(valor)
    if isinstance(muestra, int):
        return int(float(valor))
    if isinstance(muestra, float):
        return float(valor)
    if isinstance(muestra, (list, dict)):
        if isinstance(valor, str):
            valor = json.loads(valor)
        if not isinstance(valor, type(muestra)):
            raise ValueError("tipo inválido")
        return valor
    return "" if valor is None else str(valor)


def aplicar(cfg, cambios, permitidas=None):
    """Devuelve una copia de `cfg` con `cambios` aplicados. Ignora claves desconocidas o inválidas."""
    nueva = Config(**cfg.to_dict())
    for k, v in (cambios or {}).items():
        if k not in _TIPOS or (permitidas is not None and k not in permitidas):
            continue
        muestra = getattr(Config(), k)
        try:
            nuevo = _coercer(v, muestra)
        except Exception:
            continue
        if k == "modulos":                       # se mezcla: un módulo nuevo no desaparece
            nuevo = {**cfg.modulos, **nuevo}
        setattr(nueva, k, nuevo)
    return nueva


def _leer_json(ruta):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def listar_empresas(base_dir):
    """[{'id','nombre'}] de las empresas disponibles. Con una sola no se pide elegir."""
    carpeta = os.path.join(base_dir, "empresas")
    res = []
    if os.path.isdir(carpeta):
        for archivo in sorted(os.listdir(carpeta)):
            if archivo.endswith(".json") and not archivo.startswith("_"):
                d = _leer_json(os.path.join(carpeta, archivo))
                eid = archivo[:-5]
                res.append({"id": eid, "nombre": d.get("nombre", eid)})
    if not res:
        d = _leer_json(os.path.join(base_dir, "config.json"))
        res.append({"id": "default", "nombre": d.get("nombre", Config().nombre)})
    return res


def cargar_estatica(base_dir, empresa_id="default", secretos=None):
    """Capas 1–3: defaults + archivo + secretos."""
    ruta = os.path.join(base_dir, "empresas", f"{empresa_id}.json")
    datos = _leer_json(ruta) if os.path.isfile(ruta) else _leer_json(os.path.join(base_dir, "config.json"))
    cfg = Config(empresa_id=empresa_id)
    cfg = aplicar(cfg, datos)
    if secretos:
        cfg = aplicar(cfg, dict(secretos))
    cfg.empresa_id = empresa_id
    return cfg


class ServicioConfig:
    """Capa 4: lee/guarda en la tabla `Configuracion` (con una pequeña caché de 60 s)."""
    TTL = 60

    def __init__(self, estatica, tabla_provider):
        self.estatica = estatica
        self._tabla = tabla_provider            # callable -> Tabla de configuración
        self._cache = None
        self._cache_ts = 0.0

    def _overrides(self):
        import time
        if self._cache is not None and time.time() - self._cache_ts < self.TTL:
            return self._cache
        ov = {}
        try:
            for r in self._tabla().get_all_records():
                k = str(r.get("Clave", "")).strip()
                if k in EDITABLES:
                    try:
                        ov[k] = json.loads(str(r.get("Valor", "")))
                    except ValueError:
                        ov[k] = r.get("Valor", "")
        except Exception:
            ov = self._cache or {}
        self._cache, self._cache_ts = ov, time.time()
        return ov

    def efectiva(self):
        cfg = aplicar(self.estatica, self._overrides(), permitidas=EDITABLES)
        tiempo.usar_zona(cfg.zona_horaria)
        return cfg

    def invalidar(self):
        self._cache = None

    def guardar(self, cambios, usuario=""):
        """Guarda solo claves editables. Devuelve las claves realmente guardadas."""
        tabla = self._tabla()
        validos = {}
        for k, v in (cambios or {}).items():
            if k in EDITABLES:
                try:
                    validos[k] = _coercer(v, getattr(Config(), k))
                except Exception:
                    pass
        if not validos:
            return []
        filas = tabla.get_all_values()
        indice = {str(r[0]).strip(): n for n, r in enumerate(filas[1:], 2) if r}
        ahora = tiempo.ahora_str()
        for k, v in validos.items():
            registro = [k, json.dumps(v, ensure_ascii=False), ahora, usuario]
            if k in indice:
                tabla.update(f"A{indice[k]}:D{indice[k]}", [registro], value_input_option="RAW")
            else:
                tabla.append_row(registro, value_input_option="RAW")
        self.invalidar()
        return sorted(validos)

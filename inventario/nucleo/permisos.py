"""Roles, permisos y alcance por sucursal."""

# permiso -> descripción
PERMISOS = {
    "inicio": "Ver el dashboard",
    "precios": "Consultar precios",
    "contar": "Contar productos y trabajar por zonas",
    "sesiones": "Abrir y cerrar sesiones de inventario",
    "resultados": "Ver resultados y análisis",
    "movimientos_ver": "Ver movimientos y kardex",
    "movimientos_registrar": "Registrar entradas, salidas, mermas y transferencias",
    "ajustes_aprobar": "Aprobar o rechazar ajustes de stock",
    "compras": "Gestionar proveedores y órdenes de compra",
    "compras_ia": "Ver el plan de compras inteligente",
    "importar": "Importar productos y ventas",
    "usuarios": "Administrar usuarios y auditoría",
    "configurar": "Cambiar la configuración de la empresa",
    "seguridad": "Respaldos y control de accesos",
}

ROLES = {
    "ADMIN": set(PERMISOS),
    "SUPERVISOR": {"inicio", "precios", "contar", "sesiones", "resultados", "movimientos_ver", "movimientos_registrar",
                   "ajustes_aprobar", "compras", "compras_ia", "importar"},
    "CONTADOR": {"inicio", "precios", "contar", "movimientos_ver"},
    "LECTURA": {"inicio", "precios", "resultados", "movimientos_ver"},
}
ROLES_ASIGNABLES = ["CONTADOR", "SUPERVISOR", "LECTURA", "ADMIN"]

# (nombre en el menú, permiso, módulo requerido o None)
PAGINAS = [
    ("Inicio", "inicio", None),
    ("Precios", "precios", None),
    ("Sesión", "sesiones", None),
    ("Zonas", "contar", None),
    ("Inventario", "contar", None),
    ("Movimientos", "movimientos_ver", "movimientos"),
    ("Vencimientos", "movimientos_ver", "lotes"),
    ("Órdenes de Compra", "compras", "ordenes_compra"),
    ("Resultados", "resultados", None),
    ("Análisis", "resultados", None),
    ("Compras Inteligentes", "compras_ia", None),
    ("Importar datos", "importar", "importador"),
    ("Seguridad y respaldos", "seguridad", None),
    ("Configuración", "configurar", None),
    ("Administración", "usuarios", None),
]


def rol_de(usuario):
    r = str((usuario or {}).get("Rol", "")).strip().upper()
    return r if r in ROLES else "LECTURA"


def tiene(usuario, permiso):
    return permiso in ROLES[rol_de(usuario)]


def es_supervision(usuario):
    """Admin y supervisor ven stock de sistema aunque haya conteo ciego y supervisan zonas ajenas."""
    return rol_de(usuario) in ("ADMIN", "SUPERVISOR")


def paginas_para(usuario, cfg):
    return [n for n, p, m in PAGINAS if tiene(usuario, p) and (m is None or cfg.modulo(m))]


def sucursales_usuario(usuario):
    """None = todas. Si no, lista de sucursales permitidas (columna Sucursales: 'A;B' o '*')."""
    if rol_de(usuario) == "ADMIN":
        return None
    txt = str((usuario or {}).get("Sucursales", "")).strip()
    if txt in ("", "*"):
        return None
    return [s.strip() for s in txt.replace(",", ";").split(";") if s.strip()]


def filtrar_sucursales(df, usuario, columna="Sucursal"):
    permitidas = sucursales_usuario(usuario)
    if permitidas is None or df is None or df.empty or columna not in df.columns:
        return df
    ok = {s.casefold() for s in permitidas}
    return df[df[columna].astype(str).str.strip().str.casefold().isin(ok)]

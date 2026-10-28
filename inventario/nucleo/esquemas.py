"""Esquema de datos: nombre de cada tabla/hoja y sus columnas.

Un solo lugar para todo lo que se guarda. Las tablas nuevas (movimientos, lotes,
compras, ajustes, configuración) conviven con las originales sin tocarlas.
"""

# ---------- Tablas originales ----------
HEADERS_INVENTARIO = [
    "CodigoBarras", "CodigoProducto", "Producto", "Descripcion", "Categoria",
    "Marca", "Unidad", "Sucursal", "StockSistema", "CostoUnitario",
    "PrecioVenta", "Estado", "StockMinimo",
]
HEADERS_CONTEO = [
    "IdSesion", "FechaHora", "Usuario", "NombreUsuario", "CodigoBarras",
    "CodigoProducto", "Producto", "Categoria", "Sucursal", "StockSistema",
    "StockFisico", "Diferencia", "CostoUnitario", "ValorFaltante", "ValorSobrante",
    "CostoDiferencia", "TipoDiferencia", "MetodoConteo", "Observacion",
]
HEADERS_SESIONES = ["IdSesion", "FechaInicio", "FechaFin", "NombreSesion", "UsuarioCreador", "Estado", "Sucursal", "Observacion"]
HEADERS_RESUMEN = [
    "IdSesion", "Fecha", "NombreSesion", "Sucursal", "ProductosSistema",
    "ProductosContados", "ProductosOK", "ProductosFaltantes", "ProductosSobrantes",
    "UnidadesSistema", "UnidadesFisicas", "UnidadesFaltantes", "UnidadesSobrantes",
    "ValorFaltantes", "ValorSobrantes", "DesfaseNeto", "ExactitudInventario", "Estado",
    "CoberturaInventario", "ProductosPendientes", "CerosVerificados", "NoLocalizados", "ObservacionCierre",
]
HEADERS_USUARIOS = ["Usuario", "NombreCompleto", "Rol", "Password", "Estado", "Sucursales"]
HEADERS_AUDITORIA = ["FechaHora", "Usuario", "NombreCompleto", "Accion", "Detalle", "IdSesion"]
HEADERS_ZONAS = ["IdSesion", "Zona", "Responsable", "Estado", "FechaInicio", "FechaFin", "ActualizadoPor"]
HEADERS_CONTEOS_ZONA = [
    "IdSesion", "FechaHora", "Usuario", "NombreUsuario", "Zona", "CodigoBarras", "CodigoProducto", "Producto",
    "Categoria", "Sucursal", "StockSistema", "StockFisico", "CostoUnitario", "MetodoConteo", "Observacion",
    "TipoRegistro", "IdRegistro",
]
HEADERS_UNIVERSO = ["IdSesion"] + HEADERS_INVENTARIO
HEADERS_NO_LOCALIZADOS = ["IdSesion", "FechaHora", "Usuario", "CodigoBarras", "CodigoProducto", "Producto", "Sucursal", "Motivo"]
HEADERS_CONFIG_CONTEO = ["Usuario", "ConteoCiego", "ActualizadoPor", "FechaActualizacion"]
HEADERS_RECONTEOS = [
    "IdSesion", "CodigoBarras", "CodigoProducto", "Sucursal", "FechaSolicitud", "SolicitadoPor", "Motivo",
    "Estado", "FechaResolucion", "ResueltoPor", "ConteoAnterior", "ConteoNuevo",
]
VENTAS_COLUMNAS = [
    "N", "FECHA/HORA", "COMPROBANTE", "CÓDIGO DE BARRA", "CLIENTE",
    "PRODUCTO", "OBSERVACIÓN", "VARIANTE", "EQUIVALENCIA", "USUARIOS",
    "EMPLEADOS", "ALMACÉN", "TIPO", "SKU", "CATEGORÍA", "SUBCATEGORÍA",
    "U.M.", "PRECIO PROMEDIO", "COSTO*", "MONEDA", "CANTIDAD EQUIVALENCIA",
    "PRECIO X UNIDAD", "DESCUENTO", "CANTIDAD", "TOTAL",
]

# ---------- Tablas nuevas ----------
HEADERS_CONFIGURACION = ["Clave", "Valor", "Actualizado", "Usuario"]
HEADERS_MOVIMIENTOS = [
    "IdMov", "FechaHora", "Usuario", "Tipo", "Sucursal", "CodigoProducto", "CodigoBarras", "Producto",
    "Cantidad", "CostoUnitario", "Lote", "Referencia", "Motivo", "StockAntes", "StockDespues",
]
HEADERS_LOTES = ["CodigoProducto", "Sucursal", "Lote", "FechaVencimiento", "Cantidad", "FechaIngreso"]
HEADERS_PROVEEDORES = ["IdProveedor", "Nombre", "IdFiscal", "Contacto", "Telefono", "Email", "PlazoEntregaDias", "Estado"]
HEADERS_OC = ["IdOC", "Fecha", "IdProveedor", "Proveedor", "Sucursal", "Estado", "Total", "Usuario", "Observacion", "FechaRecepcion"]
HEADERS_OC_DET = ["IdOC", "CodigoProducto", "Producto", "Cantidad", "CostoUnitario", "CantidadRecibida"]
HEADERS_AJUSTES = [
    "IdAjuste", "IdSesion", "FechaHora", "CodigoProducto", "CodigoBarras", "Producto", "Sucursal", "StockSistema",
    "StockFisico", "Diferencia", "CostoUnitario", "Impacto", "Estado", "SolicitadoPor", "ResueltoPor",
    "FechaResolucion", "Comentario",
]

# clave interna -> (nombre de la hoja/tabla, columnas)
TABLAS = {
    "inventario": ("Inventario", HEADERS_INVENTARIO),
    "conteos": ("ConteoInventario", HEADERS_CONTEO),
    "sesiones": ("SesionesInventario", HEADERS_SESIONES),
    "resumen": ("ResumenInventario", HEADERS_RESUMEN),
    "usuarios": ("Usuarios", HEADERS_USUARIOS),
    "auditoria": ("Auditoria", HEADERS_AUDITORIA),
    "zonas": ("ZonasInventario", HEADERS_ZONAS),
    "conteos_zona": ("ConteosPorZona", HEADERS_CONTEOS_ZONA),
    "universo": ("UniversoInventario", HEADERS_UNIVERSO),
    "no_localizados": ("NoLocalizadosInventario", HEADERS_NO_LOCALIZADOS),
    "config_conteo": ("ConfiguracionConteo", HEADERS_CONFIG_CONTEO),
    "reconteos": ("ControlReconteos", HEADERS_RECONTEOS),
    "ventas": ("VentasProductos", VENTAS_COLUMNAS),
    "configuracion": ("Configuracion", HEADERS_CONFIGURACION),
    "movimientos": ("Movimientos", HEADERS_MOVIMIENTOS),
    "lotes": ("Lotes", HEADERS_LOTES),
    "proveedores": ("Proveedores", HEADERS_PROVEEDORES),
    "ordenes_compra": ("OrdenesCompra", HEADERS_OC),
    "ordenes_compra_det": ("OrdenesCompraDetalle", HEADERS_OC_DET),
    "ajustes": ("Ajustes", HEADERS_AJUSTES),
}
# Tablas que la app necesita desde el primer arranque
TABLAS_BASE = ["inventario", "conteos", "sesiones", "resumen", "usuarios"]


def nombre_tabla(clave):
    return TABLAS[clave][0]


def columnas(clave):
    return list(TABLAS[clave][1])

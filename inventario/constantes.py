"""Nombres de hojas y encabezados, derivados del esquema (nucleo/esquemas.py)."""
from inventario.nucleo.esquemas import TABLAS


SHEET_NAMES = {k: TABLAS[k][0] for k in ("inventario", "conteos", "sesiones", "resumen", "usuarios")}
NOMBRE_HOJA_AUDITORIA = TABLAS["auditoria"][0]
HOJA_ZONAS = TABLAS["zonas"][0]
HOJA_CONTEOS_ZONA = TABLAS["conteos_zona"][0]
HOJA_UNIVERSO = TABLAS["universo"][0]
HOJA_NO_LOCALIZADOS = TABLAS["no_localizados"][0]
HOJA_CONFIG_CONTEO = TABLAS["config_conteo"][0]
HOJA_RECONTEOS = TABLAS["reconteos"][0]
VENTAS_HOJA = TABLAS["ventas"][0]

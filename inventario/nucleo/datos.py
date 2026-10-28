"""Fachada: acceso a las tablas por su clave interna (con encabezados garantizados)."""
from . import esquemas
from .backend import a_dataframe


class Datos:
    def __init__(self, backend):
        self.backend = backend

    def t(self, clave):
        nombre, cols = esquemas.TABLAS[clave]
        return self.backend.tabla(nombre, cols)

    def df(self, clave):
        return a_dataframe(self.t(clave), esquemas.columnas(clave))

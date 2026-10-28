"""Capa de datos intercambiable.

Toda la app habla con una *Tabla* que imita a la hoja de gspread (los mismos métodos que el
código original ya usaba: get_all_records, get_all_values, row_values, append_row(s), update,
update_cell). Detrás puede haber:

  * Google Sheets  (BackendSheets)  – el original.
  * SQL            (BackendSql)     – SQLite probado; PostgreSQL implementado con el mismo SQL.
  * Memoria        (BackendMemoria) – pruebas y demos.

Así se cambia de Sheets a Postgres/Supabase tocando solo la configuración, no las pantallas.
"""
import json
import re
import threading

_A1 = re.compile(r"^([A-Za-z]+)(\d+)(?::([A-Za-z]+)(\d+))?$")


def col_a_num(letras):
    n = 0
    for ch in letras.upper():
        n = n * 26 + (ord(ch) - 64)
    return n


def num_a_col(n):
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def parse_a1(rng):
    m = _A1.match(str(rng).strip())
    if not m:
        raise ValueError(f"Rango no válido: {rng}")
    c1, r1 = col_a_num(m.group(1)), int(m.group(2))
    c2 = col_a_num(m.group(3)) if m.group(3) else c1
    r2 = int(m.group(4)) if m.group(4) else r1
    return r1, c1, r2, c2


def _s(v):
    return "" if v is None else str(v)


_INT = re.compile(r"^-?\d+$")
_FLT = re.compile(r"^-?\d*\.\d+$")


def numericizar(v):
    """Como gspread: '12' -> 12, '1.5' -> 1.5. Los códigos con ceros a la izquierda no se tocan."""
    if not isinstance(v, str):
        return v
    t = v.strip()
    if _INT.match(t) and not (len(t.lstrip("-")) > 1 and t.lstrip("-").startswith("0")):
        return int(t)
    if _FLT.match(t):
        return float(t)
    return v


# ======================= Tablas =======================
class TablaBase:
    """Implementa toda la API sobre cuatro primitivas: _grid, _append, _set_rows, _replace."""

    def get_all_values(self):
        return [list(r) for r in self._grid()]

    def get_all_records(self):
        g = self._grid()
        if not g:
            return []
        head = [str(h) for h in g[0]]
        out = []
        for r in g[1:]:
            r = list(r) + [""] * (len(head) - len(r))
            out.append({h: numericizar(v) for h, v in zip(head, r)})
        return out

    def row_values(self, n):
        g = self._grid()
        return list(g[n - 1]) if 0 < n <= len(g) else []

    def append_row(self, values, value_input_option=None):
        self._append([[_s(v) for v in values]])

    def append_rows(self, rows, value_input_option=None):
        self._append([[_s(v) for v in r] for r in rows])

    def update(self, rng, values, value_input_option=None):
        r1, c1, _, _ = parse_a1(rng)
        grid = self._grid()
        cambios = {}
        for i, fila in enumerate(values):
            n = r1 + i
            actual = list(grid[n - 1]) if n <= len(grid) else []
            necesario = c1 - 1 + len(fila)
            actual += [""] * (necesario - len(actual))
            for j, v in enumerate(fila):
                actual[c1 - 1 + j] = _s(v)
            cambios[n] = actual
        self._set_rows(cambios)

    def update_cell(self, row, col, value):
        self.update(f"{num_a_col(col)}{row}", [[value]])

    def reemplazar_todo(self, valores):
        self._replace([[_s(v) for v in r] for r in valores])

    def asegurar_columnas(self, n):
        pass


class TablaMemoria(TablaBase):
    def __init__(self):
        self.grid = []
        self._lock = threading.RLock()

    def _grid(self):
        with self._lock:
            return [list(r) for r in self.grid]

    def _append(self, filas):
        with self._lock:
            self.grid.extend(filas)

    def _set_rows(self, cambios):
        with self._lock:
            for n in sorted(cambios):
                while len(self.grid) < n:
                    self.grid.append([])
                self.grid[n - 1] = cambios[n]

    def _replace(self, grid):
        with self._lock:
            self.grid = grid


class TablaSql(TablaBase):
    """Una hoja = filas (hoja, fila, datos-json) dentro de una única tabla `hojas_filas`."""

    def __init__(self, backend, nombre):
        self.b, self.nombre = backend, nombre

    def _grid(self):
        filas = self.b.consulta("SELECT fila, datos FROM hojas_filas WHERE hoja=? ORDER BY fila", (self.nombre,))
        grid = []
        for n, datos in filas:
            while len(grid) < n - 1:
                grid.append([])
            grid.append(json.loads(datos))
        return grid

    def _append(self, filas):
        with self.b.lock:
            (maximo,), = self.b.consulta("SELECT COALESCE(MAX(fila),0) FROM hojas_filas WHERE hoja=?", (self.nombre,))
            for i, f in enumerate(filas, 1):
                self.b.ejecutar("INSERT INTO hojas_filas (hoja, fila, datos) VALUES (?,?,?)",
                                (self.nombre, int(maximo) + i, json.dumps(f, ensure_ascii=False)))

    def _set_rows(self, cambios):
        with self.b.lock:
            for n, f in cambios.items():
                dato = json.dumps(f, ensure_ascii=False)
                if self.b.ejecutar("UPDATE hojas_filas SET datos=? WHERE hoja=? AND fila=?", (dato, self.nombre, n)) == 0:
                    self.b.ejecutar("INSERT INTO hojas_filas (hoja, fila, datos) VALUES (?,?,?)", (self.nombre, n, dato))

    def _replace(self, grid):
        with self.b.lock:
            self.b.ejecutar("DELETE FROM hojas_filas WHERE hoja=?", (self.nombre,))
            for n, f in enumerate(grid, 1):
                self.b.ejecutar("INSERT INTO hojas_filas (hoja, fila, datos) VALUES (?,?,?)",
                                (self.nombre, n, json.dumps(f, ensure_ascii=False)))


class HojaSheets:
    """Envuelve una hoja de gspread. Todo pasa directo; `update` acepta ambos órdenes de argumentos
    (gspread 5 y 6) y se agregan dos utilidades."""

    def __init__(self, ws):
        self._ws = ws

    def __getattr__(self, k):
        return getattr(self._ws, k)

    def update(self, rng, values, **kw):
        try:
            return self._ws.update(range_name=rng, values=values, **kw)
        except TypeError:
            return self._ws.update(rng, values, **kw)

    def reemplazar_todo(self, valores):
        self._ws.clear()
        self._ws.update(range_name="A1", values=[[_s(v) for v in r] for r in valores], value_input_option="RAW")

    def asegurar_columnas(self, n):
        if self._ws.col_count < n:
            self._ws.add_cols(n - self._ws.col_count)


# ======================= Backends =======================
class Backend:
    nombre = "base"

    def __init__(self):
        self._verificadas = set()
        self._cerrojo = threading.RLock()

    def _obtener(self, nombre, headers, crear):
        raise NotImplementedError

    def existe(self, nombre):
        raise NotImplementedError

    def tabla(self, nombre, headers=None, crear=True):
        t = self._obtener(nombre, headers, crear)
        if headers and nombre not in self._verificadas:
            with self._cerrojo:
                self._asegurar_encabezado(t, list(headers))
                self._verificadas.add(nombre)
        return t

    @staticmethod
    def _asegurar_encabezado(t, headers):
        actual = [str(x).strip() for x in t.row_values(1)]
        if not any(actual):
            t.asegurar_columnas(len(headers))
            t.update("A1", [headers], value_input_option="RAW")
        elif actual != headers and headers[:len(actual)] == actual:   # faltan columnas nuevas al final
            t.asegurar_columnas(len(headers))
            t.update("A1", [headers], value_input_option="RAW")

    def asegurar_esquema(self, claves=None):
        """Crea las tablas que falten (con sus encabezados). Devuelve los nombres creados."""
        from .esquemas import TABLAS
        creadas = []
        for clave in (claves or TABLAS):
            nombre, cols = TABLAS[clave]
            if not self.existe(nombre):
                creadas.append(nombre)
            self.tabla(nombre, cols)
        return creadas


class BackendMemoria(Backend):
    nombre = "memoria"

    def __init__(self):
        super().__init__()
        self._t = {}

    def _obtener(self, nombre, headers, crear):
        if nombre not in self._t:
            if not crear:
                raise KeyError(nombre)
            self._t[nombre] = TablaMemoria()
        return self._t[nombre]

    def existe(self, nombre):
        return nombre in self._t


class BackendSql(Backend):
    nombre = "sql"

    def __init__(self, url):
        super().__init__()
        self.lock = threading.RLock()
        if url.startswith("sqlite"):
            import sqlite3
            ruta = url.split("///", 1)[1] if "///" in url else ":memory:"
            self._con = sqlite3.connect(ruta, check_same_thread=False, isolation_level=None)
            self.ph = "?"
        elif url.startswith("postgres"):
            import psycopg2                                     # pip install psycopg2-binary
            self._con = psycopg2.connect(url)
            self._con.autocommit = True
            self.ph = "%s"
        else:
            raise ValueError("datos_sql_url debe empezar con sqlite:/// o postgresql://")
        self.ejecutar("CREATE TABLE IF NOT EXISTS hojas_filas (hoja TEXT NOT NULL, fila INTEGER NOT NULL, datos TEXT NOT NULL, PRIMARY KEY (hoja, fila))")

    def ejecutar(self, sql, params=()):
        with self.lock:
            cur = self._con.cursor()
            cur.execute(sql.replace("?", self.ph), params)
            n = cur.rowcount
            cur.close()
            return n

    def consulta(self, sql, params=()):
        with self.lock:
            cur = self._con.cursor()
            cur.execute(sql.replace("?", self.ph), params)
            filas = cur.fetchall()
            cur.close()
            return filas

    def _obtener(self, nombre, headers, crear):
        if not crear and not self.existe(nombre):
            raise KeyError(nombre)
        return TablaSql(self, nombre)

    def existe(self, nombre):
        return bool(self.consulta("SELECT 1 FROM hojas_filas WHERE hoja=? LIMIT 1", (nombre,)))


class BackendSheets(Backend):
    nombre = "sheets"

    def __init__(self, libro):
        super().__init__()
        self.libro = libro
        self._hojas = None

    def _cargar(self):
        if self._hojas is None:                       # una sola llamada a la API, no una por hoja
            self._hojas = {ws.title: ws for ws in self.libro.worksheets()}

    def _obtener(self, nombre, headers, crear):
        self._cargar()
        ws = self._hojas.get(nombre)
        if ws is None:
            if not crear:
                raise KeyError(nombre)
            ws = self.libro.add_worksheet(title=nombre, rows=2000, cols=max(len(headers or []), 8))
            self._hojas[nombre] = ws
        return HojaSheets(ws)

    def existe(self, nombre):
        self._cargar()
        return nombre in self._hojas


def crear_backend(cfg, credenciales=None):
    """Fábrica según `cfg.datos_backend`. `credenciales` = dict de la cuenta de servicio (solo Sheets)."""
    tipo = (cfg.datos_backend or "sheets").lower()
    if tipo == "memoria":
        return BackendMemoria()
    if tipo == "sql":
        return BackendSql(cfg.datos_sql_url)
    if tipo == "sheets":
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        cred = Credentials.from_service_account_info(dict(credenciales), scopes=scopes)
        cliente = gspread.authorize(cred)
        libro = cliente.open_by_key(cfg.datos_hoja_id) if cfg.datos_hoja_id else cliente.open(cfg.datos_hoja_nombre)
        return BackendSheets(libro)
    raise ValueError(f"Backend desconocido: {tipo}")


# ======================= Utilidades sobre cualquier Tabla =======================
def _eq(a, b):
    return str(a).strip().casefold() == str(b).strip().casefold()


def buscar_filas(tabla, criterio):
    """[(numero_de_fila, {columna: valor})] cuyas columnas coinciden (sin mayúsculas/espacios)."""
    g = tabla.get_all_values()
    if not g:
        return []
    head = [str(h).strip() for h in g[0]]
    res = []
    for n, r in enumerate(g[1:], 2):
        reg = {h: (r[i] if i < len(r) else "") for i, h in enumerate(head)}
        if all(_eq(reg.get(k, ""), v) for k, v in criterio.items()):
            res.append((n, reg))
    return res


def actualizar_donde(tabla, criterio, cambios, ultima=True):
    """Actualiza UNA fila (la última coincidencia por defecto) con una sola escritura. True si encontró."""
    res = buscar_filas(tabla, criterio)
    if not res:
        return False
    n, reg = res[-1] if ultima else res[0]
    head = list(reg.keys())
    nueva = [_s(cambios.get(h, reg[h])) for h in head]
    tabla.update(f"A{n}:{num_a_col(len(head))}{n}", [nueva], value_input_option="RAW")
    return True


def agregar_dict(tabla, headers, d):
    tabla.append_row([d.get(h, "") for h in headers], value_input_option="RAW")


def a_dataframe(tabla, headers=None):
    import pandas as pd
    df = pd.DataFrame(tabla.get_all_records())
    if headers:
        for c in headers:
            if c not in df.columns:
                df[c] = ""
        df = df[list(headers) + [c for c in df.columns if c not in headers]]
    return df

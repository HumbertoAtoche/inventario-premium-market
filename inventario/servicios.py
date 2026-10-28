"""Servicios de datos: lecturas con caché (por empresa) y escrituras de la operación diaria."""
import math
import pandas as pd
import re
import streamlit as st
from inventario.constantes import HOJA_CONFIG_CONTEO, HOJA_CONTEOS_ZONA, HOJA_NO_LOCALIZADOS, HOJA_RECONTEOS, HOJA_UNIVERSO, HOJA_ZONAS
from inventario.contexto import cache_empresa, cfg, hoja_control, obtener_hoja, servicio_config, tabla
from inventario.nucleo import errores, permisos, seguridad, tiempo
from inventario.nucleo.esquemas import HEADERS_AUDITORIA, HEADERS_CONFIG_CONTEO, HEADERS_CONTEO, HEADERS_CONTEOS_ZONA, HEADERS_INVENTARIO, HEADERS_NO_LOCALIZADOS, HEADERS_RECONTEOS, HEADERS_RESUMEN, HEADERS_SESIONES, HEADERS_UNIVERSO, HEADERS_USUARIOS, HEADERS_ZONAS, VENTAS_COLUMNAS
from inventario.nucleo.seguridad import hash_password, verificar_password
from inventario.utilidades import ahora, fecha_actual, generar_id_sesion, limpiar_codigo, limpiar_numero, normalizar_df


def registrar_auditoria(accion, detalle="", id_sesion=""):
    """Bitácora de acciones críticas. Nunca interrumpe la operación principal."""
    try:
        usuario = st.session_state.get("usuario") or {}
        tabla("auditoria").append_row(
            [ahora(), usuario.get("Usuario", "SISTEMA"), usuario.get("NombreCompleto", ""), str(accion), str(detalle), str(id_sesion)],
            value_input_option="RAW")
        cargar_auditoria.clear()
    except Exception as exc:
        errores.registrar_error("auditoría", exc)


def actualizar_datos():
    """Refresco controlado: solo se ejecuta por acción explícita del usuario."""
    for cargador in (cargar_inventario, cargar_usuarios, cargar_conteos, cargar_sesiones, cargar_resumenes,
                     cargar_auditoria, cargar_universo, cargar_no_localizados, cargar_ventas):
        cargador.clear()
    servicio_config().invalidar()


@cache_empresa(ttl=60, sucursal=True)
def cargar_inventario():
    ws = obtener_hoja("inventario")
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    df = normalizar_df(df, HEADERS_INVENTARIO)
    if df.empty:
        return df
    for col in ["CodigoBarras", "CodigoProducto", "Producto", "Descripcion", "Categoria", "Marca", "Unidad", "Sucursal", "Estado"]:
        df[col] = df[col].fillna("").astype(str).str.strip()
    for col in ["StockSistema", "CostoUnitario", "PrecioVenta"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@cache_empresa(ttl=300)
def cargar_usuarios():
    ws = obtener_hoja("usuarios")
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    df = normalizar_df(df, HEADERS_USUARIOS)
    if df.empty:
        return df
    for col in HEADERS_USUARIOS:
        df[col] = df[col].fillna("").astype(str).str.strip()
    return df


@cache_empresa(ttl=30, sucursal=True)
def cargar_conteos():
    ws = obtener_hoja("conteos")
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    df = normalizar_df(df, HEADERS_CONTEO)
    for col in ["IdSesion", "FechaHora", "Usuario", "NombreUsuario", "CodigoBarras", "CodigoProducto", "Producto", "Categoria", "Sucursal", "TipoDiferencia", "MetodoConteo", "Observacion"]:
        df[col] = df[col].fillna("").astype(str).str.strip()
    for col in ["StockSistema", "StockFisico", "Diferencia", "CostoUnitario", "ValorFaltante", "ValorSobrante", "CostoDiferencia"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    zonas = consolidar_conteos_zona()
    if not zonas.empty:
        if not df.empty:
            df = df.copy()
            df["_join"] = df["IdSesion"].astype(str) + "|" + df["Sucursal"].astype(str).str.casefold() + "|" + _claves_df(df).astype(str).str.casefold()
            zonas["_join"] = zonas["IdSesion"].astype(str) + "|" + zonas["Sucursal"].astype(str).str.casefold() + "|" + _claves_df(zonas).astype(str).str.casefold()
            df = df[~df["_join"].isin(set(zonas["_join"]))].drop(columns="_join")
            zonas = zonas.drop(columns="_join")
        df = pd.concat([df, zonas], ignore_index=True)
    return df


@cache_empresa(ttl=30, sucursal=True)
def cargar_sesiones():
    ws = obtener_hoja("sesiones")
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    df = normalizar_df(df, HEADERS_SESIONES)
    if df.empty:
        return df
    for col in HEADERS_SESIONES:
        df[col] = df[col].fillna("").astype(str).str.strip()
    return df


@cache_empresa(ttl=120, sucursal=True)
def cargar_resumenes():
    ws = obtener_hoja("resumen")
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    return normalizar_df(df, HEADERS_RESUMEN)


@cache_empresa(ttl=60)
def cargar_auditoria():
    try:
        ws = tabla("auditoria")
        df = pd.DataFrame(ws.get_all_records())
    except Exception:
        return pd.DataFrame(columns=HEADERS_AUDITORIA)
    return normalizar_df(df, HEADERS_AUDITORIA)


def _claves_df(df):
    """Clave única por producto: código de barras, o código de producto, o nombre."""
    barras = df["CodigoBarras"].map(limpiar_codigo)
    codigo = df["CodigoProducto"].map(limpiar_codigo)
    nombre = df["Producto"].astype(str).str.strip()
    return barras.where(barras != "", codigo).where(lambda s: s != "", nombre)


def conteos_vigentes(df):
    """Último conteo de cada producto dentro de cada sesión (respeta los reconteos)."""
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame(columns=HEADERS_CONTEO)
    d = df.copy()
    d["_clave"] = d["IdSesion"].astype(str) + "|" + _claves_df(d)
    d = d.sort_values("FechaHora", kind="stable").drop_duplicates("_clave", keep="last")
    return d.drop(columns="_clave").sort_index()


@cache_empresa(ttl=30)
def cargar_universo():
    return normalizar_df(pd.DataFrame(hoja_control(HOJA_UNIVERSO, HEADERS_UNIVERSO).get_all_records()), HEADERS_UNIVERSO)


@cache_empresa(ttl=30)
def cargar_no_localizados():
    return normalizar_df(pd.DataFrame(hoja_control(HOJA_NO_LOCALIZADOS, HEADERS_NO_LOCALIZADOS).get_all_records()), HEADERS_NO_LOCALIZADOS)


def clave_producto(df):
    # Se identifica por sucursal + código; evita colisiones entre tiendas.
    return df["Sucursal"].astype(str).str.strip().str.casefold() + "|" + _claves_df(df).astype(str).str.strip().str.casefold()


def universo_sesion(id_sesion, sucursal=""):
    universo = cargar_universo()
    subset = universo[universo["IdSesion"].astype(str) == str(id_sesion)]
    if not subset.empty:
        d = subset[HEADERS_INVENTARIO].copy()
        for col in ["StockSistema", "CostoUnitario", "PrecioVenta"]:
            d[col] = pd.to_numeric(d[col], errors="coerce").fillna(0)
        return d.drop_duplicates(subset=["Sucursal", "CodigoProducto", "CodigoBarras"], keep="first")
    # Sesiones históricas anteriores a la actualización: catálogo actual, identificado como estimación.
    return inventario_de_sucursal(cargar_inventario(), sucursal)


def localizados_vigentes(id_sesion):
    d = cargar_no_localizados()
    d = d[d["IdSesion"].astype(str) == str(id_sesion)]
    return d.drop_duplicates(["IdSesion", "Sucursal", "CodigoBarras", "CodigoProducto"], keep="last")


def estado_cobertura(id_sesion, sucursal=""):
    inv = universo_sesion(id_sesion, sucursal).copy()
    if inv.empty:
        return inv.assign(EstadoVerificacion=pd.Series(dtype=str))
    inv["_clave"] = clave_producto(inv)
    if inv["_clave"].duplicated().any():
        raise ValueError("Existen productos con códigos duplicados en la misma sucursal. Corrige el catálogo antes de calcular la cobertura.")
    inv["EstadoVerificacion"] = "PENDIENTE"
    nc = localizados_vigentes(id_sesion)
    if not nc.empty:
        inv.loc[inv["_clave"].isin(set(clave_producto(nc))), "EstadoVerificacion"] = "NO LOCALIZADO"
    conteos = cargar_conteos()
    dc = conteos_vigentes(conteos[conteos["IdSesion"].astype(str) == str(id_sesion)]) if not conteos.empty else conteos
    if not dc.empty:
        estados = dc.copy()
        estados["_clave"] = clave_producto(estados)
        estados["_estado"] = estados.apply(lambda r: "CERO VERIFICADO" if limpiar_numero(r["StockSistema"]) == 0 and limpiar_numero(r["StockFisico"]) == 0 else ("CONFORME" if limpiar_numero(r["Diferencia"]) == 0 else ("FALTANTE" if limpiar_numero(r["Diferencia"]) < 0 else "SOBRANTE")), axis=1)
        inv["EstadoVerificacion"] = inv["_clave"].map(estados.drop_duplicates("_clave", keep="last").set_index("_clave")["_estado"]).fillna(inv["EstadoVerificacion"])
    return inv.drop(columns="_clave")


def metricas_cobertura(id_sesion, sucursal=""):
    d = estado_cobertura(id_sesion, sucursal)
    total = len(d)
    contados = int(d["EstadoVerificacion"].isin(["CONFORME", "CERO VERIFICADO", "FALTANTE", "SOBRANTE"]).sum()) if total else 0
    conformes = int(d["EstadoVerificacion"].isin(["CONFORME", "CERO VERIFICADO"]).sum()) if total else 0
    return {"total": total, "contados": contados, "pendientes": total-contados,
            "ceros": int((d["EstadoVerificacion"] == "CERO VERIFICADO").sum()) if total else 0,
            "no_localizados": int((d["EstadoVerificacion"] == "NO LOCALIZADO").sum()) if total else 0,
            "cobertura": 100*contados/total if total else 0,
            "exactitud": 100*conformes/contados if contados else 0}


def registrar_no_localizado(sesion, producto, motivo):
    if not motivo.strip():
        raise ValueError("Indica dónde se buscó o por qué no se pudo localizar el producto.")
    if ultimo_conteo_producto(sesion["IdSesion"], producto) is not None:
        raise ValueError("El producto ya tiene un conteo; utiliza reconteo para modificarlo.")
    fila = [sesion["IdSesion"], ahora(), st.session_state.usuario["Usuario"],
            limpiar_codigo(producto.get("CodigoBarras", "")), limpiar_codigo(producto.get("CodigoProducto", "")),
            producto.get("Producto", ""), producto.get("Sucursal", ""), motivo.strip()]
    hoja_control(HOJA_NO_LOCALIZADOS, HEADERS_NO_LOCALIZADOS).append_row(fila, value_input_option="RAW")
    cargar_no_localizados.clear()
    registrar_auditoria("NO_LOCALIZADO", f"{producto.get('Producto', '')}: {motivo}", sesion["IdSesion"])


def guardar_universo_sesion(id_sesion, sucursal):
    inv = inventario_de_sucursal(cargar_inventario(), sucursal)
    if inv.empty:
        raise ValueError("La sucursal no tiene productos; no se puede iniciar el inventario.")
    if clave_producto(inv).duplicated().any():
        raise ValueError("Existen códigos de producto duplicados en la sucursal. Corrige el catálogo antes de abrir la sesión.")
    rows = [[id_sesion] + [str(r.get(c, "")) for c in HEADERS_INVENTARIO] for _, r in inv.iterrows()]
    ws = hoja_control(HOJA_UNIVERSO, HEADERS_UNIVERSO)
    for i in range(0, len(rows), 300):
        ws.append_rows(rows[i:i+300], value_input_option="RAW")
    cargar_universo.clear()


def _verdadero(v):
    return str(v).strip().lower() in ("1", "true", "si", "sí", "activo", "on")


@cache_empresa(ttl=45)
def cargar_config_conteo():
    return normalizar_df(pd.DataFrame(hoja_control(HOJA_CONFIG_CONTEO, HEADERS_CONFIG_CONTEO).get_all_records()), HEADERS_CONFIG_CONTEO)


@cache_empresa(ttl=30)
def cargar_control_reconteos():
    return normalizar_df(pd.DataFrame(hoja_control(HOJA_RECONTEOS, HEADERS_RECONTEOS).get_all_records()), HEADERS_RECONTEOS)


def conteo_ciego_usuario(usuario):
    if permisos.es_supervision(usuario):
        return False
    d = cargar_config_conteo()
    fila = d[d["Usuario"].astype(str).str.casefold() == str(usuario.get("Usuario", "")).casefold()]
    return _verdadero(fila.iloc[-1]["ConteoCiego"]) if not fila.empty else bool(cfg().conteo_ciego)


def configurar_conteo_ciego(nombre_usuario, activo, administrador):
    ws = hoja_control(HOJA_CONFIG_CONTEO, HEADERS_CONFIG_CONTEO)
    filas = ws.get_all_values()
    objetivo = str(nombre_usuario).strip().casefold()
    numero = next((i for i, r in enumerate(filas[1:], 2) if r and r[0].strip().casefold() == objetivo), None)
    registro = [nombre_usuario, "SI" if activo else "NO", administrador, ahora()]
    if numero:
        ws.update(f"A{numero}:D{numero}", [registro], value_input_option="RAW")
    else:
        ws.append_row(registro, value_input_option="RAW")
    cargar_config_conteo.clear()
    registrar_auditoria("CONFIG_CONTEO_CIEGO", f"{nombre_usuario}: {'SI' if activo else 'NO'}")


def _clave_registro(p):
    return (str(p.get("Sucursal", "")).strip().casefold(),
            limpiar_codigo(p.get("CodigoBarras", "")) or limpiar_codigo(p.get("CodigoProducto", "")) or str(p.get("Producto", "")).strip())


def solicitudes_producto(id_sesion, producto):
    d = cargar_control_reconteos()
    if d.empty:
        return d
    clave = _clave_registro(producto)
    return d[(d["IdSesion"].astype(str) == str(id_sesion)) &
             (d.apply(_clave_registro, axis=1) == clave)]


def solicitud_pendiente(id_sesion, producto):
    d = solicitudes_producto(id_sesion, producto)
    return not d.empty and str(d.iloc[-1]["Estado"]).upper() == "PENDIENTE"


def solicitar_reconteo(sesion, producto, usuario, motivo):
    if not motivo.strip():
        raise ValueError("El motivo del reconteo es obligatorio.")
    if solicitud_pendiente(sesion["IdSesion"], producto):
        return
    ws = hoja_control(HOJA_RECONTEOS, HEADERS_RECONTEOS)
    ws.append_row([sesion["IdSesion"], limpiar_codigo(producto.get("CodigoBarras", "")),
                   limpiar_codigo(producto.get("CodigoProducto", "")), producto.get("Sucursal", ""),
                   ahora(), usuario.get("Usuario", ""), motivo.strip(), "PENDIENTE", "", "", "", ""], value_input_option="RAW")
    cargar_control_reconteos.clear()
    registrar_auditoria("SOLICITAR_RECONTEO", f"{producto.get('Producto', '')} · {motivo}", sesion["IdSesion"])


def resolver_reconteo(sesion, producto, usuario, anterior, nuevo):
    ws = hoja_control(HOJA_RECONTEOS, HEADERS_RECONTEOS)
    valores = ws.get_all_values()
    clave = _clave_registro(producto)
    for n in range(len(valores)-1, 0, -1):
        r = valores[n]
        if len(r) >= 8 and r[0] == str(sesion["IdSesion"]) and _clave_registro(dict(zip(HEADERS_RECONTEOS, r))) == clave and r[7] == "PENDIENTE":
            ws.update(f"H{n+1}:L{n+1}", [["RESUELTO", ahora(), usuario.get("Usuario", ""), anterior, nuevo]], value_input_option="RAW")
            cargar_control_reconteos.clear()
            return


def pendientes_anteriores(sesion):
    sesiones = cargar_sesiones()
    anteriores = sesiones[(sesiones["IdSesion"].astype(str) != str(sesion["IdSesion"])) &
                         (sesiones["Sucursal"].astype(str).str.strip().str.casefold() == str(sesion["Sucursal"]).strip().casefold()) &
                         (sesiones["Estado"].astype(str).str.upper() == "CERRADA")].copy()
    if anteriores.empty:
        return pd.DataFrame()
    anteriores = anteriores.sort_values("FechaInicio", ascending=False)
    previa = anteriores.iloc[0]
    anterior = estado_cobertura(previa["IdSesion"], previa["Sucursal"])
    actual = estado_cobertura(sesion["IdSesion"], sesion["Sucursal"])
    if anterior.empty or actual.empty:
        return pd.DataFrame()
    claves = set(clave_producto(anterior[anterior["EstadoVerificacion"].isin(["PENDIENTE", "NO LOCALIZADO"])]))
    resultado = actual[clave_producto(actual).isin(claves) & actual["EstadoVerificacion"].isin(["PENDIENTE", "NO LOCALIZADO"])].copy()
    resultado["SesionAnterior"] = previa["NombreSesion"]
    return resultado


@cache_empresa(ttl=15)
def cargar_zonas():
    return normalizar_df(pd.DataFrame(hoja_control(HOJA_ZONAS, HEADERS_ZONAS).get_all_records()), HEADERS_ZONAS)


@cache_empresa(ttl=15)
def cargar_conteos_zona():
    df = normalizar_df(pd.DataFrame(hoja_control(HOJA_CONTEOS_ZONA, HEADERS_CONTEOS_ZONA).get_all_records()), HEADERS_CONTEOS_ZONA)
    for c in ("StockSistema", "StockFisico", "CostoUnitario"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


def zonas_sesion(id_sesion):
    d = cargar_zonas()
    return d[d["IdSesion"].astype(str) == str(id_sesion)].copy()


def zona_usuario(sesion, usuario):
    zona = st.session_state.get("zona_activa", "")
    d = zonas_sesion(sesion["IdSesion"])
    match = d[d["Zona"] == zona]
    if match.empty:
        return None
    z = match.iloc[-1].to_dict()
    if not permisos.es_supervision(usuario) and str(z["Responsable"]).strip().casefold() != str(usuario.get("Usuario", "")).strip().casefold():
        return None
    return z if str(z["Estado"]).upper() == "EN PROCESO" else None


def ultimo_conteo_zona(id_sesion, zona, producto):
    d = cargar_conteos_zona()
    d = d[(d["IdSesion"].astype(str) == str(id_sesion)) & (d["Zona"] == zona)]
    if d.empty:
        return None
    k = _clave_registro(producto)
    d = d[d.apply(lambda r: _clave_registro(r) == k, axis=1)]
    return d.iloc[-1].to_dict() if not d.empty else None


def guardar_conteo_zona(sesion, usuario, producto, fisico, metodo, observacion, reconteo):
    zona = zona_usuario(sesion, usuario)
    if zona is None:
        raise ValueError("Selecciona una zona asignada y abierta antes de guardar.")
    if str(sesion.get("Estado", "")).upper() != "ABIERTA":
        raise ValueError("La sesión está cerrada.")
    cargar_conteos_zona.clear()
    previo = ultimo_conteo_zona(sesion["IdSesion"], zona["Zona"], producto)
    # No combinar un conteo general previo con uno por zonas sin conciliación explícita.
    raw = normalizar_df(pd.DataFrame(obtener_hoja("conteos").get_all_records()), HEADERS_CONTEO)
    if not raw.empty:
        anteriores = raw[raw["IdSesion"].astype(str) == str(sesion["IdSesion"])]
        if not anteriores.empty and any(_clave_registro(r) == _clave_registro(producto) for _, r in anteriores.iterrows()):
            raise ValueError("Este producto ya tiene un conteo general en la sesión. No puede mezclarse con el conteo por zonas; utiliza una nueva sesión para ese producto.")
    if previo and not reconteo:
        raise ValueError("Este producto ya fue contado en esta zona. Usa Reconteo para corregirlo.")
    if not previo and reconteo:
        raise ValueError("No existe conteo previo en esta zona.")
    if reconteo and not observacion.strip():
        raise ValueError("Indica el motivo del reconteo.")
    from uuid import uuid4
    fila = [sesion["IdSesion"], ahora(), usuario["Usuario"], usuario["NombreCompleto"], zona["Zona"], limpiar_codigo(producto.get("CodigoBarras", "")), limpiar_codigo(producto.get("CodigoProducto", "")), producto.get("Producto", ""), producto.get("Categoria", ""), producto.get("Sucursal", ""), limpiar_numero(producto.get("StockSistema", 0)), float(fisico), limpiar_numero(producto.get("CostoUnitario", 0)), metodo, observacion.strip(), "RECONTEO" if reconteo else "CONTEO", str(uuid4())]
    hoja_control(HOJA_CONTEOS_ZONA, HEADERS_CONTEOS_ZONA).append_row(fila, value_input_option="RAW")
    cargar_conteos_zona.clear()
    cargar_conteos.clear()
    registrar_auditoria("RECONTEO_ZONA" if reconteo else "CONTEO_ZONA", f"{zona['Zona']} · {producto.get('Producto','')} · {fisico} unidades · {observacion}", sesion["IdSesion"])
    return True


def consolidar_conteos_zona():
    d = cargar_conteos_zona()
    if d.empty:
        return pd.DataFrame(columns=HEADERS_CONTEO)
    d = d.copy()
    d["_clave"] = d["IdSesion"].astype(str) + "|" + d["Sucursal"].astype(str).str.casefold() + "|" + _claves_df(d).astype(str).str.casefold()
    # Un reconteo sustituye únicamente la cantidad previa de SU zona.
    d = d.drop_duplicates(["_clave", "Zona"], keep="last")
    filas = []
    for (_, _), g in d.groupby(["IdSesion", "_clave"], sort=False):
        p = g.iloc[-1]
        fisico = float(g["StockFisico"].sum())
        sistema = float(p["StockSistema"])
        costo = float(p["CostoUnitario"])
        dif = fisico - sistema
        filas.append(dict(IdSesion=p["IdSesion"], FechaHora=p["FechaHora"], Usuario=p["Usuario"], NombreUsuario=" / ".join(sorted(set(g["NombreUsuario"].astype(str)))), CodigoBarras=p["CodigoBarras"], CodigoProducto=p["CodigoProducto"], Producto=p["Producto"], Categoria=p["Categoria"], Sucursal=p["Sucursal"], StockSistema=sistema, StockFisico=fisico, Diferencia=dif, CostoUnitario=costo, ValorFaltante=max(-dif,0)*costo, ValorSobrante=max(dif,0)*costo, CostoDiferencia=dif*costo, TipoDiferencia="FALTANTE" if dif<0 else "SOBRANTE" if dif>0 else "OK", MetodoConteo="Por zonas", Observacion=" | ".join(f"{r.Zona}: {r.StockFisico:g}" for r in g.itertuples())))
    return normalizar_df(pd.DataFrame(filas), HEADERS_CONTEO)


def guardar_zona_estado(id_sesion, zona, responsable, estado, actor):
    ws = hoja_control(HOJA_ZONAS, HEADERS_ZONAS)
    datos = ws.get_all_values()
    if not datos:
        raise ValueError("No hay datos de zonas.")
    h = datos[0]
    for i, r in enumerate(datos[1:], start=2):
        if len(r)>1 and r[0] == id_sesion and r[1] == zona:
            previo = r[h.index("Estado")] if len(r)>h.index("Estado") else ""
            inicio = r[h.index("FechaInicio")] if len(r)>h.index("FechaInicio") else ""
            fin = r[h.index("FechaFin")] if len(r)>h.index("FechaFin") else ""
            valores = [id_sesion,zona,responsable,estado, inicio or (ahora() if estado=="EN PROCESO" else ""), ahora() if estado=="FINALIZADA" else ("" if previo=="FINALIZADA" else fin),actor]
            ws.update(f"A{i}:G{i}", [valores], value_input_option="RAW")
            cargar_zonas.clear()
            registrar_auditoria("ESTADO_ZONA", f"{zona}: {previo} → {estado}; responsable {responsable}", id_sesion)
            return
    raise ValueError("Zona no encontrada.")


def crear_zonas_iniciales(sesion):
    if not zonas_sesion(sesion["IdSesion"]).empty:
        return
    hoja_control(HOJA_ZONAS, HEADERS_ZONAS).append_rows([[sesion["IdSesion"], z, "", "PENDIENTE", "", "", ""] for z in cfg().zonas], value_input_option="RAW")
    cargar_zonas.clear()


def contar_productos_sesion(conteos, id_sesion):
    """Productos distintos contados en una sesión (un reconteo no suma dos veces)."""
    if conteos is None or conteos.empty:
        return 0
    dc = conteos[conteos["IdSesion"].astype(str) == str(id_sesion)]
    return len(conteos_vigentes(dc))


def ultimo_conteo_producto(id_sesion, producto):
    df = cargar_conteos()
    if df.empty:
        return None
    dc = df[df["IdSesion"].astype(str) == str(id_sesion)]
    if dc.empty:
        return None
    vig = conteos_vigentes(dc)
    clave = (
        limpiar_codigo(producto.get("CodigoBarras", ""))
        or limpiar_codigo(producto.get("CodigoProducto", ""))
        or str(producto.get("Producto", "")).strip()
    )
    coincide = vig[_claves_df(vig) == clave]
    return coincide.iloc[-1].to_dict() if not coincide.empty else None


def inventario_de_sucursal(inv, sucursal):
    """Productos que corresponden a la sucursal de la sesión.
    Si el nombre de la sucursal no coincide con ningún producto, devuelve todo el inventario
    (así nunca queda en cero por una diferencia de escritura)."""
    if inv is None or inv.empty:
        return inv
    suc = str(sucursal or "").strip().lower()
    if not suc:
        return inv
    filtrado = inv[inv["Sucursal"].astype(str).str.strip().str.lower() == suc]
    return filtrado  # Nunca mezclar sucursales si el nombre no coincide


def es_diferencia_critica(stock_sistema, stock_fisico, costo):
    """True si la diferencia es lo bastante grande como para exigir confirmación."""
    dif = abs(limpiar_numero(stock_fisico) - limpiar_numero(stock_sistema))
    if dif == 0:
        return False
    valor = dif * limpiar_numero(costo)
    base = limpiar_numero(stock_sistema)
    porcentaje = (dif / base * 100) if base > 0 else 100.0
    return valor >= cfg().umbral_dif_monto or (dif >= cfg().umbral_dif_unidades and porcentaje >= cfg().umbral_dif_pct)


def autenticar(usuario, password):
    usuarios = cargar_usuarios()
    if usuarios.empty:
        return None
    usuario = str(usuario).strip().lower()
    fila = usuarios[usuarios["Usuario"].str.lower() == usuario]
    if fila.empty:
        return None
    registro = fila.iloc[0]
    if str(registro["Estado"]).strip().lower() not in ["activo", "activa", "1", "true", "sí", "si"]:
        return None
    guardada = str(registro["Password"]).strip()
    if verificar_password(password, guardada):
        return registro.to_dict()
    return None


def buscar_por_codigo(codigo, df=None):
    if df is None:
        df = cargar_inventario()
    codigo = limpiar_codigo(codigo)
    if not codigo or df.empty:
        return None
    for col in ["CodigoBarras", "CodigoProducto"]:
        mask = df[col].map(limpiar_codigo) == codigo
        if mask.any():
            return df.loc[mask].iloc[0].to_dict()
    return None


def buscar_productos(texto, df=None):
    if df is None:
        df = cargar_inventario()
    if df.empty:
        return df
    texto = str(texto).strip()
    if not texto:
        return df.head(50).copy()
    patron = re.escape(texto)
    mask = pd.Series(False, index=df.index)
    for col in ["CodigoBarras", "CodigoProducto", "Producto", "Descripcion", "Categoria", "Marca"]:
        mask = mask | df[col].astype(str).str.contains(patron, case=False, na=False, regex=True)
    return df.loc[mask].head(100).copy()


def obtener_sesion_abierta(usuario=None):
    df = cargar_sesiones()
    if df.empty:
        return None
    abiertas = df[df["Estado"].str.upper() == "ABIERTA"].copy()
    if usuario:
        propias = abiertas[abiertas["UsuarioCreador"].astype(str).str.lower() == str(usuario).lower()]
        if not propias.empty:
            return propias.iloc[-1].to_dict()
    if not abiertas.empty:
        return abiertas.iloc[-1].to_dict()
    return None


def producto_ya_contado(id_sesion, codigo):
    df = cargar_conteos()
    if df.empty:
        return False
    codigo = limpiar_codigo(codigo)
    return bool(((df["IdSesion"] == str(id_sesion)) & ((df["CodigoBarras"].map(limpiar_codigo) == codigo) if codigo else (df["CodigoBarras"].map(limpiar_codigo) == "__NO_COINCIDE__"))).any())


def guardar_conteo(sesion, usuario, producto, stock_fisico, metodo="Escáner", observacion="", es_reconteo=False):
    # Comprobación contra datos actualizados: evita guardar accidentalmente un segundo primer conteo.
    cargar_conteos.clear()
    anterior = ultimo_conteo_producto(sesion["IdSesion"], producto)
    if ultimo_conteo_zona(sesion["IdSesion"], st.session_state.get("zona_activa", ""), producto) is not None or (not cargar_conteos_zona().empty and any((r["IdSesion"] == sesion["IdSesion"] and _clave_registro(r) == _clave_registro(producto)) for _, r in cargar_conteos_zona().iterrows())):
        raise ValueError("Este producto tiene conteos por zonas. Selecciona su zona para modificar la cantidad.")
    if anterior is not None and not es_reconteo:
        raise ValueError("Este producto ya fue contado. Abre el flujo de reconteo para modificarlo.")
    if anterior is None and es_reconteo:
        raise ValueError("No existe conteo anterior para corregir.")
    if es_reconteo and not observacion.strip():
        raise ValueError("Debes indicar el motivo de corrección para guardar el reconteo.")
    stock_sistema = limpiar_numero(producto.get("StockSistema", 0))
    costo = limpiar_numero(producto.get("CostoUnitario", 0))
    stock_fisico = limpiar_numero(stock_fisico)
    diferencia = stock_fisico - stock_sistema

    valor_faltante = abs(diferencia) * costo if diferencia < 0 else 0
    valor_sobrante = diferencia * costo if diferencia > 0 else 0
    costo_diferencia = valor_sobrante - valor_faltante

    if diferencia < 0:
        tipo = "FALTANTE"
    elif diferencia > 0:
        tipo = "SOBRANTE"
    else:
        tipo = "OK"

    obs = observacion.strip()
    if es_reconteo:
        obs = ("[RECONTEO] " + obs).strip()

    fila = [
        sesion["IdSesion"], ahora(), usuario["Usuario"], usuario["NombreCompleto"],
        limpiar_codigo(producto.get("CodigoBarras", "")),
        limpiar_codigo(producto.get("CodigoProducto", "")),
        producto.get("Producto", ""), producto.get("Categoria", ""), producto.get("Sucursal", ""),
        stock_sistema, stock_fisico, diferencia, costo, valor_faltante, valor_sobrante,
        costo_diferencia, tipo, metodo, obs
    ]
    obtener_hoja("conteos").append_row(fila, value_input_option="USER_ENTERED")
    cargar_conteos.clear()
    if not es_reconteo and es_diferencia_critica(stock_sistema, stock_fisico, costo):
        try:
            solicitar_reconteo(sesion, producto, usuario, "Diferencia crítica automática")
        except Exception:
            registrar_auditoria("ALERTA_RECONTEO", f"Pendiente de solicitud: {producto.get('Producto', '')}", sesion["IdSesion"])
    if es_reconteo:
        resolver_reconteo(sesion, producto, usuario, anterior.get("StockFisico", ""), stock_fisico)
        registrar_auditoria(
            "RECONTEO",
            f"{producto.get('Producto', '')} · físico {stock_fisico:,.0f} · sistema {stock_sistema:,.0f} · {tipo}",
            sesion["IdSesion"],
        )
    return tipo, diferencia, valor_faltante, valor_sobrante


def crear_sesion(nombre, sucursal, usuario, observacion=""):
    id_sesion = generar_id_sesion()
    fila = [
        id_sesion, ahora(), "", nombre.strip(), usuario["Usuario"],
        "ABIERTA", sucursal.strip(), observacion.strip()
    ]
    guardar_universo_sesion(id_sesion, sucursal.strip())
    obtener_hoja("sesiones").append_row(fila, value_input_option="USER_ENTERED")
    cargar_sesiones.clear()
    registrar_auditoria("CREAR_SESION", f"{nombre.strip()} · {sucursal.strip()}", id_sesion)
    return id_sesion


def cerrar_sesion(id_sesion, detalle=""):
    ws = obtener_hoja("sesiones")
    # Acción poco frecuente: una sola lectura directa para localizar la fila.
    valores = ws.get_all_values()
    if not valores:
        return False
    try:
        headers = valores[0]
        idx_id = headers.index("IdSesion")
        idx_fin = headers.index("FechaFin")
        idx_estado = headers.index("Estado")
        for n, fila in enumerate(valores[1:], start=2):
            if len(fila) > idx_id and fila[idx_id] == str(id_sesion):
                ws.update_cell(n, idx_fin + 1, ahora())
                ws.update_cell(n, idx_estado + 1, "CERRADA")
                cargar_sesiones.clear()
                registrar_auditoria("CERRAR_SESION", detalle, id_sesion)
                return True
    except Exception:
        raise
    return False


def calcular_resumen(id_sesion):
    inv = cargar_inventario()
    conteos = cargar_conteos()
    sesiones = cargar_sesiones()

    if conteos.empty:
        dc = pd.DataFrame(columns=HEADERS_CONTEO)
    else:
        dc = conteos_vigentes(conteos[conteos["IdSesion"].astype(str) == str(id_sesion)].copy())

    ses = sesiones[sesiones["IdSesion"].astype(str) == str(id_sesion)] if not sesiones.empty else pd.DataFrame()
    nombre = ses.iloc[0]["NombreSesion"] if not ses.empty else str(id_sesion)
    sucursal = ses.iloc[0]["Sucursal"] if not ses.empty else ""
    estado = ses.iloc[0]["Estado"] if not ses.empty else ""

    cobertura = metricas_cobertura(id_sesion, sucursal)
    productos_contados = cobertura["contados"]
    productos_ok = int((dc["TipoDiferencia"] == "OK").sum()) if not dc.empty else 0
    productos_faltantes = int((dc["TipoDiferencia"] == "FALTANTE").sum()) if not dc.empty else 0
    productos_sobrantes = int((dc["TipoDiferencia"] == "SOBRANTE").sum()) if not dc.empty else 0

    unidades_sistema = float(dc["StockSistema"].sum()) if not dc.empty else 0
    unidades_fisicas = float(dc["StockFisico"].sum()) if not dc.empty else 0
    unidades_faltantes = abs(float(dc.loc[dc["Diferencia"] < 0, "Diferencia"].sum())) if not dc.empty else 0
    unidades_sobrantes = float(dc.loc[dc["Diferencia"] > 0, "Diferencia"].sum()) if not dc.empty else 0
    valor_faltantes = float(dc["ValorFaltante"].sum()) if not dc.empty else 0
    valor_sobrantes = float(dc["ValorSobrante"].sum()) if not dc.empty else 0
    desfase_neto = valor_faltantes - valor_sobrantes
    exactitud = (productos_ok / productos_contados * 100) if productos_contados else 0

    return {
        "IdSesion": id_sesion,
        "Fecha": fecha_actual(),
        "NombreSesion": nombre,
        "Sucursal": sucursal,
        "ProductosSistema": cobertura["total"],
        "ProductosContados": productos_contados,
        "ProductosOK": productos_ok,
        "ProductosFaltantes": productos_faltantes,
        "ProductosSobrantes": productos_sobrantes,
        "UnidadesSistema": unidades_sistema,
        "UnidadesFisicas": unidades_fisicas,
        "UnidadesFaltantes": unidades_faltantes,
        "UnidadesSobrantes": unidades_sobrantes,
        "ValorFaltantes": valor_faltantes,
        "ValorSobrantes": valor_sobrantes,
        "DesfaseNeto": desfase_neto,
        "ExactitudInventario": exactitud,
        "Estado": estado,
        "CoberturaInventario": cobertura["cobertura"],
        "ProductosPendientes": cobertura["pendientes"],
        "CerosVerificados": cobertura["ceros"],
        "NoLocalizados": cobertura["no_localizados"],
        "ObservacionCierre": "",
    }


def guardar_resumen(resumen):
    fila = [resumen.get(col, "") for col in HEADERS_RESUMEN]
    ws = obtener_hoja("resumen")
    encabezado_actual = ws.row_values(1)
    if encabezado_actual != HEADERS_RESUMEN:
        ws.update("A1", [HEADERS_RESUMEN])
    ws.append_row(fila, value_input_option="USER_ENTERED")
    cargar_resumenes.clear()


def crear_usuario(usuario, nombre, rol, password, sucursales="*"):
    problemas = seguridad.validar_password(password, usuario, cfg().min_largo_password)
    if problemas:
        raise ValueError(" ".join(problemas))
    df = cargar_usuarios()
    if not df.empty and (df["Usuario"].str.lower() == usuario.strip().lower()).any():
        raise ValueError("Ese usuario ya existe.")
    fila = [usuario.strip(), nombre.strip(), rol.strip().upper(), hash_password(password), "ACTIVO", sucursales or "*"]
    obtener_hoja("usuarios").append_row(fila, value_input_option="USER_ENTERED")
    cargar_usuarios.clear()
    registrar_auditoria("CREAR_USUARIO", f"{usuario.strip()} · {rol.strip().upper()}")


def generar_ajustes(dc):
    """Lista de ajustes de stock lista para cargar en el sistema contable/ERP."""
    cols = ["CodigoBarras", "CodigoProducto", "Producto", "Sucursal", "StockSistema",
            "StockFisico", "Ajuste", "TipoAjuste", "CostoUnitario", "ImpactoSoles"]
    if dc is None or dc.empty:
        return pd.DataFrame(columns=cols)
    d = dc[dc["Diferencia"] != 0].copy()
    if d.empty:
        return pd.DataFrame(columns=cols)
    d["Ajuste"] = d["Diferencia"]
    d["TipoAjuste"] = d["Diferencia"].map(lambda x: "ENTRADA" if x > 0 else "SALIDA")
    d["ImpactoSoles"] = d["CostoDiferencia"]
    return d[cols].sort_values("ImpactoSoles").reset_index(drop=True)


def lista_diferencias(dc, tipo):
    """Lista COMPLETA de faltantes (tipo='FALTANTE') o sobrantes (tipo='SOBRANTE'),
    con cantidades en positivo, lista para cuadrar con el sistema de ventas."""
    es_falt = tipo == "FALTANTE"
    col_cant = "CantidadFaltante" if es_falt else "CantidadSobrante"
    col_valor = "ValorFaltante" if es_falt else "ValorSobrante"
    cols = ["CodigoBarras", "CodigoProducto", "Producto", "Categoria", "Sucursal",
            "StockSistema", "StockFisico", col_cant, "CostoUnitario", col_valor]
    if dc is None or dc.empty:
        return pd.DataFrame(columns=cols)
    d = dc[dc["TipoDiferencia"] == tipo].copy()
    if d.empty:
        return pd.DataFrame(columns=cols)
    d[col_cant] = d["Diferencia"].abs()
    return d[cols].sort_values(col_valor, ascending=False).reset_index(drop=True)


def clasificar_abc(inv, corte_a=80.0, corte_b=95.0):
    """Clasificación ABC (Pareto) por valor de inventario a costo."""
    cols = ["Clase", "Producto", "CodigoProducto", "Categoria", "StockSistema",
            "CostoUnitario", "Valor", "% Valor", "% Acumulado"]
    if inv is None or inv.empty:
        return pd.DataFrame(columns=cols)
    d = inv.copy()
    d["Valor"] = d["StockSistema"].clip(lower=0) * d["CostoUnitario"]
    d = d[d["Valor"] > 0].sort_values("Valor", ascending=False)
    if d.empty:
        return pd.DataFrame(columns=cols)
    total = d["Valor"].sum()
    d["% Valor"] = d["Valor"] / total * 100
    d["% Acumulado"] = d["% Valor"].cumsum()
    previo = d["% Acumulado"] - d["% Valor"]
    d["Clase"] = "C"
    d.loc[previo < corte_b, "Clase"] = "B"
    d.loc[previo < corte_a, "Clase"] = "A"
    return d[cols].reset_index(drop=True)


def diagnosticar_inventario(inv):
    """Reglas de calidad de datos. Devuelve [(regla, severidad, DataFrame)]."""
    if inv is None or inv.empty:
        return []
    barras = inv["CodigoBarras"].map(limpiar_codigo)
    duplicado = (barras != "") & barras.duplicated(keep=False)
    reglas = [
        ("Stock negativo", "Alta", inv["StockSistema"] < 0),
        ("Sin costo unitario", "Alta", inv["CostoUnitario"] <= 0),
        ("Precio menor al costo", "Alta",
         (inv["PrecioVenta"] > 0) & (inv["CostoUnitario"] > 0) & (inv["PrecioVenta"] < inv["CostoUnitario"])),
        ("Sin precio de venta", "Media", inv["PrecioVenta"] <= 0),
        ("Código de barras duplicado", "Media", duplicado),
        ("Sin código de barras", "Media", barras == ""),
        ("Sin categoría", "Baja", inv["Categoria"].astype(str).str.strip() == ""),
        ("Stock en cero", "Info", inv["StockSistema"] == 0),
    ]
    return [(nombre, sev, inv[mask].copy()) for nombre, sev, mask in reglas]


def productos_pendientes(inv, conteos, id_sesion):
    """Productos del inventario que todavía no se cuentan en la sesión, del más valioso al menos."""
    if inv is None or inv.empty:
        return pd.DataFrame()
    contados = set()
    if conteos is not None and not conteos.empty:
        dc = conteos[conteos["IdSesion"].astype(str) == str(id_sesion)]
        if not dc.empty:
            contados = set(_claves_df(dc))
    d = inv[~_claves_df(inv).isin(contados)].copy()
    d["Valor"] = d["StockSistema"].clip(lower=0) * d["CostoUnitario"]
    return d.sort_values("Valor", ascending=False)


def productividad_contadores(conteos, id_sesion=None):
    cols = ["Contador", "Conteos", "OK", "Faltantes", "Sobrantes", "Exactitud %",
            "Horas activas", "Conteos/hora", "Impacto neto"]
    if conteos is None or conteos.empty:
        return pd.DataFrame(columns=cols)
    d = conteos.copy()
    if id_sesion:
        d = d[d["IdSesion"].astype(str) == str(id_sesion)]
    # Solo la primera pasada de cada producto: los reconteos no inflan la productividad ni la exactitud.
    d = d[~d["Observacion"].astype(str).str.startswith("[RECONTEO]")]
    if d.empty:
        return pd.DataFrame(columns=cols)
    d["_dt"] = pd.to_datetime(d["FechaHora"], errors="coerce")
    filas = []
    for nombre, g in d.groupby("NombreUsuario"):
        n = len(g)
        ok = int((g["TipoDiferencia"] == "OK").sum())
        horas = float("nan")
        ritmo = float("nan")
        if id_sesion:
            marcas = g["_dt"].dropna()
            if len(marcas) > 1:
                horas = (marcas.max() - marcas.min()).total_seconds() / 3600
                if horas >= 0.05:
                    ritmo = n / horas
        filas.append({
            "Contador": nombre,
            "Conteos": n,
            "OK": ok,
            "Faltantes": int((g["TipoDiferencia"] == "FALTANTE").sum()),
            "Sobrantes": int((g["TipoDiferencia"] == "SOBRANTE").sum()),
            "Exactitud %": round(ok / n * 100, 1) if n else 0.0,
            "Horas activas": round(horas, 2) if horas == horas else float("nan"),
            "Conteos/hora": round(ritmo, 1) if ritmo == ritmo else float("nan"),
            "Impacto neto": round(float(g["CostoDiferencia"].sum()), 2),
        })
    return pd.DataFrame(filas, columns=cols).sort_values("Conteos", ascending=False).reset_index(drop=True)


def tendencia_sesiones(resumenes):
    if resumenes is None or resumenes.empty:
        return pd.DataFrame()
    d = resumenes.copy()
    for col in ["ExactitudInventario", "DesfaseNeto", "ValorFaltantes", "ValorSobrantes", "ProductosContados"]:
        d[col] = pd.to_numeric(d[col], errors="coerce").fillna(0)
    d = d.drop_duplicates("IdSesion", keep="last").sort_values("Fecha", kind="stable")
    d["Etiqueta"] = d["Fecha"].astype(str) + " · " + d["NombreSesion"].astype(str)
    repetidos = d.groupby("Etiqueta").cumcount()
    d["Etiqueta"] = d["Etiqueta"] + repetidos.map(lambda i: "" if i == 0 else f" ({i + 1})")
    return d.reset_index(drop=True)


def alertas_operativas(inv, sesiones):
    """Alertas breves para el dashboard de inicio."""
    alertas = []
    if sesiones is not None and not sesiones.empty:
        abiertas = sesiones[sesiones["Estado"].str.upper() == "ABIERTA"]
        for _, s in abiertas.iterrows():
            inicio = pd.to_datetime(s["FechaInicio"], errors="coerce")
            if pd.notna(inicio):
                horas = (tiempo.ahora() - inicio.to_pydatetime()).total_seconds() / 3600
                if horas >= cfg().horas_sesion_alerta:
                    alertas.append(
                        f"La sesión **{s['NombreSesion']}** lleva {horas:,.0f} h abierta. Revisa si ya debe cerrarse."
                    )
    if inv is not None and not inv.empty:
        negativos = int((inv["StockSistema"] < 0).sum())
        sin_costo = int((inv["CostoUnitario"] <= 0).sum())
        if negativos:
            alertas.append(f"Hay **{negativos:,}** producto(s) con stock negativo en el sistema.")
        if sin_costo:
            alertas.append(f"Hay **{sin_costo:,}** producto(s) sin costo unitario: su valor de inventario está subestimado.")
    return alertas


@cache_empresa(ttl=120)
def cargar_ventas():
    hoja = tabla("ventas")
    valores = hoja.get_all_values()
    if not valores:
        return pd.DataFrame(columns=VENTAS_COLUMNAS)
    cabecera = [str(v).strip() for v in valores[0]]
    if cabecera[:len(VENTAS_COLUMNAS)] != VENTAS_COLUMNAS:
        raise ValueError("La hoja VentasProductos debe comenzar en la fila 1 con los 25 encabezados del reporte, desde N hasta TOTAL. No copies la fila de título general del Excel.")
    datos = [r[:len(VENTAS_COLUMNAS)] + [""] * max(0, len(VENTAS_COLUMNAS) - len(r)) for r in valores[1:] if any(str(x).strip() for x in r)]
    return pd.DataFrame(datos, columns=VENTAS_COLUMNAS)


def preparar_ventas(df):
    if df.empty:
        d = df.copy()
        for col in ["Fecha", "Dia", "Clave", "Cantidad", "CantidadValida", "VentaTotal", "CostoTotal", "MargenTotal"]:
            d[col] = pd.Series(dtype="object")
        return d
    d = df.copy()
    d["Fecha"] = pd.to_datetime(d["FECHA/HORA"].astype(str).str.strip(), format="%d-%m-%Y %H:%M", errors="coerce")
    fallos = d["Fecha"].isna()
    if fallos.any():
        d.loc[fallos, "Fecha"] = pd.to_datetime(d.loc[fallos, "FECHA/HORA"], dayfirst=True, errors="coerce")
    d = d[d["Fecha"].notna()].copy()
    d["Dia"] = d["Fecha"].dt.normalize()
    d["Clave"] = d["CÓDIGO DE BARRA"].astype(str).str.strip()
    d["Clave"] = d["Clave"].where(d["Clave"] != "", d["SKU"].astype(str).str.strip())
    d["Clave"] = d["Clave"].where(d["Clave"] != "", d["PRODUCTO"].astype(str).str.strip())
    d["Cantidad"] = pd.to_numeric(d["CANTIDAD"].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    d["VentaTotal"] = pd.to_numeric(d["TOTAL"].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    d["CostoTotal"] = pd.to_numeric(d["COSTO*"].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    d["MargenTotal"] = d["VentaTotal"] - d["CostoTotal"]
    d["CantidadValida"] = d["Cantidad"].notna() & (d["Cantidad"] > 0)
    return d


def diagnostico_ventas(df):
    if df.empty:
        return 0, 0, 0
    return len(df), int(df["CantidadValida"].sum()), int((~df["CantidadValida"]).sum())


def resumen_demanda(df, inventario, dias_entrega, dias_seguridad, ventana, objetivo_servicio):
    """Demanda por días calendario, sin extrapolar ventas ausentes como ceros confiables."""
    if df.empty:
        return pd.DataFrame()
    fecha_fin = df["Dia"].max()
    inicio = fecha_fin - pd.Timedelta(days=ventana - 1)
    recientes = df[(df["Dia"] >= inicio) & (df["Dia"] <= fecha_fin)].copy()
    if recientes.empty:
        return pd.DataFrame()
    # Sólo se consideran días de operación conocidos; los días sin exportación
    # pueden ser días sin ventas o días faltantes, y requieren confirmación.
    dias_base = max(1, min(ventana, (fecha_fin - df["Dia"].min()).days + 1))
    recientes = recientes[recientes["CantidadValida"]].copy()
    if recientes.empty:
        return pd.DataFrame()
    a = recientes.groupby("Clave", as_index=False).agg(
        Producto=("PRODUCTO", "first"), Categoria=("CATEGORÍA", "first"),
        Unidades=("Cantidad", "sum"), Lineas=("Clave", "size"),
        VentaTotal=("VentaTotal", "sum"), CostoTotal=("CostoTotal", "sum"),
        DiasConVenta=("Dia", "nunique"),
    )
    a["DemandaDiaria"] = a["Unidades"] / dias_base
    a["MargenTotal"] = a["VentaTotal"] - a["CostoTotal"]
    a["MargenPorcentaje"] = (100 * a["MargenTotal"] / a["VentaTotal"].replace(0, float("nan"))).round(1)
    # Incluye días sin ventas del producto dentro de la ventana, no solo días con venta.
    diario = recientes.groupby(["Clave", "Dia"])["Cantidad"].sum().reset_index()
    suma_cuadrados = diario.assign(Cuadrado=diario["Cantidad"] ** 2).groupby("Clave")["Cuadrado"].sum()
    # Desviación poblacional con días cero, suponiendo que la carga del periodo es completa.
    a["DesviacionDiaria"] = ((a["Clave"].map(suma_cuadrados).fillna(0) / dias_base - a["DemandaDiaria"] ** 2).clip(lower=0)) ** 0.5
    z = {90:1.282, 95:1.645, 98:2.054, 99:2.326}.get(int(objetivo_servicio), 1.645)
    a["StockSeguridad"] = (z * a["DesviacionDiaria"] * math.sqrt(max(1, dias_entrega)) + a["DemandaDiaria"] * dias_seguridad).apply(math.ceil)
    a["PuntoPedido"] = (a["DemandaDiaria"] * dias_entrega + a["StockSeguridad"]).apply(math.ceil)
    a["StockObjetivo"] = (a["DemandaDiaria"] * (dias_entrega + dias_seguridad + 7) + a["StockSeguridad"]).apply(math.ceil)
    inv = inventario.copy()
    inv["Clave"] = inv["CodigoBarras"].astype(str).str.strip()
    inv["Clave"] = inv["Clave"].where(inv["Clave"] != "", inv["CodigoProducto"].astype(str).str.strip())
    inv = inv.groupby("Clave", as_index=False).agg(StockActual=("StockSistema", "sum"), CostoUnitario=("CostoUnitario", "mean"))
    a = a.merge(inv, on="Clave", how="left", indicator="VinculoInventario")
    a["VinculadoInventario"] = a["VinculoInventario"].eq("both")
    a["StockActual"] = a["StockActual"].fillna(0)
    a["CostoUnitario"] = a["CostoUnitario"].fillna(0)
    a["DiasCobertura"] = a["StockActual"] / a["DemandaDiaria"].replace(0, float("nan"))
    a["CompraSugerida"] = (a["StockObjetivo"] - a["StockActual"]).clip(lower=0).apply(math.ceil)
    a.loc[a["StockActual"] > a["PuntoPedido"], "CompraSugerida"] = 0
    a["InversionSugerida"] = a["CompraSugerida"] * a["CostoUnitario"]
    a["Estado"] = "Adecuado"
    a.loc[a["StockActual"] <= a["PuntoPedido"], "Estado"] = "Reponer"
    a.loc[a["StockActual"] <= 0, "Estado"] = "Sin stock"
    a.loc[a["DiasCobertura"] > 60, "Estado"] = "Sobrestock posible"
    a.loc[~a["VinculadoInventario"], "Estado"] = "Sin vincular inventario"
    a.loc[~a["VinculadoInventario"], "CompraSugerida"] = 0
    a.loc[~a["VinculadoInventario"], "InversionSugerida"] = 0
    return a.sort_values(["Estado", "InversionSugerida"], ascending=[True, False])


def _leer_reporte_excel(archivo):
    bruto = pd.read_excel(archivo, sheet_name="ventas_productos", header=0, dtype=str)
    bruto.columns = [str(c).strip() for c in bruto.columns]
    if not all(c in bruto.columns for c in VENTAS_COLUMNAS):
        bruto = pd.read_excel(archivo, sheet_name="ventas_productos", header=1, dtype=str)
        bruto.columns = [str(c).strip() for c in bruto.columns]
    faltan = [c for c in VENTAS_COLUMNAS if c not in bruto.columns]
    if faltan:
        raise ValueError("Faltan encabezados del archivo: " + ", ".join(faltan))
    return bruto[VENTAS_COLUMNAS].fillna("").astype(str)

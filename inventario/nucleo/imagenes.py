"""Logo de la empresa: se reduce para que quepa en una celda de la hoja de configuración (límite 50.000 caracteres)."""
import base64
import io

_MIME = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}


def logo_a_data_uri(contenido, limite_chars=44000):
    from PIL import Image
    im = Image.open(io.BytesIO(contenido))
    im.load()
    alfa = im.mode in ("RGBA", "LA", "P") and ("A" in im.getbands() or "transparency" in im.info)
    formatos = [("WEBP", {"quality": 80}), ("PNG", {"optimize": True})] if alfa else [("JPEG", {"quality": 82}), ("PNG", {"optimize": True})]
    for lado in (256, 192, 128, 96, 64):
        t = im.copy()
        t.thumbnail((lado, lado))
        for fmt, kw in formatos:
            buf = io.BytesIO()
            try:
                (t.convert("RGBA") if alfa else t.convert("RGB")).save(buf, fmt, **kw)
            except (OSError, KeyError, ValueError):
                continue
            uri = f"data:{_MIME[fmt]};base64," + base64.b64encode(buf.getvalue()).decode("ascii")
            if len(uri) <= limite_chars:
                return uri
    raise ValueError("La imagen es demasiado compleja. Usa un logo más simple o súbelo como archivo en la carpeta assets.")

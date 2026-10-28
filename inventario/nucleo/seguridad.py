"""Contraseñas y bloqueo de acceso.

El bloqueo vive en la memoria del SERVIDOR (no de la sesión): recargar la página o abrir
otra pestaña ya no reinicia el contador de intentos.
"""
import hashlib
import hmac
import secrets
import threading
import time


def hash_password(password):
    """PBKDF2 para usuarios nuevos. Mantiene compatibilidad de lectura con SHA256 legado."""
    salt = secrets.token_bytes(16)
    rondas = 310000
    derivada = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), salt, rondas)
    return f"pbkdf2_sha256${rondas}${salt.hex()}${derivada.hex()}"


def verificar_password(password, guardada):
    guardada = str(guardada or "").strip()
    if guardada.startswith("pbkdf2_sha256$"):
        try:
            _, rondas, salt, esperado = guardada.split("$", 3)
            derivada = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), bytes.fromhex(salt), int(rondas))
            return hmac.compare_digest(derivada, bytes.fromhex(esperado))
        except (ValueError, TypeError):
            return False
    if len(guardada) == 64:
        return hmac.compare_digest(hashlib.sha256(str(password).encode("utf-8")).hexdigest(), guardada)
    # Compatibilidad transitoria con contraseñas antiguas en texto plano.
    return bool(guardada) and hmac.compare_digest(str(password), guardada)


def validar_password(password, usuario="", minimo=10):
    """Lista de problemas (vacía = contraseña aceptable)."""
    problemas = []
    if len(password or "") < minimo:
        problemas.append(f"Debe tener al menos {minimo} caracteres.")
    if usuario and str(usuario).strip().lower() in str(password).lower():
        problemas.append("No debe contener el nombre de usuario.")
    if password and password.isdigit():
        problemas.append("No puede ser solo números.")
    return problemas


class GuardaLogin:
    """Cuenta intentos fallidos por clave (empresa|usuario) y bloquea temporalmente."""

    def __init__(self, max_intentos=5, ventana_seg=600, bloqueo_seg=300, reloj=time.time):
        self.max, self.ventana, self.bloqueo, self._t = max_intentos, ventana_seg, bloqueo_seg, reloj
        self._fallos, self._hasta = {}, {}
        self._lock = threading.Lock()

    def configurar(self, max_intentos, bloqueo_seg):
        self.max, self.bloqueo = int(max_intentos), int(bloqueo_seg)

    def segundos_bloqueado(self, clave):
        with self._lock:
            return max(0, int(self._hasta.get(clave, 0) - self._t()))

    def registrar_fallo(self, clave):
        """Devuelve (bloqueado_ahora, intentos_restantes)."""
        with self._lock:
            ahora = self._t()
            lista = [t for t in self._fallos.get(clave, []) if ahora - t < self.ventana] + [ahora]
            if len(lista) >= self.max:
                self._hasta[clave] = ahora + self.bloqueo
                self._fallos[clave] = []
                return True, 0
            self._fallos[clave] = lista
            return False, self.max - len(lista)

    def limpiar(self, clave):
        with self._lock:
            self._fallos.pop(clave, None)
            self._hasta.pop(clave, None)


_GUARDAS = {}
_GUARDAS_LOCK = threading.Lock()


def guarda_de(empresa_id):
    """Una guarda por empresa, compartida por todas las sesiones del servidor."""
    with _GUARDAS_LOCK:
        return _GUARDAS.setdefault(empresa_id, GuardaLogin())

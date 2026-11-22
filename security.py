"""Almacenamiento seguro de contraseñas (PBKDF2-HMAC-SHA256)."""
import hashlib
import hmac
import secrets

def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError('La contraseña debe tener al menos 12 caracteres')
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 600_000)
    return f'pbkdf2_sha256$600000${salt.hex()}${digest.hex()}'

def check_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = encoded.split('$')
        if algorithm != 'pbkdf2_sha256' or int(rounds) < 100_000:
            return False
        check = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(check, bytes.fromhex(digest_hex))
    except (TypeError, ValueError, AttributeError):
        return False

import base64
import hashlib
import hmac
import os
import keyring
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from smd.paths import KEYRING_SERVICE, KEYRING_USER, SALT_FILE


def load_or_create_salt() -> bytes:
    if SALT_FILE.exists():
        return SALT_FILE.read_bytes()
    salt = os.urandom(16)
    SALT_FILE.write_bytes(salt)
    return salt


def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
        backend=default_backend(),
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def get_encryption_key(password: str | None = None) -> bytes | None:
    pwd = password or keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    if not pwd:
        return None
    if not SALT_FILE.exists():
        load_or_create_salt()
    return derive_key(pwd, SALT_FILE.read_bytes())


def store_encryption_password(password: str) -> None:
    keyring.set_password(KEYRING_SERVICE, KEYRING_USER, password)
    load_or_create_salt()


def encrypt_file(file_path, key: bytes):
    from pathlib import Path

    path = Path(file_path)
    if path.name.endswith(".enc"):
        return path
    encrypted = Fernet(key).encrypt(path.read_bytes())
    encrypted_path = path.with_suffix(path.suffix + ".enc")
    encrypted_path.write_bytes(encrypted)
    path.unlink()
    return encrypted_path


def decrypt_bytes(path, key: bytes) -> bytes:
    from pathlib import Path

    return Fernet(key).decrypt(Path(path).read_bytes())


def encrypt_folder(folder, key: bytes) -> int:
    from pathlib import Path

    count = 0
    for file in Path(folder).iterdir():
        if file.is_file() and not file.name.endswith(".enc"):
            encrypt_file(file, key)
            count += 1
    return count


def decrypt_folder(folder, key: bytes) -> int:
    from pathlib import Path

    count = 0
    for file in Path(folder).iterdir():
        if file.is_file() and file.name.endswith(".enc"):
            data = decrypt_bytes(file, key)
            original = file.with_suffix("")
            original.write_bytes(data)
            file.unlink()
            count += 1
    return count


def hash_gui_pin(pin: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 100_000)
    return base64.b64encode(salt + digest).decode("ascii")


def verify_gui_pin(pin: str, stored: str) -> bool:
    raw = base64.b64decode(stored.encode("ascii"))
    salt, digest = raw[:16], raw[16:]
    check = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 100_000)
    return hmac.compare_digest(digest, check)


def manifest_hmac_key() -> bytes | None:
    key = get_encryption_key()
    if not key:
        return None
    return hashlib.sha256(key).digest()

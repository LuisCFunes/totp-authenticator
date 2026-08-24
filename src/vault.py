import json
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32
SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1

VAULT_MAGIC = b"TVAULT\x00\x01"
BACKUP_MAGIC = b"TBACKUP\x01"


def default_vault_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "TOTPAuthenticator", "vault.enc")


def _derive_key(password, salt):
    kdf = Scrypt(salt=salt, length=KEY_SIZE, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return kdf.derive(password.encode("utf-8"))


def write_container(path, magic, password, payload):
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = _derive_key(password, salt)
    ct = AESGCM(key).encrypt(nonce, payload, None)
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(magic + salt + nonce + ct)
    os.replace(tmp, path)


def read_container(path, magic, password):
    with open(path, "rb") as f:
        blob = f.read()
    header_len = len(magic) + SALT_SIZE + NONCE_SIZE
    if len(blob) < header_len + 16:
        raise ValueError("File is corrupted or truncated")
    if blob[: len(magic)] != magic:
        raise ValueError("Unrecognized file format")
    offset = len(magic)
    salt = blob[offset : offset + SALT_SIZE]
    offset += SALT_SIZE
    nonce = blob[offset : offset + NONCE_SIZE]
    offset += NONCE_SIZE
    ct = blob[offset:]
    key = _derive_key(password, salt)
    return AESGCM(key).decrypt(nonce, ct, None)


def new_accounts_payload(accounts=None):
    return {"version": 1, "accounts": accounts if accounts is not None else []}


class Vault:
    def __init__(self, path=None):
        self.path = path or default_vault_path()
        self.data = None
        self._key = None
        self._salt = None

    def exists(self):
        return os.path.exists(self.path)

    def create(self, password, data=None):
        self.data = data if data is not None else new_accounts_payload()
        self._salt = os.urandom(SALT_SIZE)
        self._key = _derive_key(password, self._salt)
        self.save()

    def unlock(self, password):
        try:
            with open(self.path, "rb") as f:
                blob = f.read()
            header_len = len(VAULT_MAGIC) + SALT_SIZE + NONCE_SIZE
            if len(blob) < header_len + 16 or blob[: len(VAULT_MAGIC)] != VAULT_MAGIC:
                return False
            offset = len(VAULT_MAGIC)
            salt = blob[offset : offset + SALT_SIZE]
            offset += SALT_SIZE
            nonce = blob[offset : offset + NONCE_SIZE]
            offset += NONCE_SIZE
            ct = blob[offset:]
            key = _derive_key(password, salt)
            payload = AESGCM(key).decrypt(nonce, ct, None)
        except (InvalidTag, OSError, ValueError):
            return False
        self._salt = salt
        self._key = key
        self.data = json.loads(payload.decode("utf-8"))
        return True

    def save(self):
        if self._key is None:
            raise RuntimeError("Vault is locked")
        payload = json.dumps(self.data).encode("utf-8")
        nonce = os.urandom(NONCE_SIZE)
        ct = AESGCM(self._key).encrypt(nonce, payload, None)
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(VAULT_MAGIC + self._salt + nonce + ct)
        os.replace(tmp, self.path)

    def lock(self):
        self._key = None
        self._salt = None
        self.data = None

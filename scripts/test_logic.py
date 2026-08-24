import os
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src import export as backup_mod
from src import importers, vault

tmp = tempfile.mkdtemp()

v = vault.Vault(os.path.join(tmp, "vault.enc"))
assert not v.exists()
account = {
    "issuer": "GitHub",
    "label": "octocat@github.com",
    "secret": "JBSWY3DPEHPK3PXP",
    "digits": 6,
    "period": 30,
    "algorithm": "SHA1",
}
v.create("correct-horse-42", vault.new_accounts_payload([account]))
assert v.exists()
assert not v.unlock("wrong-password")
reopened = vault.Vault(os.path.join(tmp, "vault.enc"))
assert reopened.unlock("correct-horse-42")
assert reopened.data["accounts"][0]["issuer"] == "GitHub"
print("vault: OK")

uri = "otpauth://totp/GitHub:octocat%40github.com?secret=jbswy3dpehpk3pxp&issuer=GitHub"
parsed = importers.parse_otpauth(uri)
assert parsed["issuer"] == "GitHub", parsed
assert parsed["label"] == "octocat@github.com", parsed
assert parsed["secret"] == "JBSWY3DPEHPK3PXP"
assert parsed["algorithm"] == "SHA1" and parsed["digits"] == 6 and parsed["period"] == 30

import pyotp

code = pyotp.TOTP("JBSWY3DPEHPK3PXP").now()
assert len(code) == 6 and code.isdigit()

for bad in ["https://example.com", "otpauth://hotp/x?secret=JBSWY3DPEHPK3PXP",
            "otpauth://totp/x?secret=NOTBASE32!!"]:
    try:
        importers.parse_otpauth(bad)
        raise AssertionError(f"should have rejected: {bad}")
    except ValueError:
        pass
print("otpauth parsing: OK")

import cv2
from PIL import Image

encoder = cv2.QRCodeEncoder.create()
qr_img = Image.fromarray(encoder.encode(uri))
decoded = importers.decode_qr_from_pil(qr_img)
assert decoded == uri, f"QR round-trip mismatch: {decoded!r}"
print("QR decode: OK")

backup_path = os.path.join(tmp, "backup.totpbak")
backup_mod.write_backup(backup_path, {"accounts": [parsed]}, "backup-passphrase")
restored = backup_mod.read_backup(backup_path, "backup-passphrase")
assert restored["accounts"][0]["secret"] == parsed["secret"]
try:
    backup_mod.read_backup(backup_path, "wrong-pass")
    raise AssertionError("wrong password should fail")
except Exception:
    pass
print("backup round-trip: OK")

current = []
assert backup_mod.merge_accounts(current, [parsed]) == 1
assert backup_mod.merge_accounts(current, [dict(parsed)]) == 0
print("merge dedupe: OK")

print("ALL LOGIC TESTS PASSED")

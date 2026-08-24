import base64
import hashlib
from urllib.parse import parse_qs, unquote, urlparse

DIGESTS = {
    "SHA1": hashlib.sha1,
    "SHA256": hashlib.sha256,
    "SHA512": hashlib.sha512,
}


def parse_otpauth(uri):
    uri = uri.strip().strip("'\"")
    parsed = urlparse(uri)
    if parsed.scheme.lower() != "otpauth":
        raise ValueError("Link must start with otpauth://")
    if parsed.netloc.lower() != "totp":
        raise ValueError("Only otpauth://totp links are supported")

    path = unquote(parsed.path.lstrip("/"))
    if not path:
        raise ValueError("Missing account name in the link")

    params = {k: v[-1] for k, v in parse_qs(parsed.query).items()}
    secret = params.get("secret", "").replace(" ", "")
    if not secret:
        raise ValueError("The link has no secret key")

    normalized = secret.upper() + "=" * (-len(secret) % 8)
    try:
        base64.b32decode(normalized)
    except Exception:
        raise ValueError("The secret key is not valid Base32")

    if ":" in path:
        issuer_from_path, label = path.split(":", 1)
    else:
        issuer_from_path, label = "", path

    issuer = params.get("issuer") or issuer_from_path
    algorithm = (params.get("algorithm") or "SHA1").upper()
    if algorithm not in DIGESTS:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    try:
        digits = int(params.get("digits") or 6)
        period = int(params.get("period") or 30)
    except ValueError:
        digits, period = 6, 30
    if digits not in (6, 7, 8):
        raise ValueError(f"Unsupported digit count: {digits}")
    if not 1 <= period <= 120:
        period = 30

    return {
        "issuer": issuer,
        "label": label,
        "secret": secret.upper(),
        "algorithm": algorithm,
        "digits": digits,
        "period": period,
    }


def decode_qr_from_pil(image):
    import cv2
    import numpy as np

    arr = np.array(image.convert("RGB"))
    detector = cv2.QRCodeDetector()
    for candidate in _qr_variants(arr):
        data, _, _ = detector.detectAndDecode(candidate)
        if data:
            return data.strip()
    return None


def _qr_variants(arr):
    import cv2
    import numpy as np

    yield arr
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    yield gray
    height, width = gray.shape[:2]
    if max(height, width) < 600:
        scale = 600 / max(height, width)
        yield cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    yield otsu


def image_from_clipboard():
    from PIL import ImageGrab

    try:
        grabbed = ImageGrab.grabclipboard()
    except Exception:
        return None
    if grabbed is None:
        return None
    if isinstance(grabbed, list):
        from PIL import Image

        for path in grabbed:
            try:
                return Image.open(path)
            except Exception:
                continue
        return None
    return grabbed

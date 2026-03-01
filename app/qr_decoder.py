"""
qr_decoder.py — Decode QR codes from image files or bytes.

Handles both clean QR scans and photos of receipts (with OpenCV pre-processing).
"""
import io
from pathlib import Path
from PIL import Image
from pyzbar.pyzbar import decode as pyzbar_decode


def decode_qr_from_bytes(image_bytes: bytes) -> str | None:
    """
    Try to extract a URL/text from a QR code in image bytes.
    Falls back to enhanced processing if simple decode fails.
    """
    img = Image.open(io.BytesIO(image_bytes))
    result = _try_decode(img)

    if not result:
        # Try grayscale + upscale for low-res photos
        result = _try_decode_enhanced(img)

    return result


def decode_qr_from_path(path: str) -> str | None:
    with open(path, "rb") as f:
        return decode_qr_from_bytes(f.read())


def _try_decode(img: Image.Image) -> str | None:
    decoded = pyzbar_decode(img)
    if decoded:
        return decoded[0].data.decode("utf-8")
    return None


def _try_decode_enhanced(img: Image.Image) -> str | None:
    """
    Pre-process the image to improve QR detection on receipt photos:
    - Convert to grayscale
    - Upscale 2x
    - Increase contrast
    """
    # Grayscale
    gray = img.convert("L")

    # Upscale 2×
    w, h = gray.size
    large = gray.resize((w * 2, h * 2), Image.LANCZOS)

    # Increase contrast with auto-levels
    from PIL import ImageOps
    enhanced = ImageOps.autocontrast(large)

    decoded = pyzbar_decode(enhanced)
    if decoded:
        return decoded[0].data.decode("utf-8")

    # Final attempt: crop the lower portion (QR is usually at bottom of receipts)
    bottom_crop = enhanced.crop((0, int(h * 2 * 0.6), w * 2, h * 2))
    decoded = pyzbar_decode(bottom_crop)
    if decoded:
        return decoded[0].data.decode("utf-8")

    return None

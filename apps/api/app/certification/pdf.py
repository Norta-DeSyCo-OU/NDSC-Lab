"""Certificate PDF rendering + signature embedding."""
from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime

import pikepdf
import qrcode
from PIL import Image
from weasyprint import HTML

from app.certification.signer import SignResult, sign_bytes
from app.core.settings import get_settings

_TEMPLATE = """
<!doctype html>
<html><head><meta charset="utf-8"><style>
  @page {{ size: A4 landscape; margin: 30mm; }}
  body {{ font-family: 'DejaVu Sans', system-ui, sans-serif; color: #0a0f1e; }}
  .frame {{ border: 4px solid #18C5FF; padding: 40px; height: 100%; }}
  h1 {{ font-size: 32pt; margin: 0 0 10pt; color: #0a1628; }}
  .sub {{ font-size: 14pt; color: #2563FF; margin-bottom: 30pt; }}
  .name {{ font-size: 28pt; font-weight: 700; border-bottom: 2px solid #1e40af; padding-bottom: 6pt; margin: 10pt 0 30pt; }}
  .course {{ font-size: 18pt; font-style: italic; margin-bottom: 30pt; }}
  .meta {{ font-size: 11pt; color: #131b35; }}
  .footer {{ margin-top: 40pt; display: flex; justify-content: space-between; align-items: flex-end; }}
  .id {{ font-family: monospace; font-size: 10pt; color: #1e3a8a; }}
  img.qr {{ width: 90pt; height: 90pt; }}
</style></head>
<body>
<div class="frame">
  <h1>Certificate of Completion</h1>
  <div class="sub">NDSC Lab — issued by Norta DeSyCo OU</div>
  <p>This is to certify that</p>
  <div class="name">{recipient}</div>
  <p>has successfully completed the course</p>
  <div class="course">{course}</div>
  <p class="meta">Issued on {issued_on} · Cert ID <span class="id">{cert_id}</span></p>
  <div class="footer">
    <div class="meta">Verify at<br><span class="id">{verify_url}</span></div>
    <img class="qr" src="{qr_data_uri}" alt="QR" />
  </div>
</div>
</body></html>
"""


@dataclass(frozen=True, slots=True)
class CertRender:
    pdf_bytes: bytes
    signature_b64: str
    key_id: str


def _qr_data_uri(text: str) -> str:
    import base64

    qr = qrcode.QRCode(version=None, box_size=4, border=1)
    qr.add_data(text)
    qr.make(fit=True)
    img: Image.Image = qr.make_image(fill_color="#0a0f1e", back_color="#FFFFFF").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def render_and_sign(
    *,
    cert_id: str,
    recipient: str,
    course: str,
    issued_at: datetime,
) -> CertRender:
    """Two-pass envelope: build the *canonical* PDF (carrying cert_id + key_id but no
    signature), sign that canonical byte stream, then embed only /NdscSig and re-save.

    The verification side reopens the signed PDF, drops /NdscSig and re-saves; because
    pikepdf serialization is deterministic for identical content, the result equals
    the original canonical bytes — and the embedded signature verifies against them.
    """
    s = get_settings()
    verify_url = f"{s.frontend_base_url}/verify/{cert_id}"
    html = _TEMPLATE.format(
        recipient=recipient,
        course=course,
        issued_on=issued_at.strftime("%Y-%m-%d"),
        cert_id=cert_id,
        verify_url=verify_url,
        qr_data_uri=_qr_data_uri(verify_url),
    )
    raw_pdf = HTML(string=html).write_pdf()

    # Pass 1: embed cert metadata (no signature yet), get canonical bytes.
    pdf = pikepdf.open(io.BytesIO(raw_pdf))
    pdf.docinfo["/NdscCertId"] = cert_id
    pdf.docinfo["/NdscKeyId"] = s.cert_ed25519_key_id
    canon_buf = io.BytesIO()
    pdf.save(canon_buf)
    canonical_bytes = canon_buf.getvalue()

    # Sign the canonical bytes.
    sig = sign_bytes(canonical_bytes)

    # Pass 2: open canonical bytes, add only /NdscSig, save final.
    pdf2 = pikepdf.open(io.BytesIO(canonical_bytes))
    pdf2.docinfo["/NdscSig"] = sig.signature_b64
    final = io.BytesIO()
    pdf2.save(final)
    return CertRender(pdf_bytes=final.getvalue(), signature_b64=sig.signature_b64, key_id=sig.key_id)


def extract_signature(signed_pdf: bytes) -> tuple[str | None, str | None, str | None]:
    pdf = pikepdf.open(io.BytesIO(signed_pdf))
    info = pdf.docinfo
    cert_id = str(info.get("/NdscCertId")) if info.get("/NdscCertId") else None
    key_id = str(info.get("/NdscKeyId")) if info.get("/NdscKeyId") else None
    sig = str(info.get("/NdscSig")) if info.get("/NdscSig") else None
    return cert_id, key_id, sig


def strip_signature(signed_pdf: bytes) -> bytes:
    """Return the canonical bytes used for verification (PDF without /NdscSig).

    Round-trips with the canonical output of `render_and_sign` pass 1.
    """
    pdf = pikepdf.open(io.BytesIO(signed_pdf))
    info = pdf.docinfo
    if "/NdscSig" in info:
        del info["/NdscSig"]
    out = io.BytesIO()
    pdf.save(out)
    return out.getvalue()

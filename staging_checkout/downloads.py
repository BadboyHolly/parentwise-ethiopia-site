"""Private, per-request authorized delivery using a mockable versioned object store.

The staging app injects generated QA-only PDFs. Production R2 credentials and
objects are never read by this staging route.
"""
import hashlib

from fastapi import Header, HTTPException, Request, Response
from sqlalchemy import select

from production_checkout.private_storage import (
    ManifestError, MockObjectStore, ProductFile, ProductManifest,
    StorageUnavailable, fetch_verified_part,
)
from .models import DownloadGrant, OrderState
from .security import order_for_customer


def dummy_pdf(part: int) -> bytes:
    label = f"QA DEMO ONLY - PART {part} - NOT A PAID PARENTWISE PRODUCT"
    stream = f"BT /F1 12 Tf 48 720 Td ({label}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n% QA ONLY\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    return bytes(output)


def _install_dummy_store(app) -> None:
    """Install only an in-memory mock when this staging app has no test store."""
    if (hasattr(app.state, "product_object_store") and
            hasattr(app.state, "product_manifest") and
            hasattr(app.state, "product_bucket")):
        return
    bucket = "qa-dummy-only"
    objects = {}
    files = []
    for part in range(1, 6):
        key = f"qa-dummy/v1/part-{part}.pdf"
        version = "qa-dummy-v1"
        content = dummy_pdf(part)
        objects[(bucket, key, version)] = content
        files.append(ProductFile(part, key, version, hashlib.sha256(content).hexdigest()))
    app.state.product_bucket = bucket
    app.state.product_object_store = MockObjectStore(objects)
    app.state.product_manifest = ProductManifest(files)


def mount_downloads(app):
    _install_dummy_store(app)

    @app.get("/api/v1/orders/{code}/downloads/part-{part}")
    def download(code: str, part: int, request: Request,
                 authorization: str = Header(default="", alias="Authorization")):
        if part < 1 or part > 5:
            raise HTTPException(404, "Download not found",
                                headers={"Cache-Control": "private, no-store"})
        with app.state.order_sessions() as db:
            # Revalidate the private bearer token, approved state and active grant
            # before every single object read. A request never trusts a prior download.
            order = order_for_customer(db, code, authorization, app.state.order_token_secret)
            state = db.scalar(select(OrderState).where(OrderState.order_id == order.id))
            grant = db.scalar(select(DownloadGrant).where(DownloadGrant.order_id == order.id))
            if (state is None or state.status != "READY_TO_DOWNLOAD" or grant is None or
                    not grant.active or grant.revoked_at is not None):
                raise HTTPException(403, "Downloads are not available for this order",
                                    headers={"Cache-Control": "private, no-store"})
            try:
                _, content = fetch_verified_part(
                    app.state.product_object_store,
                    bucket=app.state.product_bucket,
                    manifest=app.state.product_manifest,
                    part=part,
                )
            except (ManifestError, StorageUnavailable, OSError, KeyError):
                # Provider/path/version details remain server-side; retry may be safe.
                raise HTTPException(503, "Download temporarily unavailable",
                                    headers={"Cache-Control": "private, no-store",
                                             "Retry-After": "30"}) from None
            return Response(content=content, media_type="application/pdf",
                headers={"Cache-Control": "private, no-store",
                         "Content-Disposition": f'attachment; filename="qa-demo-part-{part}.pdf"',
                         "X-Content-Type-Options": "nosniff",
                         "Referrer-Policy": "no-referrer",
                         "Vary": "Authorization"})

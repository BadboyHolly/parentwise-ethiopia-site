"""Authenticated delivery of harmless, private QA-only PDF fixtures."""
import os
import re
from pathlib import Path
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from .models import Order, QaDownloadGrant
from .security import equal_hash, hash_value

router = APIRouter()
_MAKER = None
FILES = {
    'part-1': 'QA_DEMO_PART_1.pdf', 'part-2': 'QA_DEMO_PART_2.pdf',
    'part-3': 'QA_DEMO_PART_3.pdf', 'part-4': 'QA_DEMO_PART_4.pdf',
    'part-5': 'QA_DEMO_PART_5.pdf',
}

@router.get('/api/v1/orders/{code}/downloads/{document_id}')
def download(code: str, document_id: str, request: Request, authorization: str = Header(default='')):
    if os.getenv('APP_MODE', 'qa') != 'qa' or os.getenv('PAYMENTS_ENABLED', 'false').lower() != 'false':
        raise HTTPException(503, 'QA downloads are unavailable')
    filename = FILES.get(document_id)
    if not filename or not re.fullmatch(r'PW-QA-[A-F0-9]{24}', code):
        raise HTTPException(404, 'QA file not found or access denied')
    if not authorization.startswith('Bearer ') or len(authorization[7:]) != 43:
        raise HTTPException(404, 'QA file not found or access denied')
    with _MAKER() as db:
        order = db.scalar(select(Order).where(Order.order_code == code))
        if not order or not equal_hash(order.access_token_hash, hash_value(authorization[7:])):
            raise HTTPException(404, 'QA file not found or access denied')
        grant = db.scalar(select(QaDownloadGrant).where(QaDownloadGrant.order_id == order.id))
        if order.status != 'VERIFIED_PAID' or not grant or grant.revoked_at is not None:
            raise HTTPException(403, 'QA downloads are not available for this order')
        path = Path(__file__).resolve().parent.parent / 'qa-assets' / filename
        if not path.is_file():
            raise HTTPException(503, 'QA sample file is unavailable')
        return FileResponse(path, media_type='application/pdf', filename=filename,
            headers={'Cache-Control':'no-store, private', 'X-Content-Type-Options':'nosniff', 'Referrer-Policy':'no-referrer'})

def mount_customer_downloads(app, maker):
    global _MAKER
    _MAKER = maker
    app.include_router(router)

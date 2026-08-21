from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.context import tenant_query
from app.core.rbac import require_permission
from app.database import get_db
from app.models import AuditLog, User
from app.schemas import AuditLogOut

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
def list_logs(
    action: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("audit.read")),
):
    q = tenant_query(db, AuditLog, user.tenant_id)
    if action:
        q = q.filter(AuditLog.action == action)
    logs = q.order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [AuditLogOut.model_validate(l) for l in logs]
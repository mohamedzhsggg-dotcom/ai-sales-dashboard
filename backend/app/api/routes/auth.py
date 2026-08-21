from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.database import get_db
from app.models import Category, Session as SessionModel, Tenant, User
from app.schemas import LoginRequest, MerchantRegisterRequest, RefreshRequest, SetupRequest, TokenResponse, UserOut

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


def _get_default_tenant_id(db: Session) -> int:
    from app.models import Tenant
    tenant = db.query(Tenant).filter(Tenant.slug == "default").first()
    if tenant:
        return tenant.id
    # Bootstrap: first tenant
    from app.database import Base, engine
    Base.metadata.create_all(bind=engine)
    tenant = db.query(Tenant).filter(Tenant.slug == "default").first()
    if tenant:
        return tenant.id
    tenant = Tenant(name="Default", slug="default", config={"sheets": {}})
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant.id


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    refresh = create_refresh_token(user)
    db.add(SessionModel(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    ))
    db.commit()
    return TokenResponse(access_token=create_access_token(user), refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    data = decode_token(payload.refresh_token, "refresh")
    sess = db.query(SessionModel).filter(
        SessionModel.user_id == int(data["sub"]),
        SessionModel.refresh_token_hash == hash_refresh_token(payload.refresh_token),
    ).first()
    if not sess:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    # Postgres timestamps are naive; normalize to aware UTC before comparing.
    expires_at = sess.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user = db.get(User, int(data["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    return TokenResponse(access_token=create_access_token(user), refresh_token=create_refresh_token(user))


@router.post("/logout")
def logout(payload: RefreshRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sess = db.query(SessionModel).filter(
        SessionModel.refresh_token_hash == hash_refresh_token(payload.refresh_token),
        SessionModel.user_id == user.id,
    ).delete()
    db.commit()
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/setup")
def setup(payload: SetupRequest, db: Session = Depends(get_db)):
    """Bootstrap the first admin user and default tenant (dev only)."""
    if settings.APP_ENV == "production":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Setup not available in production")
    if db.query(User).count() > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already initialized")
    tenant_id = _get_default_tenant_id(db)
    user = User(
        tenant_id=tenant_id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name="Administrator",
        role="admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"ok": True, "user": UserOut.model_validate(user)}


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: MerchantRegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    slug = payload.business_name.lower().replace(" ", "-").replace("'", "")[:50]
    existing_tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
    if existing_tenant:
        slug = f"{slug}-{int(datetime.now(timezone.utc).timestamp())}"

    tenant = Tenant(name=payload.business_name, slug=slug, config={"sheets": {}})
    db.add(tenant)
    db.flush()

    # Seed Uncategorized category
    cat = Category(tenant_id=tenant.id, name="Uncategorized", parent_id=None)
    db.add(cat)
    db.flush()

    # Create admin user
    user = User(
        tenant_id=tenant.id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        phone=payload.phone,
        role="admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)
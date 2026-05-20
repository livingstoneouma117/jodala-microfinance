from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .database import get_db
from .auth import decode_token
from .models.user import User

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user:
        raise HTTPException(status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    if user.status != "active":
        raise HTTPException(status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return user

def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user

def require_view(user: User = Depends(get_current_user)) -> User:
    return user

def require_edit(user: User = Depends(get_current_user)) -> User:
    return user

def require_manage_users(user: User = Depends(get_current_user)) -> User:
    return user

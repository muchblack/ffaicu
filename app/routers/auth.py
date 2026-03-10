from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.character import Character
from app.schemas.auth import ChangePasswordRequest, LoginRequest, RegisterRequest
from app.services.auth_service import (
    authenticate,
    create_access_token,
    hash_password,
    register_character,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["認證"])


@router.post("/login")
def login(req: LoginRequest, response: Response, request: Request, db: Session = Depends(get_db)):
    host = request.client.host if request.client else ""
    character = authenticate(db, req.id, req.password, host)
    if not character:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="帳號或密碼錯誤")

    token = create_access_token(character.id)
    response.set_cookie(
        key="ffa_token",
        value=token,
        httponly=True,
        samesite="strict",
        max_age=60 * 60 * 24 * 30,
    )
    return {"message": "登入成功", "character_id": character.id, "character_name": character.name}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("ffa_token")
    return {"message": "已登出"}


@router.post("/register")
def register(req: RegisterRequest, response: Response, request: Request, db: Session = Depends(get_db)):
    existing = db.query(Character).filter(Character.id == req.id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="此帳號已被使用")

    existing_name = db.query(Character).filter(Character.name == req.name).first()
    if existing_name:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="此角色名稱已被使用")

    host = request.client.host if request.client else ""
    character = register_character(
        db=db,
        character_id=req.id,
        password=req.password,
        password_recovery=req.password_recovery,
        name=req.name,
        site_name=req.site_name,
        url=req.url,
        sex=req.sex,
        image_id=req.image_id,
        job_class=req.job_class,
        host=host,
    )

    token = create_access_token(character.id)
    response.set_cookie(
        key="ffa_token",
        value=token,
        httponly=True,
        samesite="strict",
        max_age=60 * 60 * 24 * 30,
    )
    return {"message": "角色註冊完成", "character_id": character.id}


@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    if not verify_password(req.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="目前密碼錯誤")
    if req.recovery_word != current_user.password_recovery:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密語錯誤")
    if req.new_password != req.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新密碼不一致")

    current_user.password_hash = hash_password(req.new_password)
    db.commit()
    return {"message": "密碼已變更"}

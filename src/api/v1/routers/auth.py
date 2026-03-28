from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from src.api.dependencies import DbSession
from src.api.v1.deps.auth import CurrentUser
from src.api.v1.schemas.auth import TokenResponse, UserPublic, UserSignup
from src.application.auth_service import AuthError, authenticate_user, issue_access_token, register_user

router = APIRouter()


@router.post("/signup", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def signup(body: UserSignup, db: DbSession) -> UserPublic:
    try:
        user = register_user(db, email=str(body.email), password=body.password)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    return UserPublic.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(
    db: DbSession,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenResponse:
    user = authenticate_user(db, email=form_data.username, password=form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=issue_access_token(user))


@router.get("/me", response_model=UserPublic)
def me(user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(user)

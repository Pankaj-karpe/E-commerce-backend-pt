from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schema, utils, oauth2

router = APIRouter(tags=["Auth"])

@router.post("/login", response_model=schema.Token)
def login(user_credentials: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # OAuth2PasswordRequestForm expects credentials sent as form-data (username & password)
    user = db.query(models.User).filter(models.User.email == user_credentials.username).first()

    # Verify user exists and password is correct
    if not user or not utils.verify_inHashedPass_is_savedHasedPass(user_credentials.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create and return JWT access token
    access_token = oauth2.create_access_token(data={"user_id": user.id})
    return {"access_token": access_token, "token_type": "bearer"}
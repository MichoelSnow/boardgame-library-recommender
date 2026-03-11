from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
import os

from . import crud, schemas
from .database import SessionLocal

load_dotenv()

# Password Hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise RuntimeError(
        "SECRET_KEY must be set in the environment with at least 32 characters."
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/token")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = schemas.TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = crud.get_user_by_username(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: schemas.User = Depends(get_current_user),
):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def create_initial_admin(username: str, password: str):
    """Legacy function for backward compatibility"""
    create_user_cli(username, password, is_admin=True)


def create_user_cli(username: str, password: str, is_admin: bool = False):
    """Create a user via command line interface"""
    from .database import SessionLocal
    from . import crud, schemas

    if len(password) < 6:
        print("Error: Password must be at least 6 characters long.")
        return

    db = SessionLocal()
    try:
        normalized_username = username.lower()
        if crud.get_user_by_username(db, username=normalized_username):
            user_type = "admin" if is_admin else "regular"
            print(f"User '{normalized_username}' already exists.")
            return

        user = schemas.UserCreate(
            username=normalized_username, password=password, is_admin=is_admin
        )
        crud.create_user(db, user)
        user_type = "admin" if is_admin else "regular"
        print(
            f"{user_type.capitalize()} user '{normalized_username}' created successfully."
        )
    finally:
        db.close()


def reset_password_cli(username: str, new_password: str):
    """Reset password for existing user via command line interface"""
    from .database import SessionLocal
    from . import crud

    if len(new_password) < 6:
        print("Error: Password must be at least 6 characters long.")
        return

    db = SessionLocal()
    try:
        normalized_username = username.lower()
        success = crud.admin_reset_password(
            db, username=normalized_username, new_password=new_password
        )
        if success:
            print(f"Password for user '{normalized_username}' updated successfully.")
        else:
            print(f"Error: User '{normalized_username}' not found.")
    finally:
        db.close()

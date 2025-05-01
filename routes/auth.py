from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from schemas import UserCreate, UserLogin, UserUpdate, UserOut
from crud import get_user_by_username, create_app_user, update_user_info
from database import get_db
from models import AppUser  # Ajouté pour vérifier l'existence par ID
from supabase import create_client, Client
from dotenv import load_dotenv
import os
from schemas import ForgotPasswordRequest  # Add this if not present


load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print("SUPABASE_URL =", SUPABASE_URL)
print("SUPABASE_KEY =", SUPABASE_KEY[:10], "...")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

router = APIRouter()


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest):
    try:
        supabase.auth.reset_password_email(payload.email)
        return {"message": "📧 If the email exists, a reset link has been sent."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Reset failed: {str(e)}")


@router.post("/signup", response_model=UserOut)
def signup_user(payload: UserCreate, db: Session = Depends(get_db)):
    # Vérifier si username déjà utilisé
    if get_user_by_username(db, payload.username):
        raise HTTPException(status_code=400, detail="Username already taken")

    # Créer utilisateur dans Supabase Auth
    response = supabase.auth.sign_up({
        "email": payload.email,
        "password": payload.password
    })

    data = response.model_dump()

    if data.get("error"):
        raise HTTPException(status_code=400, detail=data["error"]["message"])

    user_id = data["user"]["id"]

    # Vérifier si cet utilisateur existe déjà dans la base locale
    existing_user = db.query(AppUser).filter(AppUser.id == user_id).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists in local database.")

    # Ajouter les infos dans la table users
    # Ajouter les infos dans la table users
    user = create_app_user(
        db,
        user_id,
        payload.username,
        payload.email,
        payload.phone,
        payload.mushaf_id
    )

    return user


@router.post("/login")
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    # Get the user from the local database by username
    user = db.query(AppUser).filter(AppUser.username == payload.username).first()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid username")

    email = user.email

    print("LOGIN ATTEMPT")
    print("Username:", payload.username)
    print("Fetched email:", email)
    print("Password:", payload.password)

    # Attempt login via Supabase Auth using email/password
    response = supabase.auth.sign_in_with_password({
        "email": email,
        "password": payload.password
    })

    data = response.model_dump()

    if data.get("error"):
        raise HTTPException(status_code=400, detail=data["error"]["message"])

    return {"message": "Login success", "user_id": data["user"]["id"]}


@router.put("/update/{user_id}", response_model=UserOut)
def update_user(user_id: str, update_data: UserUpdate, db: Session = Depends(get_db)):
    # Collecte des champs à modifier dans la base locale
    update_fields = {}

    if update_data.username is not None:
        update_fields["username"] = update_data.username
    if update_data.email is not None:
        update_fields["email"] = update_data.email
    if update_data.phone is not None:
        update_fields["phone"] = update_data.phone
    # Interdire la modification du mushaf_id
    if "mushaf_id" in update_fields:
        del update_fields["mushaf_id"]

    user = update_user_info(db, user_id, update_fields)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Mise à jour dans Supabase Auth (email + password seulement si présents)
    supabase_update = {}
    if update_data.email is not None:
        supabase_update["email"] = update_data.email
    if update_data.password is not None:
        supabase_update["password"] = update_data.password

    if supabase_update:
        supabase.auth.admin.update_user_by_id(user_id, supabase_update)

    return user

@router.get("/mushaf/{user_id}", response_model=int)
def get_user_mushaf(user_id: str, db: Session = Depends(get_db)):
    user = db.query(AppUser).filter(AppUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.mushaf_id

@router.get("/userid/{username}", response_model=str)
def get_user_id_by_username(username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return str(user.id)  # ✅ Cast explicite vers str

from uuid import UUID
from sqlalchemy.exc import SQLAlchemyError
from fastapi import status

@router.delete("/delete-user/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: UUID, db: Session = Depends(get_db)):
    # Step 1: Delete from Supabase Auth
    try:
        supabase.auth.admin.delete_user(str(user_id))  # Supabase needs a string
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase Auth deletion failed: {str(e)}")

    # Step 2: Delete from local public.users table (AppUser)
    try:
        user = db.query(AppUser).filter(AppUser.id == user_id).first()
        if user:
            db.delete(user)
            db.commit()
        else:
            raise HTTPException(status_code=404, detail="User not found in local DB")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database deletion failed: {str(e)}")

    return {"detail": "User deleted successfully from Auth and local DB"}

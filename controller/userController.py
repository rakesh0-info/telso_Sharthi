import json
import secrets
from typing import Optional
import logging
from fastapi import APIRouter, Depends, HTTPException, Header, status, File, UploadFile, Request, Body, BackgroundTasks, Response, Cookie
from fastapi import security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import databaseModel.userDbModel as db_model
from sqlalchemy.orm import Session
import os
import shutil
from fastapi.responses import RedirectResponse
from pathlib import Path
from datetime import date
import time
from PasswordUtility.security import hash_password, verify_password
from PasswordUtility.passwordCheack import passwordCheack
from PasswordUtility.generateTemPass import generate_temporary_password
from Mail.sendMail import send_PasswordMail
from model.UserSchema import CreateUserSchema, AssignStudentsSchema, teacher_student_register
from model.loginRequest import LoginRequest
from OtpGeneration.generateOtp import generate_otp
from Mail.sendOtp import send_mail
from db_Get.dbSesion import get_db, require_roles, get_current_user
import re
from EnumsFile import roleEnum
from JWT.jwt_response_schemas import Token
from JWT.jwt_config import create_access_token, create_refresh_token
from jose import jwt, JWTError

from model.resetSchema import ResetPasswordSchema
from databaseModel import pending_user as db_panding
from model.otp_verify import VerifyOTPRequest
from model.reset_forget_password import ResetForgotPasswordSchema
from functools import wraps
from Redis_config.redis_con import redis_client


logger = logging.getLogger("fastapi-app")

def log_execution(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        try:
            return await func(*args, **kwargs)
        finally:
            logger.info(
                "%s completed in %.2f seconds",
                func.__name__,
                time.time() - start,
            )

    return wrapper


logging.basicConfig(level=logging.INFO)
router = APIRouter(prefix="/api/v1")
CURRENT_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = CURRENT_DIR / "my_project_images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

SERVER_LOG_FILE = os.path.join(LOG_DIR, "server.log")

server_logger = logging.getLogger("server_logger")
server_logger.setLevel(logging.INFO)

if not server_logger.handlers:
    server_file_handler = logging.FileHandler(SERVER_LOG_FILE, encoding="utf-8")
    server_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    server_file_handler.setFormatter(server_formatter)
    server_logger.addHandler(server_file_handler)

server_logger.propagate = False

REFRESH_TOKEN_EXPIRE_MINUTES = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))
SECRET_KEY = os.getenv("SECRET_KEY") 
ALGORITHM = os.getenv("ALGORITHM")

security = HTTPBearer()


# ------------------------------------------------------------------
# CACHE INVALIDATION HELPER
# ------------------------------------------------------------------
async def invalidate_user_caches(teacher_id: Optional[int] = None):
    """Centralized helper to clear global and teacher-specific caches safely."""
    keys = ["user:All", "teacher:all", "student:all"]
    if teacher_id is not None:
        keys.append(f"teacher:dashboard:{teacher_id}")
    await redis_client.delete(*keys)


@router.post("/register")
async def register(
    payload: teacher_student_register,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    clean_email = payload.email.strip().lower()
    clean_name = payload.fullName.strip()
    clean_phone = payload.ph_no.strip() if payload.ph_no else None

    if db.query(db_model.User).filter(db_model.User.email == clean_email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User email already registered."
        )

    if payload.role == roleEnum.Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin users cannot be created via this endpoint."
        )

    if any(char.isdigit() for char in clean_name) or any(char in "!@#$%^&*(),.?\":{}|<>" for char in clean_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name cannot contain special characters or numbers."
        )

    if clean_phone:
        if not re.match(r"^\+?[1-9]\d{6,14}$", clean_phone):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid phone number format. Use international format (e.g., +1234567890)."
            )

    if not passwordCheack(payload.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password length must be at least 10 and contain at least 1 special char and 1 digit."
        )

    if payload.password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password and confirmation password do not match."
        )

    subjects = payload.subject if payload.role == roleEnum.Role.TEACHER else None
    student_standard = payload.standard if payload.role == roleEnum.Role.STUDENT else None

    if payload.role == roleEnum.Role.TEACHER and not subjects:
        raise HTTPException(status_code=400, detail="Subject must be assigned to the teacher.")
    if payload.role == roleEnum.Role.STUDENT and not student_standard:
        raise HTTPException(status_code=400, detail="Standard must be assigned to the student.")

    otp = generate_otp()
    expiry_time = time.time() + 300.0

    role_value = payload.role.value if hasattr(payload.role, "value") else payload.role

    try:
        pending_user = db.query(db_panding.PendingUser).filter(
            db_panding.PendingUser.email == clean_email
        ).first()

        if pending_user:
            pending_user.fullName = clean_name
            pending_user.ph_no = clean_phone
            pending_user.role = role_value
            pending_user.dob = payload.dob
            pending_user.subject = subjects
            pending_user.standard = student_standard
            pending_user.password = hash_password(payload.password)
            pending_user.profile_pic = payload.profile_pic
            pending_user.otp = str(otp)
            pending_user.otp_expiry = expiry_time
        else:
            pending_user = db_panding.PendingUser(
                fullName=clean_name,
                email=clean_email,
                ph_no=clean_phone,
                role=role_value,
                dob=payload.dob,
                subject=subjects,
                standard=student_standard,
                password=hash_password(payload.password),
                profile_pic=payload.profile_pic,
                otp=str(otp),
                otp_expiry=expiry_time
            )
            db.add(pending_user)

        db.commit()
        db.refresh(pending_user)

    except Exception as e:
        db.rollback()
        server_logger.error(f"Database error while saving registration for {clean_email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while saving registration: {str(e)}"
        )

    background_tasks.add_task(send_mail, clean_email, otp)
    logging.info(f"OTP sent to {clean_email} for registration verification.")

    return {
        "message": "OTP sent to your email. Please verify to complete your registration."
    }


@router.post("/user/login")
async def login(
    payload: LoginRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    db_user = db.query(db_model.User).filter(db_model.User.email == payload.email).first()
    clear_password = payload.password.strip()

    if not db_user or not verify_password(clear_password, db_user.password):
        server_logger.error(f"Failed login attempt for {payload.email}. Invalid credentials.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if db_user.is_temporary_password:
        otp = generate_otp()
        expiry_time = time.time() + 300
        
        db_user.reset_otp = otp
        db_user.reset_otp_expiry = expiry_time
        db.commit()

        background_tasks.add_task(send_mail, db_user.email, otp)
        logging.info(f"Temporary password detected for {db_user.email}. OTP sent for password reset.")
        return {
            "requires_password_reset": True,
            "email": db_user.email,
            "message": "Temporary password detected. An OTP has been sent to your email to set a new password."
        }

    access_token = create_access_token({"sub": db_user.email})
    refresh_token = create_refresh_token({"sub": db_user.email})

    REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/refresh"
    )

    role_str = db_user.role.value if hasattr(db_user.role, "value") else str(db_user.role)

    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "role": role_str,
        "redirect_url": f"/api/v1/{role_str}/dashboard"
    }


@router.post("/send-otp")
async def sendMail(
    background_tasks: BackgroundTasks,
    email: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    user = db.query(db_model.User).filter(db_model.User.email == email).first()

    if not user:
        raise HTTPException(404, detail="User not found")

    if user.is_email_verify:
        return {"message": "Email is already verified. Please proceed."}

    otp = generate_otp()
    expiry_time = time.time() + 300

    user.reset_otp = otp
    user.reset_otp_expiry = expiry_time
    db.commit()

    background_tasks.add_task(send_mail, email, otp)

    return {"message": "OTP has been sent successfully to your email address."}


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    response: Response, 
    refresh_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not refresh_token:
        raise cred_exc

    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_email: Optional[str] = payload.get("sub")
        token_type: Optional[str] = payload.get("type")
        
        if user_email is None or token_type != "refresh":
            raise cred_exc
    except JWTError:
        raise cred_exc

    user = db.query(db_model.User).filter(db_model.User.email == user_email).first()
    if not user:
        raise cred_exc

    new_access_token = create_access_token({"sub": user.email})
    role_str = user.role.value if hasattr(user.role, "value") else str(user.role)

    return {
        "access_token": new_access_token, 
        "token_type": "bearer",
        "role": role_str,
        "redirect_url": f"/api/v1/{role_str}/dashboard"
    }


@router.post("/is_email_verified")
async def is_Email_verified(
        emails: str,
        db: Session = Depends(get_db)
) -> bool:
    user = db.query(db_model.User).filter(db_model.User.email == emails).first()

    if not user:
        raise HTTPException(404, detail="user not found")
    return bool(user.is_email_verify)


@router.post("/verify-otp")
@log_execution
async def verify_otp(
    payload: VerifyOTPRequest,
    db: Session = Depends(get_db)
):
    clean_email = payload.email.strip().lower()
    clean_otp = payload.otp_input.strip().zfill(6)

    pending_user = db.query(db_panding.PendingUser).filter(
        db_panding.PendingUser.email == clean_email
    ).first()

    if pending_user:
        db_otp = str(pending_user.otp).strip().zfill(6)
        if clean_otp != db_otp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP code."
            )

        try:
            role_val = roleEnum.Role(pending_user.role) if hasattr(roleEnum, "Role") else pending_user.role
        except ValueError:
            role_val = pending_user.role

        try:
            new_user = db_model.User(
                fullName=pending_user.fullName,
                email=pending_user.email,
                ph_no=pending_user.ph_no,
                role=role_val,
                dob=pending_user.dob,
                subject=pending_user.subject,
                standard=pending_user.standard,
                password=pending_user.password,
                isVerify=True,
                is_email_verify=True,
                is_temporary_password=False,
                profile_pic=pending_user.profile_pic,
                is_temp_password_chang=True
            )

            db.add(new_user)
            db.delete(pending_user)
            db.commit()
            db.refresh(new_user)

            await invalidate_user_caches()

            return {
                "message": "Account verified and created successfully. You may now log in."
            }
        except Exception as e:
            db.rollback()
            server_logger.error(f"Failed to create user account for {clean_email}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create user account: {str(e)}"
            )

    user = db.query(db_model.User).filter(
        db_model.User.email == clean_email
    ).first()

    if user and user.reset_otp:
        user_otp = str(user.reset_otp).strip().zfill(6)
        if clean_otp != user_otp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP code."
            )

        reset_token = create_access_token({"sub": user.email, "scope": "password_reset"})

        user.reset_otp = None
        user.reset_otp_expiry = None
        user.is_email_verify = True
        db.commit()

        await invalidate_user_caches()

        return {
            "message": "OTP verified successfully.",
            "reset_token": reset_token
        }

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="No pending registration or reset request found for this email."
    )


@router.post("/forgetPass")
@log_execution
async def forgetPass(
    background_tasks: BackgroundTasks,
    email: str,
    db: Session = Depends(get_db),
):
    clean_email = email.strip().lower()

    user = (
        db.query(db_model.User)
        .filter(db_model.User.email == clean_email)
        .first()
    )

    if not user:
        raise HTTPException(status_code=404, detail="User does not exist")

    otp = str(generate_otp()).zfill(6)
    expiry = int(time.time()) + 300

    user.forget_pass_otp = otp
    user.forget_pass_expiry = expiry

    db.commit()
    db.refresh(user)

    background_tasks.add_task(send_mail, clean_email, otp)
    return {"message": "OTP sent to mail"}


@router.post("/verify_otp_fogetpass")
@log_execution
async def verify_otp_forgetPass(
    payload: VerifyOTPRequest,
    db: Session = Depends(get_db),
):
    clean_email = payload.email.strip().lower()

    user = (
        db.query(db_model.User)
        .filter(db_model.User.email == clean_email)
        .first()
    )

    if not user or not user.forget_pass_otp or not user.forget_pass_expiry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active OTP request found. Please request a new code.",
        )

    try:
        is_expired = time.time() > float(user.forget_pass_expiry)
    except (ValueError, TypeError):
        is_expired = True

    if is_expired:
        user.forget_pass_otp = None
        user.forget_pass_expiry = None
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired. Please request a new one.",
        )

    clean_otp_input = payload.otp_input.strip().zfill(6)
    clean_stored_otp = str(user.forget_pass_otp).strip().zfill(6)

    if not secrets.compare_digest(clean_otp_input, clean_stored_otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP code.",
        )

    return {
        "message": "OTP verified successfully. You may now reset your password."
    }


@router.put("/upload")
async def upload_profile(current_user: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN, roleEnum.Role.TEACHER)), db: Session = Depends(get_db), file: UploadFile = File(...)):
    file_path = UPLOAD_DIR / file.filename

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

            current_user.profile_pic = f"/static/uploads/{file.filename}"
            db.commit()
            db.refresh(current_user)             
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save file: {str(e)}"
        )
    finally:
        file.file.close()

    await invalidate_user_caches(teacher_id=current_user.id if current_user.role == roleEnum.Role.TEACHER else None)

    return {"message": "Profile pic uploaded successfully"}


@router.put("/edit")
async def edit_profilePic(current_user: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN, roleEnum.Role.TEACHER)), db: Session = Depends(get_db), file: UploadFile = File(...)):
    
    if current_user.profile_pic:
        old_filename = current_user.profile_pic.split("/")[-1]
        old_file_path = UPLOAD_DIR / old_filename
        if os.path.exists(old_file_path):
            try:
                os.remove(old_file_path)
            except OSError:
                pass
                
    file_path = UPLOAD_DIR / file.filename
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
            current_user.profile_pic = f"/static/uploads/{file.filename}"
            db.commit()
            db.refresh(current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        file.file.close()

    await invalidate_user_caches(teacher_id=current_user.id if current_user.role == roleEnum.Role.TEACHER else None)
        
    return {"message": "Profile pic updated successfully"}


@router.delete("/delete-profile-pic")
async def delete_profile_pic(current_user: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN, roleEnum.Role.TEACHER)), db: Session = Depends(get_db)):
    if current_user.profile_pic:
        filename = current_user.profile_pic.split("/")[-1]
        file_path = UPLOAD_DIR / filename
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
    current_user.profile_pic = None
    db.commit()

    await invalidate_user_caches(teacher_id=current_user.id if current_user.role == roleEnum.Role.TEACHER else None)
    return {"message": "Profile picture deleted successfully"}


@router.put("/changepassword")
async def changePassword(
    oldPassword: str = Body(...), 
    newpassword: str = Body(...), 
    confirmPassword: str = Body(..., alias="confiromPassword"),
    current_user: db_model.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    if newpassword != confirmPassword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password and confirmation password do not match."
        )

    if not verify_password(oldPassword, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect old password."
        )

    if not passwordCheack(newpassword):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Password must be at least 10 characters long and contain letters, numbers, and special characters."
        )

    current_user.password = hash_password(newpassword)
    db.commit()
    db.refresh(current_user)

    return {
        "fullName": current_user.fullName,
        "message": "Password changed successfully."
    }


@router.post("/reset-password")
async def resetPassword(
    payload: ResetPasswordSchema,
    db: Session = Depends(get_db),
):
    user = (
        db.query(db_model.User)
        .filter(db_model.User.email == payload.email.strip().lower())
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    if getattr(user, "is_temp_password_chang", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Temporary password has already been used and changed."
        )

    if not verify_password(payload.temp_password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid temporary password."
        )

    if payload.newpassword != payload.confirmPassword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password and confirmation password do not match."
        )

    if not passwordCheack(payload.newpassword):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 10 characters long and contain letters, numbers, and special characters."
        )

    user.password = hash_password(payload.newpassword)
    user.is_temporary_password = False
    user.is_temp_password_chang = True
    user.isVerify = True

    db.commit()
    db.refresh(user)
    
    await invalidate_user_caches()

    return {
        "message": "Password reset successfully. Please login with your new credentials."
    }


@router.post("/reset_forgetpassword")
async def resetforgetPass(
    payload: ResetForgotPasswordSchema,
    db: Session = Depends(get_db)
):
    clean_email = payload.email.strip().lower()

    if payload.newpassword != payload.confirmPassword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password and confirmation password do not match."
        )

    if not passwordCheack(payload.newpassword):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 10 characters long and contain letters, numbers, and special characters."
        )

    user = (
        db.query(db_model.User)
        .filter(db_model.User.email == clean_email)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    if not user.forget_pass_otp or not user.forget_pass_expiry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active password reset request found. Please request a new OTP."
        )

    try:
        is_expired = time.time() > float(user.forget_pass_expiry)
    except (ValueError, TypeError):
        is_expired = True

    if is_expired:
        user.forget_pass_otp = None
        user.forget_pass_expiry = None
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP session expired. Please request a new OTP."
        )

    clean_otp_input = payload.otp_input.strip().zfill(6)
    clean_stored_otp = str(user.forget_pass_otp).strip().zfill(6)

    if not secrets.compare_digest(clean_otp_input, clean_stored_otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP code."
        )

    user.password = hash_password(payload.newpassword)
    user.is_temporary_password = False
    user.is_temp_password_chang = True
    user.isVerify = True

    user.forget_pass_otp = None
    user.forget_pass_expiry = None

    db.commit()

    return {"message": "Password reset successfully. Please log in with your new password."}


@router.put("/updatename")
async def updateName(db: Session = Depends(get_db), updateName: str = Body(...), currentUser: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN, roleEnum.Role.TEACHER))):
    has_number = any(char.isdigit() for char in updateName)
    special_chars = "!@#$%^&*(),.?\":{}|<>"
    has_special = any(char in special_chars for char in updateName)

    if (has_number or has_special):
        raise HTTPException(status_code=400, detail="Name cannot contain special characters or numbers.")
   
    currentUser.fullName = updateName
    db.commit()
    db.refresh(currentUser)

    await invalidate_user_caches(teacher_id=currentUser.id if currentUser.role == roleEnum.Role.TEACHER else None)
    return {"message": "userName updated"}


@router.put("/updatephone")
async def updatePhone(db: Session = Depends(get_db), phone: str = Body(..., embed=True), currentUser: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN, roleEnum.Role.TEACHER))):
    PHONE_REGEX = r"^\+?[1-9]\d{6,14}$"
    
    phone_no = phone.strip()
    if not re.match(PHONE_REGEX, phone_no):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number format. Use international format (e.g., +1234567890)."
        )

    currentUser.ph_no = phone
    db.commit()
    db.refresh(currentUser)

    await invalidate_user_caches(teacher_id=currentUser.id if currentUser.role == roleEnum.Role.TEACHER else None)
    return {"message": "Phone number updated"}


@router.put("/updatedob")
async def updateDob(db: Session = Depends(get_db), updatedate: date = Body(...), currentUser: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN, roleEnum.Role.TEACHER))):
    currentUser.dob = updatedate
    db.commit()
    db.refresh(currentUser)

    await invalidate_user_caches(teacher_id=currentUser.id if currentUser.role == roleEnum.Role.TEACHER else None)
    return {"message": "date of birth Updated"}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/refresh",
        httponly=True,
        samesite="lax"
    )
    return {"message": "Logged out successfully"}


@router.get("/getCur")
async def whologin(cur: db_model.User = Depends(get_current_user)):
    return cur.fullName


@router.post("/admin/create-user")
async def admin_create_user(
    payload: CreateUserSchema,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN)),
):
    if (
        db.query(db_model.User)
        .filter(db_model.User.email == payload.email)
        .first()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User email already registered.",
        )

    if payload.role == roleEnum.Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin users cannot be created via this endpoint.",
        )

    name = payload.fullName.strip()
    has_number = any(char.isdigit() for char in name)
    special_chars = "!@#$%^&*(),.?\":{}|<>"
    has_special = any(char in special_chars for char in name)

    if has_number or has_special:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name cannot contain special characters or numbers.",
        )

    if payload.ph_no:
        PHONE_REGEX = r"^\+?[1-9]\d{6,14}$"
        phone_no = payload.ph_no.strip()
        if not re.match(PHONE_REGEX, phone_no):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid phone number format. Use international format (e.g., +1234567890).",
            )

    subjects = None
    student_standard = None
    assigned_teacher_id = None

    if payload.role == roleEnum.Role.TEACHER:
        if not payload.subject:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subject must be assigned to the teacher.",
            )
        subjects = payload.subject

    elif payload.role == roleEnum.Role.STUDENT:
        if not payload.standard:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Standard must be assigned to the student.",
            )
        student_standard = payload.standard

        if payload.teacher_id:
            teacher = (
                db.query(db_model.User)
                .filter(
                    db_model.User.id == payload.teacher_id,
                    db_model.User.role == roleEnum.Role.TEACHER,
                )
                .first()
            )
            if not teacher:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Assigned teacher does not exist.",
                )
            assigned_teacher_id = teacher.id

    temp_password = generate_temporary_password()

    new_user = db_model.User(
        fullName=payload.fullName,
        email=payload.email,
        ph_no=payload.ph_no,
        role=payload.role,
        dob=payload.dob,
        subject=subjects,
        standard=student_standard,
        teacher_id=assigned_teacher_id,
        password=hash_password(temp_password),
        isVerify=False,
        is_temporary_password=True,
        profile_pic=payload.profile_pic,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Invalidate cache when new user is created
    await invalidate_user_caches(teacher_id=assigned_teacher_id)

    background_tasks.add_task(send_PasswordMail, new_user.email, temp_password)

    role_str = payload.role.value if hasattr(payload.role, "value") else str(payload.role)
    return {
        "message": f"{role_str.capitalize()} account created successfully. Credentials emailed to {payload.fullName}."
    }


@router.put("/admin/teacher/{teacher_id}/assign-students")
async def assign_students_to_teacher(
    teacher_id: int,
    payload: AssignStudentsSchema,
    db: Session = Depends(get_db),
    admin: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN)),
):
    teacher = (
        db.query(db_model.User)
        .filter(
            db_model.User.id == teacher_id,
            db_model.User.role == roleEnum.Role.TEACHER,
        )
        .first()
    )

    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found."
        )

    if not payload.student_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="student_ids list cannot be empty.",
        )

    unique_student_ids = list(set(payload.student_ids))

    valid_students_count = (
        db.query(db_model.User)
        .filter(
            db_model.User.id.in_(unique_student_ids),
            db_model.User.role == roleEnum.Role.STUDENT,
        )
        .count()
    )

    if valid_students_count != len(unique_student_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more student IDs are invalid or not registered as students.",
        )

    db.query(db_model.User).filter(
        db_model.User.id.in_(unique_student_ids)
    ).update({db_model.User.teacher_id: teacher.id}, synchronize_session="fetch")

    db.commit()

    # Safely clear cache after fetching teacher record
    await invalidate_user_caches(teacher_id=teacher.id)

    return {
        "message": f"Successfully assigned/reassigned {valid_students_count} student(s) to Teacher {teacher.fullName}."
    }


@router.get("/admin/getAllTeacher")
async def get_all_teachers(
    db: Session = Depends(get_db),
    admin: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN))
):
    cache_key = "teacher:all"

    cached_teachers = await redis_client.get(cache_key)
    if cached_teachers:
        logger.info("Get teacher from Redis")
        return json.loads(cached_teachers)
    
    # Query using Enum string value for cross-compatibility
    role_val = roleEnum.Role.TEACHER.value if hasattr(roleEnum.Role.TEACHER, "value") else roleEnum.Role.TEACHER
    teachers = db.query(db_model.User).filter(db_model.User.role == role_val).all()
    logger.info("Get teacher from database")

    teachers_data = [
        {
            "id": t.id,
            "fullName": t.fullName,
            "email": t.email,
            "ph_no": t.ph_no,
            "subject": t.subject,
            "profile_pic": t.profile_pic,
            "dob": t.dob.isoformat() if t.dob else None
        }
        for t in teachers
    ]

    await redis_client.set(cache_key, json.dumps(teachers_data), ex=300)
    return teachers_data


@router.get("/admin/getAllStudent")
async def get_all_students(
    db: Session = Depends(get_db),
    admin: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN))
):
    cache_key = "student:all"

    cached_students = await redis_client.get(cache_key)
    if cached_students:
        logger.info("Get all students from Redis")
        return json.loads(cached_students)

    # Query using Enum string value for cross-compatibility
    role_val = roleEnum.Role.STUDENT.value if hasattr(roleEnum.Role.STUDENT, "value") else roleEnum.Role.STUDENT
    students = db.query(db_model.User).filter(db_model.User.role == role_val).all()
    logger.info("Get all students from database")

    students_data = [
        {
            "id": s.id,
            "fullName": s.fullName,
            "email": s.email,
            "ph_no": s.ph_no,
            "standard": s.standard,
            "profile_pic": s.profile_pic,
            "isVerify": s.isVerify,
            "dob": s.dob.isoformat() if s.dob else None,
            "assigned_teacher": {
                "id": s.assigned_teacher.id,
                "fullName": s.assigned_teacher.fullName,
                "subject": s.assigned_teacher.subject
            } if getattr(s, "assigned_teacher", None) else None
        }
        for s in students
    ]

    await redis_client.set(cache_key, json.dumps(students_data), ex=300)
    return students_data


@router.delete("/admin/delete_student/{id}", status_code=status.HTTP_200_OK)
async def delete_student(
    id: int,
    db: Session = Depends(get_db),
    admin: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN))
):
    student = db.query(db_model.User).filter(
        db_model.User.id == id,
        db_model.User.role == roleEnum.Role.STUDENT
    ).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Student with ID {id} not found."
        )

    teacher_id = student.teacher_id

    db.delete(student)
    db.commit()

    await invalidate_user_caches(teacher_id=teacher_id)

    return {"message": f"Student '{student.fullName}' deleted successfully."}


@router.delete("/admin/delete_teacher/{id}", status_code=status.HTTP_200_OK)
async def delete_teacher(
    id: int,
    db: Session = Depends(get_db),
    admin: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN))
):
    teacher = db.query(db_model.User).filter(
        db_model.User.id == id,
        db_model.User.role == roleEnum.Role.TEACHER
    ).first()

    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Teacher with ID {id} not found."
        )

    db.query(db_model.User).filter(db_model.User.teacher_id == id).update({"teacher_id": None})

    db.delete(teacher)
    db.commit()

    try:
        await invalidate_user_caches(teacher_id=id)
        logger.info("Cache successfully cleared upon teacher deletion.") 
    except Exception as e:
        logger.error(f"Error occurred while deleting cache: {e}")

    return {"message": f"Teacher '{teacher.fullName}' deleted successfully."}


@router.get("/admin/dashboard")
async def admin_dashboard(admin: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN))):
    return {
        "message": f"Welcome to the Admin Dashboard, {admin.fullName}!",
        "user": {
            "fullName": admin.fullName,
            "email": admin.email,
            "role": admin.role,
            "profile_pic": admin.profile_pic,
            "ph_no": admin.ph_no,
            "dob": admin.dob
        }
    }


@router.get("/admin/all_teacher_student")
async def admin_assingn_teacher_student(
    db: Session = Depends(get_db),
    admin: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN))
):
    cache_key = "user:All"

    cached_data = await redis_client.get(cache_key)
    if cached_data:
        logger.info("Cache HIT - returning data from Redis")
        return json.loads(cached_data)

    role_teacher_val = roleEnum.Role.TEACHER.value if hasattr(roleEnum.Role.TEACHER, "value") else roleEnum.Role.TEACHER
    role_student_val = roleEnum.Role.STUDENT.value if hasattr(roleEnum.Role.STUDENT, "value") else roleEnum.Role.STUDENT

    teachers_raw = db.query(db_model.User).filter(db_model.User.role == role_teacher_val).all()
    students_raw = db.query(db_model.User).filter(db_model.User.role == role_student_val).all()

    teachers_list = []
    for teacher in teachers_raw:
        teachers_list.append({
            "id": teacher.id,
            "fullName": teacher.fullName,
            "email": teacher.email,
            "ph_no": teacher.ph_no,
            "dob": teacher.dob.isoformat() if teacher.dob else None,
            "isVerify": teacher.isVerify,
            "profile_pic": teacher.profile_pic,
            "subject": teacher.subject,
            "students": [
                {
                    "id": s.id,
                    "fullName": s.fullName,
                    "email": s.email,
                    "standard": s.standard
                }
                for s in teacher.students
            ]
        })

    students_list = []
    for student in students_raw:
        students_list.append({
            "id": student.id,
            "fullName": student.fullName,
            "email": student.email,
            "ph_no": student.ph_no,
            "dob": student.dob.isoformat() if student.dob else None,
            "isVerify": student.isVerify,
            "profile_pic": student.profile_pic,
            "standard": student.standard,
            "assigned_teacher": {
                "id": student.assigned_teacher.id,
                "fullName": student.assigned_teacher.fullName,
                "subject": student.assigned_teacher.subject
            }
            if getattr(student, "assigned_teacher", None)
            else None
        })

    response_data = {
        "summary": {
            "total_teachers": len(teachers_list),
            "total_students": len(students_list)
        },
        "teachers": teachers_list,
        "students": students_list
    }

    await redis_client.set(cache_key, json.dumps(response_data), ex=3600)
    return response_data


@router.put("/admin/update_student_standard/{id}")
async def update_student_standard(
    id: int,
    standard: str,
    db: Session = Depends(get_db),
    admin: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN))
):
    student = db.query(db_model.User).filter(
        db_model.User.id == id, 
        db_model.User.role == roleEnum.Role.STUDENT
    ).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {id} not found."
        )

    # Capture former teacher ID BEFORE resetting it to None
    previous_teacher_id = student.teacher_id

    action_taken = "No teacher was assigned."
    if student.teacher_id is not None:
        student.teacher_id = None
        action_taken = "Automatically unassigned from previous teacher due to standard/grade change."

    student.standard = standard
    
    db.commit()
    db.refresh(student)

    # Invalidate cache for the previous teacher
    await invalidate_user_caches(teacher_id=previous_teacher_id)

    return {
        "message": f"Successfully updated standard for student {student.fullName}.",
        "student": {
            "id": student.id,
            "fullName": student.fullName,
            "standard": student.standard,
            "teacher_id": student.teacher_id
        },
        "business_action": action_taken
    }


@router.put("/admin/update_teacher_subject/{id}")
async def update_teacher_subject(
    id: int,
    subjects: str,
    db: Session = Depends(get_db),
    admin: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN))
):
    teacher = db.query(db_model.User).filter(
        db_model.User.id == id, 
        db_model.User.role == roleEnum.Role.TEACHER
    ).first()

    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Teacher with ID {id} not found."
        )

    teacher.subject = subjects

    unassigned_count = 0
    if teacher.students:
        for student in teacher.students:
            student.teacher_id = None
            unassigned_count += 1

    db.commit()
    db.refresh(teacher)

    await invalidate_user_caches(teacher_id=teacher.id)

    return {
        "message": f"Successfully updated subject for teacher {teacher.fullName}.",
        "teacher": {
            "id": teacher.id,
            "fullName": teacher.fullName,
            "subject": teacher.subject
        },
        "business_action": f"Automatically unassigned {unassigned_count} students due to subject shift."
    }


# ------------------------------------------------------------------
# STUDENT UPDATE ENDPOINTS
# ------------------------------------------------------------------

@router.put("/admin/update_student_name/{id}")
async def adminUpdateStudentName(
    id: int,
    name: str,
    db: Session = Depends(get_db),
    admin: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN)),
):
    student = db.query(db_model.User).filter(
        db_model.User.id == id,
        db_model.User.role == roleEnum.Role.STUDENT
    ).first()

    if not student: 
        raise HTTPException(status_code=404, detail="Student Not Found")

    has_number = any(char.isdigit() for char in name)
    special_chars = "!@#$%^&*(),.?\":{}|<>"
    has_special = any(char in special_chars for char in name)
        
    if (has_number or has_special):
        raise HTTPException(status_code=400, detail="Name cannot contain special characters or numbers.")

    student.fullName = name
    db.commit()
    db.refresh(student)

    await invalidate_user_caches(teacher_id=student.teacher_id)

    return {
        "message": "Successfully updated student Name.",
        "student": {
            "id": student.id,
            "fullName": student.fullName,
            "standard": student.standard,
            "teacher_id": student.teacher_id,
            "ph_no": student.ph_no,
            "dob": str(student.dob) if student.dob else None,
        },
    }


@router.put("/admin/update_student_ph/{id}")
async def adminUpdateStudentPhone(
    id: int,
    ph: str,
    db: Session = Depends(get_db),
    admin: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN)),
):
    student = db.query(db_model.User).filter(
        db_model.User.id == id,
        db_model.User.role == roleEnum.Role.STUDENT
    ).first()

    if not student: 
        raise HTTPException(status_code=404, detail="Student Not Found")
    
    PHONE_REGEX = r"^\+?[1-9]\d{6,14}$"
    if ph:
        ph_no = ph.strip()
        if not re.match(PHONE_REGEX, ph_no):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Enter Valid Phone Number",
            )
        student.ph_no = ph_no

    db.commit()
    db.refresh(student)

    await invalidate_user_caches(teacher_id=student.teacher_id)

    return {
        "message": "Successfully updated student Phone Number.",
        "student": {
            "id": student.id,
            "fullName": student.fullName,
            "standard": student.standard,
            "teacher_id": student.teacher_id,
            "ph_no": student.ph_no,
            "dob": str(student.dob) if student.dob else None,
        },
    }


@router.put("/admin/update_student_dob/{id}")
async def adminUpdateStudentDob(
    id: int,
    dobs: date,
    db: Session = Depends(get_db),
    admin: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN)),
):
    student = db.query(db_model.User).filter(
        db_model.User.id == id,
        db_model.User.role == roleEnum.Role.STUDENT,
    ).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Student Not Found"
        )

    student.dob = dobs
    db.commit()
    db.refresh(student)

    await invalidate_user_caches(teacher_id=student.teacher_id)

    return {
        "message": "Successfully updated student DOB.",
        "student": {
            "id": student.id,
            "fullName": student.fullName,
            "standard": student.standard,
            "teacher_id": student.teacher_id,
            "ph_no": student.ph_no,
            "dob": str(student.dob) if student.dob else None,
        },
    }


# ------------------------------------------------------------------
# TEACHER UPDATE ENDPOINTS
# ------------------------------------------------------------------

@router.put("/admin/update_teacher_name/{id}")
async def adminUpdateTeacherName(
    id: int,
    name: str,
    db: Session = Depends(get_db),
    admin: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN)),
):
    teacher = db.query(db_model.User).filter(
        db_model.User.role == roleEnum.Role.TEACHER,
        db_model.User.id == id
    ).first()

    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher Not Found")

    has_number = any(char.isdigit() for char in name)
    special_chars = "!@#$%^&*(),.?\":{}|<>"
    has_special = any(char in special_chars for char in name)
    
    if (has_number or has_special):
        raise HTTPException(status_code=400, detail="Name cannot contain special characters or numbers.")

    teacher.fullName = name
    db.commit()
    db.refresh(teacher)

    await invalidate_user_caches(teacher_id=teacher.id)

    return {
        "message": "Teacher Name updated successfully!",
        "teacher": {
            "id": teacher.id,
            "fullName": teacher.fullName,
            "email": teacher.email,
            "role": teacher.role.value if hasattr(teacher.role, 'value') else teacher.role,
            "subject": teacher.subject,
            "profile_pic": teacher.profile_pic,
            "ph_no": teacher.ph_no,
            "dob": str(teacher.dob) if teacher.dob else None,
        },
    }


@router.put("/admin/update_teacher_ph/{id}")
async def adminUpdateTeacherPhone(
    id: int,
    ph: str,
    db: Session = Depends(get_db),
    admin: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN)),
):
    teacher = db.query(db_model.User).filter(
        db_model.User.role == roleEnum.Role.TEACHER,
        db_model.User.id == id
    ).first()

    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher Not Found")

    PHONE_REGEX = r"^\+?[1-9]\d{6,14}$"
    if ph:
        ph_no = ph.strip()
        if not re.match(PHONE_REGEX, ph_no):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Enter Valid Phone Number",
            )
        teacher.ph_no = ph_no

    db.commit()
    db.refresh(teacher)

    await invalidate_user_caches(teacher_id=teacher.id)

    return {
        "message": "Teacher Phone updated successfully!",
        "teacher": {
            "id": teacher.id,
            "fullName": teacher.fullName,
            "email": teacher.email,
            "role": teacher.role.value if hasattr(teacher.role, 'value') else teacher.role,
            "subject": teacher.subject,
            "profile_pic": teacher.profile_pic,
            "ph_no": teacher.ph_no,
            "dob": str(teacher.dob) if teacher.dob else None,
        },
    }


@router.put("/admin/update_teacher_dob/{id}")
async def adminUpdateTeacherDob(
    id: int,
    dobs: date,
    db: Session = Depends(get_db),
    admin: db_model.User = Depends(require_roles(roleEnum.Role.ADMIN)),
):
    teacher = db.query(db_model.User).filter(
        db_model.User.role == roleEnum.Role.TEACHER,
        db_model.User.id == id
    ).first()

    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher Not Found")

    teacher.dob = dobs
    db.commit()
    db.refresh(teacher)

    await invalidate_user_caches(teacher_id=teacher.id)

    return {
        "message": "Teacher DOB updated successfully!",
        "teacher": {
            "id": teacher.id,
            "fullName": teacher.fullName,
            "email": teacher.email,
            "role": teacher.role.value if hasattr(teacher.role, 'value') else teacher.role,
            "subject": teacher.subject,
            "profile_pic": teacher.profile_pic,
            "ph_no": teacher.ph_no,
            "dob": str(teacher.dob) if teacher.dob else None,
        },
    }
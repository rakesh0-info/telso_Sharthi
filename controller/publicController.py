from datetime import datetime, timedelta, timezone
import time
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database_config import get_db
from jwts.jwt_config import create_access_token
from jwts.token_Verify import verify_token
from mail.sendmail import send_mail
from otp_generate.otp import generate_otp
from requestModel.forget_passRequest import forgetPass
from requestModel.loginRequest import loginRequest
from databaseModel.user_model import User 
from requestModel.reset_pass import reset_pass_Request
from util_validate.password_security import hash_password, verify_password
from requestModel.loginOtp_verifyRequest import otp_verify
from util_validate.pasword_name_validate import passwordCheack

router = APIRouter(prefix="/public/api/v1", tags=["Public"])


@router.post("/login")
async def login(
    payload: loginRequest,
    db: Session = Depends(get_db),
    bg_tasks: BackgroundTasks = BackgroundTasks()
):
    exist_user = db.query(User).filter(User.email == payload.email).first()
    clear_pass = payload.password.strip()

   
    if not exist_user or not verify_password(clear_pass, exist_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    otp = generate_otp()
    expiry_time = datetime.now(timezone.utc) + timedelta(seconds=300)

    exist_user.otp = otp
    exist_user.otp_expiry = expiry_time
    db.commit()
    
    bg_tasks.add_task(send_mail, exist_user.email, otp)

    return {"message": "A verification OTP has been sent to your mail, valid for 5 minutes."}


@router.post("/login_otp_verification")
async def otp_verification(payload: otp_verify, db: Session = Depends(get_db)):
    clean_email = payload.email.strip().lower()
    clean_otp = payload.otp_input.strip().zfill(6)

    user = db.query(User).filter(User.email == clean_email).first()
    
    if not user or not user.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP or request."
        )

    user_otp = str(user.otp).strip().zfill(6)
    
    
    if clean_otp != user_otp or user.otp_expiry.timestamp() < time.time():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP code."
        )

    user.otp = None
    user.otp_expiry = None
    user.last_login=datetime.now()
    db.commit()
    db.refresh(user)

    access_token = create_access_token({"sub": user.email, "scope": "login_Verification"})
    role_str = user.role.value if hasattr(user.role, "value") else str(user.role)

    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "role": role_str,
        "redirect_url": f"{role_str}/api/v1/dashboard"
    }


@router.post("/forget_Pass")
async def forget_pass(
    payload: forgetPass, 
    db: Session = Depends(get_db), 
    bg_tasks: BackgroundTasks = BackgroundTasks()
):
    exist_user = db.query(User).filter(User.email == payload.email).first()
    if not exist_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User does not exist"
        )

    reset_pass_token = create_access_token({"sub": exist_user.email, "scope": "forget_pass_token"})

    otp = generate_otp()
    expiry = datetime.now(timezone.utc) + timedelta(seconds=300)

    exist_user.otp = otp
    exist_user.otp_expiry = expiry
    db.commit()
    db.refresh(exist_user)

  
    bg_tasks.add_task(send_mail, exist_user.email, otp)

    return {
        "reset_pass_token": reset_pass_token,
        "message": "OTP sent to your mail for resetting the password."
    }


@router.post("/forget_pass_otp_verification")
async def verify_otp_forget_pass(payload: otp_verify, db: Session = Depends(get_db)):
    clean_email = payload.email.strip().lower()
    clean_otp = payload.otp_input.strip().zfill(6)
     
    user = db.query(User).filter(User.email == clean_email).first()
         
    if not user or not user.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP or request."
        )
        
    user_otp = str(user.otp).strip().zfill(6)
    
    if clean_otp != user_otp or user.otp_expiry.timestamp() < time.time():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP code."
        )
     
    user.otp = None
    user.otp_expiry = None
    db.commit()
    db.refresh(user)

    return {
        "message": "OTP verified successfully"
    }


@router.post("/reset_password")
async def reset_pass(token: str, payload: reset_pass_Request, db: Session = Depends(get_db)):
    user = verify_token(token, db)

    

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized Access"
        )

    if user.otp is not None:
                raise HTTPException(
                    status_code= status.HTTP_400_BAD_REQUEST,
                    detail="Bad Request  you have to verify the otp first"
                )

    is_verify = passwordCheack(payload.New_Password)
    if not is_verify:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail="Password must be at least 8 characters and include at least one letter, number, and symbol."
        )

    if payload.New_Password != payload.Confrim_Password:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail="New password and confirm password do not match."
        )

   

    hashed_pwd = hash_password(payload.New_Password)
    user.password = hashed_pwd
    db.commit()
    db.refresh(user)

    return {
        "message": "Your password has been reset. You can login now."
    }
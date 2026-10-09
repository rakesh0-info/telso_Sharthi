from fastapi import APIRouter, HTTPException ,status,Depends
from sqlalchemy.orm import Session
from databaseModel.user_model import User
from database_config import get_db
from jwts.DB_Security_Config import require_roles
from enums.roleEnum import Role
from requestModel.Action import school_action, user_Action
from requestModel.School_Request import create_schools
from requestModel.User_Request import create_users,AssignAchoolAdmin
from databaseModel.School_model import School
from util_validate.password_security import hash_password



router=APIRouter(prefix="/Super_Admin/api/v1")


@router.get("/dashboard")
async def dashboard( cur:User=Depends(require_roles(Role.SUPER_ADMIN))):
    return " hy  i am Super admin"


@router.post("/create_user")
async def create_user(payload:create_users,db:Session=Depends(get_db),curr :User=Depends(require_roles(Role.SUPER_ADMIN))):

    exist_user=db.query(User).filter(User.email==payload.email).first()
    if exist_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User Already exist"
        )

    hash_pass=hash_password(payload.password)

    newUser=User(
        first_Name=payload.first_name,
        last_Name=payload.last_name,
        email=payload.email,
        phone=payload.phone,
        password=hash_pass,
        role=payload.role,
        activation_status=payload.activation_status
    )

    db.add(newUser)
    db.commit()

    return "User Added SucessFully"



@router.post("/create_school")
async def create_school(
    payload: create_schools,
    db: Session = Depends(get_db),
    curr: User = Depends(require_roles(Role.SUPER_ADMIN))
):
    exist_school = db.query(School).filter(School.School_Code == payload.school_code).first()

    if exist_school:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="School already exists"
        )
        
    admin_user_id = None
    
    if payload.school_admin_email:
        
        admin_user = db.query(User).filter(User.email == payload.school_admin_email).first()
        if admin_user:
           
            existing_assignment = db.query(School).filter(School.admin_id == admin_user.id).first()
            if existing_assignment:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Selected user is already assigned as an admin to another school"
                )
            admin_user_id = admin_user.id

    new_school = School(
        school_name=payload.school_name,
        School_Code=payload.school_code,
        District=payload.district,
        Region=payload.region,
        address=payload.address,
        phone=payload.phone,
        admin_id=admin_user_id, 
        activation_status=payload.activation_status
    )
    db.add(new_school)
    db.commit()

    return {"message": "New school added successfully"}



@router.get("/all_school_admin")
async def get_all_school_admin(
    db: Session = Depends(get_db),
    curr: User = Depends(require_roles(Role.SUPER_ADMIN))
):
    # Fetch all users who have the role of SCHOOL_ADMIN
    users = db.query(User).filter(User.role == Role.SCHOOL_ADMIN).all()

    response = []
    for u in users:
        # Check if this school admin is already assigned to a school
        assigned_school = db.query(School).filter(School.admin_id == u.id).first()

       
        if not assigned_school:
            user_data = {
                "name": f"{u.first_Name} {u.last_Name}",
                "email": u.email,
            }
            response.append(user_data)

    return response



@router.put("/assign_school_admin")
async def assign_School_Admin(
    payload: AssignAchoolAdmin,
    db: Session = Depends(get_db),
    curr: User = Depends(require_roles(Role.SUPER_ADMIN))
):
    exist_user = db.query(User).filter(User.email == payload.email).first()

    if not exist_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not exist"
        )
        
    exist_school_admin = db.query(School).filter(School.admin_id == exist_user.id).first()
    if exist_school_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already assigned to a school"
        )

    target_school = db.query(School).filter(
        School.School_Code == payload.school_code,
        School.admin_id == None
    ).first()

    if not target_school:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="School does not exist or already has an admin assigned"
        )

    target_school.admin_id = exist_user.id
    db.commit()
    db.refresh(target_school)

    return {"message": "Admin assigned to the school successfully"}


@router.get("/get_all_user")
async def get_all_user(
    db: Session = Depends(get_db),
    curr: User = Depends(require_roles(Role.SUPER_ADMIN))
):
    all_users = db.query(User).all()
    response = []

    for user in all_users:
       
        school_name = user.schools[0].school_name if user.schools else None
        school_region = user.schools[0].Region if user.schools else None

        res = {
            "name": f"{user.first_Name} {user.last_Name}",
            "email": user.email,
            "role": user.role,
            "school": school_name,
            "region": school_region,
            "last_login": user.last_login
        }
        response.append(res)

    return response


@router.get("/get_all_school")
async def get_all_School(
    db: Session = Depends(get_db),
    curr: User = Depends(require_roles(Role.SUPER_ADMIN))
):
    all_school = db.query(School).all()
    response = []

    for s in all_school:
        res = {
            "name": s.school_name,
            "school_code": s.School_Code,
            "district": s.District,
            "student": "1000 Dummy",
            "teacher": "50 dummy",
            "status": s.activation_status
        }
        response.append(res)

    return {"res": response}


@router.post("/school_action")
async def action_School(
    payload: school_action,
    db: Session = Depends(get_db),
    curr: User = Depends(require_roles(Role.SUPER_ADMIN))
):
    school = db.query(School).filter(School.School_Code == payload.school_code).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
  
    return {"message": f"Action {payload.action_type} performed on school {payload.school_code}"}


@router.post("/user_action")
async def action_user(
    payload: user_Action,
    db: Session = Depends(get_db),
    curr: User = Depends(require_roles(Role.SUPER_ADMIN))
):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    
    return {"message": f"Action {payload.action_type} performed on user {payload.email}"}
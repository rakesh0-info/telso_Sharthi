from fastapi import APIRouter, HTTPException, Query, status, Depends
from sqlalchemy.orm import Session
from databaseModel.user_model import User
from database_config import get_db
from jwts.DB_Security_Config import require_roles
from enums.roleEnum import Role
from requestModel.Action import school_action, user_Action
from requestModel.School_Request import create_schools
from requestModel.User_Request import create_users, AssignAchoolAdmin
from databaseModel.School_model import School
from util_validate.password_security import hash_password
from enums.userActivationEnum import activation

router = APIRouter(prefix="/Super_Admin/api/v1")


@router.get("/dashboard")
async def dashboard(cur: User = Depends(require_roles(Role.SUPER_ADMIN))):
    return "hy i am Super admin"


@router.post("/create_user")
async def create_user(
    payload: create_users,
    db: Session = Depends(get_db),
    curr: User = Depends(require_roles(Role.SUPER_ADMIN))
):
    exist_user = db.query(User).filter(User.email == payload.email).first()
    if exist_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User Already exist"
        )

    hash_pass = hash_password(payload.password)

    newUser = User(
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
    db.refresh(newUser)
    

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
        admin_user = db.query(User).filter(User.email == payload.school_admin_email,User.role==Role.SCHOOL_ADMIN).first()
        if not admin_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="School admin email does not exist"
            )
        
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
    db.refresh(new_school)

    u=db.query(User).filter(User.email==payload.school_admin_email).first()
    u.school_id=new_school.id
    db.commit()
    db.refresh(u)

    return {"message": "New school added successfully"}


@router.get("/all_school_admin")
async def get_all_school_admin(
    db: Session = Depends(get_db),
    curr: User = Depends(require_roles(Role.SUPER_ADMIN))
):
    users = db.query(User).filter(User.role == Role.SCHOOL_ADMIN).all()

    response = []
    for u in users:
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
        
    
    if exist_user.role != Role.SCHOOL_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have the SCHOOL_ADMIN role"
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
    exist_user.school_id=target_school.id
    db.commit()
    db.refresh(exist_user)
    return {"message": "Admin assigned to the school successfully"}





@router.get("/get_all_users", summary="Get all users with pagination and school details")
async def get_all_users(
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return (Max 500)"),
    db: Session = Depends(get_db),
    curr: User = Depends(require_roles(Role.SUPER_ADMIN))
):
    """
    Retrieves a paginated list of all system users with their associated school and region info.
    Restricted strictly to SUPER_ADMIN.
    """
    # 1. Fetch users with pagination limits to prevent memory exhaustion
    users = db.query(User).offset(skip).limit(limit).all()
    
    if not users:
        return {
            "success": True,
            "skip": skip,
            "limit": limit,
            "count": 0,
            "users": []
        }

    response = []
    for user in users:
        # Safely resolve school and region attributes across various relationship structures
        school_name = None
        school_region = None
        
        if hasattr(user, "schools") and user.schools:
            school_name = getattr(user.schools[0], "school_name", None)
            school_region = getattr(user.schools[0], "Region", None)
        elif hasattr(user, "school") and user.school:
            school_name = getattr(user.school, "school_name", None)
            school_region = getattr(user.school, "Region", None)

        # Ensure enums serialize cleanly as strings
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        
        activation_val = getattr(user, "activation_status", getattr(user, "activation", "ACTIVE"))
        activation_str = activation_val.value if hasattr(activation_val, "value") else str(activation_val)

        # Handle name formatting flexibly (first/last vs single name attribute)
        first_name = getattr(user, "first_Name", "") or ""
        last_name = getattr(user, "last_Name", "") or ""
        full_name = f"{first_name} {last_name}".strip() or getattr(user, "name", "N/A")

        response.append({
            "user_id": user.id,
            "name": full_name,
            "email": user.email,
            "role": role_str,
            "school": school_name,
            "region": school_region,
            "status": activation_str,
            "last_login": user.last_login
        })

    return {
        "success": True,
        "skip": skip,
        "limit": limit,
        "count": len(response),
        "users": response
    }





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

    if payload.action_type == "inactive" or payload.action_type == "INACTIVE":
        if school.activation_status == activation.INACTIVE:
            raise HTTPException(status_code=400, detail="School is already inactive")
        else:
            school.activation_status = activation.INACTIVE
            db.commit()
            db.refresh(school)
            return "school inactive sucessfully"
    elif payload.action_type == "active" or payload.action_type == "ACTIVE":
        if school.activation_status == activation.ACTIVE:
            raise HTTPException(status_code=400, detail="school already is in active state")
        else:
            school.activation_status = activation.ACTIVE
            db.commit()
            db.refresh(school)
            return "school activation sucessfully"


@router.post("/user_action")
async def action_user(
    payload: user_Action,
    db: Session = Depends(get_db),
    curr: User = Depends(require_roles(Role.SUPER_ADMIN))
):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if payload.action_type == "inactive" or payload.action_type == "INACTIVE":
        if user.activation_status == activation.INACTIVE:
            raise HTTPException(status_code=400, detail="user is already inactive")
        else:
            user.activation_status = activation.INACTIVE
            db.commit()
            db.refresh(user)
            return "user inactive sucessfully"
    elif payload.action_type == "active" or payload.action_type == "ACTIVE":
        if user.activation_status == activation.ACTIVE:
            raise HTTPException(status_code=400, detail="user already is in active state")
        else:
            user.activation_status = activation.ACTIVE
            db.commit()
            db.refresh(user)
            return "user activation sucessfully"
from enum import Enum

class Role(str,Enum):
    SUPER_ADMIN="Super_Admin"
    CONTENT_ADMIN="content_admin"
    SCHOOL_ADMIN="school_admin"
    USER="user"
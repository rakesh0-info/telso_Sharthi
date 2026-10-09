
from pydantic import EmailStr, BaseModel
class reset_pass_Request(BaseModel):
    New_Password :str
    Confrim_Password:str
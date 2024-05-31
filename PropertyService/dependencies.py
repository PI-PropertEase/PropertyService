from fastapi import Depends, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import EmailStr, BaseModel

from ProjectUtils.DecoderService.decode_token import decode_token


class UserBase(BaseModel):
    email: EmailStr


def get_user(res: Response, cred: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))):
    decoded_token = decode_token(res, cred)
    return UserBase(**decoded_token)

def get_user_email(user: UserBase = Depends(get_user)):
    return user.email

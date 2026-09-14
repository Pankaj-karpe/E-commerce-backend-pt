#to use hashing of password in db instead of actual password
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash(password : str):
    return pwd_context.hash(password)

def verify_inHashedPass_is_savedHasedPass(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password) 
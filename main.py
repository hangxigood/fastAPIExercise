import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Request, status, Security
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, Column, String, Date, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pydantic import BaseModel, ValidationError, validator, EmailStr
from datetime import datetime, date, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
import logging
import pymysql

pymysql.install_as_MySQLdb()

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__) 

# Load environment variables
load_dotenv()

# Database connection
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")

print(DB_USER, DB_PASSWORD, DB_HOST, DB_NAME)

SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Student model for database
class StudentDB(Base):
    __tablename__ = "students"

    studentID = Column(String(50), primary_key=True, index=True)
    studentName = Column(String(100))
    courseName = Column(String(50))
    Date = Column(Date)

# User database model
class UserDB(Base):
    __tablename__ = "users"
    
    username = Column(String(50), primary_key=True, index=True)
    email = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(100))
    is_active = Column(Boolean, default=True)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Pydantic model for request validation
class StudentCreate(BaseModel):
    studentID: str
    studentName: str
    courseName: str
    Date: date

    @validator('Date', pre=True)
    def parse_date(cls, value):
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%d/%m/%Y").date()
            except ValueError:
                raise ValueError("Date must be in DD/MM/YYYY format")
        return value

# User Pydantic models
class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class User(UserBase):
    is_active: bool

    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# JWT Settings
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Password and token functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(db: Session, username: str):
    return db.query(UserDB).filter(UserDB.username == username).first()

def authenticate_user(db: Session, username: str, password: str):
    user = get_user(db, username)
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
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
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

# Exception handler for SQLAlchemy errors
@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"SQLAlchemy error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"message": "An error occurred while processing your request."}
    )

# Exception handler for validation errors
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    logger.error(f"Validation error: {str(exc)}")
    return JSONResponse(
        status_code=422,
        content={"message": "Invalid input data.", "details": exc.errors()}
    )

# New authentication endpoints
@app.post("/register", response_model=User)
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = get_user(db, username=user.username)
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Username already registered"
        )
    hashed_password = get_password_hash(user.password)
    db_user = UserDB(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/student", status_code=201)
async def create_student(
    student: StudentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        db_student = db.query(StudentDB).filter(StudentDB.studentID == student.studentID).first()
        if db_student:
            # Return a 409 Conflict response
            return JSONResponse(
                status_code=409,
                content={"message": "Student already exists"}
            )
        
        new_student = StudentDB(**student.dict())
        db.add(new_student)
        db.commit()
        db.refresh(new_student)
        return {"message": "Student created successfully"}
    except IntegrityError as e:
        db.rollback()
        logger.error(f"IntegrityError: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid data. Please check your input.")
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

@app.put("/student/{student_id}", status_code=200)
async def update_student(
    student_id: str,
    student: StudentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        db_student = db.query(StudentDB).filter(StudentDB.studentID == student_id).first()
        if not db_student:
            return JSONResponse(
                status_code=404,
                content={"message": "Student not found"}
            )
        
        for key, value in student.dict().items():
            setattr(db_student, key, value)
        
        db.commit()
        db.refresh(db_student)
        return {"message": "Student updated successfully"}
    except IntegrityError as e:
        db.rollback()
        logger.error(f"IntegrityError: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid data. Please check your input.")
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

@app.delete("/student/{student_id}", status_code=200)
async def delete_student(
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        db_student = db.query(StudentDB).filter(StudentDB.studentID == student_id).first()
        if not db_student:
            return JSONResponse(
                status_code=404,
                content={"message": "Student not found"}
            )
        
        db.delete(db_student)
        db.commit()
        return {"message": "Student deleted successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

@app.get("/students", status_code=200)
async def get_students(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        students = db.query(StudentDB).all()
        return students
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

@app.get("/student/{student_id}", status_code=200)
async def get_student(
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        student = db.query(StudentDB).filter(StudentDB.studentID == student_id).first()
        if not student:
            return JSONResponse(
                status_code=404,
                content={"message": "Student not found"}
            )
        return student
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"message": "An unexpected error occurred."}
    )
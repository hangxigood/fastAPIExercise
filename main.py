import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, Column, String, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pydantic import BaseModel, ValidationError
from datetime import date
import logging
import pymysql

pymysql.install_as_MySQLdb()

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
    course = Column(String(50))
    presentDate = Column(Date)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Pydantic model for request validation
class StudentCreate(BaseModel):
    studentID: str
    studentName: str
    course: str
    presentDate: date

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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

@app.post("/student", status_code=201)
async def create_student(student: StudentCreate, db: Session = Depends(get_db)):
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
async def update_student(student_id: str, student: StudentCreate, db: Session = Depends(get_db)):
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


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"message": "An unexpected error occurred."}
    )
from sqlalchemy.sql import func
from sqlalchemy.dialects import mysql
from sqlalchemy import Boolean, Column, String, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Departments(Base):
    __tablename__ = 'departments'
    __table_args__= {'schema':'pruebaglobant'}
    id = Column(Integer, primary_key=True)
    department = Column(String(50), nullable=False)

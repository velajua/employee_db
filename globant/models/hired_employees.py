from sqlalchemy.sql import func
from sqlalchemy.dialects import mysql
from sqlalchemy import Boolean, Column, String, DateTime, Integer, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class HiredEmployees(Base):
    __tablename__ = 'hired_employees'
    __table_args__= {'schema':'pruebaglobant'}
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    datetime = Column(DateTime, nullable=False)
    department_id = Column(Integer, ForeignKey('pruebaglobant.departments.id'), nullable=False)
    job_id = Column(Integer, ForeignKey('pruebaglobant.jobs.id'), nullable=False)

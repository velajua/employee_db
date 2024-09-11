from sqlalchemy.sql import func
from sqlalchemy.dialects import mysql
from sqlalchemy import Boolean, Column, String, DateTime, Integer, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class HiredEmployee(Base):
    __tablename__ = 'hired_employees'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    datetime = Column(DateTime, nullable=False)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=False)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False)

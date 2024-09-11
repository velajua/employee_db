from sqlalchemy.sql import func
from sqlalchemy.dialects import mysql
from sqlalchemy import Boolean, Column, String, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Job(Base):
    __tablename__ = 'jobs'
    id = Column(Integer, primary_key=True)
    job = Column(String(50), nullable=False)

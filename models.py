from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    email = Column(String(255), unique=True, index=True)
    hashed_password = Column(Text)
    hashed_api = Column(Text, nullable=True)
    hashed_api_secret = Column(Text, nullable=True)

    strategies = relationship("Strategy", back_populates="user")

class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String(100))
    indicator = Column(String(50))
    parameters = Column(JSON)

    user = relationship("User", back_populates="strategies")

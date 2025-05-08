
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "Users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(255))
    created_at = Column(DateTime, default=datetime.now)

    # Yeni kolonlar:
    api_key = Column(String(200), nullable=True)
    api_secret = Column(String(200), nullable=True)

    strategies = relationship("Strategy", back_populates="user")


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("Users.id"))
    name = Column(String(100))
    indicator = Column(String(50))
    parameters = Column(JSON)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", back_populates="strategies")


from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
from database import Base

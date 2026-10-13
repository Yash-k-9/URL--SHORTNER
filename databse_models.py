from sqlalchemy import Column, String, Integer,Float,ForeignKey
from sqlalchemy.orm import declarative_base,relationship
from sqlalchemy import DateTime
from core.utils import utcnow

base=declarative_base()

class User(base):
    __tablename__='users'

    id=Column(Integer,primary_key=True,index=True)
    name=Column(String, nullable=False)
    email=Column(String,unique=True, nullable=False)
    number=Column(String(13),nullable=False)
    Pass=Column(String,nullable=False)
    urls = relationship(
    "Url",
    back_populates="person",
    cascade="all, delete-orphan"
    )

class Url(base):
    __tablename__='links'
    id=Column(Integer,primary_key=True,index=True)
    orig_url=Column(String,index=True)
    short_url=Column(String,unique=True)
    created_at = Column(DateTime, default=utcnow)
    expires_at = Column(DateTime, nullable=True)
    user_id=Column(Integer,ForeignKey("users.id"))

    person=relationship('User',back_populates='urls')
    clicks = relationship(
    "Click",
    back_populates="url",
    cascade="all, delete-orphan"
    )
    
class Click(base):
    __tablename__='clicks'
    id=Column(Integer,primary_key=True)
    country = Column(String, nullable=True)
    city = Column(String, nullable=True)
    browser = Column(String, nullable=True)
    device = Column(String, nullable=True)
    operating_system = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    referrer = Column(String, nullable=True)
    clicked_at = Column(DateTime, default=utcnow)

    url_id=Column(Integer,ForeignKey("links.id"))
    url=relationship('Url',back_populates='clicks')
from sqlalchemy import *
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

FloweyBase = declarative_base()

user_activity_table = Table('user_activity', FloweyBase.metadata,
        Column('user_id', Integer, ForeignKey('users.id')),
        Column('activity_id', Integer, ForeignKey('activities.id'))
        )

class User(FloweyBase):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String(length=40))
    fullname = Column(String(length=60))
    codename = Column(String(length=30), unique=True)
    access = Column(Enum('unconfirmed', 'user', 'admin'))
    date = Column(DateTime)

    def __repr__(self):
        return "<User(id=%d, name='%s', fullname='%s', codename='%s', access='%s'>" % (
                self.id, self.name, self.fullname, self.codename, self.access)

class Activity(FloweyBase):
    __tablename__ = 'activities'
    id = Column(Integer, primary_key=True)
    name = Column(String(length=100))
    date = Column(DateTime)
    attendees = relationship("User", secondary=user_activity_table, backref="activities")


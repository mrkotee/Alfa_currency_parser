from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from datetime import datetime as dt
import os
try:
    from settings import base_path, userbase_path
except ImportError:
    from alfa_bot.settings import base_path, userbase_path


Base = declarative_base()
UserBase = declarative_base()


class CurrencyTypes(Base):
    __tablename__ = "currency_type"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    abbreviation = Column(String)

    def __init__(self, abbreviation, name=''):
        self.name = name
        self.abbreviation = abbreviation


class CurrencyRates(Base):
    __tablename__ = "currency_rates"
    id = Column(Integer, primary_key=True)
    currency_type = Column(Integer, ForeignKey("currency_type.id"))
    date = Column(DateTime)
    to_buy = Column(Float)
    to_sell = Column(Float)

    def __init__(self, currency_type_id, currency_to_buy, currency_to_sell):
        self.currency_type = currency_type_id
        self.to_buy = currency_to_buy
        self.to_sell = currency_to_sell
        self.date = dt.now()


class PurchasedCurrency(Base):
    __tablename__ = "purchased_currency"
    id = Column(Integer, primary_key=True)
    id_for_user = Column(Integer)
    currency_type = Column(Integer, ForeignKey("currency_type.id"))
    date = Column(DateTime)
    currency_value = Column(Float, nullable=True)
    currency_buy_rate = Column(Float, nullable=True)
    waiting_for = Column(Float, nullable=True)
    user_id = Column(Integer, nullable=True)
    selled = Column(Boolean)

    def __init__(self, currency_type_id, user_id, id_for_user, currency_value=0.0, date=dt.now().date(), currency_buy_rate=0.0, waiting_for=0.0):
        self.currency_type = currency_type_id
        self.currency_value = currency_value
        self.id_for_user = id_for_user
        self.date = date
        self.currency_buy_rate = currency_buy_rate
        self.user_id = user_id
        self.waiting_for = waiting_for
        self.selled = False


class Users(UserBase):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer)
    name = Column(String)
    add_date = Column(DateTime)
    active = Column(Boolean)
    edit_purchase_id = Column(Integer, nullable=True)

    def __init__(self, chat_id, name):
        self.chat_id = chat_id
        self.name = name
        self.add_date = dt.now()
        self.active = True
        self.edit_purchase_id = None


if not os.path.exists(base_path):
    engine = create_engine('sqlite:///%s' % base_path, echo=False)
    Base.metadata.create_all(bind=engine)

if not os.path.exists(userbase_path):
    engine = create_engine('sqlite:///%s' % userbase_path, echo=False)
    UserBase.metadata.create_all(bind=engine)

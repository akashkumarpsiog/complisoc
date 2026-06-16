from sqlalchemy.orm import declarative_base

Base = declarative_base()
# this creates the base class for all the ORM models. databases store tables and python works with classes and objects. So SQLAlchemy needs to know which python classes are db models, which classes are tables. 
# the declarativebase() class creates the parent class. The classes inherit from the base so SQLAlchemy recognizes this is a database model. The base also provides the metadata object which is used to create tables and manage the schema.
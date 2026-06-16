from complisoc.backend.database.base import Base
from complisoc.backend.database.session import engine
from complisoc.backend.models import *


def main():
    Base.metadata.create_all(engine)
    print("Created database tables:", sorted(Base.metadata.tables.keys()))


if __name__ == "__main__":
    main()

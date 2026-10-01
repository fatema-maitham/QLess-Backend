from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dotenv import load_dotenv

load_dotenv()

from config.environment import DATABASE_URL
from models.base import Base
import models  # noqa: F401  (loads every model so all tables are known)
from data.role_data import create_roles
from data.user_data import create_users
from data.category_data import create_categories

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

db = SessionLocal()

try:
    print("Seeding the database...")

    # Empty every table first (children before parents) so seeding can be re-run
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())

    roles = create_roles()
    db.add_all(roles.values())

    users = create_users(roles)
    db.add_all(users.values())

    categories = create_categories()
    db.add_all(categories.values())

    # Person B and Person A add businesses, branches, queues, etc. below this line

    db.commit()
    print("Database seeding complete! 👋")

except Exception as e:
    db.rollback()
    print("An error occurred:", e)

finally:
    db.close()
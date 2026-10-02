from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from dotenv import load_dotenv

load_dotenv()

from config.environment import DATABASE_URL
from models.base import Base
import models  # noqa: F401  (loads every model so all tables are known)
from data.role_data import create_roles
from data.user_data import create_users
from data.category_data import create_categories
from data.business_data import create_businesses

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

db = SessionLocal()

try:
    print("Seeding the database...")

    # Empty every table and restart ids at 1 so seeding can be re-run
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    db.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

    roles = create_roles()
    db.add_all(roles.values())

    users = create_users(roles)
    db.add_all(users.values())

    categories = create_categories()
    db.add_all(categories.values())

    db.add_all(create_businesses(users, categories))

    db.commit()
    print("Database seeding complete! 👋")

except Exception as e:
    db.rollback()
    print("An error occurred:", e)

finally:
    db.close()
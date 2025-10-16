import os

DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_HOST = os.getenv("DB_HOST", "db")  # Change from localhost to db (Docker service name)
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "screener_db")

# import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:password@localhost:5432/screener_db"
)


REDIS_HOST = os.getenv("REDIS_HOST", "redis")  # Use the Redis service name, NOT localhost
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
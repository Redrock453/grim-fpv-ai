import os
from dotenv import load_dotenv

load_dotenv()

def get_env_var(name: str, default: str = "") -> str:
    return os.getenv(name, default)

DEBUG = get_env_var("DEBUG", "False").lower() == "true"
DATABASE_URL = get_env_var("DATABASE_URL", "sqlite:///./grim5.db")

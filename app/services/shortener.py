import string
import random
import hashlib
from sqlalchemy.orm import Session
from app.db.models import Link


def generate_short_code(length: int = 6) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


def generate_deterministic_code(url: str, length: int = 6) -> str:
    hash_hex = hashlib.sha256(url.encode()).hexdigest()
    return hash_hex[:length]


def create_short_code(db: Session, custom_alias: str = None) -> str:
    if custom_alias:
        existing = db.query(Link).filter(Link.short_code == custom_alias).first()
        if existing:
            raise ValueError(f"Alias '{custom_alias}' is already taken")
        return custom_alias

    for _ in range(10):
        code = generate_short_code()
        existing = db.query(Link).filter(Link.short_code == code).first()
        if not existing:
            return code

    raise ValueError("Could not generate unique short code")


def get_link_by_code(db: Session, short_code: str) -> Link | None:
    return db.query(Link).filter(Link.short_code == short_code, Link.is_active == True).first()

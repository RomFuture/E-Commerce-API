import bcrypt

# Bcrypt uses at most 72 bytes of password material.
_MAX = 72


def hash_password(plain: str) -> str:
    raw = plain.encode("utf-8")[:_MAX]
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    raw = plain.encode("utf-8")[:_MAX]
    return bcrypt.checkpw(raw, hashed.encode("ascii"))

from __future__ import annotations

import bcrypt


def hash_password(plain: str) -> str:
    data = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12))
    return data.decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False

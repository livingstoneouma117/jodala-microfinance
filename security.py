import hashlib
import os

import bcrypt


def _bcrypt_rounds() -> int:
    try:
        return max(4, int(os.environ.get("BCRYPT_ROUNDS", "12")))
    except (TypeError, ValueError):
        return 12


def _legacy_sha256_hash(password: str) -> str:
    return hashlib.sha256(str(password or "").encode("utf-8")).hexdigest()


def is_bcrypt_hash(stored_hash: str) -> bool:
    return str(stored_hash or "").startswith(("$2a$", "$2b$", "$2y$"))


def hash_password(password: str) -> str:
    raw = str(password or "").encode("utf-8")
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=_bcrypt_rounds())).decode("utf-8")


def verify_password(password: str, stored_hash: str) -> bool:
    stored = str(stored_hash or "")
    if not stored:
        return False
    if is_bcrypt_hash(stored):
        try:
            return bcrypt.checkpw(str(password or "").encode("utf-8"), stored.encode("utf-8"))
        except (ValueError, TypeError):
            return False
    return _legacy_sha256_hash(password) == stored


def password_needs_upgrade(stored_hash: str) -> bool:
    return not is_bcrypt_hash(stored_hash)

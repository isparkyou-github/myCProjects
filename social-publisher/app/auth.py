"""手机/公网访问的登录保护：访问密码 + 签名会话 Cookie。

未设置密码时不启用（本机使用零打扰）；设置后所有页面与接口都需登录，
支持保持登录 1/7/30 天或永久。密码加盐哈希存储，不存明文。
"""

import hashlib
import hmac
import secrets as _secrets
import time

from . import settings as cfg


def _auth() -> dict:
    return cfg.raw_config().get("auth") or {}


def enabled() -> bool:
    return bool(_auth().get("password_hash"))


def _hash(secret: str, password: str) -> str:
    return hashlib.sha256((secret + password).encode()).hexdigest()


def set_password(password: str) -> None:
    c = cfg.raw_config()
    secret = (c.get("auth") or {}).get("secret") or _secrets.token_hex(32)
    c["auth"] = {"secret": secret, "password_hash": _hash(secret, password)}
    cfg._write_config(c)


def clear_password() -> None:
    c = cfg.raw_config()
    c.pop("auth", None)
    cfg._write_config(c)


def check_password(password: str) -> bool:
    a = _auth()
    return bool(a) and hmac.compare_digest(
        _hash(a["secret"], password), a.get("password_hash", ""))


def make_token(keep_days: int) -> str:
    a = _auth()
    exp = 2**31 - 1 if keep_days == 0 else int(time.time()) + keep_days * 86400
    sig = hmac.new(a["secret"].encode(), str(exp).encode(),
                   hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"


def verify_token(token: str) -> bool:
    if not enabled():
        return True
    try:
        exp_s, sig = token.split(".", 1)
        exp = int(exp_s)
    except (ValueError, AttributeError):
        return False
    good = hmac.new(_auth()["secret"].encode(), exp_s.encode(),
                    hashlib.sha256).hexdigest()
    return hmac.compare_digest(good, sig) and exp > time.time()

"""
测试：安全工具 — 密码哈希 + JWT
"""
from src.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)


class TestPasswordHashing:
    def test_hash_produces_different_from_plain(self):
        """哈希后的密码不应该与原文相同"""
        plain = "mypassword123"
        hashed = hash_password(plain)
        assert hashed != plain
        assert "$2" in hashed[:3]  # bcrypt prefix

    def test_verify_correct_password(self):
        """正确密码验证通过"""
        plain = "secure-p4ss!"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password(self):
        """错误密码验证失败"""
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_same_password_different_hash(self):
        """相同密码每次哈希结果不同（salt不同）"""
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2
        assert verify_password("same", h1) is True
        assert verify_password("same", h2) is True

    def test_empty_password(self):
        """空密码也能哈希和验证"""
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("x", hashed) is False


class TestJWT:
    def test_create_and_decode(self):
        """编码后能正确解码"""
        token = create_access_token("user-uuid-123")
        user_id = decode_access_token(token)
        assert user_id == "user-uuid-123"

    def test_invalid_token_returns_none(self):
        """无效令牌返回None"""
        assert decode_access_token("not.a.valid.token") is None
        assert decode_access_token("") is None
        assert decode_access_token("abc.def") is None

    def test_tampered_token_returns_none(self):
        """篡改的令牌返回None"""
        token = create_access_token("user-1")
        # 修改签名部分（中间字符），彻底破坏签名
        parts = token.rsplit(".", 1)
        tampered = parts[0] + "." + parts[1][::-1]  # 反转签名
        assert decode_access_token(tampered) is None

    def test_different_users_different_tokens(self):
        """不同用户生成不同令牌"""
        t1 = create_access_token("user-1")
        t2 = create_access_token("user-2")
        assert t1 != t2
        assert decode_access_token(t1) == "user-1"
        assert decode_access_token(t2) == "user-2"

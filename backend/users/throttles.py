"""Login cheklovlari.

Auditoriyada o'nlab talaba bitta tashqi IP manzil (NAT) orqali kiradi, shuning uchun cheklov IP bo'yicha emas,
login nomi bo'yicha qo'yiladi: bitta hisob parolini ketma-ket sinab topish to'xtatiladi, guruh esa bir vaqtda kira
oladi. IP bo'yicha esa alohida, ancha keng chegara qoladi (ko'p hisoblarni birdan sinashdan himoya).
"""
from rest_framework.throttling import SimpleRateThrottle


class LoginUsernameThrottle(SimpleRateThrottle):
    """Bitta login nomiga urinishlar (settings: "login")."""

    scope = "login"

    def get_cache_key(self, request, view):
        username = request.data.get("username") if hasattr(request, "data") else None
        if not isinstance(username, str) or not username.strip():
            return self.cache_format % {"scope": self.scope, "ident": "ip:" + self.get_ident(request)}
        return self.cache_format % {"scope": self.scope, "ident": "user:" + username.strip().lower()}


class LoginIPThrottle(SimpleRateThrottle):
    """Bitta IP manzildan barcha loginlarga urinishlar (settings: "login_ip")."""

    scope = "login_ip"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}

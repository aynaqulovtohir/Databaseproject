from django.utils import translation


class ResetLanguageMiddleware:
    """So'rov tugagach tilni standart (o'zbekcha) holatga qaytaradi.

    LocaleMiddleware tilni ish oqimiga (thread) faollashtiradi va o'zi o'chirmaydi: shu oqimda so'rovdan
    tashqari bajariladigan ish (fon vazifasi, keyingi test) oldingi foydalanuvchining tilida qolmasin.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        finally:
            translation.deactivate()

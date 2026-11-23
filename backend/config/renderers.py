from rest_framework.renderers import JSONRenderer

from .i18n import current_lang, localize


class LocalizedJSONRenderer(JSONRenderer):
    """JSON javobdagi o'zbekcha xabarlarni so'rov tiliga (Accept-Language) o'giradi. O'zbekcha so'rovda o'zgarmaydi."""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if current_lang() != "uz" and data is not None:
            data = localize(data)
        return super().render(data, accepted_media_type, renderer_context)

"""Bot mantiqi: kelgan buyruqlarni qayta ishlash va navbatdagi xabarlarni yuborish."""
import logging

from django.utils import timezone

from . import linking, telegram
from .models import Notification

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
SEND_BATCH_SIZE = 25

TEXT_LINKED = "Hisobingiz muvaffaqiyatli bog'landi. Endi bildirishnomalar shu yerga keladi.\nO'chirish uchun /stop yozing."
TEXT_BAD_CODE = "Havola noto'g'ri yoki muddati o'tgan. Platformada «Telegramni ulash» tugmasini qayta bosing."
TEXT_START_WITHOUT_CODE = "Bu bot ta'lim platformasi bildirishnomalarini yuboradi. Ulash uchun platformadagi «Telegramni ulash» tugmasidan foydalaning."
TEXT_UNLINKED = "Bog'lanish o'chirildi. Endi bildirishnomalar kelmaydi."
TEXT_NOT_LINKED = "Bu chat hech qaysi hisobga bog'lanmagan."
TEXT_HELP = "Bu bot faqat bildirishnoma yuboradi.\n/stop - bildirishnomalarni o'chirish."


def handle_update(update):
    """Bitta kelgan xabarni qayta ishlaydi. Faqat shaxsiy chatdagi matnli xabarlar qabul qilinadi."""
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    text = (message.get("text") or "").strip()
    if chat.get("type") != "private" or not text:
        return
    chat_id = chat["id"]

    command, _, argument = text.partition(" ")
    command = command.split("@")[0].lower()

    if command == "/start":
        code = argument.strip()
        if not code:
            reply = TEXT_START_WITHOUT_CODE
        elif linking.link_chat(code, chat_id):
            reply = TEXT_LINKED
        else:
            reply = TEXT_BAD_CODE
    elif command == "/stop":
        reply = TEXT_UNLINKED if linking.unlink_chat(chat_id) else TEXT_NOT_LINKED
    else:
        reply = TEXT_HELP

    try:
        telegram.send_message(chat_id, reply)
    except telegram.TelegramError as exc:
        logger.warning("Javob yuborilmadi: %s", exc)


def send_pending():
    """Navbatdagi xabarlarni yuboradi. Qaytaradi: yuborilganlar soni."""
    sent = 0
    pending = (
        Notification.objects.filter(status=Notification.Status.PENDING)
        .select_related("user", "user__telegram_account")
        .order_by("created_at", "id")[:SEND_BATCH_SIZE]
    )
    for notification in pending:
        account = getattr(notification.user, "telegram_account", None)
        if account is None or not notification.user.is_active:
            mark_failed(notification, "Foydalanuvchi bog'lanmagan yoki bloklangan")
            continue

        notification.attempts += 1
        try:
            telegram.send_message(account.chat_id, notification.text)
        except telegram.TelegramBlockedError:
            # Foydalanuvchi botni bloklagan: bog'lanish o'chiriladi
            linking.unlink_chat(account.chat_id)
            mark_failed(notification, "Foydalanuvchi botni bloklagan")
        except telegram.TelegramTransientError as exc:
            if notification.attempts >= MAX_ATTEMPTS:
                mark_failed(notification, str(exc))
            else:
                notification.error_message = str(exc)[:255]
                notification.save(update_fields=["attempts", "error_message"])
            # Telegram vaqtincha ishlamayapti: qolganlarini keyingi safar yuboramiz
            break
        except telegram.TelegramError as exc:
            mark_failed(notification, str(exc))
        else:
            notification.status = Notification.Status.SENT
            notification.sent_at = timezone.now()
            notification.error_message = ""
            notification.save(update_fields=["status", "sent_at", "attempts", "error_message"])
            sent += 1
    return sent


def mark_failed(notification, reason):
    notification.status = Notification.Status.FAILED
    notification.error_message = reason[:255]
    notification.save(update_fields=["status", "attempts", "error_message"])

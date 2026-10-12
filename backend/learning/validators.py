"""Yuklanadigan fayllarni tekshirish: turi, hajmi va haqiqiy tarkibi."""
from pathlib import Path

from rest_framework import serializers

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

# Kengaytma -> fayl boshidagi belgi (signature). Kengaytmani o'zgartirib
# boshqa turdagi faylni yuklashdan himoya qiladi.
ZIP_SIGNATURE = b"PK\x03\x04"  # docx va pptx aslida zip arxiv
ALLOWED_FILE_TYPES = {
    ".pdf": (b"%PDF",),
    ".docx": (ZIP_SIGNATURE,),
    ".pptx": (ZIP_SIGNATURE,),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
}


def validate_material_file(uploaded_file):
    extension = Path(uploaded_file.name).suffix.lower()
    if extension not in ALLOWED_FILE_TYPES:
        raise serializers.ValidationError(
            "Ruxsat etilmagan fayl turi. Mumkin: PDF, DOCX, PPTX, PNG, JPG."
        )
    if uploaded_file.size > MAX_FILE_SIZE:
        raise serializers.ValidationError("Fayl hajmi 20 MB dan oshmasligi kerak.")
    if uploaded_file.size == 0:
        raise serializers.ValidationError("Fayl bo'sh.")

    header = uploaded_file.read(8)
    uploaded_file.seek(0)
    if not any(header.startswith(signature) for signature in ALLOWED_FILE_TYPES[extension]):
        raise serializers.ValidationError("Fayl tarkibi uning turiga mos emas.")
    return uploaded_file

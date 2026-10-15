# Ma'lumotlar bazasini loyihalash: kirish va chiqish testi

Test ma'lumotlar bazasini loyihalash bo'yicha bilimingizni o'lchaydi: ER-model, kalitlar, bog'lanishlar, normallashtirish va cheklovlar. Bilmagan savolingizni taxmin qilmasdan o'tkazib yuborishingiz mumkin. Natija bahoga ta'sir qilmaydi.

Savollar soni: 20. Har bir savol 1 ball.

Bir nechta to'g'ri javobli savollarda ball qisman beriladi: (to'g'ri belgilanganlar − noto'g'ri belgilanganlar) / to'g'ri variantlar soni, manfiy bo'lmaydi. Talabaga variantlar aralashtirilgan tartibda ko'rsatiladi.

## 1. Ma'lumotlar bazasini loyihalashda konseptual model nimani tasvirlaydi?

*Mavzu: Konseptual model · bitta to'g'ri javob*

A) SQL so'rovlarining bajarilish rejasini
B) Predmet sohasidagi obyektlar, ularning atributlari va bog'lanishlarini, aniq MBBTga bog'lanmagan holda
C) Ma'lumotlar diskda qanday saqlanishini
D) Jadvallar, ustunlarning ma'lumot turlari va indekslarni

## 2. ER-diagrammada «obyekt» (entity) nimani anglatadi?

*Mavzu: Konseptual model · bitta to'g'ri javob*

A) Jadvaldagi bitta ustunni
B) Ikki jadval orasidagi bog'lanishni
C) SQL buyrug'ini
D) Ma'lumoti saqlanadigan real yoki mavhum narsani (masalan, Talaba, Kitob)

## 3. Asosiy kalit (PRIMARY KEY) qanday talabga javob berishi kerak?

*Mavzu: Kalitlar · bitta to'g'ri javob*

A) Har doim jadvalning birinchi ustuni bo'ladi
B) Qiymatlari takrorlanmaydi va bo'sh (NULL) bo'lmaydi
C) Faqat matn turidagi ustun bo'ladi
D) Qiymatlari takrorlanishi mumkin, lekin bo'sh bo'lmaydi

## 4. Tashqi kalit (FOREIGN KEY) nima uchun ishlatiladi?

*Mavzu: Kalitlar · bitta to'g'ri javob*

A) Qidiruvni tezlashtirish uchun
B) Jadvaldagi qiymat boshqa jadvaldagi mavjud qatorga ishora qilishini ta'minlash uchun
C) Maxfiy ma'lumotlarni shifrlash uchun
D) Jadvaldagi qatorlarni tartiblash uchun

## 5. «Talaba» obyekti uchun qaysi atributlar asosiy kalit bo'la oladi (har biri har bir talabada yagona va doim mavjud)?

*Mavzu: Kalitlar · bir nechta to'g'ri javob*

A) Talaba ID raqami
B) Pasport seriyasi va raqami
C) Tug'ilgan sana
D) Ism

## 6. PostgreSQL'da UNIQUE cheklovi PRIMARY KEY dan nimasi bilan farq qiladi?

*Mavzu: Kalitlar · bitta to'g'ri javob*

A) PRIMARY KEY qiymatlari takrorlanishi mumkin, UNIQUE niki esa yo'q
B) UNIQUE faqat son turidagi ustunlarga qo'yiladi
C) Hech qanday farqi yo'q
D) UNIQUE ustunda bo'sh (NULL) qiymat bo'lishi mumkin va jadvalda bir nechta UNIQUE bo'la oladi; PRIMARY KEY esa bitta va NULL bo'lmaydi

## 7. «Har bir talaba bitta guruhda o'qiydi, bitta guruhda esa ko'p talaba bor.» Guruh va Talaba orasidagi bog'lanish turi qanday?

*Mavzu: Bog'lanishlar · bitta to'g'ri javob*

A) Bog'lanish yo'q
B) 1:1
C) 1:N (bir guruh — ko'p talaba)
D) M:N

## 8. 1:N bog'lanish relyatsion bazada qanday ifodalanadi?

*Mavzu: Bog'lanishlar · bitta to'g'ri javob*

A) «Ko'p» tomondagi jadvalga «bir» tomondagi jadvalning kalitiga ishora qiluvchi tashqi kalit qo'shiladi
B) Ikkala jadval bitta jadvalga birlashtiriladi
C) Faqat bog'lanish nomi yoziladi, kalit kerak emas
D) «Bir» tomondagi jadvalga «ko'p» tomondagi jadvalning kaliti qo'shiladi

## 9. «Talaba bir nechta fanni o'qiydi, bitta fanni esa ko'p talaba o'qiydi.» Bu bog'lanish relyatsion bazada qanday amalga oshiriladi?

*Mavzu: Bog'lanishlar · bitta to'g'ri javob*

A) Talaba va Fan kalitlarini saqlaydigan alohida oraliq jadval yaratiladi
B) Talaba jadvaliga fan_id ustuni qo'shiladi
C) Fan jadvaliga talaba_id ustuni qo'shiladi
D) Talaba va Fan bitta jadvalga birlashtiriladi

## 10. M:N bog'lanish uchun yaratilgan oraliq jadvalning asosiy kaliti odatda nima bo'ladi?

*Mavzu: Bog'lanishlar · bitta to'g'ri javob*

A) Bog'lanish nomi yozilgan matnli ustun
B) Oraliq jadvalga asosiy kalit kerak emas
C) Birinchi jadvalning asosiy kaliti
D) Ikki tashqi kalitdan iborat tarkibli kalit

## 11. «Har bir bo'limni aynan bitta mudir boshqaradi, bitta xodim esa faqat bitta bo'limni boshqara oladi.» Bo'lim va Mudir orasidagi bog'lanish turi qanday?

*Mavzu: Bog'lanishlar · bitta to'g'ri javob*

A) 1:1
B) 1:N
C) M:N
D) N:1

## 12. Normallashtirishning asosiy maqsadi nima?

*Mavzu: Normallashtirish · bitta to'g'ri javob*

A) Ma'lumotlar takrorlanishini va o'zgartirishdagi anomaliyalarni kamaytirish
B) Jadvallar sonini imkon qadar kamaytirish
C) Har qanday so'rovni tezlashtirish
D) Barcha ustunlarni bir xil ma'lumot turiga keltirish

## 13. Birinchi normal shakl (1NF) ning talabi qaysi?

*Mavzu: Normallashtirish · bitta to'g'ri javob*

A) Kalit bo'lmagan atributlar bir-biriga bog'liq bo'lmasligi
B) Har bir katakda faqat bitta, bo'linmas qiymat bo'lishi
C) Har bir jadvalda tashqi kalit bo'lishi
D) Har bir jadvalda kamida uchta ustun bo'lishi

## 14. Jadval: talaba(id, ism, telefonlar). «telefonlar» ustunida bir nechta raqam vergul bilan yozilgan. Qaysi normal shakl buzilgan?

*Mavzu: Normallashtirish · bitta to'g'ri javob*

A) 2NF
B) Hech biri buzilmagan
C) 3NF
D) 1NF

## 15. Jadval: buyurtma_tarkibi(buyurtma_id, mahsulot_kodi, mahsulot_nomi, soni), kaliti — (buyurtma_id, mahsulot_kodi). mahsulot_nomi faqat mahsulot_kodi ga bog'liq. Qaysi normal shakl buzilgan?

*Mavzu: Normallashtirish · bitta to'g'ri javob*

A) Hech biri buzilmagan
B) Faqat 3NF
C) 2NF (kalitning bir qismiga bog'liqlik)
D) 1NF

## 16. Jadval: talaba(id, ism, guruh_id, guruh_nomi), kaliti — id. guruh_nomi guruh_id ga bog'liq. Bu qanday bog'liqlik va qaysi normal shaklni buzadi?

*Mavzu: Normallashtirish · bitta to'g'ri javob*

A) Tranzitiv bog'liqlik, 3NF ni buzadi
B) Hech qanday normal shakl buzilmagan
C) Qisman bog'liqlik, 2NF ni buzadi
D) Ko'p qiymatli atribut, 1NF ni buzadi

## 17. Normallashtirilmagan jadvalda mijoz telefonini o'zgartirish uchun bir nechta qatorni yangilash kerak, bittasi esa e'tibordan chetda qoldi. Bu qanday anomaliya?

*Mavzu: Normallashtirish · bitta to'g'ri javob*

A) Yangilash (o'zgartirish) anomaliyasi
B) O'chirish anomaliyasi
C) Qo'shish anomaliyasi
D) Bu anomaliya emas

## 18. Qaysi holatlarda ma'lumotni alohida jadvalga (obyektga) ajratish kerak?

*Mavzu: Normallashtirish · bir nechta to'g'ri javob*

A) Jadvalda beshtadan ortiq ustun bo'lsa
B) Ustun nomi uzun bo'lsa
C) Atribut bir nechta qiymatga ega bo'lsa (masalan, talabaning bir nechta telefoni)
D) Bir xil ma'lumot ko'p qatorlarda takrorlansa (masalan, har bir buyurtmada mijoz ismi)

## 19. Qaysilari ma'lumotlar yaxlitligini ta'minlovchi cheklovlar (constraint)?

*Mavzu: Cheklovlar · bir nechta to'g'ri javob*

A) FOREIGN KEY
B) ORDER BY
C) CHECK
D) GROUP BY
E) PRIMARY KEY

## 20. «Mahsulot narxi manfiy bo'lmasligi kerak» qoidasini bazaning o'zida qaysi cheklov ta'minlaydi?

*Mavzu: Cheklovlar · bitta to'g'ri javob*

A) PRIMARY KEY (narx)
B) CHECK (narx >= 0)
C) DEFAULT 0
D) UNIQUE (narx)

## Javoblar kaliti

| № | Mavzu | To'g'ri javob |
|---|---|---|
| 1 | Konseptual model | B |
| 2 | Konseptual model | D |
| 3 | Kalitlar | B |
| 4 | Kalitlar | B |
| 5 | Kalitlar | A, B |
| 6 | Kalitlar | D |
| 7 | Bog'lanishlar | C |
| 8 | Bog'lanishlar | A |
| 9 | Bog'lanishlar | A |
| 10 | Bog'lanishlar | D |
| 11 | Bog'lanishlar | A |
| 12 | Normallashtirish | A |
| 13 | Normallashtirish | B |
| 14 | Normallashtirish | D |
| 15 | Normallashtirish | C |
| 16 | Normallashtirish | A |
| 17 | Normallashtirish | A |
| 18 | Normallashtirish | C, D |
| 19 | Cheklovlar | A, C, E |
| 20 | Cheklovlar | B |

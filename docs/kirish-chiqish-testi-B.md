# Ma'lumotlar bazasini loyihalash: kirish va chiqish testi (B variant)

Test ma'lumotlar bazasini loyihalash bo'yicha bilimingizni o'lchaydi: ER-model, kalitlar, bog'lanishlar, normallashtirish va cheklovlar. Bilmagan savolingizni taxmin qilmasdan o'tkazib yuborishingiz mumkin. Natija bahoga ta'sir qilmaydi.

Savollar soni: 20. Har bir savol 1 ball.

Bir nechta to'g'ri javobli savollarda ball qisman beriladi: (to'g'ri belgilanganlar − noto'g'ri belgilanganlar) / to'g'ri variantlar soni, manfiy bo'lmaydi. Talabaga variantlar aralashtirilgan tartibda ko'rsatiladi.

## 1. Konseptual modelni mantiqiy (relyatsion) modeldan nima farqlaydi?

*Mavzu: Konseptual model · bitta to'g'ri javob*

A) Konseptual modelda indekslar va fayl guruhlari belgilanadi
B) Konseptual model predmet sohasini obyektlar va bog'lanishlar orqali tasvirlaydi, jadval va ustun turlari esa unda bo'lmaydi
C) Konseptual model faqat PostgreSQL uchun tuziladi
D) Konseptual modelda har bir ustunning ma'lumot turi va uzunligi ko'rsatiladi

## 2. ER-diagrammada «atribut» nimani anglatadi?

*Mavzu: Konseptual model · bitta to'g'ri javob*

A) Ikki obyekt orasidagi bog'lanish turini
B) Jadvaldagi bitta qatorni
C) Bazaga ulanish uchun foydalanuvchi nomini
D) Obyektning saqlanadigan xususiyatini (masalan, Kitobning nomi, Talabaning tug'ilgan sanasi)

## 3. Tarkibli (composite) asosiy kalit nima?

*Mavzu: Kalitlar · bitta to'g'ri javob*

A) Boshqa jadvalga ishora qiluvchi ustun
B) Ikki yoki undan ko'p ustundan iborat kalit: qatorni ustunlar qiymatlari birgalikda yagona aniqlaydi
C) Matn va son ustunlaridan avtomatik yaratiladigan indeks
D) Har bir ustuni alohida takrorlanmaydigan kalit

## 4. Tashqi kalit (FOREIGN KEY) cheklovi qaysi xatoning oldini oladi?

*Mavzu: Kalitlar · bitta to'g'ri javob*

A) Jadvalga juda ko'p qator qo'shilishining
B) Boshqa jadvalda mavjud bo'lmagan qatorga ishora qiluvchi qiymat kiritilishining (masalan, yo'q kitob uchun ijara yozuvi)
C) Ustunga noto'g'ri ma'lumot turi yozilishining
D) Bir ustunga bir xil qiymat ikki marta yozilishining

## 5. «Avtomobil» obyekti uchun qaysi atributlar asosiy kalit bo'la oladi (har biri har bir avtomobilda yagona va doim mavjud)?

*Mavzu: Kalitlar · bir nechta to'g'ri javob*

A) VIN (kuzov raqami)
B) Ichki ro'yxat raqami (avtomobil_id)
C) Ishlab chiqarilgan yili
D) Rangi

## 6. Jadvalda bir nechta nomzod kalit bo'lsa, ulardan biri asosiy kalit qilib tanlanadi. Qolganlari bilan nima qilish to'g'ri?

*Mavzu: Kalitlar · bitta to'g'ri javob*

A) Hech narsa qilmaslik: yagonaligi o'z-o'zidan saqlanadi
B) Ularga ham PRIMARY KEY qo'yish
C) Ularni jadvaldan olib tashlash
D) Ularga UNIQUE (va kerak bo'lsa NOT NULL) cheklovini qo'yish, shunda ham ular takrorlanmaydi

## 7. «Har bir buyurtmani bitta mijoz beradi, bitta mijoz esa ko'p buyurtma bera oladi.» Mijoz va Buyurtma orasidagi bog'lanish turi qanday?

*Mavzu: Bog'lanishlar · bitta to'g'ri javob*

A) Bog'lanish yo'q
B) 1:1
C) 1:N (bir mijoz — ko'p buyurtma)
D) M:N

## 8. Muallif va Kitob orasida 1:N bog'lanish bor (bitta kitobni bitta muallif yozgan). Tashqi kalit qaysi jadvalga qo'yiladi?

*Mavzu: Bog'lanishlar · bitta to'g'ri javob*

A) Kitob jadvaliga: muallif_id ustuni Muallif jadvalining kalitiga ishora qiladi
B) Ikkala jadvalga ham bir-biriga ishora qiluvchi ustunlar
C) Alohida oraliq jadvalga
D) Muallif jadvaliga: kitob_id ustuni

## 9. «Shifokor ko'p bemorni qabul qiladi, bemor esa bir nechta shifokorga borishi mumkin.» Bu bog'lanish relyatsion bazada qanday amalga oshiriladi?

*Mavzu: Bog'lanishlar · bitta to'g'ri javob*

A) Shifokor va Bemor kalitlarini saqlaydigan alohida oraliq jadval (masalan, qabul) yaratiladi
B) Bemor jadvaliga shifokor_id ustuni qo'shiladi
C) Shifokor jadvaliga bemor_id ustuni qo'shiladi
D) Shifokor va Bemor bitta jadvalga birlashtiriladi

## 10. Talaba va Kurs orasidagi M:N bog'lanish uchun yozilish(talaba_id, kurs_id) oraliq jadvali tuzildi. Uning asosiy kaliti odatda qaysi?

*Mavzu: Bog'lanishlar · bitta to'g'ri javob*

A) Kurs nomi yozilgan matnli ustun
B) Oraliq jadvalga asosiy kalit kerak emas
C) Faqat talaba_id
D) (talaba_id, kurs_id) tarkibli kaliti

## 11. «Har bir fuqaroning bittadan pasporti bor, har bir pasport aynan bitta fuqaroga tegishli.» Fuqaro va Pasport orasidagi bog'lanish turi qanday?

*Mavzu: Bog'lanishlar · bitta to'g'ri javob*

A) 1:1
B) 1:N
C) M:N
D) N:1

## 12. Normallashtirish qaysi muammoni hal qiladi?

*Mavzu: Normallashtirish · bitta to'g'ri javob*

A) Bir xil faktning bir necha joyda saqlanishi va shu sababli qo'shish, o'zgartirish, o'chirishdagi anomaliyalarni
B) Diskdagi bo'sh joy yetishmasligini
C) So'rovlarning sekin ishlashini
D) Parollarning ochiq saqlanishini

## 13. Ikkinchi normal shakl (2NF) ning talabi qaysi?

*Mavzu: Normallashtirish · bitta to'g'ri javob*

A) Jadvalda tashqi kalit bo'lmasligi
B) Jadval 1NF da va kalit bo'lmagan har bir atribut butun kalitga to'liq bog'liq (kalitning bir qismiga emas)
C) Har bir jadvalda kamida ikkita kalit bo'lishi
D) Barcha ustunlar matn turida bo'lishi

## 14. Jadval: kitob(id, nom, mualliflar). «mualliflar» ustunida bir nechta ism nuqtali vergul bilan yozilgan. Qaysi normal shakl buzilgan?

*Mavzu: Normallashtirish · bitta to'g'ri javob*

A) 2NF
B) Hech biri buzilmagan
C) 3NF
D) 1NF

## 15. Jadval: baho(talaba_id, fan_id, fan_nomi, ball), kaliti — (talaba_id, fan_id). fan_nomi faqat fan_id ga bog'liq. Qaysi normal shakl buzilgan?

*Mavzu: Normallashtirish · bitta to'g'ri javob*

A) Hech biri buzilmagan
B) Faqat 3NF
C) 2NF (kalitning bir qismiga bog'liqlik)
D) 1NF

## 16. Jadval: xodim(id, ism, bolim_id, bolim_telefoni), kaliti — id. bolim_telefoni bolim_id ga bog'liq. Bu qanday bog'liqlik va qaysi normal shaklni buzadi?

*Mavzu: Normallashtirish · bitta to'g'ri javob*

A) Tranzitiv bog'liqlik, 3NF ni buzadi
B) Hech qanday normal shakl buzilmagan
C) Qisman bog'liqlik, 2NF ni buzadi
D) Ko'p qiymatli atribut, 1NF ni buzadi

## 17. Normallashtirilmagan jadvalda kurs haqidagi ma'lumot faqat unga yozilgan talabalar qatorlarida saqlanadi. Oxirgi talaba o'chirilganda kurs haqidagi ma'lumot ham yo'qoldi. Bu qanday anomaliya?

*Mavzu: Normallashtirish · bitta to'g'ri javob*

A) O'chirish anomaliyasi
B) Yangilash (o'zgartirish) anomaliyasi
C) Qo'shish anomaliyasi
D) Bu anomaliya emas

## 18. Qaysi belgilar jadval normallashtirilmaganini ko'rsatadi?

*Mavzu: Normallashtirish · bir nechta to'g'ri javob*

A) Jadvalda sana turidagi ustun bor
B) Jadval nomi ko'plikda yozilgan
C) Bitta katakda ro'yxat saqlanadi (masalan, «Toshkent; Samarqand; Buxoro»)
D) Kalit bo'lmagan ustun qiymati boshqa kalit bo'lmagan ustundan aniqlanadi va qatorlarda takrorlanadi

## 19. Qaysilari ustun yoki jadval darajasidagi cheklovlar (constraint)?

*Mavzu: Cheklovlar · bir nechta to'g'ri javob*

A) UNIQUE
B) SELECT
C) CHECK
D) HAVING
E) NOT NULL

## 20. «Talabaning yoshi 16 dan kichik bo'lmasligi kerak» qoidasini bazaning o'zida qaysi cheklov ta'minlaydi?

*Mavzu: Cheklovlar · bitta to'g'ri javob*

A) NOT NULL (yosh)
B) CHECK (yosh >= 16)
C) DEFAULT 16
D) UNIQUE (yosh)

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

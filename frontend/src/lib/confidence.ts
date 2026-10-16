import { useState } from 'react'

/** Ishonch shkalasi: 1 — umuman ishonmayman, 5 — to'liq ishonaman */
export const CONFIDENCE_LEVELS = [1, 2, 3, 4, 5] as const

/** Natijadan keyingi refleksiv izoh: ishonch natijaga mos kelmaganda o'ylab ko'rishga undaydi */
export function confidenceNote(confidence: number | null, correct: boolean): string | null {
  if (confidence === null) return null
  if (confidence >= 4 && !correct) {
    return "Javobingizga ishongan edingiz, lekin xato bor: qaysi taxminingiz noto'g'ri bo'lganini o'ylab ko'ring."
  }
  if (confidence <= 2 && correct) {
    return "To'g'ri! Siz ishonmagan edingiz: nimaga shubhalanganingizni o'ylab ko'ring — bilimingiz o'zingiz o'ylagandan mustahkamroq."
  }
  if (confidence >= 4 && correct) return "To'g'ri, va siz buni oldindan to'g'ri baholadingiz."
  if (confidence <= 2 && !correct) return "Shubhangiz o'rinli edi: xatoni toping va qayta tekshiring."
  return null
}

/**
 * Talaba tekshirishdan oldin belgilaydigan ishonch (ixtiyoriy). Har bir tekshiruvdan keyin tozalanadi: keyingi
 * safar ham o'z javobini ongli baholashi uchun. Server uni natija bilan solishtirib, kalibrlashni hisoblaydi.
 */
export function useConfidence() {
  const [value, setValue] = useState<number | null>(null)
  const [note, setNote] = useState<string | null>(null)
  return {
    value,
    setValue,
    note,
    /** So'rov tanasiga qo'shiladigan qism */
    body: (confidence: number | null) => (confidence === null ? {} : { confidence }),
    /** Natija kelgach: izoh chiqariladi, tanlov tozalanadi */
    record(confidence: number | null, correct: boolean) {
      setNote(confidenceNote(confidence, correct))
      setValue(null)
    },
  }
}

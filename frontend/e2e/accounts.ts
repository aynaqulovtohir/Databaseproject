// Test hisoblari: backend/users/management/commands/seed_e2e.py dagi bilan bir xil.
// Ular faqat alohida e2e bazasida mavjud.
export const PASSWORD = 'e2e-Parol-2026'

export const ACCOUNTS = {
  admin: { username: 'e2e_admin', name: 'Admin Sinov' },
  teacher: { username: 'e2e_teacher', name: "O'qituvchi Sinov" },
  student: { username: 'e2e_student', name: 'Talaba Sinov' },
  // Tadqiqotga rozilik haqida hali qaror bermagan talaba
  newcomer: { username: 'e2e_newcomer', name: 'Yangi Talaba' },
} as const

export type SavedRole = 'admin' | 'teacher' | 'student'

export const storageState = (role: SavedRole) => `e2e/.auth/${role}.json`

export const QUIZ_TITLE = 'E2E: normallashtirish'

export const ER_LAB_TITLE = 'E2E: ER-diagramma'
export const INTEGRITY_LAB_TITLE = 'Cheklovlar 1. Kutubxona: NOT NULL, UNIQUE va CHECK'
export const REVERSE_LAB_TITLE = 'Teskari loyihalash 1. Kafedra bazasi'
export const EVOLUTION_LAB_TITLE = "Migratsiya 1. Do'kon: to'liq ismni ism va familiyaga ajratish"
export const EXAM_LAB_TITLE = 'E2E: imtihon laboratoriyasi'

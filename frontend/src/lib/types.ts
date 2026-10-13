// Backend API qaytaradigan ma'lumot turlari

export type Role = 'admin' | 'teacher' | 'student'

export interface GroupShort {
  id: number
  name: string
}

export interface Me {
  id: number
  username: string
  first_name: string
  last_name: string
  role: Role
  group: GroupShort | null
  teaching_groups: GroupShort[]
}

export interface TelegramStatus {
  configured: boolean
  linked: boolean
  linked_at: string | null
}

export interface TelegramLink {
  url: string
  expires_at: string
}

export const ROLE_LABELS: Record<Role, string> = {
  admin: 'Admin',
  teacher: "O'qituvchi",
  student: 'Talaba',
}

export interface PersonShort {
  id: number
  first_name: string
  last_name: string
}

/** Admin ko'radigan foydalanuvchi (guruhlar id ko'rinishida keladi) */
export interface AdminUser {
  id: number
  username: string
  first_name: string
  last_name: string
  role: Role
  group: number | null
  teaching_groups: number[]
  is_active: boolean
}

export interface Group {
  id: number
  name: string
  teachers: number[]
  student_count: number
  created_at: string
}

export interface MaterialFile {
  id: number
  original_name: string
  size: number
  uploaded_at: string
}

export interface Material {
  id: number
  title: string
  text: string
  author: PersonShort
  /** Talabaga yuborilmaydi */
  groups?: number[]
  files: MaterialFile[]
  created_at: string
}

export interface Assignment {
  id: number
  title: string
  description: string
  /** Talabaga yuborilmaydi */
  grading_criteria?: string
  author: PersonShort
  /** Talabaga yuborilmaydi */
  groups?: number[]
  deadline: string
  created_at: string
  /** Faqat talabaga keladi: o'zining oxirgi urinishi (topshirmagan bo'lsa null) */
  my_submission?: MySubmission | null
}

export type SubmissionStatus = 'submitted' | 'graded' | 'returned'

export interface MySubmission {
  id: number
  status: SubmissionStatus
  is_late: boolean
  attempt_number: number
  /** Faqat baholangan holatda */
  score: number | null
}

/** Topshiriq bo'yicha hali yechim topshirmagan talaba */
export interface MissingStudent extends PersonShort {
  group: string
}

export interface Grade {
  score: number
  comment: string
  graded_at: string
  updated_at: string
  /** Faqat admin va o'qituvchiga keladi */
  ai_suggested_score?: number | null
  graded_by?: PersonShort | null
}

export interface Submission {
  id: number
  assignment: number
  student: PersonShort
  sql_code: string
  attempt_number: number
  is_late: boolean
  status: SubmissionStatus
  grade: Grade | null
  return_comment: string
  submitted_at: string
}

export type AnalysisStatus = 'pending' | 'processing' | 'done' | 'failed'

export interface AnalysisIssue {
  title: string
  explanation: string
  severity: 'low' | 'medium' | 'high'
}

export interface Analysis {
  status: AnalysisStatus
  summary: string
  issues: AnalysisIssue[]
  recommendations: string[]
  completed_at: string | null
  /** Quyidagilar faqat admin va o'qituvchiga keladi */
  suggested_score?: number | null
  score_rationale?: string
  error_message?: string
  model_name?: string
}

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface ChatState {
  messages: ChatMessage[]
  daily_limit: number
  used_today: number
}

export interface ChatReply {
  question: ChatMessage
  answer: ChatMessage
  daily_limit: number
  used_today: number
}

export const MAX_SCORE = 100

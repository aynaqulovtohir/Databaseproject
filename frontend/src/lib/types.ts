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
  /** Talabaga AI yordamchisi ko'rsatiladimi (tajribada nazorat guruhida o'chiriladi) */
  ai_enabled: boolean
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
  /** Tajriba: false bo'lsa, guruh talabalariga AI yordamchisi ko'rsatilmaydi */
  ai_enabled: boolean
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

/** Laboratoriya bahosi: AI yoki (AI ishlamasa) avtomatik tekshiruv qo'yadi */
export interface LabGrade {
  score: number
  comment: string
  source: 'ai' | 'auto'
  graded_at: string
}

export const GRADE_SOURCE_LABELS: Record<LabGrade['source'], string> = {
  ai: 'AI bahosi',
  auto: 'Avtomatik baho',
}

/** ER-diagramma: obyektlar (atributlari bilan) va bog'lanishlar. Kardinallik har bir uchida "1" yoki "N". */
export type ErKey = 'pk' | 'fk' | ''
export type ErCardinality = '1' | 'N'
/** Tuzatilgan diagrammada: o'zgarmagan, qo'shilgan, olib tashlangan yoki o'zgartirilgan */
export type ErStatus = 'ok' | 'added' | 'removed' | 'changed'

export interface ErAttribute {
  name: string
  key: ErKey
  status?: ErStatus
}

export interface ErEntity {
  id: string
  name: string
  x: number
  y: number
  attributes: ErAttribute[]
  status?: ErStatus
}

export interface ErRelationship {
  id: string
  name: string
  source: string
  target: string
  source_card: ErCardinality
  target_card: ErCardinality
  status?: ErStatus
}

export interface ErDiagram {
  entities: ErEntity[]
  relationships: ErRelationship[]
}

/** Baholashga topshirilgan noto'g'ri diagrammaning tuzatilgan varianti */
export interface ErFix {
  diagram: ErDiagram & { changes: string[] }
  /** AI tushuntirishi (AI ishlamasa bo'sh) */
  explanation: string
}

export type LabKind = 'sql' | 'er'

/** Talabaning laboratoriyadagi holati */
export interface LabProgress {
  attempts: number
  solved: boolean
  /** Eng yuqori baho; hali baholashga topshirmagan bo'lsa null */
  grade?: LabGrade | null
  /** Faqat bitta laboratoriya ochilganda keladi */
  last_code?: string
  /** ER laboratoriyasida: oxirgi chizilgan diagramma va oxirgi topshirishning tuzatilgan varianti */
  last_diagram?: ErDiagram | null
  last_fix?: ErFix | null
}

export interface Lab {
  id: number
  kind: LabKind
  title: string
  description: string
  /** Har bir ishga tushirishdan oldin bajariladigan tayyor jadvallar */
  setup_sql: string
  /** Talabaga yuborilmaydi */
  solution_sql?: string
  /** ER laboratoriyasining namunaviy diagrammasi. Talabaga yuborilmaydi */
  reference_diagram?: ErDiagram | null
  author: PersonShort
  /** Talabaga yuborilmaydi */
  groups?: number[]
  created_at: string
  /** Faqat talabaga keladi */
  my_progress?: LabProgress
}

export interface LabRunError {
  message: string
  /** PostgreSQL xato kodi (SQLSTATE) */
  sqlstate: string
  detail: string
  hint: string
  line: number | null
  /** Xatoning o'zbekcha tushuntirishi (bo'sh bo'lishi mumkin) */
  tip: string
}

export interface LabRunTable {
  columns: string[]
  rows: (string | null)[][]
  row_count: number
  truncated: boolean
}

export interface LabRunResult {
  is_correct: boolean
  error: LabRunError | null
  result: LabRunTable | null
  status_message: string
  /** Namunaviy yechimdan farqlar */
  differences: string[]
  checked_against_solution: boolean
  /** Faqat talabada: saqlangan urinish id'si */
  attempt_id: number | null
  ai_available: boolean
  /** Faqat baholashga topshirilganda: shu topshirishning bahosi va eng yuqori baho */
  grade?: LabGrade
  best_grade?: LabGrade
  /** ER laboratoriyasi, baholashga topshirilganda: noto'g'ri bo'lsa tuzatilgan diagramma, aks holda null */
  fix?: ErFix | null
}

/** O'qituvchi ko'radigan talaba holati */
export interface LabStudentProgress extends PersonShort {
  group: string
  attempts: number
  solved: boolean
  last_attempt_at: string | null
  code: string
  diagram: ErDiagram | null
  grade: LabGrade | null
}

export interface SimilarWork extends PersonShort {
  group: string
  solved: boolean
  code: string
  diagram: ErDiagram | null
}

/** Yechimlari shubhali darajada o'xshash ikki talaba */
export interface SimilarPair {
  students: [SimilarWork, SimilarWork]
  /** Talabalarning o'z tanlovlari (namunada yo'q bo'laklar) bo'yicha o'xshashlik, 0-1 */
  score: number
  shared: number
  /** Ikkalasida bir xil bo'lgan noodatiy xato urinishlar soni */
  shared_wrong: number
  /** Birinchi to'g'ri yechimlari orasidagi vaqt (daqiqa) */
  gap_minutes: number | null
}

export interface SimilarityReport {
  compared: number
  threshold: number
  pairs: SimilarPair[]
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

// ---------- Testlar ----------

export type QuizKind = 'pre' | 'post' | 'practice' | 'survey'

export const QUIZ_KIND_LABELS: Record<QuizKind, string> = {
  pre: 'Kirish testi',
  post: 'Chiqish testi',
  practice: 'Oddiy test',
  survey: "So'rovnoma",
}

/** likert — so'rovnoma fikri: 1-5 shkala, ball qo'yilmaydi, variantlar serverda qo'shiladi */
export type QuestionKind = 'single' | 'multiple' | 'likert'

export interface QuizChoice {
  id?: number
  text: string
  is_correct: boolean
}

export interface QuizQuestion {
  id?: number
  text: string
  kind: QuestionKind
  points: number
  choices: QuizChoice[]
}

export type QuizAttemptStatus = 'not_started' | 'in_progress' | 'submitted'

export interface MyQuizAttempt {
  status: QuizAttemptStatus
  score?: number
  max_score?: number
  percent?: number
  submitted_at?: string
  /** Faqat boshlangan testda: javoblar qabul qilinadigan oxirgi vaqt */
  deadline?: string | null
}

export interface Quiz {
  id: number
  kind: QuizKind
  title: string
  description: string
  opens_at: string | null
  closes_at: string | null
  time_limit_minutes: number | null
  author: PersonShort
  created_at: string
  question_count: number
  /** Faqat admin va o'qituvchiga */
  show_answers?: boolean
  groups?: number[]
  questions?: QuizQuestion[]
  attempt_count?: number
  /** Faqat talabaga */
  is_open?: boolean
  my_attempt?: MyQuizAttempt
}

/** Talaba testni yechayotganda: to'g'ri javoblarsiz savollar */
export interface QuizTaking {
  questions: { id: number; text: string; kind: QuestionKind; points: number; choices: { id: number; text: string }[] }[]
  /** {"savol_id": [variant id'lari]} */
  answers: Record<string, number[]>
  started_at: string
  deadline: string | null
  server_now: string
}

export interface QuizResult {
  score: number
  max_score: number
  percent: number
  submitted_at: string
  /** O'qituvchi to'g'ri javoblarni ko'rsatishga ruxsat bergan bo'lsa */
  questions:
    | {
        id: number
        text: string
        kind: QuestionKind
        points: number
        earned: number
        choices: { id: number; text: string; is_correct: boolean; selected: boolean }[]
      }[]
    | null
}

export interface SurveySegment {
  count: number
  mean: number | null
  /** 1 dan 5 gacha har bir qiymatni tanlaganlar soni (yashirilgan bo'lsa null) */
  distribution: number[] | null
  /** Javoblar kam: alohida talabaning javobi ochilib qolmasligi uchun natija yashirilgan */
  hidden: boolean
}

export interface SurveySummary {
  respondents: number
  min_responses: number
  scale: string[]
  questions: { id: number; order: number; text: string; all: SurveySegment; ai: SurveySegment; control: SurveySegment }[]
}

export interface QuizStudentResult extends PersonShort {
  group: string
  status: QuizAttemptStatus
  score: number | null
  max_score: number | null
  percent: number | null
  started_at: string | null
  submitted_at: string | null
}

// ---------- Ko'r baholash ----------

/** O'qituvchiga talaba ismi va tizim bahosisiz ko'rsatiladigan ish */
export interface BlindReviewItem {
  attempt_id: number
  lab: Pick<Lab, 'id' | 'title' | 'kind' | 'description' | 'setup_sql' | 'solution_sql' | 'reference_diagram'>
  code: string
  diagram: ErDiagram | null
  is_correct: boolean
  check: { error: { message: string; tip?: string } | null; differences: string[] }
}

export interface BlindReviewQueue {
  item: BlindReviewItem | null
  remaining: number
  reviewed: number
}

export interface AgreementStats {
  count: number
  pearson_r?: number | null
  mean_abs_diff?: number
  /** Tizim − o'qituvchi: musbat bo'lsa tizim yumshoqroq */
  mean_diff?: number
  limits_of_agreement?: [number, number] | null
  within_10?: number
  band_agreement?: number
  weighted_kappa?: number | null
  system_mean?: number
  teacher_mean?: number
}

export interface Agreement {
  overall: AgreementStats
  by_source: Record<LabGrade['source'], AgreementStats>
  pairs: { lab_id: number; lab_kind: LabKind; system: number; teacher: number; source: LabGrade['source'] }[]
  bands: { min: number; mark: number }[]
}

// ---------- Statistika ----------

export interface StatisticsLab {
  id: number
  title: string
  kind: LabKind
  students: number
  started: number
  solved: number
  solved_rate: number | null
  attempts_to_solve: number | null
  average_grade: number | null
}

export interface StatisticsGroup {
  id: number
  name: string
  ai_enabled: boolean
  students: number
  solved_rate: number | null
  average_grade: number | null
  pre_test: number | null
  post_test: number | null
  pre_count: number
  post_count: number
  gain: number | null
}

export interface AiEffectBucket {
  pairs: number
  solved: number
  rate: number | null
}

export interface LearningCurveSegment {
  students: number
  solved: number
  /** Yechganlarning birinchi to'g'ri urinishgacha o'rtacha urinishlari */
  attempts_to_solve: number | null
  /** Birinchi urinishda yechganlar ulushi (%) */
  first_try_rate: number | null
}

export interface LearningCurvePoint {
  id: number
  position: number
  title: string
  kind: LabKind
  ai: LearningCurveSegment
  control: LearningCurveSegment
}

export interface Statistics {
  groups_available: GroupShort[]
  overview: { students: number; labs: number; attempts: number; solved_rate: number | null; average_grade: number | null }
  top_errors: { category: string; label: string; count: number }[]
  labs: StatisticsLab[]
  /** Laboratoriyalar talabalar bajargan tartibda */
  learning_curve: LearningCurvePoint[]
  ai_effect: { with_advice: AiEffectBucket; without_advice: AiEffectBucket }
  groups: StatisticsGroup[]
}

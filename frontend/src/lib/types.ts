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
  /** Talabadan tadqiqotga rozilik so'ralishi kerakmi */
  consent_needed: boolean
}

/** Ilmiy tadqiqotda ishtirok etishga rozilik */
export interface ConsentStatus {
  required: boolean
  version: string
  title: string
  /** Rozilik matni xatboshilari */
  text: string[]
  contact: string
  /** null — hali qaror berilmagan */
  agreed: boolean | null
  decided_at: string | null
  needs_decision: boolean
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

/** Baholash rubrikasi mezoni; stage — bosqich tartib raqami (bosqichsiz topshiriqda null) */
export interface RubricCriterion {
  name: string
  points: number
  description: string
  stage: number | null
}

export interface AssignmentStage {
  id: number
  /** 0 dan boshlab */
  order: number
  /** Talaba nima topshiradi: SQL kod yoki ER-diagramma */
  kind: 'sql' | 'er'
  title: string
  description: string
  deadline: string
}

export interface MyStageProgress {
  stage: number
  status: SubmissionStatus | null
  is_late: boolean
  score: number | null
  max_score: number | null
}

export interface Assignment {
  id: number
  title: string
  description: string
  /** Talabaga yuborilmaydi */
  grading_criteria?: string
  /** Baholash rubrikasi (talabaga ham ko'rinadi); bo'sh bo'lsa — oddiy 0–100 baho */
  rubric: RubricCriterion[]
  /** Bosqichli loyiha; bo'sh bo'lsa — bitta topshirish */
  stages: AssignmentStage[]
  author: PersonShort
  /** Talabaga yuborilmaydi */
  groups?: number[]
  deadline: string
  /** Faqat admin va o'qituvchiga: yechimlar kelganmi (rubrika tuzilishi qulflanadi) */
  has_submissions?: boolean
  created_at: string
  /** Faqat talabaga keladi: o'zining oxirgi urinishi (topshirmagan bo'lsa null) */
  my_submission?: MySubmission | null
  /** Faqat talabaga, bosqichli loyihada: har bir bosqich holati va jami ball */
  my_stages?: { items: MyStageProgress[]; total_score: number | null } | null
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

export interface RubricScore {
  name: string
  points: number
  score: number
}

export interface Grade {
  score: number
  /** Bosqich bahosida — bosqich mezonlari yig'indisi; aks holda 100 */
  max_score: number
  /** Rubrika bo'yicha baholanganda mezonlar ballari */
  rubric_scores: RubricScore[] | null
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
  /** Bosqichli loyihada bosqich id'si */
  stage: number | null
  /** ER-diagramma bosqichida bo'sh */
  sql_code: string
  /** ER-diagramma bosqichida chizilgan diagramma */
  diagram: ErDiagram | null
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

export type LabKind = 'sql' | 'er' | 'norm'

/** Normallashtirish topshirig'i: munosabat atributlari, funksional bog'liqliklar va maqsad normal forma */
export interface NormTask {
  attributes: string[]
  fds: { lhs: string[]; rhs: string[] }[]
  target: '3NF' | 'BCNF'
}

export type NormalForm = '1NF' | '2NF' | '3NF' | 'BCNF'

/** Talabaning normallashtirish javobi (matn ko'rinishida yuboriladi, backend tekshiradi) */
export interface NormAnswer {
  keys: string[] | string[][]
  normal_form: NormalForm
  decomposition: string[] | string[][]
}

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
  /** Normallashtirish laboratoriyasida: oxirgi javob */
  last_answer?: NormAnswer | null
}

export interface Lab {
  id: number
  kind: LabKind
  title: string
  description: string
  /** Nazariya va namuna: oddiy matn, kod ``` bilan ajratiladi */
  theory: string
  /** Har bir ishga tushirishdan oldin bajariladigan tayyor jadvallar */
  setup_sql: string
  /** Talaba muharririda dastlab turadigan kod (masalan, «AI yozgan xatoli kod — xatoni toping») */
  starter_sql?: string
  /** Talabaga yuborilmaydi */
  solution_sql?: string
  /** Yashirin test ma'lumotlari. Talabaga yuborilmaydi */
  hidden_setup_sql?: string
  /** ER laboratoriyasining namunaviy diagrammasi. Talabaga yuborilmaydi */
  reference_diagram?: ErDiagram | null
  /** Normallashtirish laboratoriyasi topshirig'i (talabaga ko'rinadi) */
  norm_task?: NormTask | null
  /** O'qituvchiga: algoritm hisoblagan javob. Talabaga yuborilmaydi */
  norm_reference?: { keys: string[][]; normal_form: NormalForm; decomposition: string[][] } | null
  /** SQL laboratoriyasida talabaga beriladigan ER-model (ER → SQL) */
  given_diagram?: ErDiagram | null
  /** Indeks laboratoriyasi: rejasi (EXPLAIN) tekshiriladigan so'rov */
  plan_query?: string
  /** Vergul bilan: rejada bo'lmasligi kerak bo'lgan tugunlar. Faqat admin va o'qituvchiga */
  plan_forbidden?: string
  /** Tranzaksiya laboratoriyasi: kod ikki sessiyada bir vaqtda tekshiriladi */
  concurrent?: boolean
  /** Yaxlitlik cheklovlari laboratoriyasi: barcha sinovlar. Faqat admin va o'qituvchiga */
  probes?: LabProbe[]
  /** Talaba uchun: ko'rinadigan sinovlar va yashirinlari soni */
  probe_info?: { visible: LabProbe[]; hidden: number } | null
  /** Sxemani rivojlantirish laboratoriyasi: migratsiyadan keyin bajariladigan ilovaning yangi so'rovlari */
  check_queries?: LabCheckQuery[]
  /** Talablarni aniqlash: yashirin talablar va buyurtmachi roli. Faqat admin va o'qituvchiga */
  requirements?: InterviewRequirement[]
  client_persona?: string
  /** Talaba uchun: talablarni aniqlash laboratoriyasi bo'lsa */
  interview?: LabInterviewInfo | null
  /** O'qituvchi tanlagan mavzu (bo'sh — avtomatik) va amaldagi mavzu */
  topic?: string
  effective_topic?: string
  author: PersonShort
  /** Talabaga yuborilmaydi */
  groups?: number[]
  created_at: string
  /** Faqat talabaga keladi */
  my_progress?: LabProgress
  /** Modul (id) — faqat admin va o'qituvchi yuboradi */
  module?: number | null
  module_detail: LabModuleShort | null
  /** Moduldagi o'rni (1 dan) */
  position: number
  /** O'qituvchi belgilagan murakkablik: 1 — eng sodda, 5 — eng murakkab */
  level: number | null
  /** Talaba uchun: oldingi laboratoriya yechilmaguncha yopiq */
  locked?: boolean
  blocked_by?: { id: number; title: string } | null
}

export interface LabModuleShort {
  id: number
  title: string
  description: string
  order: number
  /** Ichidagi laboratoriyalar oldingisi yechilgandan keyin ochiladi */
  sequential: boolean
  /** Imtihon rejimi (belgilanmagan bo'lsa null) */
  exam?: LabExamInfo | null
}

/** Imtihon: oldin — yopiq, paytida — AI'siz, keyin — faqat ko'rish */
export interface LabExamInfo {
  starts_at: string
  ends_at: string
  state: 'upcoming' | 'active' | 'finished'
}

export interface LabModule extends LabModuleShort {
  exam_starts_at: string | null
  exam_ends_at: string | null
  author: PersonShort
  labs: { id: number; title: string; kind: LabKind; level: number | null; position: number }[]
  created_at: string
}

/** Qiynalayotgan laboratoriya bo'yicha shaxsiy tavsiya */
export interface StudyAdvice {
  summary: string
  struggles: { title: string; explanation: string }[]
  steps: string[]
  review: string[]
  source: 'ai' | 'rules'
  attempts: number
  created_at: string
}

export interface StudyAdviceState {
  advice: StudyAdvice | null
  /** Tavsiya oxirgi urinishdan keyin tuzilgan */
  fresh: boolean
  wrong_attempts: number
  min_wrong: number
  can_request: boolean
  ai: boolean
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

export interface LabTryTableColumn {
  name: string
  type: string
  not_null: boolean
}

/** Erkin sinashdan keyingi jadval holati */
export interface LabTryTable {
  name: string
  columns: LabTryTableColumn[]
  constraints: string[]
  row_count: number
  rows_truncated: boolean
}

/** Tranzaksiya laboratoriyasi: ikki sessiyaning vaqt chizig'idagi bitta voqea */
export interface LabConcurrentStep {
  session: 'A' | 'B'
  sql: string
  /** ok — bajarildi; waiting — qulf kutmoqda; resumed — kutishdan keyin bajarildi; error — xato */
  status: 'ok' | 'waiting' | 'resumed' | 'error'
  columns: string[]
  rows: (string | null)[][]
  message: string
}

/** Erkin sinash natijasi: tekshirilmaydi va urinish sifatida saqlanmaydi */
export interface LabTryResult {
  error: LabRunError | null
  result: LabRunTable | null
  status_message: string
  tables: LabTryTable[]
  /** Indeks laboratoriyasida: so'rov rejasi qatorlari */
  plan: string[] | null
  /** Tranzaksiya laboratoriyasida: ikki sessiyaning vaqt chizig'i */
  steps?: LabConcurrentStep[]
}

export interface LabRunResult {
  is_correct: boolean
  error: LabRunError | null
  result: LabRunTable | null
  status_message: string
  /** Namunaviy yechimdan farqlar */
  differences: string[]
  checked_against_solution: boolean
  /** Indeks laboratoriyasida: so'rov rejasi qatorlari */
  plan?: string[] | null
  /** Tranzaksiya laboratoriyasida: ikki sessiyaning vaqt chizig'i */
  steps?: LabConcurrentStep[]
  /** Faqat talabada: saqlangan urinish id'si */
  attempt_id: number | null
  ai_available: boolean
  /** To'g'ri natijada: talaba yechimini tushuntirib, AI bahosini olishi mumkin */
  ai_explain?: boolean
  /** Faqat baholashga topshirilganda: shu topshirishning bahosi va eng yuqori baho */
  grade?: LabGrade
  best_grade?: LabGrade
  /** ER laboratoriyasi, baholashga topshirilganda: noto'g'ri bo'lsa tuzatilgan diagramma, aks holda null */
  fix?: ErFix | null
  /** Cheklovlar laboratoriyasi: ko'rinadigan sinovlar natijasi, yashirinlari soni va o'tganlar ulushi */
  probes?: LabProbeResult[]
  hidden_probes?: { total: number; passed: number } | null
  ratio?: number
  /** Migratsiya laboratoriyasi: har bir yangi so'rov natijasi */
  queries?: LabCheckQueryResult[]
}

export interface LabCheckQuery {
  id: string
  title: string
  sql: string
}

export interface LabCheckQueryResult {
  id: string
  title: string
  passed: boolean
  /** Xato yoki natija farqi (bo'sh — o'tdi) */
  message: string
}

/** Yaxlitlik cheklovlari laboratoriyasi sinovi: attack — rad etilishi kerak, valid — qabul qilinishi kerak */
export interface LabProbe {
  id: string
  title: string
  kind: 'attack' | 'valid'
  sql: string
  /** Faqat o'qituvchiga */
  hidden?: boolean
}

export interface LabProbeResult {
  id: string
  title: string
  kind: LabProbe['kind']
  passed: boolean
  /** Cheklov yoki baza xabari (bo'sh bo'lishi mumkin) */
  message: string
}

export type ExplanationVerdict = 'ok' | 'partial' | 'wrong'

export const EXPLANATION_VERDICTS: Record<ExplanationVerdict, { label: string; className: string }> = {
  ok: { label: 'Tushuntirish mos', className: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200' },
  partial: { label: 'Qisman mos', className: 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200' },
  wrong: { label: 'Mos emas', className: 'bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200' },
}

/** O'qituvchi uchun: AI yozgan, qum qutida tekshirilgan xatoli kod */
export interface BuggyCode {
  buggy_sql: string
  bugs: string[]
  differences: string[]
}

/** Moslashuvchan o'quv yo'li (talaba) */
export interface LearningPath {
  topics: { topic: string; label: string; mastery: number; mastered: boolean; labs: number; solved: number }[]
  next: { id: number; title: string; topic: string; reason: string } | null
}

/** O'qituvchi: guruh talabalari mavzular bo'yicha (foizda) */
export interface GroupMastery {
  topics: { topic: string; label: string }[]
  students: (PersonShort & { group: string; mastery: Record<string, number> })[]
}

/** Loyiha himoyasi (viva) */
export interface Viva {
  status: 'asked' | 'evaluated'
  questions: string[]
  answers: string[]
  feedback: { score: 0 | 1 | 2; comment: string }[]
  created_at: string
  answered_at: string | null
  /** Faqat o'qituvchi va adminga */
  understanding?: number | null
  teacher_summary?: string
}

/** Laboratoriya murabbiyi bilan yozishma */
/** Talablarni aniqlash: buyurtmachining talabi */
export interface InterviewRequirement {
  id: string
  text: string
  kind: 'entity' | 'attribute' | 'relationship' | 'rule'
}

/** Talablarni aniqlash laboratoriyasi (talaba uchun). AI yoqilgan guruhga talablar ko'rsatilmaydi */
export interface LabInterviewInfo {
  total: number
  ai: boolean
  requirements: InterviewRequirement[] | null
}

export interface InterviewState {
  messages: { id: number; role: 'user' | 'assistant'; content: string; created_at: string }[]
  questions_left: number
  total: number
  found: InterviewRequirement[]
  /** Laboratoriya to'g'ri yechilgandan keyin: aniqlanmagan talablar */
  missed: InterviewRequirement[] | null
}

export interface LabChatState {
  messages: { id: number; role: 'user' | 'assistant'; content: string; created_at: string }[]
  /** Bugun qolgan umumiy AI yordamlari soni */
  ai_left: number
}

/** Indeks laboratoriyasi: qum qutida o'lchangan reja */
export interface PlanMeasure {
  ok: boolean
  error: string
  plan: string[]
  /** Rejalashtiruvchi baholagan narx (shartli birlik) */
  cost: number | null
  /** Rejada qolgan taqiqlangan tugunlar haqida xabarlar */
  remaining: string[]
}

export interface PlanExplanation {
  explanation: string
  before: PlanMeasure
  after: PlanMeasure
}

export interface PlanSuggestion {
  explanation: string
  index_sql: string
  suggestion: PlanMeasure
  mine: PlanMeasure
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
  /** Talabaning o'z yechimini tushuntirishi va AI bahosi */
  explanation: { text: string; verdict: ExplanationVerdict; feedback: string } | null
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

export type QuizKind = 'pre' | 'post' | 'delayed' | 'practice' | 'survey'

export const QUIZ_KIND_LABELS: Record<QuizKind, string> = {
  pre: 'Kirish testi',
  post: 'Chiqish testi',
  delayed: 'Kechiktirilgan test',
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

// ---------- AI xarajati ----------

export interface AIUsageTotals {
  requests: number
  failed: number
  input_tokens: number
  output_tokens: number
  /** Prompt caching: keshdan arzon narxda o'qilgan kirish tokenlari (input_tokens ga kirmaydi) */
  cache_read_tokens: number
  /** AQSh dollari (narx sozlanmagan bo'lsa 0) */
  cost: number
}

export interface AIUsageReport {
  days: number
  price: {
    input_per_mtok: number
    output_per_mtok: number
    fast_input_per_mtok: number
    fast_output_per_mtok: number
    configured: boolean
  }
  today: AIUsageTotals
  month: AIUsageTotals
  previous_month: AIUsageTotals
  period: AIUsageTotals
  daily: (AIUsageTotals & { date: string })[]
  by_purpose: (AIUsageTotals & { purpose: string; label: string })[]
  by_model: (AIUsageTotals & { model: string })[]
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
  /** Kechiktirilgan test (kurs tugagandan bir necha hafta keyin) */
  delayed_test: number | null
  delayed_count: number
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

/** Laboratoriya bo'yicha eng ko'p uchraydigan xatolar (o'qituvchi uchun) */
export interface LabMistake {
  kind: 'error' | 'difference'
  text: string
  tip: string
  attempts: number
  students: number
  /** Urinib ko'rgan talabalarning necha foizi shu xatoga duch kelgan */
  share: number
}

export interface LabMistakesReport {
  students: number
  attempted: number
  solved: number
  stuck: number
  wrong_attempts: number
  items: LabMistake[]
}

// Kompetentlik modeli (competence ilovasi)
export type CompetenceStage = 'initial' | 'final' | 'delayed'
export type CompetenceLevel = 'low' | 'medium' | 'high'

export interface CompetenceIndicator {
  id: number
  name: string
  source: string
  source_label: string
  weight: number
  topics: string[]
  ai_only: boolean
  stages: CompetenceStage[]
}

export interface CompetenceComponent {
  id: number
  name: string
  description: string
  medium_from: number
  high_from: number
  stages: CompetenceStage[]
  indicators: CompetenceIndicator[]
}

export interface CompetenceModel {
  components: CompetenceComponent[]
  stages: { key: CompetenceStage; label: string }[]
  levels: { key: CompetenceLevel; label: string }[]
  overall_thresholds: { medium_from: number; high_from: number }
}

export interface CompetenceScore {
  score: number | null
  level: CompetenceLevel | null
}

export interface CompetenceDistribution {
  counts: Record<CompetenceLevel, number>
  percents: Record<CompetenceLevel, number | null>
  measured: number
  unmeasured: number
}

export interface CompetenceSummaryItem {
  distribution: CompetenceDistribution
  mean: number | null
}

export interface CompetenceSummary {
  components: (CompetenceSummaryItem & { component: number })[]
  overall: CompetenceSummaryItem
}

export interface CompetenceReport {
  group: { id: number; name: string; ai_enabled: boolean }
  stage: CompetenceStage
  students: { id: number; name: string; components: Record<string, CompetenceScore>; overall: CompetenceScore }[]
  summary: CompetenceSummary
}

export interface CompetenceComparison {
  groups: { id: number; name: string; ai_enabled: boolean; students: number; stages: Record<CompetenceStage, CompetenceSummary> }[]
  cohorts: Record<'experimental' | 'control', { groups: number; students: number; stages: Record<CompetenceStage, CompetenceSummary> }>
}

export type CompetenceCohort = 'experimental' | 'control'

export interface StatTestChi {
  chi2: number
  df: number
  p: number
  cramers_v: number
  min_expected: number
  reliable: boolean
}

export interface StatTestT {
  t: number
  df: number
  p: number
  cohens_d: number | null
  hedges_g: number | null
}

export interface StatTestU {
  u: number
  z: number
  p: number
  approximate: boolean
}

export interface StatPaired {
  n: number
  mean_diff: number
  t: number
  df: number
  p: number
  d_z: number
}

export interface StatDescribe {
  n: number
  mean: number | null
  sd: number | null
}

export interface CompetenceEfficiencyStage {
  describe: Record<CompetenceCohort, StatDescribe>
  levels: Record<CompetenceCohort, number[]>
  chi_square: StatTestChi | null
  t_test: StatTestT | null
  mann_whitney: StatTestU | null
  efficiency_ratio: number | null
}

/** Ikki kesim orasidagi o'zgarish: har bir guruh ichida (juftlangan t) va guruhlar farqi (Uelch t) */
export type CompetenceChange = Record<
  CompetenceCohort,
  { n: number; before_mean: number | null; after_mean: number | null; paired: StatPaired | null }
> & { difference: StatTestT | null }

export interface CompetenceEfficiencyRow {
  key: string
  name: string
  stages: Record<CompetenceStage, CompetenceEfficiencyStage>
  /** Tajriba boshidan oxirigacha */
  growth: CompetenceChange
  /** Tajriba oxiridan kechiktirilgan testgacha (bilim saqlanishi) */
  retention: CompetenceChange
}

export interface CompetenceEfficiency {
  alpha: number
  min_expected: number
  students: Record<CompetenceCohort, number>
  rows: CompetenceEfficiencyRow[]
}

// O'zaro baholash (ER)
export type PeerCriterionKey = 'entities' | 'attributes' | 'relationships' | 'clarity'

export interface PeerReviewReceived {
  id: number
  scores: Record<PeerCriterionKey, number>
  comment: string
  helpful: boolean | null
  created_at: string
}

export interface PeerReviewState {
  criteria: { key: PeerCriterionKey; name: string; hint: string }[]
  scale: { value: number; label: string }[]
  per_lab: number
  written: number
  /** Baholanadigan navbatdagi ish (muallif ismisiz) */
  current: { attempt_id: number; diagram: ErDiagram } | null
  /** Navbatda ish bo'lmasa — sababi */
  reason: string
  /** Talabaning o'z ishlariga berilgan baholar (baholovchi ismisiz) */
  received: PeerReviewReceived[]
}

// Erta ogohlantirish
export type RiskLevel = 'high' | 'medium' | 'low' | 'none'

export interface RiskReport {
  group: { id: number; name: string }
  labs: number
  median_solved: number
  students: {
    id: number
    name: string
    level: RiskLevel
    level_label: string
    score: number
    reasons: { code: string; text: string }[]
    last_activity: string | null
    solved: number
  }[]
}

// AI sifatini nazorat qilish
export type AIRating = 'helpful' | 'unclear' | 'wrong' | 'revealed'

export interface AIQualityItem {
  attempt: number
  kind: 'hint' | 'explanation'
  kind_label: string
  level: number
  lab: { title: string; description: string }
  work: string
  is_correct: boolean
  differences: string[]
  explanation: string
  verdict: string
  text: string
}

export interface AIQualityState {
  next: AIQualityItem | null
  rated_by_me: number
  ratings: { value: AIRating; label: string }[]
  summary: {
    kind: string
    label: string
    total: number
    ratings: { rating: AIRating; label: string; count: number; percent: number | null; ci95: [number, number] | null }[]
  }[]
}

// ---------- Laboratoriyalarning psixometrik tahlili ----------

export type LabLevelKey = 'very_easy' | 'easy' | 'medium' | 'hard' | 'very_hard'

export interface LabLevel {
  /** 1 — juda oson ... 5 — juda qiyin */
  number: number
  key: LabLevelKey
  label: string
}

export interface ScaleLabel {
  key: string
  label: string
}

export interface LabAnalysisRow {
  id: number
  title: string
  kind: 'sql' | 'er' | 'norm'
  topic: string
  assigned: number
  started: number
  /** Kamida min_students talaba boshlagan bo'lsa true */
  analysed: boolean
  in_reliability: boolean
  solved_rate: number | null
  first_try_rate: number | null
  attempts_to_solve: number | null
  minutes_to_solve: number | null
  hint_rate: number | null
  /** Qiyinlik indeksi (0-1): o'rtacha ball ulushi */
  p: number | null
  level: LabLevel | null
  /** Tuzatilgan korrelyatsiya (ajrata olish) */
  r: number | null
  discrimination: ScaleLabel | null
  /** Yuqori va quyi 27% farqi */
  d: number | null
  alpha_if_deleted: number | null
  cohorts: Record<'ai' | 'control', { students: number; p: number | null }> | null
  verdict: { key: 'good' | 'review' | 'replace'; label: string } | null
  advice: string[]
}

export interface LabAnalysis {
  consent_required: boolean
  students: number
  excluded_no_consent: number
  min_students: number
  reliable_students: number
  levels: (LabLevel & { above: number | null })[]
  distribution: (LabLevel & { count: number })[]
  reliability: {
    alpha: number | null
    interpretation: ScaleLabel | null
    labs: number
    students: number
    mean: number | null
    sd: number | null
    sem: number | null
  }
  labs: LabAnalysisRow[]
}

// ---------- Test psixometrikasi ----------

export interface QuizChoiceAnalysis {
  id: number
  text: string
  is_correct: boolean
  /** Tanlaganlar ulushi (0-1): hammasi, yuqori va quyi 27% */
  share: number | null
  upper: number | null
  lower: number | null
  flag: string | null
}

export interface QuizQuestionAnalysis {
  id: number
  order: number
  text: string
  kind: 'single' | 'multiple'
  points: number
  p: number | null
  r: number | null
  discrimination: ScaleLabel | null
  d: number | null
  alpha_if_deleted: number | null
  skipped: number | null
  choices: QuizChoiceAnalysis[]
  verdict: { key: 'good' | 'review' | 'replace'; label: string }
  advice: string[]
}

export interface SurveyScaleAnalysis {
  label: string
  students: number
  alpha: number | null
  interpretation: ScaleLabel | null
  items: { id: number; order: number; text: string; mean: number | null; r: number | null; alpha_if_deleted: number | null; advice: string[] }[]
}

interface QuizAnalysisBase {
  consent_required: boolean
  students: number
  excluded_no_consent: number
  min_students: number
  reliable_students: number
  enough: boolean
}

export type QuizAnalysis =
  | (QuizAnalysisBase & {
      kind: 'test'
      reliability: {
        coefficient: string
        alpha: number | null
        interpretation: ScaleLabel | null
        questions: number
        mean: number | null
        sd: number | null
        max: number
        sem: number | null
      } | null
      extreme_groups?: number
      questions: QuizQuestionAnalysis[]
    })
  | (QuizAnalysisBase & { kind: 'survey'; scales: SurveyScaleAnalysis[] })

// ---------- Tajriba natijasining statistik tahlili ----------

export type ExperimentCohort = 'experimental' | 'control'

export interface Descriptive {
  n: number
  mean: number | null
  sd: number | null
}

export interface Normality {
  w: number
  p: number
  normal: boolean
}

export interface StatTest {
  test: 'student' | 'welch' | 'mann_whitney' | 'paired_t' | 'wilcoxon'
  label: string
  reason: string
  statistic: { name: string; value: number | null; df?: number | null; z?: number | null }
  p: number
  significant: boolean
  effect: { name: string; value: number | null; label: string | null }
  cohens_d?: number | null
  assumptions?: {
    normality: Record<ExperimentCohort, Normality | null>
    levene: { f: number; p: number; equal: boolean } | null
  }
  normality?: Normality | null
  /** Ikkilamchi solishtiruvlar uchun Xolm bo'yicha tuzatilgan p */
  p_holm?: number
  significant_holm?: boolean
}

export interface ExperimentAnalysis {
  consent_required: boolean
  students: number
  excluded_no_consent: number
  quizzes: { pre: number; post: number; delayed: number }
  alpha: number
  primary: { outcome: string; label: string }
  cohorts: Record<
    ExperimentCohort,
    {
      label: string
      students: number
      dropped: number
      groups: number
      pre: Descriptive
      post: Descriptive
      delayed: Descriptive
      delayed_missing: number
      gain: { class: number | null; level: string | null; individual: Descriptive; excluded_full_pre: number }
      ceiling: { students: number; share: number | null; warning: boolean }
      pre_post: StatTest | null
      post_delayed: StatTest | null
    }
  >
  baseline: StatTest | null
  comparisons: { post: StatTest | null; gain: StatTest | null; delayed: StatTest | null }
  ancova: {
    primary: boolean
    f: number
    df1: number
    df2: number
    p: number
    significant: boolean
    partial_eta2: number
    effect_label: string
    adjusted_means: Record<ExperimentCohort, number>
    slopes: { f: number; p: number; parallel: boolean } | null
  } | null
  power: {
    observed_d: number | null
    achieved: number | null
    required_per_group_observed: number | null
    required_per_group_medium: number
    target: number
    alpha: number
    approximate: boolean
  }
  clustering: {
    groups: Record<ExperimentCohort, number>
    confounded: boolean
    icc: {
      value: number
      f: number
      p: number
      clusters: number
      mean_size: number
      design_effect: number
      effective_n: number
    } | null
  }
  conclusions: string[]
}

// ---------- Ekspert baholashi (mazmun validligi) ----------

export interface ExpertItem {
  key: string
  order: number
  text: string
  kind: 'single' | 'multiple' | 'likert'
  choices: { text: string; is_correct: boolean }[]
}

export interface ExpertRating {
  /** Lawshe: 3 — zarur, 2 — foydali, lekin zarur emas, 1 — keraksiz */
  essential?: number
  /** Mosligi 1-4 */
  relevance?: number
  /** Aniqligi 1-4 */
  clarity?: number
  comment?: string
}

export interface ExpertInfo {
  full_name?: string
  degree?: string
  position?: string
  workplace?: string
  experience_years?: number | null
}

/** Ekspert sahifasi (login yo'q, shaxsiy havola) */
export interface ExpertPage {
  title: string
  quiz_title: string
  construct: string
  instructions: string
  label: string
  open: boolean
  closes_at: string | null
  submitted_at: string | null
  items: ExpertItem[]
  expert: ExpertInfo
  ratings: Record<string, ExpertRating>
}

export interface ExpertInvite {
  id: number
  label: string
  revoked: boolean
  started: boolean
  rated: number
  submitted_at: string | null
  created_at: string
}

export interface ExpertResults {
  experts: number
  invited: number
  min_experts: number
  recommended_experts: number
  cvr_critical: number | null
  cvr_testable: boolean
  i_cvi_target: number | null
  summary: {
    cvi: number | null
    s_cvi_ave: number | null
    s_cvi_ave_ok: boolean
    s_cvi_ua: number | null
    s_cvi_ua_ok: boolean
    s_cvi_ave_target: number
    s_cvi_ua_target: number
    keep: number
    revise: number
    remove: number
  }
  items: {
    key: string
    order: number
    text: string
    essential: number
    cvr: number | null
    cvr_ok: boolean
    relevant: number
    i_cvi: number | null
    i_cvi_ok: boolean
    kappa: number | null
    kappa_label: string | null
    clarity: number | null
    verdict: { key: 'keep' | 'revise' | 'remove'; label: string } | null
    comments: string[]
  }[]
  panel_experts: (ExpertInfo & { label: string; submitted_at: string })[]
}

export interface ExpertPanel {
  id: number
  quiz: number | null
  quiz_title: string
  title: string
  construct: string
  instructions: string
  closes_at: string | null
  author: PersonShort
  created_at: string
  items_count: number
  invites: ExpertInvite[]
  results: ExpertResults | null
}

/** ER-diagramma chizish jarayonidagi bitta qadam (backend: labs/process.py) */
export interface ErProcessStep {
  at: string
  /** Birinchi qadamdan beri o'tgan daqiqa */
  minutes: number
  session: number
  /** edit — oraliq holat, run — tekshirish, submit — baholashga topshirish */
  source: 'edit' | 'run' | 'submit'
  events: { activity: string; label: string; detail: string }[]
  /** Namunaga moslik (0-1) */
  ratio: number | null
  diagram: ErDiagram
}

export interface ErProcessMetrics {
  steps: number
  sessions: number
  total_minutes: number
  active_minutes: number
  design_events: number
  added: number
  removed: number
  churn: number | null
  edits: number
  cardinality_changes: number
  first_relationship_minutes: number | null
  entities_first_share: number | null
  checks: number
  check_gap_minutes: number | null
  first_check_ratio: number | null
  final_ratio: number | null
  max_ratio: number | null
  strategy: 'avval_obyektlar' | 'aralash' | 'sinab_korish' | 'aniqlanmadi'
}

export interface ErProcess {
  steps: ErProcessStep[]
  metrics: ErProcessMetrics | null
  strategy_label: string | null
}

export type ErStrategy = ErProcessMetrics['strategy']

/** Pirson χ² (labs/process_stats.py) */
export interface ErChiTest {
  chi2: number
  df: number
  p: number
  significant: boolean
  cramers_v: number
  effect_label: string | null
  reliable: boolean
}

/** ER-diagramma chizish jarayoni statistikasi (GET /statistics/er-process/) */
export interface ErProcessStatistics {
  labs: { id: number; title: string }[]
  works: number
  students: number
  cohorts: Record<ExperimentCohort, string>
  strategies: {
    items: {
      strategy: ErStrategy
      label: string
      count: number
      share: number | null
      mean_grade: number | null
      solved_rate: number | null
      by_cohort: Record<ExperimentCohort, number>
    }[]
    solved_test: ErChiTest | null
    grade_test: { h: number; df: number; p: number; significant: boolean; epsilon2: number; effect_label: string | null } | null
    cohort_test: ErChiTest | null
  }
  cohort_comparison: {
    curves: Record<ExperimentCohort, { n: number; points: number[] }>
    comparisons: {
      metric: string
      label: string
      experimental: { n: number; mean: number | null }
      control: { n: number; mean: number | null }
      test: StatTest | null
    }[]
  }
  transitions: {
    strategies: { strategy: ErStrategy; label: string }[]
    students: number
    matrix: number[][]
  }
  conclusions: string[]
}

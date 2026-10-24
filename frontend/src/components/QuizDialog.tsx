import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, Loader2, Lock, Plus, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { CheckList } from '@/components/CheckList'
import { FormField } from '@/components/FormField'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { api } from '@/lib/api'
import { toLocalInputValue } from '@/lib/format'
import { applyFormError } from '@/lib/forms'
import { useGroupOptions } from '@/lib/groups'
import { QUIZ_KIND_LABELS, type Quiz, type QuizForm, type QuizKind, type QuizQuestion } from '@/lib/types'

const QUIZ_FIELDS = [
  'kind',
  'form',
  'title',
  'description',
  'opens_at',
  'closes_at',
  'time_limit_minutes',
  'show_answers',
  'groups',
  'questions',
] as const
const MAX_CHOICES = 10

function emptyQuestion(): QuizQuestion {
  return {
    text: '',
    kind: 'single',
    points: 1,
    choices: [
      { text: '', is_correct: true },
      { text: '', is_correct: false },
    ],
  }
}

/** Savollarni tekshiradi: xato bo'lsa birinchi xato matnini qaytaradi */
function questionsProblem(questions: QuizQuestion[], survey: boolean): string | null {
  for (const [index, question] of questions.entries()) {
    const number = index + 1
    if (!question.text.trim()) return `${number}-savol matni bo'sh.`
    if (survey) continue
    if (question.choices.length < 2) return `${number}-savolda kamida 2 ta javob varianti bo'lsin.`
    if (question.choices.some((choice) => !choice.text.trim())) return `${number}-savolda bo'sh javob varianti bor.`
    const correct = question.choices.filter((choice) => choice.is_correct).length
    if (question.kind === 'single' && correct !== 1) return `${number}-savolda aynan bitta to'g'ri javobni belgilang.`
    if (correct < 1) return `${number}-savolda kamida bitta to'g'ri javobni belgilang.`
  }
  return null
}

function QuestionEditor({
  question,
  number,
  total,
  survey,
  onChange,
  onMove,
  onRemove,
}: {
  question: QuizQuestion
  number: number
  total: number
  /** So'rovnomada savol faqat fikr matnidan iborat (javob — 1-5 shkala) */
  survey: boolean
  onChange: (question: QuizQuestion) => void
  onMove: (offset: -1 | 1) => void
  onRemove: () => void
}) {
  const prefix = `question-${number}`

  function setKind(kind: QuizQuestion['kind']) {
    // Bitta javobli savolga o'tilganda faqat birinchi to'g'ri variant qoladi
    let seen = false
    const choices =
      kind === 'single'
        ? question.choices.map((choice) => {
            const keep = choice.is_correct && !seen
            if (choice.is_correct) seen = true
            return { ...choice, is_correct: keep }
          })
        : question.choices
    onChange({ ...question, kind, choices })
  }

  function setCorrect(index: number, checked: boolean) {
    onChange({
      ...question,
      choices: question.choices.map((choice, position) =>
        question.kind === 'single'
          ? { ...choice, is_correct: position === index }
          : position === index
            ? { ...choice, is_correct: checked }
            : choice,
      ),
    })
  }

  return (
    <fieldset className="grid gap-3 rounded-lg border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <legend className="font-medium">{number}-savol</legend>
        <div className="ml-auto flex items-center gap-1">
          <Button type="button" variant="ghost" size="icon" aria-label={`${number}-savolni yuqoriga`} disabled={number === 1} onClick={() => onMove(-1)}>
            <ArrowUp aria-hidden="true" />
          </Button>
          <Button type="button" variant="ghost" size="icon" aria-label={`${number}-savolni pastga`} disabled={number === total} onClick={() => onMove(1)}>
            <ArrowDown aria-hidden="true" />
          </Button>
          <Button type="button" variant="ghost" size="icon" aria-label={`${number}-savolni o'chirish`} onClick={onRemove}>
            <Trash2 aria-hidden="true" />
          </Button>
        </div>
      </div>
      <Textarea
        aria-label={`${number}-savol matni`}
        className="min-h-16"
        maxLength={2000}
        placeholder={survey ? 'Fikr, masalan: «AI maslahatlari xatoni topishimga yordam berdi.»' : 'Savol matni'}
        value={question.text}
        onChange={(event) => onChange({ ...question, text: event.target.value })}
      />
      {survey ? (
        <p className="text-xs text-muted-foreground">
          Talaba 1 dan 5 gacha shkalada javob beradi: 1 — mutlaqo qo'shilmayman, 5 — to'liq qo'shilaman.
        </p>
      ) : (
        <>
          <div className="flex flex-wrap items-end gap-3">
            <label className="grid gap-1 text-sm">
              <span className="text-xs text-muted-foreground">Savol turi</span>
              <select
                className="h-9 rounded-md border bg-background px-2 text-sm"
                value={question.kind}
                onChange={(event) => setKind(event.target.value as QuizQuestion['kind'])}
              >
                <option value="single">Bitta to'g'ri javob</option>
                <option value="multiple">Bir nechta to'g'ri javob</option>
              </select>
            </label>
            <label className="grid gap-1 text-sm">
              <span className="text-xs text-muted-foreground">Ball</span>
              <Input
                type="number"
                min={1}
                max={100}
                className="h-9 w-20"
                value={question.points}
                onChange={(event) => onChange({ ...question, points: Math.max(1, Number(event.target.value) || 1) })}
              />
            </label>
          </div>
          <div className="grid gap-2">
            <span className="text-xs text-muted-foreground">
              Javob variantlari: to'g'risini belgilang {question.kind === 'multiple' ? '(bir nechta bo\'lishi mumkin)' : ''}
            </span>
            {question.choices.map((choice, index) => (
              <div key={index} className="flex items-center gap-2">
                <input
                  type={question.kind === 'single' ? 'radio' : 'checkbox'}
                  name={`${prefix}-correct`}
                  aria-label={`${index + 1}-variant to'g'ri`}
                  className="size-4 shrink-0"
                  checked={choice.is_correct}
                  onChange={(event) => setCorrect(index, event.target.checked)}
                />
                <Input
                  aria-label={`${number}-savol, ${index + 1}-variant`}
                  className="h-9 flex-1"
                  maxLength={1000}
                  placeholder={`${index + 1}-variant`}
                  value={choice.text}
                  onChange={(event) =>
                    onChange({
                      ...question,
                      choices: question.choices.map((item, position) =>
                        position === index ? { ...item, text: event.target.value } : item,
                      ),
                    })
                  }
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={`${index + 1}-variantni o'chirish`}
                  disabled={question.choices.length <= 2}
                  onClick={() => onChange({ ...question, choices: question.choices.filter((_, position) => position !== index) })}
                >
                  <Trash2 aria-hidden="true" />
                </Button>
              </div>
            ))}
            <Button
              type="button"
              variant="outline"
              className="justify-self-start"
              disabled={question.choices.length >= MAX_CHOICES}
              onClick={() => onChange({ ...question, choices: [...question.choices, { text: '', is_correct: false }] })}
            >
              <Plus aria-hidden="true" />
              Variant qo'shish
            </Button>
          </div>
        </>
      )}
    </fieldset>
  )
}

interface QuizDialogProps {
  /** Berilmasa — yangi test yaratiladi */
  quiz?: Quiz
  onClose: () => void
}

export function QuizDialog({ quiz, onClose }: QuizDialogProps) {
  const queryClient = useQueryClient()
  const { groups } = useGroupOptions()
  // Talabalar boshlagan testning savollarini o'zgartirib bo'lmaydi (natijalar solishtirilishi uchun)
  const locked = Boolean(quiz?.attempt_count)

  const [kind, setKind] = useState<QuizKind>(quiz?.kind ?? 'pre')
  const [form, setForm] = useState<QuizForm>(quiz?.form ?? '')
  const [title, setTitle] = useState(quiz?.title ?? '')
  const [description, setDescription] = useState(quiz?.description ?? '')
  const [opensAt, setOpensAt] = useState(quiz?.opens_at ? toLocalInputValue(quiz.opens_at) : '')
  const [closesAt, setClosesAt] = useState(quiz?.closes_at ? toLocalInputValue(quiz.closes_at) : '')
  const [timeLimit, setTimeLimit] = useState(quiz?.time_limit_minutes ? String(quiz.time_limit_minutes) : '')
  const [showAnswers, setShowAnswers] = useState(quiz?.show_answers ?? false)
  const [groupIds, setGroupIds] = useState<number[]>(quiz?.groups ?? [])
  const [questions, setQuestions] = useState<QuizQuestion[]>(() =>
    // So'rovnoma savollarida variantlar shkaladan olingan: tahrirlashda ular kerak emas
    (quiz?.questions ?? [emptyQuestion()]).map((question) =>
      question.kind === 'likert' ? { ...emptyQuestion(), text: question.text } : question,
    ),
  )
  const survey = kind === 'survey'
  const research = kind === 'pre' || kind === 'post' || kind === 'delayed'
  const [errors, setErrors] = useState<Record<string, string>>({})

  const mutation = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {
        kind,
        form: research ? form : '',
        title: title.trim(),
        description,
        opens_at: opensAt ? new Date(opensAt).toISOString() : null,
        closes_at: closesAt ? new Date(closesAt).toISOString() : null,
        time_limit_minutes: timeLimit ? Number(timeLimit) : null,
        show_answers: survey ? false : showAnswers,
        groups: groupIds,
      }
      if (!locked) {
        body.questions = questions.map((question) =>
          survey
            ? { text: question.text.trim(), kind: 'likert' }
            : {
                text: question.text.trim(),
                kind: question.kind,
                points: question.points,
                choices: question.choices.map((choice) => ({ text: choice.text.trim(), is_correct: choice.is_correct })),
              },
        )
      }
      return quiz
        ? api<Quiz>(`/quizzes/${quiz.id}/`, { method: 'PATCH', body })
        : api<Quiz>('/quizzes/', { method: 'POST', body })
    },
    onSuccess: (saved) => {
      toast.success(quiz ? 'Test saqlandi' : 'Test yaratildi')
      queryClient.setQueryData(['quiz', saved.id], saved)
      void queryClient.invalidateQueries({ queryKey: ['quizzes'] })
      onClose()
    },
    onError: (error) => applyFormError(error, QUIZ_FIELDS, setErrors),
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const problems: Record<string, string> = {}
    if (!groupIds.length) problems.groups = 'Kamida bitta guruh tanlang.'
    if (!locked) {
      const problem = questions.length ? questionsProblem(questions, survey) : 'Kamida bitta savol qo\'shing.'
      if (problem) problems.questions = problem
    }
    setErrors(problems)
    if (!Object.keys(problems).length) mutation.mutate()
  }

  function moveQuestion(index: number, offset: -1 | 1) {
    const next = [...questions]
    ;[next[index], next[index + offset]] = [next[index + offset], next[index]]
    setQuestions(next)
  }

  return (
    <Dialog open onOpenChange={(open) => (!open && !mutation.isPending ? onClose() : undefined)}>
      <DialogContent className="max-h-[92svh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{quiz ? 'Testni tahrirlash' : 'Yangi test'}</DialogTitle>
          <DialogDescription>
            Kirish testi o'qitishdan oldin, chiqish testi keyin o'tkaziladi. Ularga parallel variantlarni bering (masalan,
            kirishga A, chiqishga B): juft savollar bir xil mavzu va qiyinlikda, lekin talaba savollarni eslab qolmaydi. So'rovnomada ball qo'yilmaydi: talabalar fikrlarga 1–5 shkalada baho beradi.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="grid gap-4" noValidate>
          <div className={research ? 'grid gap-4 sm:grid-cols-[12rem_9rem_1fr]' : 'grid gap-4 sm:grid-cols-[12rem_1fr]'}>
            <FormField id="quiz_kind" label="Turi" error={errors.kind}>
              <select
                id="quiz_kind"
                className="h-10 rounded-md border bg-background px-2 text-sm"
                value={kind}
                onChange={(event) => setKind(event.target.value as QuizKind)}
              >
                {Object.entries(QUIZ_KIND_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </FormField>
            {research ? (
              <FormField id="quiz_form" label="Parallel variant" error={errors.form}>
                <select
                  id="quiz_form"
                  className="h-10 rounded-md border bg-background px-2 text-sm"
                  value={form}
                  disabled={locked}
                  onChange={(event) => setForm(event.target.value as QuizForm)}
                >
                  <option value="">Variantsiz</option>
                  <option value="A">A variant</option>
                  <option value="B">B variant</option>
                </select>
              </FormField>
            ) : null}
            <FormField id="quiz_title" label="Sarlavha" error={errors.title}>
              <Input
                id="quiz_title"
                className="h-10"
                maxLength={200}
                aria-invalid={Boolean(errors.title)}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
              />
            </FormField>
          </div>
          <FormField id="quiz_description" label="Izoh (ixtiyoriy)" error={errors.description}>
            <Textarea
              id="quiz_description"
              className="min-h-16"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </FormField>
          <div className="grid gap-4 sm:grid-cols-3">
            <FormField id="quiz_opens" label="Ochilish vaqti" error={errors.opens_at} hint="Bo'sh — darhol ochiq">
              <Input id="quiz_opens" type="datetime-local" className="h-10" value={opensAt} onChange={(event) => setOpensAt(event.target.value)} />
            </FormField>
            <FormField id="quiz_closes" label="Yopilish vaqti" error={errors.closes_at} hint="Bo'sh — muddatsiz">
              <Input id="quiz_closes" type="datetime-local" className="h-10" value={closesAt} onChange={(event) => setClosesAt(event.target.value)} />
            </FormField>
            <FormField id="quiz_limit" label="Vaqt (daqiqa)" error={errors.time_limit_minutes} hint="Bo'sh — cheklanmagan">
              <Input
                id="quiz_limit"
                type="number"
                min={1}
                max={600}
                className="h-10"
                value={timeLimit}
                onChange={(event) => setTimeLimit(event.target.value)}
              />
            </FormField>
          </div>
          {survey ? null : (
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-0.5 size-4" checked={showAnswers} onChange={(event) => setShowAnswers(event.target.checked)} />
              <span>
                Topshirgandan keyin talabaga to'g'ri javoblarni ko'rsatish
                <span className="block text-xs text-muted-foreground">
                  Kirish testida belgilamang: aks holda talabalar chiqish testining javoblarini oldindan bilib oladi.
                </span>
              </span>
            </label>
          )}
          <FormField id="quiz_groups" label="Guruhlar" error={errors.groups}>
            <CheckList
              idPrefix="quiz-group"
              options={groups.map((group) => ({ id: group.id, label: group.name }))}
              selected={groupIds}
              onChange={setGroupIds}
              emptyText="Sizga hali guruh biriktirilmagan. Administratorga murojaat qiling."
              invalid={Boolean(errors.groups)}
            />
          </FormField>

          <div className="grid gap-3">
            <h3 className="font-medium">Savollar ({questions.length})</h3>
            {locked ? (
              <p className="flex items-center gap-2 rounded-lg border bg-muted/40 p-3 text-sm text-muted-foreground">
                <Lock className="size-4 shrink-0" aria-hidden="true" />
                Talabalar testni boshlagan: natijalar solishtirilishi uchun savollarni o'zgartirib bo'lmaydi.
              </p>
            ) : (
              <>
                {questions.map((question, index) => (
                  <QuestionEditor
                    key={index}
                    question={question}
                    number={index + 1}
                    total={questions.length}
                    survey={survey}
                    onChange={(next) => setQuestions(questions.map((item, position) => (position === index ? next : item)))}
                    onMove={(offset) => moveQuestion(index, offset)}
                    onRemove={() => setQuestions(questions.filter((_, position) => position !== index))}
                  />
                ))}
                <Button type="button" variant="outline" className="justify-self-start" onClick={() => setQuestions([...questions, emptyQuestion()])}>
                  <Plus aria-hidden="true" />
                  Savol qo'shish
                </Button>
              </>
            )}
            {errors.questions ? (
              <p className="text-sm text-destructive" role="alert">
                {errors.questions}
              </p>
            ) : null}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" size="lg" disabled={mutation.isPending} onClick={onClose}>
              Bekor qilish
            </Button>
            <Button type="submit" size="lg" disabled={mutation.isPending || !title.trim()}>
              {mutation.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
              Saqlash
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

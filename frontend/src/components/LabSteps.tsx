import { Check, ListChecks } from 'lucide-react'
import { useState } from 'react'

import { useUser } from '@/lib/auth'
import { MAX_SCORE, type Lab } from '@/lib/types'
import { cn } from '@/lib/utils'

interface Step {
  title: string
  text: string
  done: boolean
  /** Bahoga ta'sir qilmaydi: hisobga kirmaydi va «hozirgi qadam» bo'lmaydi */
  optional?: boolean
}

function firstSteps(lab: Lab): Omit<Step, 'done'>[] {
  const read = `«Laboratoriya sharti»ni diqqat bilan o'qing${lab.theory.trim() ? ", «Nazariya va namuna»dagi ishlangan misolni ko'rib chiqing" : ''}.`
  if (lab.kind === 'er') {
    const source = lab.setup_sql.trim()
      ? " «Berilgan baza»dagi jadval va tashqi kalitlarga qarang."
      : lab.interview?.ai
        ? " Shartda talablar to'liq emas: ularni «Buyurtmachi bilan suhbat»da savol berib aniqlang."
        : lab.interview
          ? " «Buyurtmachi talablari» ro'yxatini ko'rib chiqing."
          : ''
    return [
      { title: 'Topshiriqni tushuning', text: read + source },
      { title: 'Diagrammani chizing', text: "«Mening ER-diagrammam»da obyektlar, atributlar va bog'lanishlarni chizing." },
    ]
  }
  if (lab.kind === 'norm') {
    return [
      { title: 'Topshiriqni tushuning', text: `${read} Atributlar va funksional bog'liqliklarga qarang.` },
      {
        title: "Javobni to'ldiring",
        text: "«Mening javobim»ga nomzod kalitlarni, hozirgi normal formani va dekompozitsiyani yozing.",
      },
    ]
  }
  const extras = [
    lab.given_diagram?.entities.length ? ' Berilgan ER-modelga qarang.' : '',
    lab.setup_sql.trim() ? " «Tayyor jadvallar»ni ko'rib chiqing: ularni qayta yozish shart emas." : '',
    lab.probes?.length ? " «Cheklovlar sinovlari» kodingiz nimaga bardosh berishi kerakligini ko'rsatadi." : '',
    lab.check_queries?.length ? " «Tekshiruv so'rovlari» ham kodingizdan keyin ishlashi kerak." : '',
    lab.plan_query?.trim() ? " «Tekshiriladigan so'rov»ni qayta yozmang: kodingizdan keyin uning rejasi tekshiriladi." : '',
  ].join('')
  return [
    { title: 'Topshiriqni tushuning', text: read + extras },
    {
      title: 'Kodni yozib, sinab ko\'ring',
      text: `«Mening kodim»ga SQL yozing${lab.starter_sql?.trim() ? ' (maydondagi boshlang\'ich koddan boshlang)' : ''} va «Sinab ko'rish»ni bosing: natija ko'rinadi, urinish hisoblanmaydi.`,
    },
  ]
}

function labSteps(lab: Lab, aiEnabled: boolean): Step[] {
  const progress = lab.my_progress ?? { attempts: 0, solved: false, grade: null }
  const examActive = lab.module_detail?.exam?.state === 'active'
  const ai = aiEnabled && !examActive
  const started = progress.attempts > 0

  const check = [
    "«Tekshirish»ni bosing va xato bo'lsa, ko'rsatilgan farqlarni tuzatib qayta tekshiring.",
    ai ? " Qiynalsangiz, AI maslahati yoki «Murabbiy»dan foydalaning." : '',
    lab.module_detail?.sequential ? " To'g'ri chiqsa, moduldagi keyingi laboratoriya ochiladi." : '',
  ].join('')

  const submit = [
    "Tayyor bo'lgach «Baholashga topshirish»ni bosing: ball qo'yiladi. Qayta topshirish mumkin, eng yuqori ball saqlanadi.",
    lab.kind === 'er' && !examActive ? " Diagrammangizning tuzatilgan varianti ham ko'rsatiladi." : '',
    progress.grade ? ` Hozirgi ballingiz: ${progress.grade.score} / ${MAX_SCORE}.` : '',
  ].join('')

  const steps: Step[] = [
    ...firstSteps(lab).map((step) => ({ ...step, done: started })),
    { title: 'Tekshiring va tuzating', text: check, done: progress.solved },
    { title: 'Baholashga topshiring', text: submit, done: progress.solved && Boolean(progress.grade) },
  ]
  if (lab.kind === 'er' && !examActive) {
    steps.push({
      title: "Guruhdoshlaringiz ishini baholang",
      text: "To'g'ri yechgach, «O'zaro baholash»da guruhdoshlaringiz diagrammalarini rubrika bo'yicha baholang.",
      done: false,
      optional: true,
    })
  }
  return steps
}

/** Talabaga laboratoriyani bajarish tartibi: qaysi qadamda turgani urinishlari va bahosidan aniqlanadi. */
export function LabSteps({ lab }: { lab: Lab }) {
  const user = useUser()
  const steps = labSteps(lab, user.ai_enabled)
  const required = steps.filter((step) => !step.optional)
  const doneCount = required.filter((step) => step.done).length
  const current = steps.find((step) => !step.optional && !step.done)
  // Faqat sahifa ochilganda hisoblanadi: natijani o'qiyotganda blok yopilib, sahifa siljimasin
  const [initiallyOpen] = useState(() => doneCount < required.length)

  // Imtihon tugagan: endi tekshirib ham, topshirib ham bo'lmaydi
  if (lab.module_detail?.exam?.state === 'finished') return null

  return (
    <details open={initiallyOpen} className="mb-4 rounded-xl border bg-card p-4">
      <summary className="flex cursor-pointer flex-wrap items-center gap-2 font-medium select-none">
        <ListChecks className="size-5 shrink-0 text-primary" aria-hidden="true" />
        Bajarish tartibi
        <span className="text-sm font-normal text-muted-foreground tabular-nums">
          {doneCount} / {required.length} qadam
        </span>
      </summary>
      <ol className="mt-4 grid gap-3">
        {steps.map((step, index) => {
          const isCurrent = step === current
          return (
            <li key={step.title} aria-current={isCurrent ? 'step' : undefined} className="flex items-start gap-3">
              <span
                className={cn(
                  'flex size-7 shrink-0 items-center justify-center rounded-full border text-sm font-medium tabular-nums',
                  step.done && 'border-emerald-600 bg-emerald-600 text-white',
                  isCurrent && 'border-primary bg-primary text-primary-foreground',
                )}
              >
                {step.done ? <Check className="size-4" aria-hidden="true" /> : index + 1}
                {step.done ? <span className="sr-only">{index + 1} — bajarilgan</span> : null}
              </span>
              <div className={cn('min-w-0', isCurrent && 'rounded-lg bg-muted/50 px-3 py-2')}>
                <h3 className="text-sm font-medium">
                  {step.title}
                  {step.optional ? <span className="font-normal text-muted-foreground"> (ixtiyoriy)</span> : null}
                </h3>
                <p className="mt-0.5 text-sm text-muted-foreground">{step.text}</p>
              </div>
            </li>
          )
        })}
      </ol>
    </details>
  )
}

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { CheckList } from '@/components/CheckList'
import { ErEditor } from '@/components/ErEditor'
import { FormField } from '@/components/FormField'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { api } from '@/lib/api'
import { cleanDiagram, EMPTY_DIAGRAM } from '@/lib/er'
import { applyFormError } from '@/lib/forms'
import { useGroupOptions } from '@/lib/groups'
import { cn } from '@/lib/utils'
import type { ErDiagram, Lab, LabKind } from '@/lib/types'

const LAB_FIELDS = ['kind', 'title', 'description', 'theory', 'setup_sql', 'solution_sql', 'hidden_setup_sql', 'starter_sql', 'norm_task', 'reference_diagram', 'given_diagram', 'plan_query', 'plan_forbidden', 'concurrent', 'topic', 'groups'] as const

const KIND_OPTIONS: { value: LabKind; label: string; hint: string }[] = [
  { value: 'sql', label: 'SQL kod', hint: 'Talaba SQL yozadi, natija namunaviy yechim bilan solishtiriladi.' },
  { value: 'er', label: 'ER-diagramma', hint: 'Talaba ER-diagramma chizadi, u namunaviy diagramma bilan solishtiriladi.' },
  {
    value: 'norm',
    label: 'Normallashtirish',
    hint: "Talaba nomzod kalitlarni, normal formani va dekompozitsiyani topadi; javob algoritm bilan tekshiriladi.",
  },
]

function fdsText(lab?: Lab) {
  return (lab?.norm_task?.fds ?? []).map((fd) => `${fd.lhs.join(', ')} -> ${fd.rhs.join(', ')}`).join('\n')
}
const TOPIC_OPTIONS = [
  ['', "Avtomatik (laboratoriya turidan)"],
  ['er', 'ER-model'],
  ['design', 'Jadvallarni loyihalash'],
  ['norm', 'Normallashtirish'],
  ['er_sql', 'ER-modeldan jadvallarga'],
  ['select', "SELECT so'rovlari"],
  ['index', 'Indekslar'],
  ['transaction', 'Tranzaksiyalar'],
] as const
const SQL_PROPS = { spellCheck: false, autoCapitalize: 'none', autoCorrect: 'off' } as const

interface LabDialogProps {
  /** Berilmasa — yangi laboratoriya yaratiladi */
  lab?: Lab
  onClose: () => void
}

export function LabDialog({ lab, onClose }: LabDialogProps) {
  const queryClient = useQueryClient()
  const { groups } = useGroupOptions()

  const [kind, setKind] = useState<LabKind>(lab?.kind ?? 'sql')
  const [referenceDiagram, setReferenceDiagram] = useState<ErDiagram>(lab?.reference_diagram ?? EMPTY_DIAGRAM)
  const [givenDiagram, setGivenDiagram] = useState<ErDiagram>(lab?.given_diagram ?? EMPTY_DIAGRAM)
  const [title, setTitle] = useState(lab?.title ?? '')
  const [description, setDescription] = useState(lab?.description ?? '')
  const [theory, setTheory] = useState(lab?.theory ?? '')
  const [setupSql, setSetupSql] = useState(lab?.setup_sql ?? '')
  const [solutionSql, setSolutionSql] = useState(lab?.solution_sql ?? '')
  const [hiddenSql, setHiddenSql] = useState(lab?.hidden_setup_sql ?? '')
  const [planQuery, setPlanQuery] = useState(lab?.plan_query ?? '')
  const [planForbidden, setPlanForbidden] = useState(lab?.plan_forbidden ?? 'Seq Scan')
  const [concurrent, setConcurrent] = useState(lab?.concurrent ?? false)
  const [starterSql, setStarterSql] = useState(lab?.starter_sql ?? '')
  const [topic, setTopic] = useState(lab?.topic ?? '')
  const [normAttributes, setNormAttributes] = useState(lab?.norm_task?.attributes.join(', ') ?? '')
  const [normFds, setNormFds] = useState(fdsText(lab))
  const [normTarget, setNormTarget] = useState<'3NF' | 'BCNF'>(lab?.norm_task?.target ?? '3NF')
  const [groupIds, setGroupIds] = useState<number[]>(lab?.groups ?? [])
  const [errors, setErrors] = useState<Record<string, string>>({})

  const mutation = useMutation({
    mutationFn: () => {
      const common = { title: title.trim(), description, theory, topic, groups: groupIds }
      const body =
        kind === 'er'
          ? { ...common, kind, reference_diagram: cleanDiagram(referenceDiagram) }
          : kind === 'norm'
            ? { ...common, kind, norm_task: { attributes: normAttributes, fds: normFds, target: normTarget } }
            : {
              ...common,
              kind,
              setup_sql: setupSql,
              solution_sql: solutionSql,
              hidden_setup_sql: hiddenSql,
              starter_sql: starterSql,
              given_diagram: givenDiagram.entities.length ? cleanDiagram(givenDiagram) : null,
              plan_query: planQuery,
              plan_forbidden: planForbidden,
              concurrent,
            }
      return lab
        ? api<Lab>(`/labs/${lab.id}/`, { method: 'PATCH', body })
        : api<Lab>('/labs/', { method: 'POST', body })
    },
    onSuccess: (saved) => {
      toast.success(lab ? 'Laboratoriya saqlandi' : 'Laboratoriya yaratildi')
      queryClient.setQueryData(['lab', saved.id], saved)
      void queryClient.invalidateQueries({ queryKey: ['labs'] })
      onClose()
    },
    onError: (error) => applyFormError(error, LAB_FIELDS, setErrors),
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const problems: Record<string, string> = {}
    if (!groupIds.length) problems.groups = 'Kamida bitta guruh tanlang.'
    if (kind === 'er' && !referenceDiagram.entities.length) {
      problems.reference_diagram = 'Namunaviy diagrammada kamida bitta obyekt chizing.'
    }
    setErrors(problems)
    if (!Object.keys(problems).length) mutation.mutate()
  }

  return (
    <Dialog open onOpenChange={(open) => (!open && !mutation.isPending ? onClose() : undefined)}>
      <DialogContent className={cn('max-h-[92svh] overflow-y-auto', kind === 'er' ? 'sm:max-w-6xl' : 'sm:max-w-2xl')}>
        <DialogHeader>
          <DialogTitle>{lab ? 'Laboratoriyani tahrirlash' : 'Yangi laboratoriya'}</DialogTitle>
          <DialogDescription>{KIND_OPTIONS.find((option) => option.value === kind)?.hint}</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="grid gap-4" noValidate>
          {lab ? null : (
            <fieldset className="grid gap-1.5">
              <legend className="mb-1.5 text-sm font-medium">Laboratoriya turi</legend>
              <div className="flex flex-wrap gap-2">
                {KIND_OPTIONS.map((option) => (
                  <label
                    key={option.value}
                    className={cn(
                      'flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm',
                      kind === option.value && 'border-primary bg-primary/5',
                    )}
                  >
                    <input
                      type="radio"
                      name="lab_kind"
                      value={option.value}
                      checked={kind === option.value}
                      onChange={() => setKind(option.value)}
                    />
                    {option.label}
                  </label>
                ))}
              </div>
            </fieldset>
          )}
          <FormField id="lab_title" label="Sarlavha" error={errors.title}>
            <Input
              id="lab_title"
              className="h-10"
              aria-invalid={Boolean(errors.title)}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </FormField>
          <FormField
            id="lab_description"
            label="Laboratoriya sharti"
            error={errors.description}
            hint={
              kind === 'er'
                ? "Obyekt va atribut nomlarini aniq yozing: talaba diagrammasi nomlar bo'yicha solishtiriladi."
                : 'Jadval va ustun nomlarini aniq yozing: talaba natijasi namuna bilan solishtiriladi.'
            }
          >
            <Textarea
              id="lab_description"
              className="max-h-64 min-h-24"
              aria-invalid={Boolean(errors.description)}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </FormField>
          <FormField
            id="lab_theory"
            label="Nazariya va namuna (ixtiyoriy)"
            error={errors.theory}
            hint="Talabaga shart ostida ko'rinadi. Kodni ``` qatorlari orasiga yozing. Namunani boshqa mavzuda bering, yechimni yozmang."
          >
            <Textarea
              id="lab_theory"
              className="max-h-64 min-h-24"
              maxLength={20000}
              aria-invalid={Boolean(errors.theory)}
              value={theory}
              onChange={(event) => setTheory(event.target.value)}
            />
          </FormField>
          {kind === 'er' ? (
            <div className="grid gap-1.5">
              <span className="text-sm font-medium">Namunaviy ER-diagramma</span>
              <p className="text-xs text-muted-foreground">
                Talabaga ko'rinmaydi. Talaba diagrammasi shu bilan solishtiriladi: obyektlar, atributlar, PK va
                bog'lanishlar kardinalligi. FK atributlari solishtirilmaydi.
              </p>
              <ErEditor value={referenceDiagram} onChange={setReferenceDiagram} />
              {errors.reference_diagram ? (
                <p className="text-xs text-destructive" role="alert">
                  {errors.reference_diagram}
                </p>
              ) : null}
            </div>
          ) : kind === 'norm' ? (
            <>
              <FormField
                id="lab_norm_attributes"
                label="Munosabat atributlari"
                error={errors.norm_task}
                hint="Vergul bilan, lotin harflarida (2–12 ta). Talabaga ko'rinadi."
              >
                <Input
                  id="lab_norm_attributes"
                  placeholder="talaba_id, ism, fan_id, fan_nomi, baho"
                  aria-invalid={Boolean(errors.norm_task)}
                  value={normAttributes}
                  onChange={(event) => setNormAttributes(event.target.value)}
                  {...SQL_PROPS}
                />
              </FormField>
              <FormField
                id="lab_norm_fds"
                label="Funksional bog'liqliklar"
                hint="Har bir qatorda bittasi: chap tomon -> o'ng tomon. Talabaga ko'rinadi."
              >
                <Textarea
                  id="lab_norm_fds"
                  className="max-h-64 min-h-28 font-mono text-sm md:text-xs"
                  placeholder={'talaba_id -> ism\nfan_id -> fan_nomi\ntalaba_id, fan_id -> baho'}
                  value={normFds}
                  onChange={(event) => setNormFds(event.target.value)}
                  {...SQL_PROPS}
                />
              </FormField>
              <FormField id="lab_norm_target" label="Maqsad normal forma">
                <select
                  id="lab_norm_target"
                  className="h-10 justify-self-start rounded-md border bg-background px-2 text-sm"
                  value={normTarget}
                  onChange={(event) => setNormTarget(event.target.value as '3NF' | 'BCNF')}
                >
                  <option value="3NF">3NF (bog'liqliklar saqlanishi ham tekshiriladi)</option>
                  <option value="BCNF">BCNF</option>
                </select>
              </FormField>
            </>
          ) : (
            <>
              <div className="grid gap-1.5">
                <span className="text-sm font-medium">Talabaga beriladigan ER-model (ixtiyoriy)</span>
                <p className="text-xs text-muted-foreground">
                  ER → SQL laboratoriyasi uchun: talaba shu model bo'yicha jadvallarni yaratadi. Talabaga ko'rinadi;
                  tekshiruv namunaviy yechim bo'yicha. Bo'sh qoldirilsa, ko'rsatilmaydi.
                </p>
                <ErEditor value={givenDiagram} onChange={setGivenDiagram} />
                {errors.given_diagram ? (
                  <p className="text-xs text-destructive" role="alert">
                    {errors.given_diagram}
                  </p>
                ) : null}
              </div>
              <FormField
                id="lab_setup"
                label="Tayyor jadvallar (SQL)"
                error={errors.setup_sql}
                hint="Ixtiyoriy. Talaba kodidan oldin bajariladi va talabaga ko'rinadi: CREATE TABLE va INSERT buyruqlari."
              >
                <Textarea
                  id="lab_setup"
                  className="max-h-64 min-h-28 font-mono text-sm md:text-xs"
                  placeholder={"CREATE TABLE kitob (id INT PRIMARY KEY, nomi VARCHAR(100));\nINSERT INTO kitob VALUES (1, 'Alifbo');"}
                  aria-invalid={Boolean(errors.setup_sql)}
                  value={setupSql}
                  onChange={(event) => setSetupSql(event.target.value)}
                  {...SQL_PROPS}
                />
              </FormField>
              <FormField
                id="lab_solution"
                label="Namunaviy yechim (SQL)"
                error={errors.solution_sql}
                hint="Talabaga ko'rinmaydi. Bo'sh qoldirilsa, xatosiz ishlagan har qanday kod to'g'ri hisoblanadi."
              >
                <Textarea
                  id="lab_solution"
                  className="max-h-64 min-h-28 font-mono text-sm md:text-xs"
                  placeholder="SELECT nomi FROM kitob ORDER BY nomi;"
                  aria-invalid={Boolean(errors.solution_sql)}
                  value={solutionSql}
                  onChange={(event) => setSolutionSql(event.target.value)}
                  {...SQL_PROPS}
                />
              </FormField>
              <FormField
                id="lab_hidden"
                label="Yashirin test ma'lumotlari (SQL, ixtiyoriy)"
                error={errors.hidden_setup_sql}
                hint="Talabaga ko'rinmaydi. Boshlang'ich jadvallar bilan bir xil jadvallar, lekin boshqa ma'lumotlar. To'g'ri chiqqan kod shu ma'lumotlarda ham tekshiriladi: natijani qo'lda yozib aldab bo'lmaydi."
              >
                <Textarea
                  id="lab_hidden"
                  className="max-h-64 min-h-28 font-mono text-sm md:text-xs"
                  aria-invalid={Boolean(errors.hidden_setup_sql)}
                  value={hiddenSql}
                  onChange={(event) => setHiddenSql(event.target.value)}
                  {...SQL_PROPS}
                />
              </FormField>
              <FormField
                id="lab_starter"
                label="Boshlang'ich kod (ixtiyoriy)"
                error={errors.starter_sql}
                hint="Talaba muharririda dastlab turadi. Masalan, «AI yozgan xatoli yechim — xatolarini toping» mashqi uchun."
              >
                <Textarea
                  id="lab_starter"
                  className="max-h-64 min-h-16 font-mono text-sm md:text-xs"
                  aria-invalid={Boolean(errors.starter_sql)}
                  value={starterSql}
                  onChange={(event) => setStarterSql(event.target.value)}
                  {...SQL_PROPS}
                />
              </FormField>
              <FormField
                id="lab_plan_query"
                label="Rejasi tekshiriladigan so'rov (indeks laboratoriyasi, ixtiyoriy)"
                error={errors.plan_query}
                hint="Talaba kodidan keyin shu so'rovning EXPLAIN rejasi olinadi (so'rov bajarilmaydi). Talabaga ko'rinadi. Namunaviy yechim indeks yaratishi kerak."
              >
                <Textarea
                  id="lab_plan_query"
                  className="max-h-40 min-h-16 font-mono text-sm md:text-xs"
                  placeholder="SELECT id FROM foydalanuvchi WHERE email = '...'"
                  maxLength={5000}
                  aria-invalid={Boolean(errors.plan_query)}
                  value={planQuery}
                  onChange={(event) => setPlanQuery(event.target.value)}
                  {...SQL_PROPS}
                />
              </FormField>
              <div className="grid gap-1">
                <label className="flex items-center gap-2 text-sm font-medium">
                  <input
                    type="checkbox"
                    className="size-4"
                    checked={concurrent}
                    onChange={(event) => setConcurrent(event.target.checked)}
                  />
                  Ikki sessiyada bir vaqtda tekshirish (tranzaksiya laboratoriyasi)
                </label>
                <p className="text-xs text-muted-foreground">
                  Talaba kodi (BEGIN … COMMIT) A va B sessiyalarida bir vaqtda bajariladi; natija ketma-ket ikki marta
                  bajarilgandagiga teng bo'lishi kerak. Namunaviy yechim ham shu tekshiruvdan o'tishi kerak.
                </p>
                {errors.concurrent ? (
                  <p className="text-xs text-destructive" role="alert">
                    {errors.concurrent}
                  </p>
                ) : null}
              </div>
              {planQuery.trim() ? (
                <FormField
                  id="lab_plan_forbidden"
                  label="Rejada bo'lmasligi kerak"
                  error={errors.plan_forbidden}
                  hint="Vergul bilan: Seq Scan, Sort, Bitmap Heap Scan."
                >
                  <Input
                    id="lab_plan_forbidden"
                    maxLength={200}
                    aria-invalid={Boolean(errors.plan_forbidden)}
                    value={planForbidden}
                    onChange={(event) => setPlanForbidden(event.target.value)}
                  />
                </FormField>
              ) : null}
            </>
          )}
          <FormField
            id="lab_topic"
            label="Mavzu"
            error={errors.topic}
            hint="Talabaning o'quv yo'li (mavzular bo'yicha o'zlashtirish va tavsiya) shu bo'yicha hisoblanadi."
          >
            <select
              id="lab_topic"
              className="h-10 justify-self-start rounded-md border bg-background px-2 text-sm"
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
            >
              {TOPIC_OPTIONS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </FormField>
          <FormField id="lab_groups" label="Guruhlar" error={errors.groups}>
            <CheckList
              idPrefix="lab-group"
              options={groups.map((group) => ({ id: group.id, label: group.name }))}
              selected={groupIds}
              onChange={setGroupIds}
              emptyText="Sizga hali guruh biriktirilmagan. Administratorga murojaat qiling."
              invalid={Boolean(errors.groups)}
            />
          </FormField>
          <DialogFooter>
            <Button type="button" variant="outline" size="lg" disabled={mutation.isPending} onClick={onClose}>
              Bekor qilish
            </Button>
            <Button type="submit" size="lg" disabled={mutation.isPending || !title.trim() || !description.trim()}>
              {mutation.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
              {mutation.isPending ? (kind === 'sql' ? 'Kod tekshirilmoqda…' : 'Saqlanmoqda…') : 'Saqlash'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

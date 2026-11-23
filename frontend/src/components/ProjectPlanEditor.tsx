import { Plus, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { RUBRIC_TOTAL, rubricTotal, type CriterionDraft, type StageDraft } from '@/lib/rubric'
import { cn } from '@/lib/utils'
import { t } from '@/lib/i18n'

const MAX_STAGES = 8
const MAX_CRITERIA = 20

interface ProjectPlanEditorProps {
  stages: StageDraft[]
  onStagesChange: (stages: StageDraft[]) => void
  rubric: CriterionDraft[]
  onRubricChange: (rubric: CriterionDraft[]) => void
  /** Yechimlar kelgan: bosqichlar soni, ballar va biriktirish o'zgartirilmaydi */
  locked: boolean
  stagesError?: string
  rubricError?: string
}

/** Bosqichlar va baholash rubrikasi muharriri (topshiriq formasida). */
export function ProjectPlanEditor({
  stages,
  onStagesChange,
  rubric,
  onRubricChange,
  locked,
  stagesError,
  rubricError,
}: ProjectPlanEditorProps) {
  const total = rubricTotal(rubric)

  function updateStage(index: number, patch: Partial<StageDraft>) {
    onStagesChange(stages.map((stage, i) => (i === index ? { ...stage, ...patch } : stage)))
  }

  function removeStage(index: number) {
    onStagesChange(stages.filter((_, i) => i !== index))
    // O'chirilgan bosqich mezonlari bosqichsiz qoladi, keyingilari bittaga suriladi
    onRubricChange(
      rubric.map((item) =>
        item.stage === null || item.stage < index ? item : { ...item, stage: item.stage === index ? null : item.stage - 1 },
      ),
    )
  }

  function updateCriterion(index: number, patch: Partial<CriterionDraft>) {
    onRubricChange(rubric.map((item, i) => (i === index ? { ...item, ...patch } : item)))
  }

  return (
    <div className="grid gap-5">
      <section className="grid gap-2" aria-labelledby="stages_heading">
        <div>
          <h3 id="stages_heading" className="text-sm font-medium">
            {t('Bosqichlar (ixtiyoriy)')}
          </h3>
          <p className="text-xs text-muted-foreground">
            {t("Loyihani bosqichlarga bo'ling: har bir bosqich alohida topshiriladi va o'z mezonlari bo'yicha baholanadi. Loyiha muddati — oxirgi bosqich muddati.")}
          </p>
        </div>
        {stages.map((stage, index) => (
          <div key={index} className="grid gap-2 rounded-lg border p-3">
            <div className="flex items-center gap-2">
              <span className="shrink-0 text-sm font-medium">{index + 1}.</span>
              <Input
                aria-label={t('{value}-bosqich sarlavhasi', { value: index + 1 })}
                className="h-9"
                placeholder={t('Masalan: ER-model')}
                maxLength={200}
                value={stage.title}
                onChange={(event) => updateStage(index, { title: event.target.value })}
              />
              {!locked ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={t("{value}-bosqichni o'chirish", { value: index + 1 })}
                  onClick={() => removeStage(index)}
                >
                  <Trash2 aria-hidden="true" />
                </Button>
              ) : null}
            </div>
            <label className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              {t('Talaba topshiradi')}
              <select
                className="h-9 rounded-md border bg-background px-2 text-sm text-foreground"
                disabled={locked}
                value={stage.kind}
                onChange={(event) => updateStage(index, { kind: event.target.value as StageDraft['kind'] })}
              >
                <option value="sql">{t('SQL kod')}</option>
                <option value="er">{t('ER-diagramma')}</option>
              </select>
            </label>
            <Textarea
              aria-label={t('{value}-bosqich sharti', { value: index + 1 })}
              className="max-h-40 min-h-14"
              placeholder={t('Bu bosqichda nima topshiriladi')}
              maxLength={5000}
              value={stage.description}
              onChange={(event) => updateStage(index, { description: event.target.value })}
            />
            <label className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              {t('Muddat')}
              <Input
                type="datetime-local"
                className="h-9 w-full sm:w-64"
                value={stage.deadline}
                onChange={(event) => updateStage(index, { deadline: event.target.value })}
              />
            </label>
          </div>
        ))}
        {!locked && stages.length < MAX_STAGES ? (
          <Button
            type="button"
            variant="outline"
            className="justify-self-start"
            onClick={() => onStagesChange([...stages, { kind: 'sql', title: '', description: '', deadline: '' }])}
          >
            <Plus aria-hidden="true" />
            {t("Bosqich qo'shish")}
          </Button>
        ) : null}
        {stagesError ? (
          <p className="text-xs text-destructive" role="alert">
            {stagesError}
          </p>
        ) : null}
      </section>

      <section className="grid gap-2" aria-labelledby="rubric_heading">
        <div>
          <h3 id="rubric_heading" className="text-sm font-medium">
            {t('Baholash rubrikasi')}{' '}{stages.length ? '' : t('(ixtiyoriy)')}
          </h3>
          <p className="text-xs text-muted-foreground">
            {t("Talabaga oldindan ko'rinadi. Har bir mezonga ball alohida qo'yiladi, ballar yig'indisi {RUBRIC_TOTAL}.", { RUBRIC_TOTAL })}
            {stages.length ? t(' Har bir mezonni bosqichga biriktiring.') : ''}
            {locked ? t(" Yechimlar kelgan: ball va bosqichni o'zgartirib bo'lmaydi, nomi va izohini — mumkin.") : ''}
          </p>
        </div>
        {rubric.map((item, index) => (
          <div key={index} className="grid gap-2 rounded-lg border p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Input
                aria-label={t('{value}-mezon nomi', { value: index + 1 })}
                className="h-9 min-w-0 flex-1 basis-48"
                placeholder={t('Masalan: Normallashtirish')}
                maxLength={100}
                value={item.name}
                onChange={(event) => updateCriterion(index, { name: event.target.value })}
              />
              <Input
                aria-label={t('{value}-mezon bali', { value: index + 1 })}
                type="number"
                min={1}
                max={RUBRIC_TOTAL}
                className="h-9 w-20"
                disabled={locked}
                value={item.points}
                onChange={(event) => updateCriterion(index, { points: event.target.value })}
              />
              <span className="text-xs text-muted-foreground">{t('ball')}</span>
              {stages.length ? (
                <select
                  aria-label={t('{value}-mezon bosqichi', { value: index + 1 })}
                  className="h-9 rounded-md border bg-background px-2 text-sm"
                  disabled={locked}
                  value={item.stage ?? ''}
                  onChange={(event) =>
                    updateCriterion(index, { stage: event.target.value === '' ? null : Number(event.target.value) })
                  }
                >
                  <option value="">{t('Bosqichni tanlang')}</option>
                  {stages.map((stage, stageIndex) => (
                    <option key={stageIndex} value={stageIndex}>
                      {stageIndex + 1}. {stage.title || t('bosqich')}
                    </option>
                  ))}
                </select>
              ) : null}
              {!locked ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={t("{value}-mezonni o'chirish", { value: index + 1 })}
                  onClick={() => onRubricChange(rubric.filter((_, i) => i !== index))}
                >
                  <Trash2 aria-hidden="true" />
                </Button>
              ) : null}
            </div>
            <Input
              aria-label={t('{value}-mezon izohi', { value: index + 1 })}
              className="h-9"
              placeholder={t('Nima tekshiriladi (ixtiyoriy)')}
              maxLength={1000}
              value={item.description}
              onChange={(event) => updateCriterion(index, { description: event.target.value })}
            />
          </div>
        ))}
        <div className="flex flex-wrap items-center gap-3">
          {!locked && rubric.length < MAX_CRITERIA ? (
            <Button
              type="button"
              variant="outline"
              onClick={() =>
                onRubricChange([...rubric, { name: '', points: '', description: '', stage: stages.length ? 0 : null }])
              }
            >
              <Plus aria-hidden="true" />
              {t("Mezon qo'shish")}
            </Button>
          ) : null}
          {rubric.length ? (
            <span
              className={cn('text-sm tabular-nums', total === RUBRIC_TOTAL ? 'text-muted-foreground' : 'text-destructive')}
            >
              {t('Jami: {total} / {RUBRIC_TOTAL}', { total, RUBRIC_TOTAL })}
            </span>
          ) : null}
        </div>
        {rubricError ? (
          <p className="text-xs text-destructive" role="alert">
            {rubricError}
          </p>
        ) : null}
      </section>
    </div>
  )
}

// Topshiriq formasidagi bosqichlar va rubrika qoralamalari (ProjectPlanEditor)

export const RUBRIC_TOTAL = 100

export interface StageDraft {
  kind: 'sql' | 'er'
  title: string
  description: string
  /** datetime-local qiymati */
  deadline: string
}

export interface CriterionDraft {
  name: string
  points: string
  description: string
  stage: number | null
}

export function rubricTotal(rubric: CriterionDraft[]) {
  return rubric.reduce((sum, item) => sum + (Number.parseInt(item.points, 10) || 0), 0)
}

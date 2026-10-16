import { useQuery } from '@tanstack/react-query'
import { ArrowRight, CircleCheck } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api } from '@/lib/api'
import { fullName } from '@/lib/auth'
import type { GroupMastery, LearningPath as LearningPathData } from '@/lib/types'

/** O'zlashtirish ko'rsatkichi: bitta rang, qiymat matn bilan ham yoziladi (rang yagona belgi emas) */
function Meter({ value, label }: { value: number; label: string }) {
  return (
    <div
      className="h-2 min-w-0 flex-1 rounded-full bg-muted"
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={value}
    >
      <div className="h-full rounded-full" style={{ width: `${value}%`, background: 'var(--series-1)' }} />
    </div>
  )
}

/** Talaba: mavzular bo'yicha o'zlashtirish va keyingi tavsiya etilgan laboratoriya */
export function LearningPathCard() {
  const path = useQuery({
    queryKey: ['learning-path'],
    queryFn: () => api<LearningPathData>('/labs/recommendations/'),
  })
  if (!path.data?.topics.length) return null
  const { topics, next } = path.data
  return (
    <Card className="mb-4">
      <CardHeader>
        <CardTitle>Mening o'quv yo'lim</CardTitle>
        <CardDescription>
          Har bir mavzu bo'yicha ko'nikmani egallaganingiz ehtimoli: urinishlaringizdan hisoblanadi (Bayesian Knowledge
          Tracing). 95% — mavzu o'zlashtirilgan.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        {next ? (
          <Link
            to={`/labs/${next.id}`}
            className="flex items-center gap-3 rounded-lg border bg-primary/5 p-3 outline-none hover:bg-primary/10 focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            <div className="min-w-0 flex-1">
              <div className="text-xs text-muted-foreground">Keyingi tavsiya</div>
              <div className="font-medium">{next.title}</div>
              <p className="mt-0.5 text-xs text-muted-foreground">{next.reason}</p>
            </div>
            <ArrowRight className="size-5 shrink-0" aria-hidden="true" />
          </Link>
        ) : null}
        <ul className="grid gap-2.5 sm:grid-cols-2">
          {topics.map((topic) => (
            <li key={topic.topic} className="grid gap-1">
              <div className="flex items-baseline justify-between gap-2 text-sm">
                <span className="flex items-center gap-1.5">
                  {topic.label}
                  {topic.mastered ? <CircleCheck className="size-3.5 text-emerald-600" aria-label="o'zlashtirilgan" /> : null}
                </span>
                <span className="text-xs text-muted-foreground tabular-nums">
                  {topic.mastery}% · {topic.solved}/{topic.labs} lab.
                </span>
              </div>
              <Meter value={topic.mastery} label={`${topic.label}: ${topic.mastery}%`} />
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

/** O'qituvchi: guruhdagi har bir talabaning mavzular bo'yicha o'zlashtirishi (jadval ko'rinishida) */
export function GroupMasteryCard({ groupId }: { groupId: string }) {
  const report = useQuery({
    queryKey: ['group-mastery', groupId],
    queryFn: () => api<GroupMastery>(`/labs/recommendations/?group=${groupId}`),
  })
  if (!report.data?.students.length || !report.data.topics.length) return null
  const { topics, students } = report.data
  return (
    <Card>
      <CardHeader>
        <CardTitle>Mavzular bo'yicha o'zlashtirish</CardTitle>
        <CardDescription>
          Bayesian Knowledge Tracing bo'yicha foizlar: kim qaysi mavzuda qiynalayotganini ko'rsatadi. 95% va undan
          yuqori — o'zlashtirilgan, 50% dan past — yordam kerak. Taxminiy ko'rsatkich: baho emas.
        </CardDescription>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Talaba</TableHead>
              {topics.map((topic) => (
                <TableHead key={topic.topic} className="text-right">
                  {topic.label}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {students.map((student) => (
              <TableRow key={student.id}>
                <TableCell className="font-medium">{fullName(student)}</TableCell>
                {topics.map((topic) => {
                  const value = student.mastery[topic.topic]
                  return (
                    <TableCell
                      key={topic.topic}
                      className={`text-right tabular-nums ${value !== undefined && value < 50 ? 'font-semibold' : ''}`}
                    >
                      {value === undefined ? '—' : `${value}%`}
                    </TableCell>
                  )
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BookOpen, Download, FileText, Loader2, Pencil, Plus, Trash2, X } from 'lucide-react'
import { useState, type ChangeEvent, type FormEvent } from 'react'
import { toast } from 'sonner'

import { CheckList } from '@/components/CheckList'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { FormField } from '@/components/FormField'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { api, errorMessage } from '@/lib/api'
import { fullName, useUser } from '@/lib/auth'
import { downloadFile } from '@/lib/download'
import { applyFormError } from '@/lib/forms'
import { formatDateTime, formatFileSize } from '@/lib/format'
import { groupNames, useGroupOptions } from '@/lib/groups'
import type { GroupShort, Material, MaterialFile } from '@/lib/types'

// Backend ham xuddi shu cheklovlarni tekshiradi (learning/validators.py)
const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.pptx', '.png', '.jpg', '.jpeg']
const MAX_FILE_SIZE = 20 * 1024 * 1024
const MATERIAL_FIELDS = ['title', 'text', 'groups'] as const

function checkFile(file: File): string | null {
  const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
  if (!ALLOWED_EXTENSIONS.includes(extension)) return `${file.name}: ruxsat etilmagan fayl turi.`
  if (file.size > MAX_FILE_SIZE) return `${file.name}: hajmi 20 MB dan oshmasligi kerak.`
  if (file.size === 0) return `${file.name}: fayl bo'sh.`
  return null
}

function FileRow({ file, onRemove, removing }: { file: MaterialFile; onRemove?: () => void; removing?: boolean }) {
  const [downloading, setDownloading] = useState(false)

  async function handleDownload() {
    setDownloading(true)
    try {
      await downloadFile(`/materials/files/${file.id}/download/`, file.original_name)
    } catch (error) {
      toast.error(errorMessage(error))
    } finally {
      setDownloading(false)
    }
  }

  return (
    <li className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm">
      <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <span className="min-w-0 flex-1 truncate">{file.original_name}</span>
      <span className="shrink-0 text-xs text-muted-foreground">{formatFileSize(file.size)}</span>
      <Button
        type="button"
        variant="ghost"
        size="icon-lg"
        aria-label={`${file.original_name}: yuklab olish`}
        disabled={downloading}
        onClick={() => void handleDownload()}
      >
        {downloading ? <Loader2 className="animate-spin" /> : <Download />}
      </Button>
      {onRemove ? (
        <Button
          type="button"
          variant="ghost"
          size="icon-lg"
          aria-label={`${file.original_name}: o'chirish`}
          disabled={removing}
          onClick={onRemove}
        >
          <Trash2 />
        </Button>
      ) : null}
    </li>
  )
}

interface MaterialDialogProps {
  material?: Material
  groups: GroupShort[]
  onClose: () => void
}

function MaterialDialog({ material, groups, onClose }: MaterialDialogProps) {
  const queryClient = useQueryClient()
  const [title, setTitle] = useState(material?.title ?? '')
  const [text, setText] = useState(material?.text ?? '')
  const [groupIds, setGroupIds] = useState<number[]>(material?.groups ?? [])
  const [existingFiles, setExistingFiles] = useState<MaterialFile[]>(material?.files ?? [])
  const [newFiles, setNewFiles] = useState<File[]>([])
  const [errors, setErrors] = useState<Record<string, string>>({})

  const removeFile = useMutation({
    mutationFn: (file: MaterialFile) => api(`/materials/files/${file.id}/`, { method: 'DELETE' }),
    onSuccess: (_data, file) => {
      setExistingFiles((files) => files.filter((item) => item.id !== file.id))
      void queryClient.invalidateQueries({ queryKey: ['materials'] })
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  const save = useMutation({
    mutationFn: async () => {
      const body = { title: title.trim(), text, groups: groupIds }
      const saved = material
        ? await api<Material>(`/materials/${material.id}/`, { method: 'PATCH', body })
        : await api<Material>('/materials/', { method: 'POST', body })
      // Fayllar material saqlangandan keyin birma-bir yuklanadi
      const failed: string[] = []
      for (const file of newFiles) {
        const form = new FormData()
        form.append('file', file)
        try {
          await api(`/materials/${saved.id}/files/`, { method: 'POST', body: form })
        } catch (error) {
          failed.push(`${file.name}: ${errorMessage(error)}`)
        }
      }
      return failed
    },
    onSuccess: (failed) => {
      void queryClient.invalidateQueries({ queryKey: ['materials'] })
      if (failed.length) {
        toast.warning(`Material saqlandi, lekin ba'zi fayllar yuklanmadi. ${failed.join(' ')}`)
      } else {
        toast.success(material ? 'Material saqlandi' : "Material qo'shildi")
      }
      onClose()
    },
    onError: (error) => applyFormError(error, MATERIAL_FIELDS, setErrors),
  })

  function handleFilesPicked(event: ChangeEvent<HTMLInputElement>) {
    const picked = Array.from(event.target.files ?? [])
    event.target.value = ''
    const accepted: File[] = []
    for (const file of picked) {
      const problem = checkFile(file)
      if (problem) toast.error(problem)
      else accepted.push(file)
    }
    setNewFiles((files) => [...files, ...accepted])
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!groupIds.length) {
      setErrors({ groups: 'Kamida bitta guruh tanlang.' })
      return
    }
    setErrors({})
    save.mutate()
  }

  return (
    <Dialog open onOpenChange={(open) => (!open && !save.isPending ? onClose() : undefined)}>
      <DialogContent className="max-h-[92svh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{material ? 'Materialni tahrirlash' : 'Yangi material'}</DialogTitle>
          <DialogDescription>Materialni faqat tanlangan guruhlar talabalari ko'radi.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="grid gap-4" noValidate>
          <FormField id="material_title" label="Sarlavha" error={errors.title}>
            <Input
              id="material_title"
              className="h-10"
              aria-invalid={Boolean(errors.title)}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </FormField>
          <FormField id="material_text" label="Matn" error={errors.text} hint="Ixtiyoriy.">
            <Textarea
              id="material_text"
              className="max-h-64 min-h-28"
              aria-invalid={Boolean(errors.text)}
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
          </FormField>
          <FormField id="material_groups" label="Guruhlar" error={errors.groups}>
            <CheckList
              idPrefix="material-group"
              options={groups.map((group) => ({ id: group.id, label: group.name }))}
              selected={groupIds}
              onChange={setGroupIds}
              emptyText="Sizga hali guruh biriktirilmagan. Administratorga murojaat qiling."
              invalid={Boolean(errors.groups)}
            />
          </FormField>
          <FormField id="material_files" label="Fayllar" hint="PDF, DOCX, PPTX, PNG yoki JPG; har biri 20 MB gacha.">
            <div className="grid gap-2">
              {existingFiles.length ? (
                <ul className="grid gap-2">
                  {existingFiles.map((file) => (
                    <FileRow
                      key={file.id}
                      file={file}
                      removing={removeFile.isPending}
                      onRemove={() => removeFile.mutate(file)}
                    />
                  ))}
                </ul>
              ) : null}
              {newFiles.length ? (
                <ul className="grid gap-2">
                  {newFiles.map((file, index) => (
                    <li key={`${file.name}-${index}`} className="flex items-center gap-2 rounded-lg border border-dashed px-3 py-2 text-sm">
                      <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                      <span className="min-w-0 flex-1 truncate">{file.name}</span>
                      <span className="shrink-0 text-xs text-muted-foreground">{formatFileSize(file.size)}</span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-lg"
                        aria-label={`${file.name}: ro'yxatdan olib tashlash`}
                        onClick={() => setNewFiles((files) => files.filter((_, itemIndex) => itemIndex !== index))}
                      >
                        <X />
                      </Button>
                    </li>
                  ))}
                </ul>
              ) : null}
              <Input
                id="material_files"
                type="file"
                multiple
                className="h-10"
                accept={ALLOWED_EXTENSIONS.join(',')}
                onChange={handleFilesPicked}
              />
            </div>
          </FormField>
          <DialogFooter>
            <Button type="button" variant="outline" size="lg" disabled={save.isPending} onClick={onClose}>
              Bekor qilish
            </Button>
            <Button type="submit" size="lg" disabled={save.isPending || !title.trim()}>
              {save.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
              Saqlash
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function MaterialsPage() {
  const user = useUser()
  const queryClient = useQueryClient()
  const isStaff = user.role !== 'student'
  const { groups } = useGroupOptions()
  const [editing, setEditing] = useState<Material | 'new' | null>(null)
  const [deleting, setDeleting] = useState<Material | null>(null)

  const materials = useQuery({ queryKey: ['materials'], queryFn: () => api<Material[]>('/materials/') })

  const remove = useMutation({
    mutationFn: (material: Material) => api(`/materials/${material.id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      toast.success("Material o'chirildi")
      void queryClient.invalidateQueries({ queryKey: ['materials'] })
      setDeleting(null)
    },
    onError: (error) => {
      toast.error(errorMessage(error))
      setDeleting(null)
    },
  })

  const addButton = isStaff ? (
    <Button size="lg" onClick={() => setEditing('new')}>
      <Plus aria-hidden="true" />
      Material qo'shish
    </Button>
  ) : null

  let content
  if (materials.isPending) {
    content = <ListSkeleton />
  } else if (materials.isError) {
    content = <ErrorState error={materials.error} onRetry={() => void materials.refetch()} />
  } else if (!materials.data.length) {
    content = (
      <EmptyState
        icon={BookOpen}
        title="Hali material yo'q"
        description={
          isStaff
            ? "Talabalar uchun birinchi o'quv materialini qo'shing."
            : user.group
              ? "O'qituvchi material qo'shganda shu yerda ko'rinadi."
              : 'Siz hali guruhga biriktirilmagansiz. Administratorga murojaat qiling.'
        }
        action={addButton}
      />
    )
  } else {
    content = (
      <div className="grid gap-4">
        {materials.data.map((material) => (
          <Card key={material.id}>
            <CardHeader>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <CardTitle>{material.title}</CardTitle>
                  <CardDescription className="mt-1">
                    {fullName(material.author)} · {formatDateTime(material.created_at)}
                    {isStaff ? ` · Guruhlar: ${groupNames(material.groups, groups)}` : null}
                  </CardDescription>
                </div>
                {isStaff ? (
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="icon-lg"
                      aria-label={`${material.title}: tahrirlash`}
                      onClick={() => setEditing(material)}
                    >
                      <Pencil />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-lg"
                      aria-label={`${material.title}: o'chirish`}
                      onClick={() => setDeleting(material)}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                ) : null}
              </div>
            </CardHeader>
            {material.text || material.files.length ? (
              <CardContent className="grid gap-3">
                {material.text ? <p className="text-sm whitespace-pre-wrap">{material.text}</p> : null}
                {material.files.length ? (
                  <ul className="grid gap-2 sm:grid-cols-2">
                    {material.files.map((file) => (
                      <FileRow key={file.id} file={file} />
                    ))}
                  </ul>
                ) : null}
              </CardContent>
            ) : null}
          </Card>
        ))}
      </div>
    )
  }

  return (
    <>
      <PageHeader
        title="Materiallar"
        description={isStaff ? "Guruhlar uchun o'quv materiallari." : "Guruhingizga berilgan o'quv materiallari."}
        actions={materials.data?.length ? addButton : null}
      />
      {content}

      {editing ? (
        <MaterialDialog
          key={editing === 'new' ? 'new' : editing.id}
          material={editing === 'new' ? undefined : editing}
          groups={groups}
          onClose={() => setEditing(null)}
        />
      ) : null}
      <ConfirmDialog
        open={Boolean(deleting)}
        title="Materialni o'chirish"
        description={deleting ? `«${deleting.title}» va unga biriktirilgan barcha fayllar o'chiriladi. Bu amalni qaytarib bo'lmaydi.` : ''}
        confirmLabel="O'chirish"
        pending={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting)}
        onClose={() => setDeleting(null)}
      />
    </>
  )
}

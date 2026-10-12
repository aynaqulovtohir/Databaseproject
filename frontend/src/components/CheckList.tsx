import { Checkbox } from '@/components/ui/checkbox'

interface CheckListProps {
  /** Har bir katakcha id'si uchun old qo'shimcha */
  idPrefix: string
  options: { id: number; label: string }[]
  selected: number[]
  onChange: (selected: number[]) => void
  emptyText: string
  invalid?: boolean
}

/** Bir nechta variantni tanlash (guruhlar, o'qituvchilar). */
export function CheckList({ idPrefix, options, selected, onChange, emptyText, invalid }: CheckListProps) {
  if (!options.length) return <p className="text-sm text-muted-foreground">{emptyText}</p>

  function toggle(id: number, checked: boolean) {
    onChange(checked ? [...selected, id] : selected.filter((item) => item !== id))
  }

  return (
    <div
      className="grid max-h-44 gap-2 overflow-y-auto rounded-lg border p-3 aria-invalid:border-destructive sm:grid-cols-2"
      aria-invalid={invalid}
    >
      {options.map((option) => (
        <label key={option.id} htmlFor={`${idPrefix}-${option.id}`} className="flex items-center gap-2 text-sm">
          <Checkbox
            id={`${idPrefix}-${option.id}`}
            checked={selected.includes(option.id)}
            onCheckedChange={(checked) => toggle(option.id, checked === true)}
          />
          <span className="min-w-0 truncate">{option.label}</span>
        </label>
      ))}
    </div>
  )
}

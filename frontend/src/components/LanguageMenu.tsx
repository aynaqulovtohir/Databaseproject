import { Languages } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { LANGS, setLang, t, useLang, type Lang } from '@/lib/i18n'

/** Interfeys tili: UZ / EN / RU. Tanlanganda butun tizim shu tilga o'tadi. */
export function LanguageMenu() {
  const lang = useLang()
  const active = LANGS.find((item) => item.value === lang)!
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="lg"
          className="gap-1.5 px-2 font-semibold text-heading"
          aria-label={t('Interfeys tili: {lang}', { lang: active.label })}
          title={t('Til')}
        >
          <Languages className="size-5" aria-hidden="true" />
          <span className="text-xs">{active.short}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-44">
        <DropdownMenuLabel>{t('Til')}</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={lang} onValueChange={(value) => void setLang(value as Lang)}>
          {LANGS.map((item) => (
            <DropdownMenuRadioItem key={item.value} value={item.value} lang={item.value}>
              <span className="w-7 text-xs font-semibold text-muted-foreground">{item.short}</span>
              {item.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

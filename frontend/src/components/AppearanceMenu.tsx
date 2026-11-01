import { Palette } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { setTextSize, setTheme, TEXT_SIZES, THEMES, useTextSize, useTheme, type TextSize, type Theme } from '@/lib/appearance'

/** Mavzu va yozuv o'lchami. Tanlaganda menyu yopilmaydi: natija darhol ko'rinadi. */
export function AppearanceMenu() {
  const theme = useTheme()
  const textSize = useTextSize()
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-lg" aria-label="Ko'rinish: mavzu va yozuv o'lchami" title="Ko'rinish">
          <Palette className="size-5" aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="max-h-[80svh] w-52 overflow-y-auto">
        <DropdownMenuLabel>Mavzu</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={theme} onValueChange={(value) => setTheme(value as Theme)}>
          {THEMES.map((item) => (
            <DropdownMenuRadioItem key={item.value} value={item.value} onSelect={(event) => event.preventDefault()}>
              {item.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuLabel>Yozuv o'lchami</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={textSize} onValueChange={(value) => setTextSize(value as TextSize)}>
          {TEXT_SIZES.map((item) => (
            <DropdownMenuRadioItem key={item.value} value={item.value} onSelect={(event) => event.preventDefault()}>
              {item.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

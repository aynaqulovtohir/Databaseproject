import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <p className="text-5xl font-semibold text-muted-foreground">404</p>
      <p className="text-sm text-muted-foreground">Bunday sahifa topilmadi yoki sizda unga ruxsat yo'q.</p>
      <Button asChild size="lg">
        <Link to="/">Bosh sahifaga qaytish</Link>
      </Button>
    </div>
  )
}

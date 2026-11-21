import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'

/** NiceAdmin "pages-error-404" uslubida; rasm shablondan (public/not-found.svg). */
export function NotFoundPage() {
  return (
    <section className="flex flex-col items-center px-4 py-8 text-center">
      <p className="font-heading text-[7rem] leading-[1] font-bold text-primary sm:text-[11.25rem]">404</p>
      <h1 className="mt-2 mb-6 font-heading text-xl font-bold text-heading sm:text-2xl">
        Bunday sahifa topilmadi yoki sizda unga ruxsat yo'q.
      </h1>
      <Button asChild size="lg" className="bg-[#51678f] px-8 text-white hover:bg-[#3e4f6f]">
        <Link to="/">Bosh sahifaga qaytish</Link>
      </Button>
      <img src="/not-found.svg" alt="" className="mt-8 w-full max-w-md lg:max-w-xl" />
    </section>
  )
}

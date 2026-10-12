import { ApiError, apiFetch } from '@/lib/api'

/**
 * Faylni token bilan yuklab oladi. Oddiy havola ishlamaydi,
 * chunki backend har safar Authorization sarlavhasini tekshiradi.
 */
export async function downloadFile(path: string, filename: string) {
  const response = await apiFetch(path)
  if (!response.ok) {
    throw new ApiError(response.status, null, "Faylni yuklab bo'lmadi.")
  }
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

import { toast } from 'sonner'

import { errorMessage, fieldErrors } from '@/lib/api'

/**
 * Backend xatosini formaga joylaydi. Formada ko'rsatib bo'lmaydigan xato
 * (masalan, `detail` yoki notanish maydon) bildirishnoma sifatida chiqadi.
 */
export function applyFormError(
  error: unknown,
  knownFields: readonly string[],
  setErrors: (errors: Record<string, string>) => void,
) {
  const fields = fieldErrors(error)
  setErrors(fields)
  const unknown = Object.keys(fields).find((field) => !knownFields.includes(field))
  if (unknown) toast.error(fields[unknown])
  else if (!Object.keys(fields).length) toast.error(errorMessage(error))
}

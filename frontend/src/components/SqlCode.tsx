/** SQL kodni o'zgarmas ko'rinishda ko'rsatadi (uzun qatorlar gorizontal aylanadi). */
export function SqlCode({ code }: { code: string }) {
  return (
    <pre className="max-h-[28rem] overflow-auto rounded-lg border bg-muted/50 p-3 font-mono text-xs leading-relaxed">
      <code>{code}</code>
    </pre>
  )
}

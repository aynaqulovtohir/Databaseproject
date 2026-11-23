// Tarjima lug'atlarini tekshiradi: koddagi har bir t('...') kaliti en va ru lug'atlarida bo'lishi kerak.
//   node scripts/i18n-check.mjs            — yetishmayotgan/ortiqcha kalitlarni ko'rsatadi (xato bo'lsa exit 1)
//   node scripts/i18n-check.mjs --keys     — koddagi barcha kalitlarni JSON qilib chiqaradi
import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'

const root = path.resolve(import.meta.dirname, '..')
const LANGS = ['en', 'ru']

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) return entry.name === 'locales' ? [] : walk(full)
    return /\.(tsx?)$/.test(entry.name) ? [full] : []
  })
}

const keys = new Map()
const dynamic = []
for (const file of walk(path.join(root, 'src'))) {
  const source = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true)
  const where = (node) => `${path.relative(root, file)}:${source.getLineAndCharacterOfPosition(node.getStart()).line + 1}`
  const add = (text, node) => {
    if (/[A-Za-z]/.test(text) && !keys.has(text)) keys.set(text, where(node))
  }
  // t(...) argumenti: literal yoki shart ifodasining literal tarmoqlari
  const literals = (node) => {
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return [node]
    if (ts.isParenthesizedExpression(node)) return literals(node.expression)
    if (ts.isConditionalExpression(node)) {
      const branches = [literals(node.whenTrue), literals(node.whenFalse)]
      return branches.every(Boolean) ? branches.flat() : null
    }
    return null
  }
  // localized({...}) ichidagi matnlar: texnik maydonlardan tashqari barcha satr qiymatlar
  const SKIP = new Set(['value', 'key', 'id', 'to', 'className', 'kind', 'tone', 'color'])
  const collectLocalized = (node) => {
    if (ts.isPropertyAssignment(node) && SKIP.has(node.name.getText(source))) return
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
      if (!(ts.isPropertyAssignment(node.parent) && node.parent.name === node)) add(node.text, node)
      return
    }
    ts.forEachChild(node, collectLocalized)
  }
  const visit = (node) => {
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression)) {
      const name = node.expression.text
      const arg = node.arguments[0]
      if (name === 't' && arg) {
        const found = literals(arg)
        if (found) found.forEach((item) => add(item.text, item))
        else dynamic.push(where(node))
      }
      if (name === 'localized' && arg) collectLocalized(arg)
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
}

if (process.argv.includes('--keys')) {
  console.log(JSON.stringify([...keys.keys()], null, 1))
  process.exit(0)
}

// Dinamik kalitlar (serverdan kelgan matn, nav/mavzu yorliqlari) tekshirilmaydi: ular boshqa joyda t() siz yozilgan
if (process.argv.includes('--dynamic')) dynamic.forEach((item) => console.log(`dinamik: ${item}`))

let failed = false
for (const lang of LANGS) {
  const dir = path.join(root, 'src/locales', lang)
  const dict = {}
  for (const name of fs.readdirSync(dir).filter((n) => n.endsWith('.json'))) {
    Object.assign(dict, JSON.parse(fs.readFileSync(path.join(dir, name), 'utf8')))
  }
  const missing = [...keys.keys()].filter((key) => !dict[key])
  // Kalitdagi {nom} o'rinlari tarjimada ham bo'lishi kerak
  const badParams = [...keys.keys()].filter((key) => {
    if (!dict[key]) return false
    const names = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(',')
    return names(key) !== names(dict[key])
  })
  // Koddan o'chirilgan matnlar lug'atda qolib ketmasin
  const unused = Object.keys(dict).filter((key) => !keys.has(key))
  console.log(
    `${lang}: ${keys.size} kalit, ${missing.length} ta tarjimasiz, ${badParams.length} ta o'rin xatosi, ${unused.length} ta ortiqcha`,
  )
  for (const key of unused.slice(0, 30)) console.log(`  ortiqcha: ${JSON.stringify(key)}`)
  for (const key of missing.slice(0, 30)) console.log(`  tarjimasiz: ${JSON.stringify(key)} (${keys.get(key)})`)
  for (const key of badParams) console.log(`  o'rinlar mos emas: ${JSON.stringify(key)}`)
  if (missing.length || badParams.length || unused.length) failed = true
}
process.exit(failed ? 1 : 0)

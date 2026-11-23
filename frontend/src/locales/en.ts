// Lug'at: kalit — koddagi o'zbekcha asl matn, qiymat — tarjimasi. Bo'limlar en/*.json fayllarida.
// Bo'sh qiymat "hali tarjima qilinmagan" degani: o'zbekcha matn ko'rsatiladi.
const parts = import.meta.glob<Record<string, string>>('./en/*.json', { eager: true, import: 'default' })

const dictionary: Record<string, string> = Object.assign({}, ...Object.values(parts))
export default dictionary

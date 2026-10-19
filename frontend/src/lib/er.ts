import type { ErDiagram } from '@/lib/types'

export const EMPTY_DIAGRAM: ErDiagram = { entities: [], relationships: [] }

/** Yuborishdan oldin: bo'sh nomli atributlar tashlab yuboriladi, nomlardagi chetki bo'sh joylar olinadi */
export function cleanDiagram(diagram: ErDiagram): ErDiagram {
  return {
    entities: diagram.entities.map((entity) => ({
      id: entity.id,
      name: entity.name.trim(),
      x: entity.x,
      y: entity.y,
      attributes: entity.attributes
        .filter((attribute) => attribute.name.trim())
        .map((attribute) => ({ name: attribute.name.trim(), key: attribute.key })),
    })),
    relationships: diagram.relationships.map((relationship) => ({
      id: relationship.id,
      name: relationship.name.trim(),
      source: relationship.source,
      target: relationship.target,
      source_card: relationship.source_card,
      target_card: relationship.target_card,
    })),
  }
}

/** Serverdagi nom solishtirish bilan bir xil (labs/er.py normalize) */
function normalizeName(name: string) {
  return name.replace(/[ʻʼ‘’`´]/g, "'").trim().toLowerCase().replace(/[\s_-]+/g, '_')
}

/**
 * Chizish jarayonini yozish uchun oraliq holat: chizilayotgan diagramma hali to'liq bo'lmasligi mumkin, shuning uchun
 * nomsiz obyektlar va takrorlangan nomlar tashlab yuboriladi (server faqat to'g'ri tuzilgan diagrammani qabul qiladi).
 */
export function snapshotDiagram(diagram: ErDiagram): ErDiagram {
  const clean = cleanDiagram(diagram)
  const names = new Set<string>()
  const entities = clean.entities.filter((entity) => {
    const name = normalizeName(entity.name)
    if (!name || names.has(name)) return false
    names.add(name)
    return true
  })
  const ids = new Set(entities.map((entity) => entity.id))
  return {
    entities: entities.map((entity) => {
      const attributes = new Set<string>()
      return {
        ...entity,
        attributes: entity.attributes.filter((attribute) => {
          const name = normalizeName(attribute.name)
          if (attributes.has(name)) return false
          attributes.add(name)
          return true
        }),
      }
    }),
    relationships: clean.relationships.filter(
      (relationship) => ids.has(relationship.source) && ids.has(relationship.target),
    ),
  }
}

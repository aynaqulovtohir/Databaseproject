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

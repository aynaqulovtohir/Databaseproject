import '@xyflow/react/dist/style.css'

import {
  Background,
  BaseEdge,
  ConnectionMode,
  Controls,
  EdgeLabelRenderer,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useInternalNode,
  useNodesState,
  useReactFlow,
  type Connection,
  type Edge,
  type EdgeProps,
  type FinalConnectionState,
  type InternalNode,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import { KeyRound, Link2, Plus, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import type { ErAttribute, ErCardinality, ErDiagram, ErEntity, ErKey, ErRelationship, ErStatus } from '@/lib/types'

const MAX_NAME_LENGTH = 64
const MAX_ENTITIES = 40
const MAX_ATTRIBUTES = 40

type EntityNode = Node<{ entity: ErEntity }, 'entity'>
type RelationshipEdge = Edge<{ relationship: ErRelationship }, 'relationship'>

function newId(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`
}

const STATUS_BORDER: Record<ErStatus, string> = {
  ok: 'border-border',
  added: 'border-emerald-500 ring-2 ring-emerald-200',
  removed: 'border-red-400 border-dashed opacity-60',
  changed: 'border-amber-500 ring-2 ring-amber-200',
}

const STATUS_EDGE: Record<ErStatus, string> = {
  ok: '#64748b',
  added: '#059669',
  removed: '#dc2626',
  changed: '#d97706',
}

const KEY_LABELS: Record<ErKey, string> = { pk: 'PK', fk: 'FK', '': '' }

// ---------- Obyekt (tugun) ----------

function AttributeRow({ attribute }: { attribute: ErAttribute }) {
  const status = attribute.status ?? 'ok'
  return (
    <li
      className={cn(
        'flex items-center gap-1.5 px-2 py-0.5 text-xs',
        status === 'added' && 'bg-emerald-50 text-emerald-800',
        status === 'removed' && 'text-red-700 line-through',
        status === 'changed' && 'bg-amber-50 text-amber-900',
      )}
    >
      <span className="w-5 shrink-0 font-semibold text-muted-foreground">{KEY_LABELS[attribute.key]}</span>
      <span className={cn(attribute.key === 'pk' && 'underline')}>{attribute.name}</span>
      {status === 'added' ? <span className="ml-auto">+</span> : null}
    </li>
  )
}

const HANDLE_CLASS = '!size-2.5 !border-2 !border-background !bg-primary opacity-0 transition-opacity group-hover:opacity-100'

function EntityNodeView({ data, selected }: NodeProps<EntityNode>) {
  const { entity } = data
  const status = entity.status ?? 'ok'
  return (
    <div
      className={cn(
        'group min-w-36 rounded-lg border-2 bg-card text-card-foreground shadow-sm',
        STATUS_BORDER[status],
        selected && 'outline-2 outline-offset-2 outline-primary',
      )}
    >
      {/* Bog'lanish chizish uchun to'rt tomondagi nuqtalar (Loose rejimda har biri ikki yo'nalishda ishlaydi) */}
      <Handle type="source" position={Position.Top} id="top" className={HANDLE_CLASS} />
      <Handle type="source" position={Position.Right} id="right" className={HANDLE_CLASS} />
      <Handle type="source" position={Position.Bottom} id="bottom" className={HANDLE_CLASS} />
      <Handle type="source" position={Position.Left} id="left" className={HANDLE_CLASS} />
      <div className="rounded-t-md border-b bg-muted px-2 py-1 text-center text-sm font-semibold">{entity.name}</div>
      {entity.attributes.length ? (
        <ul className="py-1">
          {entity.attributes.map((attribute, index) => (
            <AttributeRow key={index} attribute={attribute} />
          ))}
        </ul>
      ) : (
        <p className="px-2 py-1 text-xs text-muted-foreground italic">atribut yo'q</p>
      )}
    </div>
  )
}

// ---------- Bog'lanish (chiziq) ----------

/** Tugun markazidan boshqa nuqtaga tortilgan chiziqning tugun chegarasini kesib o'tgan nuqtasi */
function borderPoint(node: InternalNode, toward: { x: number; y: number }) {
  const width = node.measured.width ?? 0
  const height = node.measured.height ?? 0
  const center = {
    x: node.internals.positionAbsolute.x + width / 2,
    y: node.internals.positionAbsolute.y + height / 2,
  }
  const dx = toward.x - center.x
  const dy = toward.y - center.y
  if (!dx && !dy) return center
  const scale = 1 / Math.max(Math.abs(dx) / (width / 2 || 1), Math.abs(dy) / (height / 2 || 1))
  return { x: center.x + dx * scale, y: center.y + dy * scale }
}

function nodeCenter(node: InternalNode) {
  return {
    x: node.internals.positionAbsolute.x + (node.measured.width ?? 0) / 2,
    y: node.internals.positionAbsolute.y + (node.measured.height ?? 0) / 2,
  }
}

function CardLabel({ x, y, text, color }: { x: number; y: number; text: string; color: string }) {
  return (
    <div
      className="nodrag nopan pointer-events-none absolute rounded bg-background px-1 text-xs font-bold"
      style={{ transform: `translate(-50%, -50%) translate(${x}px, ${y}px)`, color }}
    >
      {text}
    </div>
  )
}

function RelationshipEdgeView({ id, source, target, data, selected }: EdgeProps<RelationshipEdge>) {
  const sourceNode = useInternalNode(source)
  const targetNode = useInternalNode(target)
  if (!sourceNode || !targetNode || !data) return null
  const { relationship } = data
  const status = relationship.status ?? 'ok'
  const color = selected ? 'var(--color-primary)' : STATUS_EDGE[status]
  const style = { stroke: color, strokeWidth: selected ? 2.5 : 1.75, strokeDasharray: status === 'removed' ? '6 4' : undefined }

  let path: string
  let start: { x: number; y: number }
  let end: { x: number; y: number }
  let middle: { x: number; y: number }
  if (source === target) {
    // O'z-o'ziga bog'lanish (masalan, xodim — rahbar): tugunning o'ng tomonida halqa
    const width = sourceNode.measured.width ?? 0
    const top = sourceNode.internals.positionAbsolute
    start = { x: top.x + width, y: top.y + 14 }
    end = { x: top.x + width, y: top.y + 44 }
    path = `M ${start.x} ${start.y} C ${start.x + 70} ${start.y - 30}, ${end.x + 70} ${end.y + 30}, ${end.x} ${end.y}`
    middle = { x: start.x + 55, y: (start.y + end.y) / 2 }
  } else {
    start = borderPoint(sourceNode, nodeCenter(targetNode))
    end = borderPoint(targetNode, nodeCenter(sourceNode))
    path = `M ${start.x} ${start.y} L ${end.x} ${end.y}`
    middle = { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 }
  }
  // Kardinallik belgisi chiziq uchidan biroz ichkarida
  const along = (from: { x: number; y: number }, to: { x: number; y: number }) => {
    const length = Math.hypot(to.x - from.x, to.y - from.y) || 1
    const shift = Math.min(18, length / 4)
    return { x: from.x + ((to.x - from.x) / length) * shift, y: from.y + ((to.y - from.y) / length) * shift }
  }
  const sourceLabel = source === target ? { x: start.x + 14, y: start.y - 10 } : along(start, end)
  const targetLabel = source === target ? { x: end.x + 14, y: end.y + 10 } : along(end, start)

  return (
    <>
      <BaseEdge id={id} path={path} style={style} interactionWidth={18} />
      <EdgeLabelRenderer>
        <CardLabel x={sourceLabel.x} y={sourceLabel.y} text={relationship.source_card} color={color} />
        <CardLabel x={targetLabel.x} y={targetLabel.y} text={relationship.target_card} color={color} />
        {relationship.name ? (
          <div
            className="nodrag nopan pointer-events-none absolute rounded-full border bg-amber-50 px-2 py-0.5 text-[11px] text-amber-950"
            style={{ transform: `translate(-50%, -50%) translate(${middle.x}px, ${middle.y}px)`, borderColor: color }}
          >
            {relationship.name}
          </div>
        ) : null}
      </EdgeLabelRenderer>
    </>
  )
}

const NODE_TYPES = { entity: EntityNodeView }
const EDGE_TYPES = { relationship: RelationshipEdgeView }

function toNode(entity: ErEntity, previous?: EntityNode): EntityNode {
  return {
    ...previous,
    id: entity.id,
    type: 'entity',
    position: { x: entity.x, y: entity.y },
    data: { entity },
  }
}

// ---------- Tahrirlash paneli ----------

function EntityPanel({
  entity,
  onChange,
  onDelete,
}: {
  entity: ErEntity
  onChange: (entity: ErEntity) => void
  onDelete: () => void
}) {
  function updateAttribute(index: number, patch: Partial<ErAttribute>) {
    onChange({
      ...entity,
      attributes: entity.attributes.map((attribute, position) => (position === index ? { ...attribute, ...patch } : attribute)),
    })
  }

  return (
    <div className="grid gap-3">
      <div className="grid gap-1.5">
        <label htmlFor="er-entity-name" className="text-sm font-medium">
          Obyekt nomi
        </label>
        <Input
          id="er-entity-name"
          value={entity.name}
          maxLength={MAX_NAME_LENGTH}
          onChange={(event) => onChange({ ...entity, name: event.target.value })}
        />
      </div>
      <div className="grid gap-1.5">
        <span className="text-sm font-medium">Atributlar</span>
        {entity.attributes.map((attribute, index) => (
          <div key={index} className="flex items-center gap-1.5">
            <Input
              aria-label={`${index + 1}-atribut nomi`}
              value={attribute.name}
              maxLength={MAX_NAME_LENGTH}
              className="h-8 min-w-0 flex-1 text-sm"
              onChange={(event) => updateAttribute(index, { name: event.target.value })}
            />
            <select
              aria-label={`${attribute.name || `${index + 1}-atribut`} kaliti`}
              className="h-8 rounded-md border bg-background px-1 text-xs"
              value={attribute.key}
              onChange={(event) => updateAttribute(index, { key: event.target.value as ErKey })}
            >
              <option value="">—</option>
              <option value="pk">PK</option>
              <option value="fk">FK</option>
            </select>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label={`«${attribute.name}» atributini o'chirish`}
              onClick={() => onChange({ ...entity, attributes: entity.attributes.filter((_, position) => position !== index) })}
            >
              <Trash2 aria-hidden="true" />
            </Button>
          </div>
        ))}
        <Button
          type="button"
          variant="outline"
          disabled={entity.attributes.length >= MAX_ATTRIBUTES}
          onClick={() => onChange({ ...entity, attributes: [...entity.attributes, { name: '', key: '' }] })}
        >
          <Plus aria-hidden="true" />
          Atribut qo'shish
        </Button>
        <p className="text-xs text-muted-foreground">
          <KeyRound className="mr-1 inline size-3" aria-hidden="true" />
          PK — asosiy kalit, FK — tashqi kalit (ixtiyoriy: bog'lanish uni ifodalaydi).
        </p>
      </div>
      <Button type="button" variant="destructive" onClick={onDelete}>
        <Trash2 aria-hidden="true" />
        Obyektni o'chirish
      </Button>
    </div>
  )
}

function CardinalitySelect({
  id,
  label,
  value,
  onChange,
}: {
  id: string
  label: string
  value: ErCardinality
  onChange: (value: ErCardinality) => void
}) {
  return (
    <div className="grid gap-1">
      <label htmlFor={id} className="text-xs text-muted-foreground">
        {label}
      </label>
      <select
        id={id}
        className="h-8 rounded-md border bg-background px-2 text-sm"
        value={value}
        onChange={(event) => onChange(event.target.value as ErCardinality)}
      >
        <option value="1">1 (bitta)</option>
        <option value="N">N (ko'p)</option>
      </select>
    </div>
  )
}

function RelationshipPanel({
  relationship,
  names,
  onChange,
  onDelete,
}: {
  relationship: ErRelationship
  names: Record<string, string>
  onChange: (relationship: ErRelationship) => void
  onDelete: () => void
}) {
  const source = names[relationship.source] || '?'
  const target = names[relationship.target] || '?'
  return (
    <div className="grid gap-3">
      <p className="text-sm">
        <span className="font-medium">{source}</span> — <span className="font-medium">{target}</span>
      </p>
      <div className="grid gap-1.5">
        <label htmlFor="er-relationship-name" className="text-sm font-medium">
          Bog'lanish nomi
        </label>
        <Input
          id="er-relationship-name"
          placeholder="masalan: o'qiydi"
          value={relationship.name}
          maxLength={MAX_NAME_LENGTH}
          onChange={(event) => onChange({ ...relationship, name: event.target.value })}
        />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <CardinalitySelect
          id="er-source-card"
          label={`«${source}» tomonida`}
          value={relationship.source_card}
          onChange={(value) => onChange({ ...relationship, source_card: value })}
        />
        <CardinalitySelect
          id="er-target-card"
          label={`«${target}» tomonida`}
          value={relationship.target_card}
          onChange={(value) => onChange({ ...relationship, target_card: value })}
        />
      </div>
      <p className="text-xs text-muted-foreground">
        Masalan, «Talaba» tomonida N va «Guruh» tomonida 1: bitta guruhda ko'p talaba, har bir talaba bitta guruhda.
      </p>
      <Button type="button" variant="destructive" onClick={onDelete}>
        <Trash2 aria-hidden="true" />
        Bog'lanishni o'chirish
      </Button>
    </div>
  )
}

// ---------- Muharrir ----------

interface ErEditorProps {
  value: ErDiagram
  /** Berilmasa — faqat ko'rish rejimi */
  onChange?: (diagram: ErDiagram) => void
  className?: string
}

function ErEditorInner({ value, onChange, className }: ErEditorProps) {
  const readOnly = !onChange
  const { fitView } = useReactFlow()
  const [nodes, setNodes, onNodesChange] = useNodesState<EntityNode>(value.entities.map((entity) => toNode(entity)))
  const [selected, setSelected] = useState<{ kind: 'entity' | 'relationship'; id: string } | null>(null)

  // Diagramma tashqaridan o'zgarganda tugunlar yangilanadi (o'lchami va tanlanganligi saqlanadi)
  useEffect(() => {
    setNodes((current) => {
      const byId = new Map(current.map((node) => [node.id, node]))
      return value.entities.map((entity) => toNode(entity, byId.get(entity.id)))
    })
  }, [value.entities, setNodes])

  const edges = useMemo<RelationshipEdge[]>(
    () =>
      value.relationships.map((relationship) => ({
        id: relationship.id,
        type: 'relationship',
        source: relationship.source,
        target: relationship.target,
        data: { relationship },
        selected: selected?.kind === 'relationship' && selected.id === relationship.id,
      })),
    [value.relationships, selected],
  )

  const names = useMemo(
    () => Object.fromEntries(value.entities.map((entity) => [entity.id, entity.name])),
    [value.entities],
  )

  function update(patch: Partial<ErDiagram>) {
    onChange?.({ ...value, ...patch })
  }

  function addEntity() {
    const index = value.entities.length
    // Uch ustunli to'r, qo'shni ustunlar biroz pastga surilgan: chiziqlar obyektlar ustidan kamroq o'tadi
    const entity: ErEntity = {
      id: newId('e'),
      name: `Obyekt ${index + 1}`,
      x: 40 + (index % 3) * 300,
      y: 40 + Math.floor(index / 3) * 260 + (index % 3 === 1 ? 120 : 0),
      attributes: [{ name: 'id', key: 'pk' }],
    }
    update({ entities: [...value.entities, entity] })
    setSelected({ kind: 'entity', id: entity.id })
    // Yangi obyekt ko'rinadigan maydonga sig'ishi uchun (u o'lchangandan keyin)
    window.setTimeout(() => void fitView({ padding: 0.2, maxZoom: 1.1, duration: 200 }), 50)
  }

  function removeEntity(id: string) {
    update({
      entities: value.entities.filter((entity) => entity.id !== id),
      relationships: value.relationships.filter((item) => item.source !== id && item.target !== id),
    })
    setSelected(null)
  }

  /** Chiziq nuqtaga emas, obyektning o'ziga tashlanganda ham bog'lanish yaratiladi */
  function connectEnd(event: MouseEvent | TouchEvent, state: FinalConnectionState) {
    if (state.isValid || !state.fromNode) return
    const point = 'changedTouches' in event ? event.changedTouches[0] : event
    const element = document.elementFromPoint(point.clientX, point.clientY)
    const target = element?.closest('.react-flow__node')?.getAttribute('data-id')
    if (target) connect({ source: state.fromNode.id, target, sourceHandle: null, targetHandle: null })
  }

  function connect(connection: Connection) {
    if (!connection.source || !connection.target) return
    const relationship: ErRelationship = {
      id: newId('r'),
      name: '',
      source: connection.source,
      target: connection.target,
      source_card: 'N',
      target_card: '1',
    }
    update({ relationships: [...value.relationships, relationship] })
    setSelected({ kind: 'relationship', id: relationship.id })
  }

  const selectedEntity = selected?.kind === 'entity' ? value.entities.find((item) => item.id === selected.id) : undefined
  const selectedRelationship =
    selected?.kind === 'relationship' ? value.relationships.find((item) => item.id === selected.id) : undefined

  const canvas = (
    <div className={cn('h-[32rem] overflow-hidden rounded-lg border bg-muted/30', className)}>
      <ReactFlow<EntityNode, RelationshipEdge>
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        edgeTypes={EDGE_TYPES}
        onNodesChange={onNodesChange}
        onNodeDragStop={(_, node) => {
          // Joylashuv diagrammaga faqat sudrash tugaganda yoziladi (ko'rish rejimida saqlanmaydi)
          if (readOnly) return
          update({
            entities: value.entities.map((entity) =>
              entity.id === node.id ? { ...entity, x: Math.round(node.position.x), y: Math.round(node.position.y) } : entity,
            ),
          })
        }}
        onConnect={connect}
        onConnectEnd={connectEnd}
        connectionRadius={30}
        onNodeClick={(_, node) => !readOnly && setSelected({ kind: 'entity', id: node.id })}
        onEdgeClick={(_, edge) => !readOnly && setSelected({ kind: 'relationship', id: edge.id })}
        onPaneClick={() => setSelected(null)}
        connectionMode={ConnectionMode.Loose}
        nodesConnectable={!readOnly}
        elementsSelectable={!readOnly}
        deleteKeyCode={null}
        fitView
        fitViewOptions={{ padding: 0.2, maxZoom: 1.1 }}
        minZoom={0.2}
      >
        <Background gap={20} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  )

  if (readOnly) return canvas

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant="outline" disabled={value.entities.length >= MAX_ENTITIES} onClick={addEntity}>
          <Plus aria-hidden="true" />
          Obyekt qo'shish
        </Button>
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          <Link2 className="size-3.5" aria-hidden="true" />
          Bog'lanish: obyekt chetidagi nuqtani boshqa obyektga sudrang. Tahrirlash uchun obyekt yoki chiziqni bosing.
        </span>
      </div>
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_17rem]">
        {canvas}
        <div className="rounded-lg border p-3">
          {selectedEntity ? (
            <EntityPanel
              key={selectedEntity.id}
              entity={selectedEntity}
              onChange={(entity) =>
                update({ entities: value.entities.map((item) => (item.id === entity.id ? entity : item)) })
              }
              onDelete={() => removeEntity(selectedEntity.id)}
            />
          ) : selectedRelationship ? (
            <RelationshipPanel
              key={selectedRelationship.id}
              relationship={selectedRelationship}
              names={names}
              onChange={(relationship) =>
                update({
                  relationships: value.relationships.map((item) => (item.id === relationship.id ? relationship : item)),
                })
              }
              onDelete={() => {
                update({ relationships: value.relationships.filter((item) => item.id !== selectedRelationship.id) })
                setSelected(null)
              }}
            />
          ) : (
            <div className="grid gap-2 text-sm text-muted-foreground">
              <p className="font-medium text-foreground">Qanday chiziladi</p>
              <ol className="list-decimal space-y-1 pl-4">
                <li>«Obyekt qo'shish» bilan obyekt yarating va uni bosib nomi va atributlarini yozing.</li>
                <li>Asosiy kalit atributiga PK belgisini qo'ying.</li>
                <li>Obyekt ustiga kursorni olib boring: chetida nuqtalar chiqadi. Nuqtani boshqa obyektga sudrang.</li>
                <li>Chiziqni bosib, bog'lanish nomi va ikki tomondagi kardinallikni (1 yoki N) tanlang.</li>
              </ol>
              <p>{value.entities.length} ta obyekt, {value.relationships.length} ta bog'lanish.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/** ER-diagramma muharriri. `onChange` berilmasa, faqat ko'rsatadi (tuzatilgan diagramma uchun ranglar bilan). */
export function ErEditor(props: ErEditorProps) {
  return (
    <ReactFlowProvider>
      <ErEditorInner {...props} />
    </ReactFlowProvider>
  )
}

/** Tuzatilgan diagramma ranglarining izohi */
export function ErFixLegend() {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
      <li className="flex items-center gap-1.5">
        <span className="size-3 rounded-sm border-2 border-emerald-500" aria-hidden="true" /> qo'shilgan
      </li>
      <li className="flex items-center gap-1.5">
        <span className="size-3 rounded-sm border-2 border-dashed border-red-400" aria-hidden="true" /> olib tashlangan
      </li>
      <li className="flex items-center gap-1.5">
        <span className="size-3 rounded-sm border-2 border-amber-500" aria-hidden="true" /> o'zgartirilgan
      </li>
    </ul>
  )
}

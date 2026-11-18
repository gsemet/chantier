// The contract of the CR board mod (hooks/register.tsx): the shapes of the
// STATUS.json files it reads and of the state it keeps. Self-contained: no import.

/** A CR's long gate, as `status/gate.py` builds it: the same words on every surface. */
export type ChantierGate = {
  state: 'none' | 'queued' | 'running' | 'passed' | 'carried' | 'failed' | 'waived' | 'exempt'
  /** The pass, or the head a pass was carried from (seven characters); null with none. */
  head: string | null
  /** The `--no-gate` rule of an exempt CR, or the note of the order that waived the gate. */
  waiver: string | null
  /** The CR whose gate validates a covered CR, and its PR. */
  validated_by: { cr: string; pr: string | null } | null
  /** The backlog folder of the CR that runs the gate afterwards, for a waiver of one CR. */
  follow_up: string | null
  /** The CRs a waived stack leaves to this CR's gate (the stack's top); else empty. */
  validates: string[]
  /** The "Long gate" column's words. */
  text: string
}

/** A CR row of a batch section: `status.py`'s `_row`. */
export type ChantierRow = {
  cr: string
  title: string
  state: string
  severity: string
  step: string
  label: string
  /** The step a working CR is at, or `waits for the user`; null when it shows none. Absent from an older file. */
  phase?: string | null
  /** A ready CR's state: `ready locally`, `PR in draft` or `ready to merge`; null for any other. */
  readiness: string | null
  round: number
  branch: string | null
  pr: string | null
  /** Absent from a STATUS.json written before the long gate was shown. */
  gate?: ChantierGate
  cost_usd: number | null
  blocked: string | null
  silent_minutes: number | null
  /** Relative to `.agents/changes/`. */
  folder: string | null
}

export type ChantierBatch = {
  batch: string
  folder: string
  state: string
  spent_usd: number
  budget_usd: number | null
  asks_unread: number
  heartbeat: string | null
  orders_pending: number
  slots?: { taken: number; total: number }
  mode?: string | null // the batch's shape: stack, series or parallel
  crs: ChantierRow[]
}

export type ChantierBacklogItem = {
  priority: string
  item: string
  title: string
  /** Relative to `.agents/changes/`. */
  path: string
  /** The spec-writer's state, read from the folder; null with no specification. */
  spec?: 'specifying' | 'specified' | null
  files: number
}

/** A merged or trashed CR. */
export type ChantierPast = {
  cr: string | null
  title: string
  state: string | null
  batch: string | null
  pr: string | null
  cost_usd: number | null
  when: string | null
  /** Relative to `.agents/changes/`. */
  path: string
}

/** `.agents/changes/STATUS.json`. */
export type ChantierIndex = {
  schema: number
  updated: string
  batches: ChantierBatch[]
  active_crs: number
  backlog: ChantierBacklogItem[]
  merged: ChantierPast[]
  merged_total: number
  trashed: ChantierPast[]
  trashed_total: number
}

export type ChantierStep = {
  name: string
  done: boolean
  verdict: string
  note: string
}

export type ChantierDocument = {
  kind: string
  name?: string
  /** Relative to the folder of the STATUS.json that names it. */
  path: string
}

/** A CR's own `STATUS.json`. */
export type ChantierSheet = {
  schema: number
  cr: string
  title: string
  label: string
  /** The step text, as on a row; null when it shows none. Absent from an older file. */
  phase?: string | null
  cost_usd: number | null
  now: string
  next: string
  blocked: string | null
  pr: { url: string; number: number | null } | null
  gate?: ChantierGate
  steps: ChantierStep[]
  documents: ChantierDocument[]
}

/** One screen above the board; the way back drops the last one. */
export type ChantierPage = {
  kind: 'cr' | 'items' | 'doc' | 'dir'
  /** The shown file or folder, absolute. */
  path: string
  /** The shown file's modification time when it was read. */
  mtime: number | null
  sheet: ChantierSheet | null
  /** The names of a folder's files (`items` and `dir`). */
  names: string[]
  text: string | null
  /** One line for what cannot be shown. */
  note: string | null
}

export type ChantierFeed = {
  index: ChantierIndex | null
  mtime: number | null
  readAt: number | null
  /** One line, drawn above the last good view. */
  note: string | null
  /** One line, drawn alone: the schema is not the one this board reads. */
  fatal: string | null
  /** The index path when it does not exist. */
  missing: string | null
}

declare module 'claude-code' {
  interface PluginState {
    chantier: {
      /** Where the files are (every project of a surface), found at opening and at Refresh; `unseated` is the line said when no seat names the session. */
      site: Shaped<{ root: string | null; bases: { name: string | null; dir: string }[]; error: string | null; unseated: string | null; sid: { id: string | null; error: string | null } | null }>
      feed: Shaped<ChantierFeed>
      pages: Shaped<ChantierPage[]>
      /** Sections turned from their default (batches open, the rest folded). */
      turned: Shaped<string[]>
      /** The chantier role skills this session loaded: a compaction of such a session gets the reload message. */
      roles: Shaped<string[]>
      /** The time of the last check, drawn as the header's "checked Ns ago". */
      checkedAt: Shaped<number | null>
      /** The agents started with a `writes:` line: agent id -> the folders it may write in and the folder it runs in. */
      workers: Shaped<Record<string, { folders: string[]; cwd: string }>>
    }
  }
}

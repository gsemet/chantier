// The contract of the CR board mod (hooks/register.tsx): the shapes of the
// STATUS.json files it reads and of the state it keeps. Self-contained: no import.

/** A CR row of a batch section: `status.py`'s `_row`. */
export type ChantierRow = {
  cr: string
  title: string
  state: string
  severity: string
  step: string
  label: string
  round: number
  branch: string | null
  pr: string | null
  cost_usd: number | null
  blocked: string | null
  silent_minutes: number | null
  /** Relative to `3-requests/`. */
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
  crs: ChantierRow[]
}

export type ChantierBacklogItem = {
  priority: string
  item: string
  title: string
  /** Relative to `3-requests/`. */
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
  /** Relative to `3-requests/`. */
  path: string
}

/** `3-requests/STATUS.json`. */
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
  cost_usd: number | null
  now: string
  next: string
  blocked: string | null
  pr: { url: string; number: number | null } | null
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
      /** Where the files are, found once at opening. */
      site: Shaped<{ root: string | null; error: string | null }>
      feed: Shaped<ChantierFeed>
      pages: Shaped<ChantierPage[]>
      /** Sections turned from their default (batches open, the rest folded). */
      turned: Shaped<string[]>
      /** The time of the last check, drawn as the age of the read. */
      checkedAt: Shaped<number | null>
    }
  }
}

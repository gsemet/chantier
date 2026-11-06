// The CR board: a read-only pane over `.agents/changes/3-requests/STATUS.json`.
// It writes nothing and runs no process but `git rev-parse`. See README.md.
import { atom, read, update } from 'claude-code'
import type { EngineInterface as Engine, Register } from 'claude-code'

import type {
  ChantierBatch,
  ChantierIndex,
  ChantierPage,
  ChantierPast,
  ChantierRow,
  ChantierSheet,
} from '../types'

const PANE = 'cr-board'
const TITLE = 'CR board'
const COMMAND = 'chantier-board'
const SCHEMA = 2
const EVERY_MS = 15000
const SILENT_MINUTES = 40
const MAX_DOC_BYTES = 200 * 1024
const INDEX = '.agents/changes/3-requests/STATUS.json'

// Change a tag when the shape of its value changes: it declines what an earlier
// version stored, which outlives a reload.
const site = atom({ plugin: 'chantier', key: 'site' } as const, { root: null, error: null }, { shape: 'site-1' })
const feed = atom(
  { plugin: 'chantier', key: 'feed' } as const,
  { index: null, mtime: null, readAt: null, note: null, fatal: null, missing: null },
  { shape: 'feed-1' },
)
const pages = atom({ plugin: 'chantier', key: 'pages' } as const, [], { shape: 'pages-1' })
const turned = atom({ plugin: 'chantier', key: 'turned' } as const, [], { shape: 'turned-1' })
const checkedAt = atom({ plugin: 'chantier', key: 'checkedAt' } as const, null, { shape: 'checked-1' })

// ---- paths: plain strings, `/` everywhere, no Node ----

const slash = (p: string) => p.replace(/\\/g, '/')

const isDrive = (s: string) => /^[A-Za-z]:$/.test(s)

function clean(p: string): string {
  const parts: string[] = []
  for (const seg of slash(p).split('/')) {
    if (seg === '' || seg === '.') continue
    if (seg === '..') {
      if (parts.length > 0 && !(parts.length === 1 && isDrive(parts[0] ?? ''))) parts.pop()
      continue
    }
    parts.push(seg)
  }
  return (slash(p).startsWith('/') ? '/' : '') + parts.join('/')
}

const parentOf = (p: string) => clean(p + '/..')

const fold = (p: string) => (/^[A-Za-z]:/.test(p) ? p.toLowerCase() : p)

function isInside(root: string, p: string): boolean {
  const a = fold(clean(p))
  const r = fold(clean(root))
  return a === r || a.startsWith(r.endsWith('/') ? r : r + '/')
}

/** `href` resolved from the folder `base`, the `#fragment` and `?query` dropped; null for a URL. */
function resolveFrom(base: string, href: string): string | null {
  if (/^[A-Za-z][A-Za-z0-9+.-]*:(?!\/[^/]|$)/.test(href) && !/^[A-Za-z]:[\\/]/.test(href)) return null
  let rel = (href.split('#')[0] ?? '').split('?')[0] ?? ''
  try {
    rel = decodeURI(rel)
  } catch {
    // keep it as written
  }
  if (rel === '') return null
  const abs = rel.startsWith('/') || rel.startsWith('\\') || /^[A-Za-z]:[\\/]/.test(rel)
  return clean(abs ? rel : base + '/' + rel)
}

const message = (err: unknown) =>
  String((err as { message?: unknown } | null)?.message ?? err)

// ---- small views of the data ----

function money(n: number | null | undefined): string {
  return n === null || n === undefined ? '-' : '$' + n.toFixed(2)
}

function gauge(spent: number, budget: number | null): string {
  if (!budget || budget <= 0) return ''
  const full = Math.max(0, Math.min(10, Math.round((spent / budget) * 10)))
  return '█'.repeat(full) + '░'.repeat(10 - full)
}

/** The steps as one line: notes dropped, a repeated name kept once, what is still ahead in brackets. */
function stepsLine(steps: ChantierSheet['steps']): string {
  const seen: string[] = []
  const out: string[] = []
  for (const s of steps) {
    const text = s.name + (s.verdict ? ' ' + s.verdict : '')
    if (seen.includes(text)) continue
    seen.push(text)
    out.push(s.done ? text : '(' + text + ')')
  }
  return out.join(' > ') || 'none yet'
}

// The same icons as status.py ICON; the label starts with its own, drawn here before the id instead.
const ICON: Record<string, string> = { red: '🔴', yellow: '🟡', green: '🟢', grey: '⚪' }
const LEADING_ICON = /^(🔴|🟡|🟢|⚪)\s*/u
const PRIORITIES = ['inbox', 'P1', 'P2', 'P3', 'P4']
const isWaiting = (r: ChantierRow) => r.state === 'blocked' || r.state === 'ready'

const dirLines = (t: string) => t.replace(/\r/g, '')

// ---- the files ----

async function findRoot($: Engine): Promise<{ root: string | null; error: string | null }> {
  const cwd = slash(await $.session.cwd())
  let out: { exitCode: number; stdout: string }
  try {
    out = await $.process.run(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'], { cwd })
  } catch (err) {
    return { root: null, error: `Cannot look for the main checkout: ${message(err)}` }
  }
  // Not a repository: the session's folder.
  if (out.exitCode !== 0) return { root: clean(cwd), error: null }
  return { root: parentOf(out.stdout.trim()), error: null }
}

const isMissing = (err: unknown) => /ENOENT|ENOTDIR|no such file|not found|does not exist/i.test(message(err))

const schemaOf = (d: unknown): unknown => (d !== null && typeof d === 'object' ? (d as { schema?: unknown }).schema : undefined)

async function readJson($: Engine, path: string): Promise<unknown> {
  return JSON.parse(await $.fs.read(path))
}

/** Reads the index again only if its modification time changed. */
async function checkIndex($: Engine, root: string): Promise<void> {
  const path = root + '/' + INDEX
  let mtime: number
  try {
    mtime = (await $.fs.stat(path)).mtimeMs
  } catch (err) {
    if (!isMissing(err)) {
      await update($, feed, f => ({ ...f, note: `Cannot read ${path}: ${message(err)}`, missing: null }))
      return
    }
    await update($, feed, f => ({ ...f, index: null, mtime: null, missing: path, note: null, fatal: null }))
    return
  }
  const before = await read($, feed)
  if (mtime === before.mtime && before.missing === null) return
  const now = await $.clock.now()
  let data: unknown
  try {
    data = await readJson($, path)
  } catch (err) {
    await update($, feed, f => ({
      ...f,
      mtime,
      missing: null,
      note: `${path} does not parse (${message(err)}): showing the last view.`,
    }))
    return
  }
  if (schemaOf(data) !== SCHEMA) {
    await update($, feed, f => ({
      ...f,
      mtime,
      missing: null,
      note: null,
      index: null,
      fatal: `${path} has schema ${String(schemaOf(data))}; this board reads schema ${SCHEMA}.`,
    }))
    return
  }
  await update($, feed, () => ({ index: data as ChantierIndex, mtime, readAt: now, note: null, fatal: null, missing: null }))
}

async function loadPage($: Engine, kind: ChantierPage['kind'], path: string): Promise<ChantierPage> {
  const page: ChantierPage = { kind, path, mtime: null, sheet: null, names: [], text: null, note: null }
  const st = await $.fs.stat(path)
  page.mtime = st.mtimeMs
  if (kind === 'cr') {
    try {
      const data = await readJson($, path)
      if (schemaOf(data) !== SCHEMA) page.note = `${path} has schema ${String(schemaOf(data))}; this board reads schema ${SCHEMA}.`
      else page.sheet = data as ChantierSheet
    } catch (err) {
      page.note = `${path} does not parse: ${message(err)}`
    }
  } else if (kind === 'items' || kind === 'dir') {
    const entries: { name: string; kind: string }[] = await $.fs.list(path)
    page.names = entries
      .filter(e => (kind === 'dir' ? true : e.kind === 'file' && /\.md$/i.test(e.name)))
      .map(e => e.name + (e.kind === 'dir' ? '/' : ''))
      .sort()
  } else {
    if (st.size > MAX_DOC_BYTES) {
      page.note = `${path} is over 200 KB: not shown.`
    } else {
      const text: string = await $.fs.read(path)
      // The engine hands back text, not bytes, so U+FFFD is the only sign of invalid UTF-8; a file that holds a real U+FFFD is misreported.
      if (text.includes('\uFFFD')) page.note = `${path} is not UTF-8: not shown.`
      else page.text = dirLines(text)
    }
  }
  return page
}

/** The top page, read again only if its modification time changed. */
async function checkPage($: Engine): Promise<void> {
  const all = await read($, pages)
  const top = all[all.length - 1]
  if (!top) return
  let mtime: number
  try {
    mtime = (await $.fs.stat(top.path)).mtimeMs
  } catch (err) {
    await update($, pages, list => list.map((p, i) => (i === list.length - 1 ? { ...p, note: `${top.path}: ${message(err)}` } : p)))
    return
  }
  if (mtime === top.mtime) return
  const fresh = await loadPage($, top.kind, top.path)
  await update($, pages, list => list.map((p, i) => (i === list.length - 1 && p.path === top.path ? fresh : p)))
}

let timer: { cancel: () => void } | null = null

async function check($: Engine): Promise<void> {
  try {
    const where = await read($, site)
    if (where.root === null) return
    await checkIndex($, where.root)
    await checkPage($)
  } catch (err) {
    await update($, feed, f => ({ ...f, note: `Could not check the files: ${message(err)}` }))
  }
  const now = await $.clock.now()
  await update($, checkedAt, () => now)
}

async function begin($: Engine): Promise<void> {
  const where = await findRoot($)
  await update($, site, () => where)
  await update($, pages, () => [])
  if (timer === null) timer = $.clock.every(EVERY_MS, () => void check($))
  await check($)
}

function end(): void {
  if (timer !== null) timer.cancel()
  timer = null
}

async function open($: Engine): Promise<boolean> {
  const placed = await $.ui.open({ id: PANE, title: TITLE })
  if (!placed.isPlaced) return false
  await begin($)
  return true
}

// ---- navigation, from the handlers ----

async function guarded($: Engine, work: () => Promise<void>): Promise<void> {
  try {
    await work()
  } catch (err) {
    await update($, feed, f => ({ ...f, note: message(err) }))
  }
}

async function push($: Engine, kind: ChantierPage['kind'], path: string): Promise<void> {
  const page = await loadPage($, kind, path)
  await update($, pages, list => [...list, page])
}

/** A CR's sheet from its folder, or the list of an inbox or backlog item's Markdown files. */
async function showCr($: Engine, dir: string): Promise<void> {
  const status = dir + '/STATUS.json'
  if (await $.fs.exists(status)) await push($, 'cr', status)
  else await push($, 'items', dir)
}

async function showPath($: Engine, path: string): Promise<void> {
  const st = await $.fs.stat(path)
  await push($, st.kind === 'dir' ? 'dir' : 'doc', path)
}

const back = ($: Engine) => update($, pages, list => list.slice(0, -1))

const flip = ($: Engine, key: string) =>
  update($, turned, list => (list.includes(key) ? list.filter(k => k !== key) : [...list, key]))

// ---- the drawing ----

function minutesSince(iso: string | null, now: number): number | null {
  if (!iso) return null
  const t = Date.parse(iso)
  return Number.isNaN(t) ? null : Math.round((now - t) / 60000)
}

export const register: Register = on => {
  // Any session that loads the chantier skill gets the pane; the prompt is returned unchanged.
  on('skill.prompt', async ($, e, next) => {
    const result = await next(e)
    if (e.skill.split(':').pop() !== 'chantier') return result
    try {
      await open($)
    } catch (err) {
      await update($, feed, f => ({ ...f, note: message(err) }))
    }
    return result
  })

  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: COMMAND,
      description: 'Show or hide the chantier CR board',
    })
    return next(e)
  })

  on('command.run', { command: COMMAND }, async $ => {
    const shown = (await $.ui.panes()).some((p: { id: string }) => p.id === PANE)
    if (shown) {
      end()
      await $.ui.close({ id: PANE })
      return { text: 'CR board closed.' }
    }
    const isPlaced = await open($)
    return { text: isPlaced ? 'CR board opened.' : 'The CR board could not be placed here.' }
  })

  // A closed pane runs nothing.
  on('ui.close', { id: PANE }, async ($, e, next) => {
    end()
    return next(e)
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button, Link, Markdown } = $.ui.resolve(e)
    const where = await read($, site)
    const f = await read($, feed)
    const stack = await read($, pages)
    const open_ = await read($, turned)
    await read($, checkedAt)
    const now: number = await $.clock.now()

    const isOpen = (key: string, byDefault: boolean) => byDefault !== open_.includes(key)

    const Fold = (key: string, byDefault: boolean, label: string) => (
      <Button
        key={'fold-' + key}
        plain
        label={(isOpen(key, byDefault) ? '▾ ' : '▸ ') + label}
        onPress={() => void flip($, key)}
      />
    )

    if (where.error !== null) return <Text>{where.error}</Text>
    if (where.root === null) return <Text dimColor>Looking for the chantier files...</Text>
    if (f.fatal !== null) return <Text>{f.fatal}</Text>
    if (f.missing !== null) return <Text>{`No chantier status here: ${f.missing} not found.`}</Text>

    const root = where.root
    const note = f.note === null ? null : <Text italic>{f.note}</Text>

    const Cr = (dir: string | null, id: string) =>
      dir === null ? (
        <Text bold>{id}</Text>
      ) : (
        <Button
          key={'cr-' + dir}
          plain
          label={id}
          onPress={() => void guarded($, () => showCr($, clean(root + '/.agents/changes/3-requests/' + dir)))}
        />
      )

    const Row = (r: ChantierRow) => (
      <Box key={r.cr} flexDirection="column">
        <Box flexWrap="wrap" columnGap={1}>
          <Text>{ICON[r.severity] ?? ''}</Text>
          {Cr(r.folder, r.cr)}
          <Text>{r.label.replace(LEADING_ICON, '')}</Text>
          <Text>{r.title}</Text>
        </Box>
        <Box flexWrap="wrap" columnGap={1} paddingLeft={2}>
          {r.pr !== null && <Link href={r.pr} label="PR" />}
          <Text dimColor>{money(r.cost_usd)}</Text>
          {r.branch !== null && <Text dimColor>{r.branch}</Text>}
          {r.silent_minutes !== null && <Text dimColor>{`silent ${r.silent_minutes} min`}</Text>}
        </Box>
        {r.blocked !== null && (
          <Box paddingLeft={2}>
            <Text>{r.blocked}</Text>
          </Box>
        )}
      </Box>
    )

    const Past = (p: ChantierPast, i: number) => (
      <Box key={p.path + i} flexWrap="wrap" columnGap={1}>
        {Cr(p.path, p.cr ?? p.path.split('/').pop() ?? p.path)}
        <Text>{p.title}</Text>
        {p.state !== null && <Text dimColor>{p.state}</Text>}
        {p.pr !== null && <Link href={p.pr} label="PR" />}
        {p.cost_usd !== null && <Text dimColor>{money(p.cost_usd)}</Text>}
      </Box>
    )

    const Batch = (b: ChantierBatch) => {
      const spent = money(b.spent_usd)
      const budget = b.budget_usd === null ? '' : ` / $${+b.budget_usd.toFixed(2)}`
      const waiting = b.crs.filter(isWaiting)
      const rest = b.crs.filter(r => !isWaiting(r))
      const age = minutesSince(b.heartbeat, now)
      const isLive = b.state === 'open' && b.crs.some(r => r.state === 'working')
      const isSilent = isLive && age !== null && age > SILENT_MINUTES
      const key = 'batch-' + b.folder
      const shown = b.state !== 'landed' // a landed batch is folded, its cost still on the title line
      return (
        <Box key={key} flexDirection="column">
          {Fold(key, shown, `${b.batch}  ${spent}${budget} ${gauge(b.spent_usd, b.budget_usd)}`)}
          {isOpen(key, shown) && (
            <Box flexDirection="column" paddingLeft={2}>
              <Text bold>Waiting for you</Text>
              {waiting.map(Row)}
              {b.asks_unread > 0 && <Text>{`${b.asks_unread} unread ask${b.asks_unread === 1 ? '' : 's'}`}</Text>}
              {isSilent && <Text>{`Foreman silent for ${age} min`}</Text>}
              {waiting.length === 0 && b.asks_unread === 0 && !isSilent && (
                <Text dimColor>Nothing waits for you.</Text>
              )}
              <Text bold>In progress</Text>
              {rest.map(Row)}
              {rest.length === 0 && <Text dimColor>No other live CR.</Text>}
            </Box>
          )}
        </Box>
      )
    }

    const back_ = (
      <Button key="back" label="< Back" onPress={() => void back($)} />
    )

    // ---- a page above the board ----
    const top = stack[stack.length - 1]
    if (top !== undefined) {
      const base = parentOf(top.path)
      const Doc = (d: { label: string; path: string | null; isDir?: boolean }) => {
        const target = d.path
        if (target === null || !isInside(root, target)) return <Text key={d.label}>{d.label}</Text>
        return (
          <Button
            key={'doc-' + target}
            plain
            label={d.label}
            onPress={() => void guarded($, () => showPath($, target))}
          />
        )
      }
      if (top.kind === 'cr' && top.sheet !== null) {
        const s = top.sheet
        return (
          <Box flexDirection="column">
            {back_}
            {note}
            <Text bold>{`${s.cr} ${s.title}`}</Text>
            <Text>{`${s.label}  ${money(s.cost_usd)}`}</Text>
            <Text>{stepsLine(s.steps)}</Text>
            <Text>{`Now: ${s.now}`}</Text>
            <Text>{`Next: ${s.next}`}</Text>
            {s.blocked !== null && <Text>{`Blocked: ${s.blocked}`}</Text>}
            {s.pr !== null && <Link href={s.pr.url} label={s.pr.number === null ? 'PR' : `PR #${s.pr.number}`} />}
            <Text bold>Documents</Text>
            {s.documents.map(d => Doc({ label: d.name ?? d.kind, path: resolveFrom(base, d.path) }))}
          </Box>
        )
      }
      if (top.kind === 'items' || top.kind === 'dir') {
        return (
          <Box flexDirection="column">
            {back_}
            {note}
            <Text bold>{top.path.split('/').pop() ?? top.path}</Text>
            {top.names.length === 0 && <Text dimColor>No file here.</Text>}
            {top.names.map(n => Doc({ label: n, path: resolveFrom(top.path, n) }))}
          </Box>
        )
      }
      if (top.kind === 'doc' && top.text !== null) {
        const links = [...top.text.matchAll(/\]\(([^)\s]+)\)/g)].map(m => m[1] ?? '').filter(h => h !== '' && resolveFrom(base, h) !== null)
        return (
          <Box flexDirection="column">
            {back_}
            {note}
            <Markdown
              key="doc"
              text={top.text}
              pressableLinks={links}
              onLinkPress={link => {
                const target = resolveFrom(base, link.href)
                if (target !== null && isInside(root, target)) void guarded($, () => showPath($, target))
              }}
            />
          </Box>
        )
      }
      return (
        <Box flexDirection="column">
          {back_}
          {note}
          <Text>{top.note ?? 'Nothing to show.'}</Text>
        </Box>
      )
    }

    // ---- the board ----
    const index = f.index
    if (index === null) return <Text dimColor>Reading the status...</Text>
    const waitingCount = index.batches.reduce(
      (n, b) => n + b.crs.filter(isWaiting).length + b.asks_unread,
      0,
    )
    const age = f.readAt === null ? null : Math.max(0, Math.round((now - f.readAt) / 1000))
    return (
      <Box flexDirection="column">
        <Text bold>
          {`${index.active_crs} live · ${waitingCount} waiting for you${age === null ? '' : ` · read ${age}s ago`}`}
        </Text>
        {note}
        {index.batches.map(Batch)}
        {index.batches.length === 0 && <Text dimColor>No open batch.</Text>}
        {Fold('backlog', false, `Backlog (${index.backlog.length})`)}
        {isOpen('backlog', false) && (
          <Box flexDirection="column" paddingLeft={2}>
            {PRIORITIES.map(pr => {
              const items = index.backlog.filter(r => r.priority === pr)
              return (
                <Box key={pr} flexDirection="column">
                  {Fold('backlog-' + pr, false, `${pr} (${items.length})`)}
                  {isOpen('backlog-' + pr, false) &&
                    items.map(r => (
                      <Box key={r.path} paddingLeft={2} flexWrap="wrap" columnGap={1}>
                        {Cr(r.path, r.title)}
                        <Text dimColor>{`${r.files} file${r.files === 1 ? '' : 's'}`}</Text>
                      </Box>
                    ))}
                </Box>
              )
            })}
          </Box>
        )}
        {Fold('landed', false, `Landed (${index.landed.length} of ${index.landed_total})`)}
        {isOpen('landed', false) && <Box flexDirection="column" paddingLeft={2}>{index.landed.map(Past)}</Box>}
        {Fold('trashed', false, `Trashed (${index.trashed.length} of ${index.trashed_total})`)}
        {isOpen('trashed', false) && <Box flexDirection="column" paddingLeft={2}>{index.trashed.map(Past)}</Box>}
      </Box>
    )
  })
}

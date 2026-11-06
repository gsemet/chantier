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

const PRIORITIES = ['inbox', 'P1', 'P2', 'P3', 'P4']
const isWaiting = (r: ChantierRow) => r.state === 'blocked' || r.state === 'ready'

// ---- the tables: Markdown, so a surface draws them as it draws a table in a reply ----

const cell = (s: string) => s.replace(/\\/g, '\\\\').replace(/\|/g, '\\|').replace(/\s+/g, ' ').trim()

const table = (head: string[], rows: string[][]) =>
  [head, head.map(() => '---'), ...rows].map(r => `| ${r.map(c => (c === '' ? '-' : c)).join(' | ')} |`).join('\n')

const prCell = (url: string | null) => (url === null ? '-' : `[#${url.split('/').pop()}](${url})`)

/** The label with its repeated word dropped ("blocked Blocked 2/3"), and a long silence. */
function stateCell(r: ChantierRow): string {
  const silent = r.silent_minutes !== null && r.silent_minutes > SILENT_MINUTES ? ` · silent ${r.silent_minutes} min` : ''
  return cell(r.label.replace(/(\p{L}+) \1/iu, '$1') + silent)
}

const fileUrl = (path: string) => 'file://' + (path.startsWith('/') ? '' : '/') + encodeURI(path).replace(/\(/g, '%28').replace(/\)/g, '%29')

function fromFileUrl(href: string): string {
  const path = decodeURI(href.replace(/^file:\/\//, ''))
  return clean(/^\/[A-Za-z]:/.test(path) ? path.slice(1) : path)
}

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
      immediate: true,
    })
    return next(e)
  })

  // `immediate`: it also runs during a turn, so this hook assumes nothing of the turn's state.
  on('command.run', { command: COMMAND }, async $ => {
    const shown = (await $.ui.panes()).some((p: { id: string }) => p.id === PANE)
    if (shown) {
      end()
      await $.ui.close({ id: PANE })
      return { text: 'CR board closed.' }
    }
    const isPlaced = await open($)
    // No detection of the view: a Remote Control view is answered as the host is.
    return {
      text: isPlaced
        ? 'CR board opened on the machine running this session; a Remote Control view does not show it.'
        : 'The CR board could not be placed here.',
    }
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

    const crUrl = (dir: string) => fileUrl(clean(root + '/.agents/changes/3-requests/' + dir))
    const crCell = (dir: string | null, id: string) => (dir === null ? `**${id}**` : `[${cell(id)}](${crUrl(dir)})`)

    /** A table of `file:` links, listed by `urls`; a press on one inside the checkout calls `onOpen`, one outside opens nothing. */
    const Linked = (key: string, text: string, urls: string[], onOpen: (path: string) => Promise<void>) => (
      <Markdown
        key={key}
        text={text}
        pressableLinks={urls}
        onLinkPress={link => {
          const path = fromFileUrl(link.href)
          if (isInside(root, path)) void guarded($, () => onOpen(path))
        }}
      />
    )

    /** A table whose CR links open the CR's sheet; a PR's link keeps the surface's own behaviour. */
    const Table = (key: string, head: string[], rows: string[][], dirs: (string | null)[]) =>
      Linked(key, table(head, rows), dirs.filter(d => d !== null).map(crUrl), dir => showCr($, dir))

    /** A document's name as a link opening it in the pane; plain text when it is outside the checkout. */
    const docCell = (label: string, path: string | null) =>
      path === null || !isInside(root, path) ? cell(label) : `[${cell(label)}](${fileUrl(path)})`

    const Files = (key: string, head: string[], rows: { label: string; path: string | null; more?: string[] }[]) =>
      Linked(
        key,
        table(head, rows.map(r => [docCell(r.label, r.path), ...(r.more ?? [])])),
        rows.flatMap(r => (r.path !== null && isInside(root, r.path) ? [fileUrl(r.path)] : [])),
        p => showPath($, p),
      )

    const COLUMNS = ['CR', 'Subject', 'State', 'PR', 'Cost']

    const Crs = (key: string, rows: ChantierRow[]) =>
      Table(
        key,
        COLUMNS,
        rows.map(r => [crCell(r.folder, r.cr), cell(r.title), stateCell(r), prCell(r.pr), money(r.cost_usd)]),
        rows.map(r => r.folder),
      )

    const Pasts = (key: string, rows: ChantierPast[]) =>
      Table(
        key,
        COLUMNS,
        rows.map(p => [
          crCell(p.path, p.cr ?? p.path.split('/').pop() ?? p.path),
          cell(p.title),
          p.state ?? '-',
          prCell(p.pr),
          money(p.cost_usd),
        ]),
        rows.map(p => p.path),
      )

    /** A section: its fold, then what it holds while open. */
    const Section = (key: string, byDefault: boolean, label: string, body: () => unknown) => (
      <Box key={'section-' + key} flexDirection="column" rowGap={1}>
        {Fold(key, byDefault, label)}
        {isOpen(key, byDefault) && body()}
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
      const why = waiting.filter(r => r.blocked !== null)
      return Section(key, shown, `${b.batch}  ${spent}${budget} ${gauge(b.spent_usd, b.budget_usd)}`, () => (
        <Box flexDirection="column" rowGap={1} paddingLeft={2}>
          {b.asks_unread > 0 && <Text>{`${b.asks_unread} unread ask${b.asks_unread === 1 ? '' : 's'}`}</Text>}
          {isSilent && <Text>{`Foreman silent for ${age} min`}</Text>}
          {Section(key + '-waiting', true, `Waiting for you (${waiting.length})`, () =>
            waiting.length === 0 ? <Text dimColor>Nothing waits for you.</Text> : Crs(key + '-waiting-table', waiting),
          )}
          {why.length > 0 &&
            Section(key + '-why', false, `Why (${why.length})`, () => (
              <Markdown key={key + '-why-text'} text={why.map(r => `- **${r.cr}:** ${r.blocked}`).join('\n')} />
            ))}
          {Section(key + '-rest', true, `In progress (${rest.length})`, () =>
            rest.length === 0 ? <Text dimColor>No other live CR.</Text> : Crs(key + '-rest-table', rest),
          )}
        </Box>
      ))
    }

    const back_ = (
      <Button key="back" label="< Back" onPress={() => void back($)} />
    )

    // ---- a page above the board ----
    const top = stack[stack.length - 1]
    if (top !== undefined) {
      const base = parentOf(top.path)
      if (top.kind === 'cr' && top.sheet !== null) {
        const s = top.sheet
        return (
          <Box flexDirection="column">
            {back_}
            {note}
            <Text bold>{`${s.cr} ${s.title}`}</Text>
            <Text>{`${s.label}  ${money(s.cost_usd)}`}</Text>
            {s.steps.length === 0 ? (
              <Text dimColor>No step yet.</Text>
            ) : (
              <Markdown
                key="steps"
                text={table(['Step', 'Done', 'Verdict'], s.steps.map(x => [cell(x.name), x.done ? 'yes' : 'no', cell(x.verdict ?? '-')]))}
              />
            )}
            <Text>{`Now: ${s.now}`}</Text>
            <Text>{`Next: ${s.next}`}</Text>
            {s.blocked !== null && <Text>{`Blocked: ${s.blocked}`}</Text>}
            {s.pr !== null && <Link href={s.pr.url} label={s.pr.number === null ? 'PR' : `PR #${s.pr.number}`} />}
            <Text bold>Documents</Text>
            {s.documents.length === 0 ? (
              <Text dimColor>No document yet.</Text>
            ) : (
              Files(
                'documents',
                ['Document', 'Kind'],
                s.documents.map(d => ({ label: d.name ?? d.kind, path: resolveFrom(base, d.path), more: [cell(d.kind)] })),
              )
            )}
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
            {top.names.length > 0 &&
              Files(
                'files',
                ['File'],
                top.names.map(n => ({ label: n, path: resolveFrom(top.path, n) })),
              )}
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
    const backlog = PRIORITIES.flatMap(pr => index.backlog.filter(r => r.priority === pr))
    return (
      <Box flexDirection="column" rowGap={1}>
        <Text bold>
          {`${index.active_crs} live · ${waitingCount} waiting for you${age === null ? '' : ` · read ${age}s ago`}`}
        </Text>
        {note}
        {index.batches.map(Batch)}
        {index.batches.length === 0 && <Text dimColor>No open batch.</Text>}
        {Section('backlog', false, `Backlog (${index.backlog.length})`, () =>
          Table(
            'backlog-table',
            ['Priority', 'Item', 'Title', 'Files'],
            backlog.map(r => [r.priority, crCell(r.path, r.item), cell(r.title), String(r.files)]),
            backlog.map(r => r.path),
          ),
        )}
        {Section('landed', false, `Landed (${index.landed.length} of ${index.landed_total})`, () =>
          Pasts('landed-table', index.landed),
        )}
        {Section('trashed', false, `Trashed (${index.trashed.length} of ${index.trashed_total})`, () =>
          Pasts('trashed-table', index.trashed),
        )}
      </Box>
    )
  })
}

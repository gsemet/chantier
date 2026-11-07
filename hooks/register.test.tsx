// Tests of the CR board. Nothing sits beneath the plugin in a test: the hooks here
// stand for the engine, so the file system, the process and the session's folder are fakes.
import type { On } from 'claude-code'
import { expect, mock, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'

const ROOT = '/work/repo'
const INDEX = `${ROOT}/.agents/changes/3-requests/STATUS.json`
const BATCH = '01-demo'
const CR_DIR = `${ROOT}/.agents/changes/3-requests/${BATCH}/01-first`

const PANE = {
  plugin: 'chantier',
  component: 'Pane',
  requestId: 'cr-board',
  props: {
    title: 'CR board',
    isFocused: false,
    bodyColumns: 40,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 20 },
    view: {},
  },
} as const

const row = (over = {}) => ({
  cr: 'CR-1',
  title: 'First change',
  state: 'working',
  severity: 'yellow',
  step: 'Round',
  label: '🟡 working Round 1/3',
  round: 1,
  branch: 'chantier/demo/cr-1',
  pr: null,
  cost_usd: 1.5,
  blocked: null,
  silent_minutes: 2,
  folder: `${BATCH}/01-first`,
  ...over,
})

const index = (over = {}) => ({
  schema: 2,
  updated: '2026-11-06T10:00:00Z',
  batches: [
    {
      batch: 'demo',
      folder: BATCH,
      state: 'running',
      spent_usd: 5.07,
      budget_usd: 20,
      asks_unread: 0,
      heartbeat: null,
      orders_pending: 0,
      crs: [row()],
    },
  ],
  active_crs: 1,
  backlog: [],
  merged: [],
  merged_total: 0,
  trashed: [],
  trashed_total: 0,
  ...over,
})

const sheet = (over = {}) => ({
  schema: 2,
  cr: 'CR-1',
  title: 'First change',
  label: '🟡 working Round 1/3',
  cost_usd: 1.5,
  now: 'A coder is working.',
  next: 'The long gate.',
  blocked: null,
  pr: null,
  steps: [
    { name: 'Round 1', done: true, verdict: '', note: 'a note' },
    { name: 'Round 1', done: true, verdict: '', note: 'again' },
    { name: 'Shipped', done: false, verdict: '', note: '' },
  ],
  documents: [
    { kind: 'intent', path: '01-intent.md' },
    { kind: 'escape', path: '../../../../../../outside.md' },
  ],
  ...over,
})

/** The engine spells a path as the host does (C:\work\repo on Windows): the fakes compare without the drive. */
const n = (p: string) => p.replace(/\\/g, '/').replace(/^[A-Za-z]:/, '')

/** A file system, a process and a session folder, as the engine would answer them. */
function world(on: On, cwd = ROOT) {
  const files = new Map<string, { text: string; mtime: number }>()
  const dirs = new Map<string, string[]>()
  const calls = { stat: [] as string[], read: [] as string[], run: [] as any[], register: [] as any[], open: 0, close: 0 }
  let gitStdout = `${ROOT}/.git\n`
  let gitExit = 0
  let gitDeny: string | null = null
  let isOpen = false
  let mtime = 1
  const put = (path: string, value: unknown) =>
    files.set(n(path), { text: typeof value === 'string' ? value : JSON.stringify(value), mtime: ++mtime })

  on('skill.prompt', (_, e) => ({ text: e.text }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.cwd', () => ({ value: cwd }))
  on('process.run', (_, e) => {
    calls.run.push({ argv: e.argv, cwd: n(String(e.init?.cwd)) })
    if (gitDeny !== null) return { deny: gitDeny }
    return { value: { exitCode: gitExit, stdout: gitStdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('fs.stat', (_, e) => {
    calls.stat.push(n(e.path))
    const f = files.get(n(e.path))
    if (f) return { value: { kind: 'file', size: f.text.length, mtimeMs: f.mtime, isLink: false } }
    if (dirs.has(n(e.path))) return { value: { kind: 'dir', size: 0, mtimeMs: 1, isLink: false } }
    return { deny: `ENOENT: no such file or directory, stat '${e.path}'` }
  })
  on('fs.read', (_, e) => {
    calls.read.push(n(e.path))
    const f = files.get(n(e.path))
    return f ? { value: f.text } : { deny: `ENOENT: ${e.path}` }
  })
  on('fs.exists', (_, e) => ({ value: files.has(n(e.path)) || dirs.has(n(e.path)) }))
  on('fs.list', (_, e) => ({
    value: (dirs.get(n(e.path)) ?? []).map(name => ({
      name,
      kind: dirs.has(n(e.path) + '/' + name) ? 'dir' : 'file',
      size: 1,
      mtimeMs: 1,
      isLink: false,
    })),
  }))
  on('command.register', (_, e) => {
    calls.register.push(e)
    return { value: { command: 'chantier-board' } }
  })
  on('ui.open', () => {
    calls.open += 1
    isOpen = true
    return { value: { isPlaced: true } }
  })
  on('ui.close', () => {
    calls.close += 1
    isOpen = false
    return { value: undefined }
  })
  on('ui.panes', () => ({ value: isOpen ? [{ id: 'cr-board', title: 'CR board', isShown: true, isFocused: false, isPlaced: true }] : [] }))

  return {
    calls,
    put,
    dirs,
    git: (stdout: string, exitCode = 0) => {
      gitStdout = stdout
      gitExit = exitCode
    },
    refuseGit: (reason: string) => {
      gitDeny = reason
    },
  }
}

const skill = ($: Engine) => $.skill.prompt({ skill: 'chantier', text: 'THE PROMPT' })
const board = ($: Engine) => $.ui.mount({ ...PANE, surface: 'terminal' })
const words = async (ui: any) =>
  [
    ...(await ui.findAll({ type: 'Text' })).map((t: any) => t.text),
    ...(await ui.findAll({ type: 'Button' })).map((b: any) => b.props.label),
    ...(await ui.findAll({ type: 'Markdown' })).map((m: any) => m.props.text),
  ].join('\n')

test('the chantier skill opens the pane and returns its prompt unchanged', async ($, on) => {
  mock.clock(on)
  const w = world(on)
  w.put(INDEX, index())

  const out = await skill($)
  expect(out.text).toBe('THE PROMPT')
  expect(w.calls.open).toBe(1)
  expect(w.calls.run[0].argv).toEqual(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'])
  // The first check runs at opening.
  expect(w.calls.stat).toContain(INDEX)

  await $.skill.prompt({ skill: 'another', text: 'X' })
  expect(w.calls.open).toBe(1)
})

test('/chantier-board opens the pane, then closes it', async ($, on) => {
  mock.clock(on)
  const w = world(on)
  w.put(INDEX, index())
  const run = () => $.command.run({ command: 'chantier-board', args: '', origin: { kind: 'plugin', name: 'test' }, presentation: { isFullscreen: false, columns: 80 } })

  expect((await run()).text).toBe(
    'CR board opened on the machine running this session; a Remote Control view does not show it.',
  )
  expect(w.calls.open).toBe(1)
  expect((await run()).text).toBe('CR board closed.')
  expect(w.calls.close).toBe(1)
})

test('the command is registered immediate, to run during a turn', async ($, on) => {
  mock.clock(on)
  const w = world(on)

  await $.session.start({ source: 'startup', cwd: ROOT } as any)
  expect(w.calls.register).toHaveLength(1)
  expect(w.calls.register[0].immediate).toBe(true)
})

test('a session in a worktree reads the main checkout', async ($, on) => {
  mock.clock(on)
  const w = world(on, '/work/repo.worktrees/cr-1')
  w.git(`${ROOT}/.git\n`)
  w.put(INDEX, index())

  await skill($)
  expect(w.calls.run[0].cwd).toBe('/work/repo.worktrees/cr-1')
  expect(w.calls.stat[0]).toBe(INDEX)
})

test('outside a git repository the session folder is the root', async ($, on) => {
  mock.clock(on)
  const w = world(on, '/work/plain')
  w.git('', 128)
  w.put('/work/plain/.agents/changes/3-requests/STATUS.json', index())

  await skill($)
  expect(w.calls.stat[0]).toBe('/work/plain/.agents/changes/3-requests/STATUS.json')
})

test('a process that is refused is said in one line, with its error', async ($, on) => {
  mock.clock(on)
  const w = world(on)
  w.refuseGit('process.run is not allowed here')

  await skill($)
  expect(w.calls.stat).toEqual([])
  const ui = await board($)
  expect(await words(ui)).toContain('Cannot look for the main checkout: ')
  expect(await words(ui)).toContain('process.run is not allowed here')
  await ui.unmount()
})

test('a file whose time did not change is not read again; one that changed is', async ($, on) => {
  const clock = mock.clock(on)
  const w = world(on)
  w.put(INDEX, index())

  await skill($)
  expect(w.calls.read.filter(p => p === INDEX).length).toBe(1)

  await clock.advance(15000)
  expect(w.calls.stat.filter(p => p === INDEX).length).toBe(2)
  expect(w.calls.read.filter(p => p === INDEX).length).toBe(1)

  w.put(INDEX, index({ active_crs: 7 }))
  await clock.advance(15000)
  expect(w.calls.read.filter(p => p === INDEX).length).toBe(2)
})

test('a closed pane runs no timer', async ($, on) => {
  const clock = mock.clock(on)
  const w = world(on)
  w.put(INDEX, index())
  await skill($)
  await $.command.run({ command: 'chantier-board', args: '', origin: { kind: 'plugin', name: 'test' }, presentation: { isFullscreen: false, columns: 80 } })
  const before = w.calls.stat.length

  await clock.advance(120000)
  expect(w.calls.stat.length).toBe(before)
})

test('without an index the pane says so in one line', async ($, on) => {
  mock.clock(on)
  world(on)

  await skill($)
  const ui = await board($)
  expect(await words(ui)).toBe(`No chantier status here: ${INDEX} not found.`)
  await ui.unmount()
})

test('a file that does not parse keeps the last view; another schema is said alone', async ($, on) => {
  const clock = mock.clock(on)
  const w = world(on)
  w.put(INDEX, index())
  await skill($)
  const ui = await board($)
  expect(await words(ui)).toContain('First change')

  w.put(INDEX, '{ not json')
  await clock.advance(15000)
  const kept = await words(ui)
  expect(kept).toContain('does not parse')
  expect(kept).toContain('First change')

  w.put(INDEX, index({ schema: 3 }))
  await clock.advance(15000)
  const alone = await words(ui)
  expect(alone).toContain('schema 3')
  expect(alone).not.toContain('First change')
  await ui.unmount()
})

test('the board, a sheet and a document open and go back; a path leaving the checkout is plain text', async ($, on) => {
  mock.clock(on)
  const w = world(on)
  w.put(INDEX, index({ merged: [], merged_total: 0 }))
  w.put(`${CR_DIR}/STATUS.json`, sheet())
  w.put(`${CR_DIR}/01-intent.md`, '# Intent\n\nSee [the spec](03-change-spec.md) and [site](https://example.com).')
  w.put(`${CR_DIR}/03-change-spec.md`, '# Spec')

  await skill($)
  const ui = await board($)
  expect(await words(ui)).toContain('Waiting for you')

  await ui.press({ key: REST, link: { href: `file://${CR_DIR}` } })
  const steps = await words(ui)
  expect(steps).toContain('| Step | Done | Verdict |')
  expect(steps).toContain('| Shipped | no | - |')
  expect(steps).not.toContain('a note')
  // The escaping document is plain text in its cell, the other one a link.
  const docs = await ui.find({ key: 'documents' })
  expect(docs?.props.pressableLinks).toEqual([`file://${CR_DIR}/01-intent.md`])
  expect(docs?.props.text).toContain(`[intent](file://${CR_DIR}/01-intent.md) | intent |`)
  expect(docs?.props.text).toContain('| escape | escape |')

  // A link out of the checkout opens nothing on the sheet.
  await ui.press({ key: 'documents', link: { href: 'file:///work/outside.md' } })
  expect(await ui.find({ key: 'documents' })).toBeDefined()

  await ui.press({ key: 'documents', link: { href: `file://${CR_DIR}/01-intent.md` } })
  const doc = await ui.find({ key: 'doc' })
  expect(doc?.props.pressableLinks).toEqual(['03-change-spec.md'])

  await ui.press({ key: 'back' })
  expect(await words(ui)).toContain('Documents')
  await ui.press({ key: 'back' })
  expect(await words(ui)).toContain('Waiting for you')
  await ui.unmount()
})

const REST = `batch-${BATCH}-rest-table`
const batch = (over = {}) => ({ ...index().batches[0]!, ...over })
const label = async (ui: any, key: string) => (await ui.find({ key }))?.props.label as string | undefined

test('a paused batch is folded, with its cost on its title line', async ($, on) => {
  mock.clock(on)
  const w = world(on)
  w.put(INDEX, index({ batches: [batch({ state: 'paused' })] }))

  await skill($)
  const ui = await board($)
  expect(await label(ui, `fold-batch-${BATCH}`)).toContain('$5.07')
  expect(await words(ui)).not.toContain('Waiting for you')
  await ui.press({ key: `fold-batch-${BATCH}` })
  expect(await words(ui)).toContain('Waiting for you')
  await ui.unmount()
})

test('a row draws its severity icon once, in the State column', async ($, on) => {
  mock.clock(on)
  const w = world(on)
  w.put(INDEX, index())
  await skill($)
  const ui = await board($)
  const all = (await words(ui)) as string
  expect(all.split('🟡').length - 1).toBe(1)
  expect(all).toContain('| 🟡 working Round 1/3 |')
  await ui.unmount()
})

test('the board shows each label the CLI draws unchanged, one icon per state', async ($, on) => {
  mock.clock(on)
  const w = world(on)
  const labels = [
    '⚪ queued',
    '🟠 queued, waits for CR-1 queued',
    '🟡 working Round 1/3',
    '🟠 blocked Waits 1/3',
    '🔴 blocked Question 1/3',
    '🔵 ready Notify 1/3',
    '✅ merged',
    '⚪ dropped',
  ]
  const crs = labels.map((label, i) => row({ cr: `CR-${i + 1}`, label, silent_minutes: null }))
  w.put(INDEX, index({ batches: [batch({ crs })] }))
  await skill($)
  const ui = await board($)
  const shown = (await words(ui)) as string
  for (const label of labels) expect(shown).toContain(`| ${label} |`)
  await ui.unmount()
})

test('Backlog, Merged and Trashed are folded and open when pressed', async ($, on) => {
  mock.clock(on)
  const w = world(on)
  const past = (cr: string, state: string) => ({
    cr, title: `${cr} title`, state, batch: 'demo', pr: null, cost_usd: 2, when: '2026-11-01T10:00:00Z', path: `../archives/${cr}`,
  })
  w.put(
    INDEX,
    index({
      backlog: [{ priority: 'P1', item: 'idea', title: 'An idea', path: '1-backlog/P1/idea', files: 2 }],
      merged: [past('CR-7', 'merged')],
      merged_total: 12,
      trashed: [past('CR-8', 'cancelled')],
      trashed_total: 3,
    }),
  )

  await skill($)
  const ui = await board($)
  expect(await label(ui, 'fold-backlog')).toContain('Backlog (1)')
  expect(await label(ui, 'fold-merged')).toContain('Merged (1 of 12)')
  expect(await label(ui, 'fold-trashed')).toContain('Trashed (1 of 3)')
  const closed = await words(ui)
  for (const hidden of ['CR-7 title', 'CR-8 title']) expect(closed).not.toContain(hidden)
  expect(await ui.find({ key: 'backlog-table' })).toBeUndefined()

  await ui.press({ key: 'fold-backlog' })
  expect((await ui.find({ key: 'backlog-table' }))?.props.text).toContain('| P1 |')

  await ui.press({ key: 'fold-merged' })
  await ui.press({ key: 'fold-trashed' })
  const open = await words(ui)
  expect(open).toContain('CR-7 title')
  expect(open).toContain('CR-8 title')
  await ui.press({ key: 'fold-merged' })
  expect(await words(ui)).not.toContain('CR-7 title')
  await ui.unmount()
})

test('a table holds no long text: why a CR is blocked is a fold of its own', async ($, on) => {
  mock.clock(on)
  const w = world(on)
  const blocked = row({ state: 'blocked', label: '🔴 blocked Blocked 2/3', blocked: 'needs a restack' })
  w.put(INDEX, index({ batches: [batch({ crs: [blocked] })] }))
  await skill($)
  const ui = await board($)
  const shown = await words(ui)
  expect(shown).toContain('| 🔴 blocked 2/3 |')
  expect(shown).not.toContain('needs a restack')
  await ui.press({ key: `fold-batch-${BATCH}-why` })
  expect(await words(ui)).toContain('needs a restack')
  await ui.unmount()
})

test('a cell escapes backslash and pipe and folds whitespace; a link out of the checkout opens nothing on the board', async ($, on) => {
  mock.clock(on)
  const w = world(on)
  w.put(INDEX, index({ batches: [batch({ crs: [row({ title: 'a|b\\c\n  d' })] })] }))
  await skill($)
  const ui = await board($)
  expect(await words(ui)).toContain('| a\\|b\\\\c d |')
  await ui.press({ key: REST, link: { href: 'file:///work/outside' } })
  expect(await words(ui)).toContain('Waiting for you')
  await ui.unmount()
})

test('a batch header shows its slots, and nothing when the index has none', async ($, on) => {
  mock.clock(on)
  const w = world(on)
  w.put(INDEX, index({ batches: [batch({ slots: { taken: 2, total: 3 } })] }))
  await skill($)
  const ui = await board($)
  expect(await words(ui)).toContain('Slots 2/3, 1 free')
  await ui.unmount()

  w.put(INDEX, index({ batches: [batch()] }))
  await skill($)
  const old = await board($)
  expect(await words(old)).not.toContain('Slots')
  await old.unmount()
})

test('a live batch whose Foreman is silent for long says so', async ($, on) => {
  mock.clock(on, { now: Date.parse('2026-11-06T10:00:00Z') })
  const w = world(on)
  w.put(INDEX, index({ batches: [batch({ heartbeat: '2026-11-06T09:10:00Z' })] }))
  await skill($)
  const ui = await board($)
  expect(await words(ui)).toContain('Foreman silent for 50 min')
  await ui.unmount()

  w.put(INDEX, index({ batches: [batch({ heartbeat: '2026-11-06T09:55:00Z' })] }))
  await skill($)
  const fresh = await board($)
  expect(await words(fresh)).not.toContain('Foreman silent')
  await fresh.unmount()
})

test('an item holding only a sub-folder lists it, and the folder lists its file, which opens', async ($, on) => {
  mock.clock(on)
  const w = world(on)
  const dir = `${ROOT}/.agents/changes/3-requests/1-backlog/P1/idea`
  w.put(INDEX, index({ backlog: [{ priority: 'P1', item: 'idea', title: 'An idea', path: '1-backlog/P1/idea', files: 1 }] }))
  w.put(`${dir}/intake/request.md`, '# Request')
  w.dirs.set(n(dir), ['intake'])
  w.dirs.set(n(`${dir}/intake`), ['request.md'])

  await skill($)
  const ui = await board($)
  await ui.press({ key: 'fold-backlog' })
  await ui.press({ key: 'backlog-table', link: { href: `file://${dir}` } })
  const top = await ui.find({ key: 'files' })
  expect(top?.props.pressableLinks).toEqual([`file://${dir}/intake`])
  expect(top?.props.text).toContain('intake/')
  await ui.press({ key: 'files', link: { href: `file://${dir}/intake` } })
  const inner = await ui.find({ key: 'files' })
  expect(inner?.props.text).toContain('request.md')
  await ui.press({ key: 'files', link: { href: `file://${dir}/intake/request.md` } })
  expect((await ui.find({ key: 'doc' }))?.props.text).toBe('# Request')
  await ui.unmount()
})

test('an inbox or backlog item opens as the list of every file it holds', async ($, on) => {
  mock.clock(on)
  const w = world(on)
  const dir = `${ROOT}/.agents/changes/3-requests/1-backlog/P1/idea`
  w.put(INDEX, index({ backlog: [{ priority: 'P1', item: 'idea', title: 'An idea', path: '1-backlog/P1/idea', files: 2 }] }))
  w.put(`${dir}/01-intent.md`, '# Intent')
  w.dirs.set(n(dir), ['01-intent.md', 'notes.txt', '02-more.md'])

  await skill($)
  const ui = await board($)
  await ui.press({ key: 'fold-backlog' })
  await ui.press({ key: 'backlog-table', link: { href: `file://${dir}` } })
  const files = await ui.find({ key: 'files' })
  expect(files?.props.text).toContain('| File |')
  expect(files?.props.pressableLinks).toEqual([`file://${dir}/01-intent.md`, `file://${dir}/02-more.md`, `file://${dir}/notes.txt`])
  expect(files?.props.text).toContain('notes.txt')
  await ui.press({ key: 'files', link: { href: `file://${dir}/01-intent.md` } })
  expect((await ui.find({ key: 'doc' }))?.props.text).toBe('# Intent')
  await ui.unmount()
})

test('a document over 200 KB or not UTF-8 is not shown, with one line', async ($, on) => {
  mock.clock(on)
  const w = world(on)
  w.put(INDEX, index())
  w.put(
    `${CR_DIR}/STATUS.json`,
    sheet({ documents: [{ kind: 'big', path: 'big.md' }, { kind: 'bin', path: 'bin.md' }] }),
  )
  w.put(`${CR_DIR}/big.md`, 'a'.repeat(200 * 1024 + 1))
  w.put(`${CR_DIR}/bin.md`, 'caf\uFFFD')

  await skill($)
  const ui = await board($)
  await ui.press({ key: REST, link: { href: `file://${CR_DIR}` } })
  await ui.press({ key: 'documents', link: { href: `file://${CR_DIR}/big.md` } })
  expect(await words(ui)).toContain(`${CR_DIR}/big.md is over 200 KB: not shown.`)
  expect(await ui.find({ key: 'doc' })).toBeUndefined()
  await ui.press({ key: 'back' })
  await ui.press({ key: 'documents', link: { href: `file://${CR_DIR}/bin.md` } })
  expect(await words(ui)).toContain(`${CR_DIR}/bin.md is not UTF-8: not shown.`)
  expect(await ui.find({ key: 'doc' })).toBeUndefined()
  await ui.unmount()
})

test('an https link stays a link; a relative link opens in the pane', async ($, on) => {
  mock.clock(on)
  const w = world(on)
  w.put(INDEX, index())
  w.put(`${CR_DIR}/STATUS.json`, sheet({ documents: [{ kind: 'intent', path: '01-intent.md' }] }))
  w.put(`${CR_DIR}/01-intent.md`, 'See [the spec](03-change-spec.md) and [site](https://example.com).')
  w.put(`${CR_DIR}/03-change-spec.md`, '# Spec')

  await skill($)
  const ui = await board($)
  await ui.press({ key: REST, link: { href: `file://${CR_DIR}` } })
  await ui.press({ key: 'documents', link: { href: `file://${CR_DIR}/01-intent.md` } })
  const doc = await ui.find({ key: 'doc' })
  // The https link is left to the surface: not in the pane's list, still in the text.
  expect(doc?.props.pressableLinks).not.toContain('https://example.com')
  expect(doc?.props.text).toContain('(https://example.com)')

  await ui.press({ key: 'doc', link: { href: '03-change-spec.md' } })
  expect((await ui.find({ key: 'doc' }))?.props.text).toBe('# Spec')
  await ui.press({ key: 'back' })
  expect((await ui.find({ key: 'doc' }))?.props.text).toContain('See [the spec]')
  await ui.unmount()
})
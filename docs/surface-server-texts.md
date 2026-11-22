# The surface server

The surface server, started with chantier serve, is one process per planning surface and machine. The planning folder stays the only truth: plain JSON and Markdown, edited by the CLI, the agents, git and you, with no database; the server reads it and edits only the backlog and the configuration, through the CLI's own commands, never a batch. The process holds the web board with its published API (a WebSocket, and HTTP as the same protocol, behind a key: the private key reads and acts, the public key reads only), the forge hub, which reads the forge read-only at most every 20 s and appends journal lines, and the writer, which commits, rebases and pushes the surface's published paths within 5 minutes of a change. It reads the files cheaply: each project's state sits in memory behind a fingerprint of its folder, a walk of file stats with no file opened; the system's change notifications (watchfiles) say what moved; one walk follows once a project's files are quiet for 1 s, at most 5 s after the first change; the archives and the trash are read for their last folders only. Each session's watcher subscribes to the events of its project, reads only that project's journal lines and wakes its session. The clients are the web board, chantier live in a terminal and any API client.

## Header

```md
## 🖥️ The surface server

One process per planning surface and machine: it serves the plan, and the plan stays the only truth.
```

## Clients (left)

```md
🌐 The web board
browser, phone
```

```md
⌨️ chantier live
terminal, reads only
```

```md
🔌 Any API client
scripts, other tools
```

```md
🔑 Two keys
private: reads and acts
public: reads only
```

## The server process

```md
chantier serve
· one process, four jobs
```

```md
🌐 The web board and its published API

one API: a WebSocket, and HTTP as the same protocol (for a network where a WebSocket does not pass)
behind a key: the private key reads and acts, the public key reads only
serves the record, the planning folder's files and the web client's files
```

```md
👁️ How it reads

each project's state sits in memory, behind a fingerprint of its folder:
a walk of file stats, no file opened; a project that did not change answers 304
the system's change notifications (watchfiles) say what moved
one walk once a project's files are quiet for 1 s, at most 5 s after the first change
the archives and the trash: only their last folders; no notifications: a check every 5 s
```

```md
🏛️ The forge hub

reads the forge, read-only, with your own gh or glab, through the connector of its forge
at most every 20 s, and only while a client is subscribed
appends journal lines: a merge, a red CI, a wait met; runs no git, messages no agent
```

```md
✍️ The writer

commits, rebases and pushes the surface's published paths (projects/, root chantier.yaml)
within 5 minutes of a change, with your own git identity and hooks, never forced
one writer per surface and machine, held by an OS lock
```

```md
The server never edits a batch and never messages an agent.
```

## Session watchers (right)

```md
👀 Session watchers

one per project and session,
reads only its project's
journal lines (events topic),
and wakes its session
```

```md
events
```

## The forge and the surface's remote (right)

```md
🦊 The forge

GitHub · GitLab
PRs and MRs, read only
```

```md
reads
```

```md
🌿 The surface's remote

its git repository,
fetched and pushed
```

```md
fetch · push
```

## The planning folder (bottom)

```md
reads the files, appends journal lines, edits the backlog
```

```md
🗄️ The planning folder, the only truth

plain JSON and Markdown, no database
edited by the CLI, the agents, git and you
the server reads it and edits only the backlog and the configuration,
through the CLI's own commands
```

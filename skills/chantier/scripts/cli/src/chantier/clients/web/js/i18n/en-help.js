// English words of the Help page: its intro and headings, then each topic's name, one-line summary and
// body (plain text, paragraphs split by a blank line, a list as lines starting with `- `).
// Merged into en.js.
export default {
  'help.intro':
    'chantier in a few cards: its concepts and the roles of its agents. Click a card for more.',
  'help.concepts': 'Concepts',
  'help.roles': 'Roles',
  'help.close': 'Close',
  'help.read_more': 'Read more',
  'help.change_request.name': 'Change request',
  'help.change_request.line':
    "One level over your tracker's issues: a folder that describes what you want.",
  'help.change_request.body':
    "A Change Request (CR) sits one level over the issues of your tracker. Small requests that do not belong in the tracker, an idea, a bug, a report, are accepted and prioritised here without entering it. The tracker keeps the strategic, long-term plan; the planning folder is the tactical, short-term one, closest to the work site.\n\nA CR is a folder, and its content varies, from one line of text to several HTML prototypes. The agents read it and find the request's intent.\n\nCRs are fungible in the plan: they can be split, merged or dropped.",
  'help.grill.name': 'Grill and specification',
  'help.grill.line':
    'The questions a change needs, asked one by one, then written down as a specification.',
  'help.grill.body':
    'The Chief of Staff, or a Griller, asks the questions a change needs. Each answer is recorded in the CR.\n\nWhen you say "grilled enough", you choose where the CR goes: the next batch (3-ready, the default) or the running batch, offered only while a batch is open.\n\nThen the spec-writer writes the Change Specification in the background. On an impactful CR, the spec critic checks it afterwards and never edits it.\n\nNothing starts without your go.',
  'help.planning_folder.name': 'Planning folder',
  'help.planning_folder.line': 'Where chantier writes everything, as plain Markdown and JSON.',
  'help.planning_folder.body':
    "The planning folder is the only place chantier writes. Everything in it is Markdown and JSON, readable by you and by the agents.\n\nA CR moves through its stages as folders:\n\n- the inbox, where ideas land\n- the backlog, P1 to P4\n- 3-ready, the next batch\n- 4-batch, with pending, active and done CRs\n- then the archives\n\nIt is .agents/changes/ in your project, or the project's folder of an external planning surface.",
  'help.batch.name': 'Batch and slots',
  'help.batch.line': 'A set of CRs built together, up to ready-to-merge pull requests.',
  'help.batch.body':
    'chantier is not continuous delivery, where one intent is one PR and one release. It is n CRs, m PRs (normally close to n), p batches, and one release.\n\nYou plan a set of CRs ahead, for instance by grilling during the day, and chantier builds the batch on its own, up to ready-to-merge PRs.\n\nSlots are the CRs that run side by side. A CR added while the batch runs is queued and taken when a slot frees.\n\nA batch is running, paused or closed. A batch closes on your yes, and you merge the pull requests yourself.',
  'help.cr_lifecycle.name': "A CR's life",
  'help.cr_lifecycle.line': 'From planning to archive: study, implementation, QA and release.',
  'help.cr_lifecycle.body':
    "A CR is carried through planning, study, implementation, QA, deployment and finally archive.\n\n- Planning is mainly with the Chief of Staff.\n- The central implementation loop delegates to Drivers, with strict reviews.\n- A QA loop lets a validation agent act like a user, to check what the integration and end-to-end tests do not.\n- The release runs with supervised auto-merge, and can monitor the deployment, to production, to package registries or to documentation pages.\n\nEach step has an agent that acts, and several files, mostly Markdown, are added to the CR's folder along the way.",
  'help.planning_modes.name': 'Planning modes',
  'help.planning_modes.line': 'Plan inside your project, or in a repository of its own.',
  'help.planning_modes.body':
    "Chantier plans in one of two places.\n\n- In-project, the default, with nothing to declare: .agents/changes/ in your project.\n- External: a git repository of its own, the planning surface, with one folder per project. Your project's repository gets only the code and, if you want, each CR's cleaned archive in its PR.\n\nThe Chief of Staff, the Foreman and the Griller run on the default branch: your project's main checkout in-project, the surface's checkout in external mode. Only the code gets worktrees, one per CR, in your project.\n\nIn a planning surface, the surface server commits and pushes the plan.",
  'help.steering.name': 'Direct or Foreman',
  'help.steering.line':
    'Who steers the batch: the Chief of Staff itself, or a nested Foreman session.',
  'help.steering.body':
    'In direct mode the Chief of Staff steers the batch itself. In Foreman mode a nested Foreman session steers it.\n\nThe mode follows where you are: Foreman at the desktop, direct from the phone under Remote Control, or in a terminal or VS Code. Saying foreman or direct forces one.\n\nIn both modes a CR added while the batch runs is queued and taken when a slot frees.\n\nDirect mode is simpler to use remotely. In Foreman mode the Chief of Staff stays free to grill while the Foreman runs the batch. In direct mode it holds no grill while a batch runs: open a Griller session instead.',
  'help.batch_modes.name': 'Batch modes',
  'help.batch_modes.line': "Parallel, series or stack: how a batch's pull requests relate.",
  'help.batch_modes.body':
    'A batch has one of three modes. They say how the PRs relate, and who merges what, when. You merge, never chantier.\n\n- Parallel, the default: every CR starts from the default branch at once. You merge in the order PRs become ready; after each merge the others are rebased.\n- Series: the CRs have the order you gave. The next one starts once the previous is handed back, and its PR is a draft until the previous merges.\n- Stack: parallel, with a stack driver that makes one native stack of PRs on the forge.\n\nA CR that depends on another (depends.json) waits for it in every mode. A running batch can switch mode on request.',
  'help.project_rules.name': "Your project's rules",
  'help.project_rules.line':
    'Your changes must land without chantier: your own files are the only configuration.',
  'help.project_rules.body':
    "Your changes must be able to land without chantier. chantier is there to industrialise, not to replace your rules.\n\nYour AGENTS.md, and an optional chantier.yaml, are the only configuration. The chantier.yaml sets the agent and model of each role, and the skills it needs. It can be the project's, and its planning surface's.\n\nEverything chantier writes is Markdown and JSON in the planning folder.\n\nYou can use your own agent for a role, or add a review step after the Inspector: say it, and the role runs it from the next batch.",
  'help.gates.name': 'Gates',
  'help.gates.line': 'The fast gate and the long gate you declare in your AGENTS.md.',
  'help.gates.body':
    "A gate is a command that decides whether work is good enough to go on. You declare two in your AGENTS.md.\n\n- The fast gate runs often, for example in a Coder's round.\n- The long gate runs at the pushed head of a CR, by a Verifier, before the CR is handed back.\n\nAt init, the Chief of Staff checks the long gate, and proposes the exact lines to write in your AGENTS.md. It writes them on your yes.\n\nYou can change them later: say, for instance, that your long gate is npm test.",
  'help.costs.name': 'Costs and limits',
  'help.costs.line': 'What a batch costs, and the limits that cap it.',
  'help.costs.body':
    'A batch has a budget. Steering and the Drivers are most of what it spends; coding itself is a small share.\n\nThe Chief of Staff\'s own session is priced apart, on its own lines, and never in the budget.\n\nTo measure your own, ask "what did it cost?" or run chantier cost. It gives the spend by role, by CR, and what explains each figure.\n\nTwo limits are set on this board\'s Configuration page, in its Limits tab: the slots of a new batch (batch.slots), and how many CRs are specified at once (specifying.parallel).',
  'help.boards.name': 'Boards',
  'help.boards.line':
    'Three ways to watch a batch: this web board, a pane in Claude Code, a terminal view.',
  'help.boards.body':
    "The same record is shown three ways.\n\n- This web board: live batches, what waits for you, the backlog and the merged CRs. Its Dashboard draws the closed batches as graphs, for one project or, on All projects, summed over every project. It can run on your phone too, where you can triage the backlog. It is one client of the server's published API, which a script can use as well.\n- A read-only pane in Claude Code, opened with /chantier-board or by loading the Chief of Staff.\n- chantier live, a view of a running board in your terminal, read-only toward the server: it writes only live.json, its two column widths.\n\nThe boards show the state; the steering session acts on it.",
  'help.chief_of_staff.name': 'Chief of Staff',
  'help.chief_of_staff.line': 'The one person you talk to, in your own session.',
  'help.chief_of_staff.body':
    "You talk to the Chief of Staff, in your own session. It holds the seat: the one session that opens and runs batches in the repository.\n\nIt keeps the backlog, and asks the questions a change needs. Nothing starts without your go, and you merge the pull requests.\n\nIt opens a batch on your word, and in direct mode it steers the batch itself, starting the Drivers.\n\nIts session is priced apart from the batch's budget.",
  'help.griller.name': 'Griller',
  'help.griller.line': 'An optional session that grills beside the Chief of Staff.',
  'help.griller.body':
    'A Griller is an optional session of yours, started with /chantier:griller. It refines the inbox and the backlog while the Chief of Staff runs batches.\n\nIt never opens a batch. The Chief of Staff picks up what it files.\n\nIt matters most in direct mode, where the Chief of Staff, busy steering, holds no grill while a batch runs.',
  'help.foreman.name': 'Foreman',
  'help.foreman.line': 'A nested session that steers a batch, so the Chief of Staff stays free.',
  'help.foreman.body':
    'In Foreman mode, a nested Foreman session steers each batch. It starts the Drivers and follows the batch.\n\nYour Chief of Staff stays free for a natural, dynamic conversation while the batch runs, so you can grill future topics with it.\n\nThe Foreman is the default at the desktop. From the phone, a terminal or VS Code, direct mode is used instead, unless you ask for foreman.',
  'help.driver.name': 'Driver',
  'help.driver.line': 'Runs one CR in its own worktree, up to a pull request handed back ready.',
  'help.driver.body':
    "A Driver, or CR driver, takes one CR to completion. It works in the CR's own git worktree, in your project.\n\nIt delegates to short workers: the Investigator, Coder, Inspector, Verifier and Debugger, any of which can be your own agent. Its reviews are strict.\n\nIt ends when the pull request is handed back ready to merge. The Foreman, or the Chief of Staff in direct mode, starts the Drivers.",
  'help.spec_writer.name': 'Spec-writer and spec critic',
  'help.spec_writer.line': 'One writes the Change Specification, the other checks it.',
  'help.spec_writer.body':
    "The spec-writer writes the Change Specification in the background, once you say a CR is grilled enough.\n\nOn an impactful CR, the spec critic checks the specification afterwards. It never edits it.\n\nBoth are agents of the Chief of Staff or the Griller: you are not asked to wait for them, and the batch's Drivers start from the specification they leave.",
  'help.investigator.name': 'Investigator',
  'help.investigator.line': 'Optional: maps unfamiliar code before the first round.',
  'help.investigator.body':
    'The Investigator is optional. When the code is unfamiliar, it maps it before round 1.\n\nIt is one of the short workers the CR driver runs. Like the others, it can be your own agent.\n\nIt reads and maps; it does not change the code.',
  'help.coder.name': 'Coder',
  'help.coder.line': 'Writes the code of a round and runs the fast gate.',
  'help.coder.body':
    'The Coder writes the code of a round of a CR, in the CR\'s worktree, and runs your fast gate.\n\nIt is a short worker the CR driver starts. You can name your own agent for it, for instance a language specialist: say "use my rust-coder as the coder".\n\nIf a Coder runs into trouble, a new one can start on the role\'s escalation model.',
  'help.inspector.name': 'Inspector',
  'help.inspector.line': 'Reviews each round, reading the diff before the commit.',
  'help.inspector.body':
    'The Inspector reviews each round, and reads the diff before the commit.\n\nYour own extra review steps run after it: say "add a security review with sec-reviewer" and the Driver runs it after the Inspector.\n\nLike the other workers, the Inspector can be your own agent.',
  'help.verifier.name': 'Verifier',
  'help.verifier.line': 'Runs the long gate at the pushed head before a CR is handed back.',
  'help.verifier.body':
    "The Verifier runs your long gate at the pushed head of a CR, before the CR is handed back. A CR is not ready until the Verifier says it is verified.\n\nThe Verifier's cost is a large part of a parallel batch, since each rebase can ask for a new verification.\n\nIt can be your own agent.",
  'help.debugger.name': 'Debugger',
  'help.debugger.line': 'A short worker that finds why something fails.',
  'help.debugger.body':
    "The Debugger is a short worker the CR driver runs, and it can be your own agent.\n\nIt is one of the three roles that carry an escalation: the model a new agent of that role starts on after a named trouble. The other two are the Coder and the conflict resolver. The escalation model is Opus by default, and is set per role in the configuration.\n\nIts default model is the same as the Verifier's.",
  'help.conflict_resolver.name': 'Conflict resolver',
  'help.conflict_resolver.line': 'Settles the conflicts of a rebase.',
  'help.conflict_resolver.body':
    "The conflict resolver is a worker that settles a rebase's conflicts. The CR driver and the stack driver can both run it.\n\nAfter each merge, in parallel mode, every PR still open is rebased onto the default branch, conflict or not. That is where this worker is called, so it adds to the cost of a parallel batch.",
  'help.stack_driver.name': 'Stack driver',
  'help.stack_driver.line': 'In stack mode, builds the native stack on the forge and restacks it.',
  'help.stack_driver.body':
    'In stack mode, the stack driver is responsible for the PR stacks. As soon as two PRs are handed back ready, it makes one native stack on the forge, and the CRs started afterwards are built on it. This is for GitHub, with the gh stack extension.\n\nWhen a change is inserted into a stack ready to merge, it sends the PRs above back to draft, restacks, and verifies the stack before they turn ready again.',
  'help.release_driver.name': 'Release driver',
  'help.release_driver.line': "Runs a release CR by your project's own procedure.",
  'help.release_driver.body':
    'A release is a CR like the others. The Release driver runs it by your project\'s own release procedure, from your "release" to the archive.\n\nYou approve each irreversible action, or say "auto".\n\nA procedure ranges from a simple package publish to a long one, with a release, its notes, a pipeline to follow and an announcement. It stays written and maintained in your project, and a retro improves it.',
};

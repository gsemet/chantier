// The live refresh: the page subscribes to the `board` topic and to the `project` topic of the
// project shown (the one before is dropped when the project changes), and writes each event into
// the store. The server pushes a change as it sees it; nothing here asks on a timer.
import { withLive } from '../model/live.js';
import { projectState } from './api.js';
import { ALL } from './router.js';
import { subscribe as onStore, snapshot, update } from './store.js';
import { subscribe } from './transport.js';

const FAILS_BEFORE_NOTICE = 2;

export const unreachable = (fails) => fails >= FAILS_BEFORE_NOTICE;

const lines = (b) => JSON.stringify([b?.projects ?? [], b?.writer ?? null]);

// The board's events carry the seats too, which no view shows: redraw on the projects and the writer.
function onBoard(data) {
  if (lines(snapshot().board) !== lines(data)) update({ board: data });
}

const onProject = (project) => (data) => {
  if (snapshot().project === project) update({ data: withLive(data), rev: data.rev });
};

// Read the shown project again now, after a write: one `project.state` call.
export async function reload() {
  const project = snapshot().project;
  if (!project || project === ALL) return;
  const got = await projectState(project);
  if (snapshot().project === project) update({ data: withLive(got.data), rev: got.rev });
}

// Start watching. It returns the function that stops it.
export function start() {
  const offBoard = subscribe('board', {}, onBoard);
  let shown = null;
  let offProject = () => {};
  const follow = ({ project }) => {
    if (project === shown) return;
    shown = project;
    offProject();
    offProject =
      project && project !== ALL ? subscribe('project', { project }, onProject(project)) : () => {};
  };
  follow(snapshot());
  const stop = onStore(follow);
  return () => {
    stop();
    offProject();
    offBoard();
  };
}

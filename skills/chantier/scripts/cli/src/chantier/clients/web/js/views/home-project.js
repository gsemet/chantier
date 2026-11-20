// The "Project" section of Home: where the project is (its folder in the planning surface, its
// repository's path) and its upstream; on All projects, the surface's own path and upstream.
import { html } from '../core/dom.js';
import { safeUrl } from '../core/format.js';
import { t } from '../model/words.js';
import { current, surfacePath } from '../ui/picker.js';

// The forge page of an `origin`: an HTTPS remote as it is, `git@host:owner/repo` as an HTTPS page,
// nothing for any other form.
export function forgePage(origin) {
  const ssh = /^git@([^:/\s]+):(.+?)(?:\.git)?\/?$/.exec(origin);
  if (ssh) return ['https:', '', ssh[1], ssh[2]].join('/');
  return /^https:\/\//i.test(origin) && safeUrl(origin) ? origin.replace(/\.git$/, '') : null;
}

const upstream = (origin) => {
  if (!origin) return html`<span class="mut">${t('project.p_none')}</span>`;
  const page = forgePage(origin);
  return page
    ? html`<a href="${page}" target="_blank" rel="noopener" title="${origin}">${origin}</a>`
    : html`<span title="${origin}">${origin}</span>`;
};

const line = (label, value) => html`<dt>${label}</dt><dd>${value}</dd>`;

const section = (rows) =>
  html`<section class="block wide pjt"><h2>${t('project.section')}</h2><dl>${rows}</dl></section>`;

export function projectBlock(state) {
  const p = current(state);
  if (!p) return '';
  const folder = p.folder ? line(t('project.p_folder'), html`<code>${p.folder}</code>`) : '';
  return section(
    html`${folder}${line(t('project.p_repo'), html`<code>${p.repo_path}</code>`)}${line(t('project.p_origin'), upstream(p.origin))}`,
  );
}

export const surfaceBlock = (state) =>
  section(
    html`${line(t('project.p_path'), html`<code>${surfacePath(state)}</code>`)}${line(t('project.p_origin'), upstream(state.board?.served_origin))}`,
  );

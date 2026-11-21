// The Help page's topics, in display order: each its id (the address's `h=`), its group and the page of
// chantier's documentation it links (null: none). Data only: every word is in i18n/en-help.js and
// fr-help.js, as `help.<id>.name`, `.line` and `.body`.

export const TOPICS = [
  {
    id: 'change_request',
    group: 'concepts',
    doc: 'https://github.com/gsemet/chantier#change-requests-lifecycle',
  },
  {
    id: 'grill',
    group: 'concepts',
    doc: 'https://github.com/gsemet/chantier/blob/main/docs/use-cases.md#turn-ideas-into-ready-work',
  },
  {
    id: 'planning_folder',
    group: 'concepts',
    doc: 'https://github.com/gsemet/chantier/blob/main/docs/planning-folder.md',
  },
  {
    id: 'batch',
    group: 'concepts',
    doc: 'https://github.com/gsemet/chantier/blob/main/docs/use-cases.md#the-life-of-a-batch',
  },
  {
    id: 'cr_lifecycle',
    group: 'concepts',
    doc: 'https://github.com/gsemet/chantier#detailed-lifecycle',
  },
  {
    id: 'planning_modes',
    group: 'concepts',
    doc: 'https://github.com/gsemet/chantier/blob/main/docs/planning-modes.md',
  },
  {
    id: 'steering',
    group: 'concepts',
    doc: 'https://github.com/gsemet/chantier/blob/main/docs/use-cases.md#choose-your-configuration',
  },
  { id: 'batch_modes', group: 'concepts', doc: 'https://github.com/gsemet/chantier#batch-modes' },
  {
    id: 'project_rules',
    group: 'concepts',
    doc: 'https://github.com/gsemet/chantier/blob/main/docs/agents-and-models.md',
  },
  {
    id: 'gates',
    group: 'concepts',
    doc: 'https://github.com/gsemet/chantier/blob/main/docs/gates.md',
  },
  {
    id: 'costs',
    group: 'concepts',
    doc: 'https://github.com/gsemet/chantier/blob/main/docs/costs.md',
  },
  {
    id: 'boards',
    group: 'concepts',
    doc: 'https://github.com/gsemet/chantier/blob/main/docs/boards.md',
  },
  {
    id: 'chief_of_staff',
    group: 'roles',
    doc: 'https://github.com/gsemet/chantier/blob/main/docs/use-cases.md',
  },
  {
    id: 'griller',
    group: 'roles',
    doc: 'https://github.com/gsemet/chantier/blob/main/docs/use-cases.md#a-chief-of-staff-and-grillers-in-remote',
  },
  {
    id: 'foreman',
    group: 'roles',
    doc: 'https://github.com/gsemet/chantier/blob/main/docs/use-cases-foreman.md',
  },
  {
    id: 'driver',
    group: 'roles',
    doc: 'https://github.com/gsemet/chantier/blob/main/docs/agents-and-models.md',
  },
  {
    id: 'spec_writer',
    group: 'roles',
    doc: 'https://github.com/gsemet/chantier/blob/main/docs/use-cases.md#turn-ideas-into-ready-work',
  },
  {
    id: 'investigator',
    group: 'roles',
    doc: 'https://github.com/gsemet/chantier/blob/main/docs/agents-and-models.md',
  },
  {
    id: 'coder',
    group: 'roles',
    doc: 'https://github.com/gsemet/chantier/blob/main/docs/agents-and-models.md',
  },
  {
    id: 'inspector',
    group: 'roles',
    doc: 'https://github.com/gsemet/chantier/blob/main/docs/agents-and-models.md',
  },
  {
    id: 'verifier',
    group: 'roles',
    doc: 'https://github.com/gsemet/chantier/blob/main/docs/gates.md',
  },
  {
    id: 'debugger',
    group: 'roles',
    doc: 'https://github.com/gsemet/chantier/blob/main/docs/agents-and-models.md',
  },
  { id: 'conflict_resolver', group: 'roles', doc: null },
  { id: 'stack_driver', group: 'roles', doc: 'https://github.com/gsemet/chantier#batch-modes' },
  { id: 'release_driver', group: 'roles', doc: 'https://github.com/gsemet/chantier#releases' },
];

export const topicIds = () => TOPICS.map((t) => t.id);

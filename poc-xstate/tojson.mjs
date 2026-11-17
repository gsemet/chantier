import { feedMachine } from '../skills/chantier/scripts/cli/src/chantier/board/web/js/views/prs-feed-machine.js';
import { machineToJSON, getMachineSerializationDiagnostics } from 'xstate';
import { writeFileSync } from 'node:fs';
console.log(JSON.stringify(getMachineSerializationDiagnostics?.(feedMachine), null, 1)?.slice(0, 1500));
writeFileSync('feed.json', JSON.stringify(machineToJSON(feedMachine), null, 2));

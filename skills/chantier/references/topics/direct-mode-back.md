# A switch back to Foreman mode

On the user's word, and only where a Foreman can start: preflight in Foreman mode passes first (P1, P2); under Remote Control it starts a new Foreman or reuses one, as at the desk. Start no new Driver.
- Before the Foreman starts, stop each live Driver you own (CR, stack, QA, release) by the host's stop, after `$CHANTIER note <cr> "switch to Foreman mode: Driver stopped; the Foreman restarts it"`.
- Then start the Foreman with the next epoch, as in starting a batch (`help foreman-start`), adding to its prompt "Resume: restart every CR the switch stopped by the restart path, `resume: switch to Foreman mode`".
- No Driver of yours runs once the Foreman claims (two Drivers on one CR is what this prevents). Your epoch is then stale and your steering commands are refused (exit 3): the batch's steering is the Foreman's.
- A switch to direct mode undoes it.

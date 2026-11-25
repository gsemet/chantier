# The critic's steps, after the spec-writer ends

1. Review the specification against `02-answers.md`.
2. Start one `spec-critic` in the background, first line copied from `playbook`, agent and model as it prints; the prompt names the card and the folder, nothing of the grill. `work/specifying` takes each agent's line (`<time> <agent id> <role>`) until the spec is shown. A refused start: restart once as for the writer.
3. Sort: a finding that touches behaviour (scope, behaviour, risk) is a question; any other (a record fix, a wrong name, a dropped decision, a settled inconsistency, an unproved claim to mark) is a fix. An unproved claim a decision rests on is a question.
4. Fixes first: run the writer once with them in its brief before the user sees anything; a fix it refuses with a reason you accept is dropped, else it is a question.
5. Then the user: one summary line counting what is true ("critique : 10 points, 6 corrigés sans vous, 4 questions"), then the questions with the spec's own, in the series format (at most 5 per call). No question: the line, then the spec. No finding: "critique : aucun point". The full list is shown on request only.
6. Record the answers, run the writer again, review. Run the critic again only if the answers change behaviour ("critique, 2e passage"); else the spec is final once approved.

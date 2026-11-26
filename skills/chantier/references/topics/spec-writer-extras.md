# Spec-writer: a CI job, a matrix, an issue

Parts of a specification that depend on the CR.

- A CR that adds or changes a CI job: read the project's CI files, read-only, to name the environment the job runs in: its system, and what is absent there that the local machine has (caches, tools, credentials, network state). The specification gives the evidence that proves the job before the push as the project's rules ask for it, and says which differences only the job's first CI run can prove. What the CI files and the answers do not give goes in the open questions.
- What the CR changes depends on the host, or on a shipped default versus a configured value: give its host and default matrix ([concepts](../concepts.md), "Words") in the evidence, one line per cell. Name no matrix when there is no such dependency.
- The CR has an issue: copy its `issue:` line(s) under the specification's title, where [concepts](../concepts.md) places them.
- A check on a shipped file may use a prepared text only for a case the shipped file cannot hold (a refusal, a broken input), named as such and paired with a check on the shipped file.

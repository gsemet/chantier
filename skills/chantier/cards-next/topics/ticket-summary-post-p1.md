# Ticket summary: posting (part 1 of 2)

7. Publish on the yes only, by the Chief of Staff only, every text from its file, never typed in a shell. Route: the tracker's issue artifacts, else attachments, else a collapsed `<details>` of the comment.
 - GitHub (unproved): when `gh issue artifact --help` lists `create` (a preview: read the flags there): `gh issue artifact create <link> work/issue-plan.md --type plan`, then `work/issue-demo.html --type embedded_html`; `gh issue artifact list <link> --json number,name,url`; put the links in the comment, then `gh issue comment <link> --body-file work/issue-comment.md`. Else collapsed sections (plan as Markdown, demo as a fenced `html` block).
 - GitLab (unproved): `glab issue note` reading the message from a file; uploads if `glab` offers them, else collapsed sections.
 - Jira or other (unproved): the capability's comment action fed from the file, never retyped; its attachment action if any, else a collapsed section, else the plan in the comment and no demo, said in the ask.
 A refused or failed post: tell the user the exact text and stop, the texts kept in `work/`; nothing retried another way; if an artifact fails, the comment is not posted.
8. Verify: read back the comment's URL and the artifact or attachment list; say what is visible and to whom (artifacts may be hidden from the reporter).
9. Record under the yes in `02-answers.md`: `Posted on <ticket link>, <date>: comment <url>; plan <ref>; demo <ref or none>`.

# SUARA task management

This folder is the team's shared project tracker. Maintain these Markdown files manually in GitHub or VS Code. No app, database or automation is needed.

| File | What to use it for |
| --- | --- |
| [TASK_BOARD.md](TASK_BOARD.md) | Authoritative status, owner role, dates and dependencies for every task; acceptance checklists for integration work |
| [COMPLETED_TASKS.md](COMPLETED_TASKS.md) | Historical deliverables, evidence and known completion dates |
| [TEAM_ASSIGNMENTS.md](TEAM_ASSIGNMENTS.md) | Map role placeholders to real names and find each role's work |
| [CHANGELOG.md](CHANGELOG.md) | Record actual tracker edits and the reasons for changes |

## Dates and current scope

The planned integration phase runs from **2026-11-04 to 2026-11-29**. All phase dates are proposals awaiting team confirmation. The tracker was actually created on **2026-11-02** (Asia/Seoul). The board's initial Last Updated value, 2026-11-04, is the requested initial planning date, not an actual edit date. Use actual edit dates in the changelog and in later Last Updated changes.

Use ISO dates (`YYYY-MM-DD`) everywhere. Use **Unknown (not verified)** for historical dates that cannot be confirmed. Do not substitute the report date for a task's completion date.

The foundation uses real audio preprocessing, synthetic analyzers, a fictional catalog and fixed mock rankings. Completed foundation work does not mean real AI has been integrated. All T01-T11 integration work starts as Not Started.

## Add a task

1. Find the highest existing integration ID in the board and history, and choose the next unused ID (initially T12). Never reuse or rename an existing ID.
2. Add one authoritative row to the board with the task name, clear description, why it matters, responsible role, planned start, expected deadline, status and dependency IDs.
3. Use **Unassigned** when an owner has not been agreed. Existing E1/E3/E6 labels are proposed role assignments, not confirmed people.
4. Add an acceptance-criteria checklist below the board using the task ID as a heading.
5. Add the task link to the relevant role's assignment row and record the addition in the changelog.

If a date is not agreed, write **TBD (team confirmation needed)** instead of inventing a commitment.

## Update a status

Edit the task's **Status cell in TASK_BOARD.md only**. Use exactly:

| Status | Meaning |
| --- | --- |
| Not Started | Work has not begun |
| In Progress | The owner is actively working |
| Blocked | Work cannot continue; record the blocker and next action |
| In Review | Deliverables are ready and waiting for review |
| Completed | Acceptance criteria are met and completion is supported by evidence |

The table is the sole source of current status. Checkboxes record acceptance criteria, not a second task status. A checked criterion alone does not complete a task. Keep the team Progress column as a link to the board rather than maintaining duplicate counts.

When a status changes, update Last Updated with the actual edit date, add a changelog row and adjust the team summary if responsibilities or blockers changed. For a blocker, add a short note under the task's criteria naming what is missing, who will act and the next check-in date.

## Assign responsibilities

Replace **Unassigned** in TEAM_ASSIGNMENTS.md with the confirmed person's name; keep the role name so existing board rows still make sense. Several roles may be held by one person. Shared tasks need one agreed coordinator; list that person in the task's acceptance notes. Main Pipeline Lead coordinates T01 and all-team activities.

If ownership changes, update the board's responsible role if necessary, the assignment links and the changelog. Do not invent teammate names or treat proposed role ownership as confirmation.

## Change deadlines or dependencies

Edit the planned start/deadline or dependency cell in the board. Record the old value, new value and reason in the changelog using the actual edit date. Review affected successor tasks and the proposed phase deadline with the team. Preserve an original expected deadline in the changelog/history when it is known. Scheduled overlap does not waive an unmet dependency.

## Mark a task completed

1. Review all acceptance criteria and link the reviewed deliverables, test outputs or PR.
2. Set the board's status to Completed only when evidence supports it.
3. Add a historical record in COMPLETED_TASKS.md with ID, name, responsible member, original expected deadline, verified actual completion date (or Unknown), deliverables, evidence and limitations.
4. Update the team summary if needed and add a changelog row.

Keep completed tasks on the board and in history when a new phase begins. Do not copy current status into history or team summaries. If completed work is reopened, update the board, retain the original history, and append a dated reopening note and changelog entry.

## Record a change

Add a row to [CHANGELOG.md](CHANGELOG.md):

`| YYYY-MM-DD | Task ID | What changed (old -> new) | Actual editor or Unassigned | Reason and evidence | `

Use the actual date of the edit in Asia/Seoul, never the planned start date as a backdated activity claim. Record owner, date, status, dependency and scope changes. Identify the actual editor when known.

## Before saving or opening a PR

Check links and unique IDs, review dates/dependencies, and verify evidence for new completions. Confirm that only intended files changed with `git diff` and `git status`. Commit or open a PR using the team's agreed workflow; do not push or merge without explicit approval.

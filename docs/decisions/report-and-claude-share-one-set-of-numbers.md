# Report and Claude share one set of numbers

Status: accepted (2026-10-14)

## Context

Tally logged every session but only Claude could summarise them, through
the MCP `training_summary` tool. Report (RAS-47) puts the same numbers in
the app as a third mode beside Workout and Manage. Two copies of the
splitting rules would drift, and a user who asks Claude "how was last
week?" after looking at Report would get a different answer.

## Decision

`apps/activity/report.py` owns the rules: which sessions fall in a period
(UK days, weeks from Monday, calendar months), how an exercise's time is
shared evenly between its types but counts in full for each muscle, and
what happens to time on a deleted exercise. The Report view and
`training_summary` both call `report.totals`; neither computes a split
itself.

Report is a server-rendered page under `/app/`, styled with Manage's
`planner.css` and its header. It needs a connection, like Manage, so the
phone shows it disabled offline and it is not precached.

## Consequences

- A change to the rules is one edit, and both callers' tests cover it.
- The finish screen on the phone still computes its own split in
  `engine.js` for one session offline; it follows the same rules and is
  checked by the demo-report test, not shared code.
- Balance became the sixth exercise type in the same change, so the
  report's type split and its "Not trained" list include it.

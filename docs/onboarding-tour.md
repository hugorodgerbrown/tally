# Onboarding tour — Tally

The script for the first-run tour. Agree it before building it; the rules
it follows are in
[docs/decisions/every-app-has-an-onboarding-tour.md](decisions/every-app-has-an-onboarding-tour.md).

Status: not written yet.

## The job

One sentence: what a new person should have done, for real, by the end.
This is the event fivebar measures after `Tour finished`.

## The demo data

Who and what is in the private demo copy, and how its dates are set
around today so every screen is full.

## Chapters

One chapter per page the tour visits. Each one: the page intro, then the
zoom-ins, then the real tap that leads to the next page.

### Chapter 0: Welcome

**Page intro:** a warm welcome, what the app is for, and that this is a
demo where nothing is saved.

| Frame | Element | Advances on | Coach mark |
|---|---|---|---|
| 0 | Welcome | Show me round | |

### Chapter 1: <page>

**Page intro:**

| Frame | Element | Advances on | Coach mark |
|---|---|---|---|
| 1.0 | Page intro | Next | |
| 1.1 | | Next | |

### Last chapter: Over to you

The demo copy is deleted and the person lands on their real first action.

## Events

| Event | Sent when | Data |
|---|---|---|
| `Tour started` | The tour is started | `replay`: true / false |
| `Tour ended` | End tour is tapped | `chapter` |
| `Tour finished` | The last chapter is reached | |
| (the app's first real action) | | `after_tour`: true / false |

## Left out on purpose

What the tour doesn't teach, and where people meet it instead.

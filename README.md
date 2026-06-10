# Scout × Grok — Lead Feed

This repo is the bridge between the **Grok task automation** (which finds artist-hiring
leads on non-Reddit platforms) and the **Scout iOS app**.

## How it works (append-only, never resets)

```
Grok run  ──► creates inbox/<timestamp>.json   (create-only: cannot overwrite anything)
                       │
                       ▼
        GitHub Action (merge-leads.yml)
          • merges all inbox files into leads.json
          • de-dupes by post_id, sorts newest-first
          • normalizes to the exact app schema
          • clears inbox/
                       │
                       ▼
        Scout iOS app  ──► reads leads.json   (single, always-valid file)
```

**Why this design:** Grok's connector can only *replace* a whole file, so asking it
to edit `leads.json` directly caused every run to wipe the previous leads. Instead,
each run writes a brand-new `inbox/` file (it can never clobber another run), and the
Action is the single, deterministic writer of `leads.json`.

The schema below matches the app's `Lead` model in `Scoutios/Models.swift` exactly, so
no app-side decoding changes are required. The Action also auto-corrects schema drift
(legacy keys, bad `quality` strings, fractional seconds, nulls) before the app sees it.

## `leads.json` format

**Top level is a BARE ARRAY of lead objects — NOT an object wrapper.**

```json
[
  {
    "post_id": "x-1933000000000000001",
    "platform": "Twitter/X",
    "source": "@indiegamedev",
    "author": "@indiegamedev",
    "title": "[Hiring] Character artist for card game",
    "content": "Looking for a character illustrator for ~20 cards, paid up front. DM to discuss.",
    "url": "https://x.com/indiegamedev/status/1933000000000000001",
    "quality": "High Quality",
    "budget": "$500",
    "created_at": "2026-06-09T04:30:12Z"
  }
]
```

### Field rules (all REQUIRED — emit `""` rather than omitting a key)
| Key | Type | Rules |
|-----|------|-------|
| `post_id` | string | Stable unique id (`<platform>-<id>`); used for de-dupe. |
| `platform` | string | `Facebook` \| `Twitter/X` \| `Instagram` \| `Discord` \| `Threads`. |
| `source` | string | Handle / page / server the post came from. |
| `author` | string | Who posted it. |
| `title` | string | Short title. |
| `content` | string | Full post text. |
| `url` | string | Link to the post. |
| `quality` | string | **Exactly** one of `High Quality` \| `Medium` \| `Low`. Anything else breaks the whole decode. |
| `budget` | string | Free-form (`"$500"`, `"$50-100"`, `""` for unknown). |
| `created_at` | string | ISO-8601 UTC, **no fractional seconds** (e.g. `2026-06-09T05:34:12Z`). |

### Hard constraints (a single violation fails decoding of the entire array)
- Top level is an **array**, not `{ "leads": [...] }`.
- `quality` must be one of the three exact strings above.
- `created_at` must be plain ISO-8601 with a `Z`/offset and **no milliseconds**.
- Every key must be present on every object; use empty strings, never omit.

## App endpoint

The app reads via the GitHub Contents API with `Accept: application/vnd.github.v3.raw`:

```
https://api.github.com/repos/<owner>/<repo>/contents/leads.json?ref=main
```

The Reddit feed is written by `Jack0fcodes/redd0tBot`. Grok writes the non-Reddit
feed here in `Jack0fcodes/Scout_Grok`. See the app's `LeadStore.swift` `endpoint`
constant to point it at the desired source(s).

## Grok task prompt (create-only — paste into the scheduled Grok task)

```
Act as a client-finding assistant with GitHub access via my connected GitHub account.

STEP 1 — SEARCH
Find posts where people are actively hiring or looking for artists (character art,
illustration, backgrounds, custom cards, etc.).
RULES:
- Only posts from the LAST 3 DAYS. Only real CLIENTS hiring.
- EXCLUDE artists advertising themselves, vague/non-committal posts, and
  closed/outdated/fulfilled requests. DO NOT include Reddit.
PLATFORMS: Facebook, Twitter / X, Instagram, Discord (public servers), Threads.

STEP 2 — BUILD A JSON ARRAY of this run's leads. Each object, ALL keys required
(use "" for unknown, never omit a key):
{
  "post_id": "<platform>-<post id>",
  "platform": "Twitter/X",            // Facebook | Twitter/X | Instagram | Discord | Threads
  "source": "<handle / page / server>",
  "author": "<who posted>",
  "title": "<short title>",
  "content": "<full post text; include contact method here>",
  "url": "<link to the post>",
  "quality": "High Quality",          // EXACTLY "High Quality" | "Medium" | "Low"
  "budget": "$500",                   // free-form string, or ""
  "created_at": "2026-06-09T05:34:12Z" // ISO-8601 UTC, NO fractional seconds
}

STEP 3 — SAVE (CREATE-ONLY). Using my connected GitHub account, CREATE A NEW FILE
in repository Jack0fcodes/Scout_Grok on branch main at path:
  inbox/<current UTC timestamp>.json     e.g. inbox/2026-06-09T1430.json
whose entire contents are the JSON array from Step 2 (a bare array: [ {...}, ... ]).
Do NOT read, edit, or overwrite leads.json or any existing file — only create this
one new inbox file. If there are no qualifying leads, create the file with an empty
array: []
Reply only with: "Created inbox/<filename> with N leads".
```

Key point: the prompt tells Grok to **create a new `inbox/` file every run** and to
**never touch `leads.json`** — that's what makes resets impossible. The Action handles
all merging.

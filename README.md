# Scout × Grok — Lead Feed

This repo is the bridge between the **Grok task automation** (which finds artist-hiring
leads on non-Reddit platforms) and the **Scout iOS app**.

- Grok searches for leads and writes them to **`leads.json`** via the GitHub connector.
- The Scout app fetches `leads.json` and renders the feed.

The schema below matches the app's `Lead` model in `Scoutios/Models.swift` exactly, so
no app-side decoding changes are required.

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

# Scout × Grok — Lead Feed

This repo is the bridge between the **Grok task automation** (which finds artist-hiring
leads) and the **Scout iOS app** (which displays them).

- Grok searches for leads and writes them to **`leads.json`** via the GitHub connector.
- The Scout app fetches that JSON and renders the feed.

Raw URL the app reads:

```
https://raw.githubusercontent.com/Jack0fcodes/Scout_Grok/main/leads.json
```

## `leads.json` schema

```jsonc
{
  "generatedAt": "2026-06-09T06:00:00Z",   // ISO 8601 UTC, when this run wrote the file
  "count": 2,                               // number of items in "leads"
  "leads": [
    {
      "id": "x-1933000000000000001",        // stable unique id (platform + post id) for de-dupe
      "platform": "Twitter/X",              // Reddit | Twitter/X | Facebook | Instagram | Discord | Threads
      "source": "@indiegamedev",            // subreddit, handle, server, or page the post came from
      "author": "@indiegamedev",            // who posted it
      "title": "[Hiring] Character artist for card game",
      "description": "Looking for a character illustrator for ~20 cards, paid up front.",
      "priority": "High",                   // High | Medium | Low
      "budget": "$500",                     // display string, or null when unknown ("No budget")
      "contact": "DM @indiegamedev",        // how to reach the client
      "postLink": "https://x.com/indiegamedev/status/1933000000000000001",
      "datePosted": "2026-06-09T04:30:00Z"  // ISO 8601 UTC; app computes "Xm ago"
    }
  ]
}
```

### Field notes
- **`budget`** is a string for flexible display (`"$500"`, `"$50–100"`); use `null` for unknown → app shows "No budget".
- **`priority`** drives the High/Medium/Low badge.
- **`datePosted`** must be ISO 8601 UTC so the app can compute relative time.
- **`id`** lets the automation de-duplicate across runs (same post never added twice).

## Swift (Codable) model for the app

```swift
struct LeadFeed: Codable {
    let generatedAt: Date
    let count: Int
    let leads: [Lead]
}

struct Lead: Codable, Identifiable {
    let id: String
    let platform: String
    let source: String
    let author: String
    let title: String
    let description: String
    let priority: String     // "High" | "Medium" | "Low"
    let budget: String?      // nil → "No budget"
    let contact: String
    let postLink: String
    let datePosted: Date
}

// Decoding:
let decoder = JSONDecoder()
decoder.dateDecodingStrategy = .iso8601
let feed = try decoder.decode(LeadFeed.self, from: data)
```

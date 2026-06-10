# inbox/

Drop zone for the Grok task automation.

**Each Grok run creates ONE new file here** named with a timestamp, e.g.
`inbox/2026-06-10T0900.json`, containing a bare JSON array of that run's new leads.

Grok must only **create** files here — never edit `leads.json` directly. Because
each run writes a brand-new filename, runs can never overwrite or wipe each other.

A GitHub Action (`.github/workflows/merge-leads.yml`) then:
1. merges every file in this folder into the canonical `../leads.json`,
2. de-duplicates by `post_id` and sorts newest-first,
3. normalizes each record to the exact schema the Scout app decodes,
4. clears this folder.

So this folder is normally empty between runs — that's expected.

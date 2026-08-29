# CSV → schedule JSON (LLM prompt)

Use [`csv-to-schedule-llm-prompt.json`](csv-to-schedule-llm-prompt.json) as the system/instruction payload for an LLM that should turn a start-list CSV into Raspberry-PAB import JSON.

## How to use

1. Paste the contents of `csv-to-schedule-llm-prompt.json` as the system prompt (or “instructions”).
2. Send a user message like:

```text
event_date: 2026-06-21

CSV:
name,race,call_up,start_time
Carlos,Pro Men,Staging,11:00
Ana,Pro Women,11:00,11:15
```

3. Expect a single JSON object matching Admin → **Import JSON** / `POST /api/import`.

## Notes

- Preferred CSV headers: `name,race,call_up,start_time`
- Legacy `name,start_time` is fine; `race` / `call_up` become empty / omitted
- The Pi can also import CSV directly via Admin → **Import CSV** without an LLM

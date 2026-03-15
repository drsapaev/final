# W2D Appointments QRCode Legacy Contract

Date: 2026-03-11
Mode: docs-only review

## Mounted contract

Legacy route:

- `GET /api/v1/appointments/qrcode`
- mounted in `backend/app/api/v1/endpoints/appointments.py`
- function: `qrcode_png()`

## Request shape

Accepted query parameters:

- `department` (required)
- `date_str` (optional)
- `date` (optional)
- `d` (optional)

Those date variants are normalized through `_pick_date(...)`.

## Response shape

Current response is a tiny compatibility payload:

```json
{
  "format": "text",
  "data": "<department>::<effective_date>"
}
```

The route does not generate a PNG.

## Runtime meaning

`appointments/qrcode` is not:

- a queue allocator path
- an OnlineDay lifecycle owner
- a stats path

It is a small compatibility helper that returns QR-related source data for the
frontend-side rendering flow.

The route comment in code explicitly describes it as a stub:

- "Маршрут-заглушка"
- return data for frontend-side QR rendering

## State effects

This route is read-only:

- no `OnlineDay` writes
- no `Setting(category="queue")` writes
- no queue issuance
- no stats mutation
- no broadcast side effects

## Architectural position

Within the remaining OnlineDay legacy island, this surface is lighter than
`open_day`, `close_day`, `next_ticket`, `appointments.stats`, `queues.stats`,
or `board/state`.

It is best understood as a mounted compatibility/support endpoint rather than a
core operational legacy route.

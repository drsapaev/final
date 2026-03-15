# W2D appointments.qrcode deprecation prep

## What changed

The mounted route:

- `GET /api/v1/appointments/qrcode`

is now explicitly marked as deprecated in OpenAPI and has a documented response
model.

The route remains:

- mounted
- read-only
- behaviorally unchanged

## Why this is the right bounded step

Earlier review already showed that this route is:

- a stub compatibility helper
- not an OnlineDay write owner
- not the active frontend QR path
- not backed by a confirmed in-repo live consumer

That makes deprecation-prep the safest next step.

## What did not change

This slice intentionally did not:

- remove the route
- redirect callers
- change the returned payload
- alter QR queue behavior
- touch blocked operational legacy tails

## Practical effect

`appointments/qrcode` is now clearly communicated as:

- legacy
- compatibility-only
- on a retirement path unless stronger consumer evidence appears later

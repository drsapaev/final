# Wave 2C Confirmation Design Intent

Date: 2026-03-07
Mode: analysis-first, docs-only

## Sources Reviewed

- `docs/ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md`
  - section `РњРЅРѕР¶РµСЃС‚РІРµРЅРЅС‹Рµ РѕС‡РµСЂРµРґРё РґР»СЏ РѕРґРЅРѕРіРѕ РїР°С†РёРµРЅС‚Р°`
  - section `Р“РёР±СЂРёРґРЅРѕРµ СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ`
  - section `РЎС†РµРЅР°СЂРёРё РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ`
  - checklist block under `Backend (РѕС‡РµСЂРµРґРё Рё РІРёР·РёС‚С‹)`

## Question 1

Does the design document allow more than one active queue entry for the same
patient in the same queue (`queue_id + day`)?

## Answer

No explicit allowance was found.

## Evidence

### Multiple queue entries are described as cross-service, not same-queue duplicates

The design document says one patient may have multiple queue entries, but it
defines that as:

- one entry per service/specialist
- each entry owning its own `queue_time`
- QR multi-select creating separate queue rows for different services

That intent appears in:

- `РњРЅРѕР¶РµСЃС‚РІРµРЅРЅС‹Рµ РѕС‡РµСЂРµРґРё РґР»СЏ РѕРґРЅРѕРіРѕ РїР°С†РёРµРЅС‚Р°`
- `РЎС†РµРЅР°СЂРёР№ 1: QR-СЂРµРіРёСЃС‚СЂР°С†РёСЏ СѓС‚СЂРѕРј (РјРЅРѕР¶РµСЃС‚РІРµРЅРЅР°СЏ)`
- `РЎС†РµРЅР°СЂРёР№ 3: Р”РѕР±Р°РІР»РµРЅРёРµ СѓСЃР»СѓРіРё РІ СЂРµРіРёСЃС‚СЂР°С‚СѓСЂРµ`
- `РЎС†РµРЅР°СЂРёР№ 5: Р”РѕР±Р°РІР»РµРЅРёРµ СѓСЃР»СѓРіРё Рє СЂСѓС‡РЅРѕР№ Р·Р°РїРёСЃРё`

In all of those cases, multiple rows are justified by different services or
specialists, not by creating a second active row in the same queue for the same
patient.

### Hybrid editing preserves existing rows and adds only genuinely new queue claims

`Р“РёР±СЂРёРґРЅРѕРµ СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ` says:

- personal data changes do not change existing queue order
- new services create new queue rows with the current edit time
- old services keep their existing `queue_time` and place

That implies the design expects an existing queue claim to be preserved rather
than duplicated for the same queue/day.

## Question 2

Does the design document allow creating a new queue entry during confirmation
for the same visit?

## Answer

It allows creating the first queue entry for a confirmed visit, but it does not
justify creating an additional active entry when one already exists in the same
queue/day.

## Evidence

### Confirmed visits are supposed to become queue entries

`РЎС†РµРЅР°СЂРёР№ 6: РЈС‚СЂРµРЅРЅСЏСЏ СЃР±РѕСЂРєР° (Morning Assignment)` explicitly says confirmed
visits receive queue entries and move to `open`.

The backend checklist also states that confirmed visits for the current day
receive queue entries.

So the design clearly allows:

- visit is confirmed
- queue entry is created as a result of that confirmation state

### But duplicate-in-same-queue behavior is not described

The document does not define a rule that confirmation may create another active
row in the same queue/day for the same patient or visit.

It also does not define confirmation as an override to the "one row per
service/specialist queue claim" model.

## Design-Intent Verdict

Based on the design document alone:

- multiple active queue rows are intended across different queue claims
  (different services/specialists/queues)
- confirmation may materialize a queue claim for a confirmed visit
- confirmation is not documented as a license to create a second active row in
  the same queue/day when an active row already exists

## Implication For Contract Clarification

The design source supports this inference:

- confirmation should create a queue row only when that queue claim does not
  already exist
- if the queue claim already exists, the domain should prefer reuse or explicit
  conflict handling over silent duplicate creation

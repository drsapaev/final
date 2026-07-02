# FIX 16 & 17: True SSOT Architecture for Frontend

## ✅ STATUS: COMPLETE (2025-12-23)

## Problem Statement

1. Backend returns flat list: 1 row = 1 OnlineQueueEntry.
   Frontend was aggregating/merging entries, breaking the SSOT principle.

2. Backend stores LOCAL time but adds 'Z' (UTC) suffix during JSON serialization.
   Frontend converts "UTC" to local, causing +5 hour offset.

## Root Causes (FIXED)

### FIX 16: SSOT Architecture
Frontend was resolving queue_time via:
- ❌ queue_tag lookup
- ❌ patient-level aggregation
- ❌ "matchingQueue" selection
- ❌ Reading from `entry.data.queue_time` instead of `entry.queue_time`

### FIX 17: Timezone Double Conversion
- ❌ Backend sends `2025-12-23T09:33:24Z` (with 'Z' suffix)
- ❌ Frontend parses as UTC, then converts to local: 09:33 + 5 = 14:33
- ❌ But the time was ALREADY local (09:33), so result is wrong

## Solutions Implemented

### FIX 16: Layer 1 - flatEntries (SSOT)
- Raw array collected BEFORE any deduplication
- Each item = one OnlineQueueEntry
- Contains: entry_id, service_id, queue_tag, queue_time
- queue_time read from `entry.queue_time` (top-level from backend)
- Stored in `rawEntries` state

### FIX 16: Layer 2 - Tab Filtering
- Filters `rawEntries` by queue_tag
- Each row = one entry
- Time column reads `entry.queue_time` directly
- NO aggregation for tabs

### FIX 16: Layer 3 - "All Departments" View
- Uses aggregated `appointments` for visual grouping
- Still shows all queue_numbers in tooltip

### FIX 17: Timezone Fix
- `safeParseDate()` in EnhancedAppointmentsTable.jsx now strips 'Z' suffix
- Time string `2025-12-23T09:33:24Z` → `2025-12-23T09:33:24` (no Z)
- JavaScript parses this as LOCAL time, not UTC
- Result: displays 09:33 correctly

## Acceptance Criteria (ALL PASSED)

✅ Patient with N services → N independent rows
✅ Each row has its own queue_time
✅ Adding new service: old services keep original times
✅ Each tab shows entries with correct times
✅ No aggregation affects queue_time display
✅ Time displays correctly (no +5 hour offset)

## Files Modified

### FIX 16
- `frontend/src/pages/RegistrarPanel.jsx`
  - Collect flatEntries before deduplication
  - Read queue_time from entry.queue_time (top-level)
  - Tab filtering uses rawEntries, not appointments

### FIX 17
- `frontend/src/components/tables/EnhancedAppointmentsTable.jsx`
  - `safeParseDate()`: Strip 'Z' suffix to prevent double timezone conversion

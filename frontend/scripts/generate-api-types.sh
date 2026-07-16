#!/bin/bash
# scripts/generate-api-types.sh
# Phase 0.5 — OpenAPI → TypeScript types generation pipeline.
# Plan: JS-to-TS-Migration-Plan v3, section 0.5.2
#
# Source of truth: backend/openapi.json (FastAPI-generated, 731 schemas / 997 paths)
# Output: src/types/generated/api.ts (read-only after generation)
#
# CI runs `generate:api-types:check` to fail if generated types are stale.
set -euo pipefail

# Resolve repo paths robustly regardless of where the script is invoked from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$FRONTEND_DIR/.." && pwd)"
OPENAPI_PATH="$REPO_ROOT/backend/openapi.json"

OUTPUT_DIR="$FRONTEND_DIR/src/types/generated"
OUTPUT_FILE="$OUTPUT_DIR/api.ts"

if [ ! -f "$OPENAPI_PATH" ]; then
  echo "ERROR: OpenAPI spec not found at $OPENAPI_PATH" >&2
  echo "Ensure backend/openapi.json exists (run backend codegen if needed)." >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

# Use npx to find the locally-installed openapi-typescript binary.
# `--export-type` produces `export type` declarations (recommended for v7+).
npx openapi-typescript "$OPENAPI_PATH" \
  --output "$OUTPUT_FILE" \
  --export-type

# Prepend warning header so nobody edits the file by hand.
HEADER='// ⚠️ АВТОГЕНЕРИРОВАННЫЙ ФАЙЛ — НЕ РЕДАКТИРОВАТЬ ВРУЧНУЮ!
// Источник: backend/openapi.json (731 schemas, 997 paths)
// Регенерация: npm run generate:api-types
// CI guard: npm run generate:api-types:check (fails if generated is stale)
//
// Изменения должны идти через: backend → openapi.json → npm run generate:api-types
//

'

# Use a temp file + mv to avoid sed -i portability issues across GNU/BSD sed.
TMP_FILE="$(mktemp)"
printf '%s' "$HEADER" > "$TMP_FILE"
cat "$OUTPUT_FILE" >> "$TMP_FILE"
mv "$TMP_FILE" "$OUTPUT_FILE"

echo "✅ Generated API types: $OUTPUT_FILE"
echo "   Source: $OPENAPI_PATH"
echo "   Size: $(wc -c < "$OUTPUT_FILE") bytes, $(wc -l < "$OUTPUT_FILE") lines"

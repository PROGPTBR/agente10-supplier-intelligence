# Sprint 3 — Frontend UI + backend endpoints for cluster review/shortlist

**Date:** 2026-05-13
**Goal:** Make Sprint 2's pipeline usable by a non-technical pilot user via a polished web UI. Add the remaining backend endpoints the UI needs.

---

## 0. Context

Sprint 2 shipped the async pipeline (CSV → cluster → CNAE → top-10 shortlist) end-to-end with REST API (POST/GET /api/v1/uploads) + CLI. Sprint 2 final review flagged 3 missing API endpoints, the lack of UI, and `progresso_pct` field gap. Sprint 3 closes all of those.

Frontend stack already scaffolded in Sprint 0: Next.js 16 + React 19 + Tailwind v4 + @base-ui/react. Currently only an empty placeholder home page exists.

The pilot user persona: non-technical procurement analyst who uploads a material catalog (CSV/XLSX), waits ~2 min for processing, reviews 50-200 clusters, overrides 5-20 mis-classified CNAEs, and exports / hands off shortlists to RFx workflows (Sprint 4+).

---

## 1. Objective

Build the **polished MVP** UI (option C from brainstorming):

1. Dashboard with stats and recent activity
2. Uploads list and detail (with live progress)
3. Cluster review with filters, manual CNAE override, notes
4. Shortlist viewer per cluster
5. CNAE override triggers shortlist regeneration

Add the 6 backend endpoints the UI needs. Reuse the Sprint 2 pipeline + tenant_context for everything tenant-scoped.

### Definition of Done

- 5 frontend routes work end-to-end against running backend
- Upload synthetic 50-row CSV → progress bar shows live updates → all clusters appear → CNAE override works → shortlist regenerates → state persists across refresh
- 6 new backend endpoints work + tested
- `pnpm test` runs ≥10 frontend unit tests passing
- `make test-backend-integration` adds ≥4 new API tests, all passing
- `pnpm lint` + `make lint` both clean
- `pnpm build` produces a working production bundle
- Accessibility: forms have labels, tables have ARIA, contrast OK on badges
- No regressions: Sprint 1.2/1.3/2 backend tests still passing

### Out of scope (Sprint 4+)

- Real auth (JWT, multi-user, roles)
- WebSockets / SSE — polling is sufficient
- CSV/Excel export of shortlists
- Bulk actions on clusters
- Playwright E2E automated tests
- i18n (PT-BR hardcoded)
- Mobile-optimized layout (desktop-first; tablet OK)
- Real-time collaboration
- Estágio 4 curator UI (Sprint 1.4 dependency)

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Next.js 16 App Router (no Pages dir)                     │
│  React 19 + Tailwind v4 + @base-ui/react + shadcn         │
│                                                            │
│  /                  → redirect to /dashboard               │
│  /dashboard         → stat cards + recent uploads          │
│  /uploads           → all uploads (table)                  │
│  /uploads/new       → drag-drop CSV upload                 │
│  /uploads/[id]      → live progress + cluster table        │
│  /clusters/[id]     → CNAE override + shortlist preview    │
│                                                            │
│  Server state: TanStack Query v5 (polling, optimistic UI) │
│  Auth: NEXT_PUBLIC_TENANT_ID env → X-Tenant-ID header     │
│  HTTP: fetch wrapper with header injection                 │
└──────────────────────────────────────────────────────────┘
         │ REST
         ▼
┌──────────────────────────────────────────────────────────┐
│  Backend Sprint 2 endpoints + 6 new (Sprint 3)             │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Backend endpoints (new)

```
GET /api/v1/uploads
  Headers: X-Tenant-ID
  Response 200:
    [{ upload_id, nome_arquivo, status, linhas_total,
       linhas_classificadas, data_upload, progresso_pct }, ...]
  Ordered by data_upload DESC

GET /api/v1/uploads/{id}  (already exists, add progresso_pct)
  Response 200: + progresso_pct (linhas_classificadas / max(linhas_total,1) * 100)

GET /api/v1/uploads/{id}/clusters
  Query: ?metodo=retrieval|curator|manual_pending|retrieval_fallback&revisado=true|false
  Response 200:
    [{ id, nome_cluster, cnae, cnae_descricao, cnae_confianca, cnae_metodo,
       num_linhas, revisado_humano, shortlist_size }, ...]
  Joins cnae_taxonomy for descricao; subquery COUNT for shortlist_size.

GET /api/v1/clusters/{id}
  Response 200:
    { id, upload_id, nome_cluster, cnae, cnae_descricao,
      cnae_confianca, cnae_metodo, num_linhas, revisado_humano,
      notas_revisor, shortlist_gerada, sample_linhas: [<= 5 strings] }

GET /api/v1/clusters/{id}/shortlist
  Response 200:
    [{ cnpj, razao_social, nome_fantasia, capital_social, uf, municipio,
       data_abertura, rank_estagio3 }, ...]

PATCH /api/v1/clusters/{id}
  Body: { cnae?, notas_revisor?, revisado_humano?, handoff_rfx? }
  Behavior:
    - If cnae changed: reset shortlist_gerada=false; spawn BackgroundTask
      that re-runs _shortlist_stage for THIS cluster only.
    - Other fields: simple UPDATE.
  Response 200: cluster shape (same as GET /clusters/{id})

GET /api/v1/dashboard/stats
  Response 200:
    { uploads_total, uploads_done, clusters_total, clusters_revised,
      clusters_by_metodo: { retrieval: N, curator: N, manual_pending: N,
                            retrieval_fallback: N },
      shortlists_total,
      recent_uploads: [<= 5 latest UploadSummary objects] }
```

All endpoints validate `X-Tenant-ID` via the existing `get_tenant_id` Depends helper from Sprint 2. RLS enforces isolation.

### Backend file changes

- `backend/src/agente10/api/uploads.py` — add `GET /uploads` list, add `progresso_pct` to existing GET
- `backend/src/agente10/api/clusters.py` (new) — clusters list, cluster detail, shortlist, PATCH
- `backend/src/agente10/api/dashboard.py` (new) — stats
- `backend/src/agente10/main.py` — register 2 new routers
- `backend/src/agente10/estagio3/shortlist_generator.py` (no change, but called from PATCH path) — used by re-trigger logic
- New helper for partial shortlist regen: a small module-level function that wraps `generate_shortlist` for a single cluster (or call directly inside the BackgroundTask).

---

## 4. Frontend file structure

```
frontend/
├── app/
│   ├── layout.tsx                      # root + QueryClientProvider + AppShell
│   ├── globals.css
│   ├── page.tsx                        # redirect to /dashboard
│   ├── dashboard/page.tsx              # stat cards + recent uploads
│   ├── uploads/
│   │   ├── page.tsx                    # uploads list (table)
│   │   ├── new/page.tsx                # CSV upload form
│   │   └── [id]/page.tsx               # progress + cluster table
│   └── clusters/
│       └── [id]/page.tsx               # CNAE override + shortlist
│
├── components/
│   ├── ui/                             # shadcn-generated (button, card, table, dialog, badge, input, label, combobox, progress)
│   ├── shell/
│   │   ├── AppShell.tsx                # sidebar + header + main slot
│   │   └── SidebarNav.tsx              # Dashboard, Uploads links
│   ├── upload/
│   │   ├── UploadDropzone.tsx          # drag-drop CSV/XLSX
│   │   └── UploadProgressBar.tsx       # polled progresso_pct
│   ├── cluster/
│   │   ├── ClusterTable.tsx            # rows with cnae + confianca + metodo + revisado
│   │   ├── ClusterFilters.tsx          # by metodo, by revisado, search
│   │   ├── ClusterCnaeEditor.tsx       # combobox autocomplete
│   │   ├── ClusterReviewForm.tsx       # cnae editor + notas + revisado toggle
│   │   └── ConfidenceBadge.tsx         # color + text by metodo
│   ├── shortlist/
│   │   └── ShortlistTable.tsx          # rank + razao + capital + UF
│   └── dashboard/
│       ├── StatCard.tsx
│       └── ClustersByMetodoChart.tsx   # CSS mini-bar chart
│
├── lib/
│   ├── api/
│   │   ├── client.ts                   # fetch wrapper, X-Tenant-ID injection
│   │   ├── uploads.ts                  # typed queries/mutations
│   │   ├── clusters.ts
│   │   └── dashboard.ts
│   ├── tenant.ts                       # readTenantId() from env
│   ├── types.ts                        # zod schemas for API responses
│   └── cnae-taxonomy.json              # 1331 CNAEs bundled (~80KB)
│
├── tests/
│   ├── components/
│   │   ├── ClusterTable.test.tsx
│   │   ├── ConfidenceBadge.test.tsx
│   │   ├── UploadDropzone.test.tsx
│   │   └── ClusterCnaeEditor.test.tsx
│   └── api/
│       └── client.test.ts
│
└── (existing config: package.json, tsconfig.json, etc.)
```

---

## 5. UX flows

### Upload flow
1. Sidebar **Uploads → New** → `/uploads/new`
2. UploadDropzone: drag CSV/XLSX (max 50MB, descricao_original required)
3. Submit → `POST /uploads` → 202 + upload_id → router push `/uploads/{id}`
4. UploadProgressBar polls `GET /uploads/{id}` every 2s while status ∈ {pending, processing}
5. On status=done: "Review N clusters" button appears, cluster table renders below

### Cluster review flow
1. `/uploads/{id}` shows ClusterTable: nome_cluster, num_linhas, cnae+descricao, ConfidenceBadge, revisado checkbox, shortlist count, "Open" link
2. ClusterFilters above table: metodo dropdown + revisado toggle + nome_cluster search (client-side filter)
3. Click "Open" → `/clusters/{id}` page
4. ClusterReviewForm shows:
   - 5 sample linhas (descricao_original) so revisor sees the data
   - Current cnae + descricao + ConfidenceBadge
   - ClusterCnaeEditor (combobox over bundled taxonomy; fuzzy filter on code + descricao)
   - notas_revisor textarea
   - "Mark reviewed" toggle
5. ShortlistTable below (read-only top-10)
6. "Save" button → PATCH /clusters/{id} (TanStack mutation):
   - Optimistic update of cluster.cnae, revisado_humano in cache
   - If cnae changed: invalidate shortlist query; TanStack refetches and may show stale data briefly. Frontend additionally enables `refetchInterval: 2000` on the shortlist query when `shortlist_gerada=false` (returned by GET /clusters/{id}); polling stops once flag flips to true.
   - Toast on success/failure
7. "Back to clusters" link returns to `/uploads/{id}` with filters preserved (URL state)

### Dashboard
- Auto-load `/dashboard/stats` on mount (TanStack query, refetch on focus)
- 4 StatCards: total uploads, % done, clusters reviewed, % manual_pending
- ClustersByMetodoChart: CSS-based stacked bar (no chart library)
- Recent uploads list: last 5 with status pills

---

## 6. Error handling

### Backend
- 4xx errors return `{detail: string}` (FastAPI default)
- 5xx errors logged; client shows generic toast
- Invalid PATCH cnae (not in cnae_taxonomy) → 400 with helpful message

### Frontend
- TanStack Query retry: 1 attempt on GET, 0 on PATCH (idempotency unclear)
- All mutations show toast on success/error
- Network errors → AppShell-level error banner + retry button
- 404 cluster → redirect to `/uploads` with toast
- Empty states for: no uploads, no clusters, no shortlist (all common — keep informative)

---

## 7. Testing strategy

### Frontend unit (Vitest + @testing-library/react)
- `ClusterTable.test.tsx` — renders rows, filter callbacks
- `ConfidenceBadge.test.tsx` — color/text by metodo
- `UploadDropzone.test.tsx` — drag accepts CSV, rejects PDF, size limit
- `ClusterCnaeEditor.test.tsx` — fuzzy filter narrows, selecting commits
- `client.test.ts` — header injection, error parsing
- `lib/tenant.test.ts` — reads env, throws if missing

### Backend integration
- `test_api_uploads_list.py` — GET list returns sorted, filtered by tenant
- `test_api_clusters_list.py` — GET with metodo + revisado filters
- `test_api_cluster_detail.py` — GET single + sample_linhas
- `test_api_cluster_patch.py` — PATCH cnae triggers shortlist regen; PATCH notas no regen
- `test_api_dashboard_stats.py` — counts match SQL truth

### Manual smoke test (DoD gate)
1. Start `make up` + `pnpm dev`
2. Open `/dashboard` — sees empty state OR existing stats
3. Upload `backend/tests/fixtures/catalogo_sintetico.csv`
4. Watch progress bar to done
5. Open a manual_pending cluster
6. Change CNAE in combobox
7. Confirm shortlist regen visible after ~10s
8. Refresh — state persisted

---

## 8. Decisions fixed

- Polling interval: 2s (UploadProgressBar) while not-terminal
- Stack: Next.js 16 App Router, React 19, Tailwind v4, @base-ui/react, shadcn/ui, TanStack Query v5
- Tenant: `NEXT_PUBLIC_TENANT_ID` env var; `NEXT_PUBLIC_API_BASE_URL` for API base
- CNAE picker: bundled JSON (~80KB), client-side fuzzy filter
- Charts: CSS only (no Recharts/Chart.js) — keep bundle small
- Validation: zod for API response shape; native form validation for inputs
- Toasts: `@base-ui/react` Toast primitive (already in stack)

---

## 9. New dependencies (frontend)

```json
{
  "dependencies": {
    "@tanstack/react-query": "^5.x",
    "zod": "^3.x"
  }
}
```

No new backend deps.

---

## 10. Risks + mitigation

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Next.js 16 App Router gotchas (per AGENTS.md "breaking changes") | High | Medium | Each implementer reads `node_modules/next/dist/docs/` for the specific API they use before writing code |
| PATCH cnae regen race (user navigates away before regen completes) | Medium | Low | Backend is idempotent (shortlist_gerada flag + dedup); next page load fetches fresh data |
| Bundled CNAE JSON outdated when IBGE updates taxonomy | Low | Low | Rebuild step copies `backend/data/cnae_2.3/*.json` → `frontend/lib/cnae-taxonomy.json` |
| Polling at 2s creates thundering herd if 10+ revisors load same page | Low | Low | Tab inactive → TanStack pauses polling; acceptable for pilot scale |
| Sprint 2 `_cnae_stage` long transaction still unfixed | Medium | High at scale | Not in Sprint 3 scope; documented in memory follow-ups; pilot scale tolerates |

---

## 11. Sprint 3 task list (preview — actual plan via writing-plans)

1. Backend: add `progresso_pct` + GET /uploads list endpoint + 4 tests
2. Backend: clusters router (list, detail, shortlist GETs) + 3 tests
3. Backend: PATCH cluster + shortlist regen background task + 1 test
4. Backend: dashboard router + stats endpoint + 1 test
5. Frontend: layout shell + tenant config + API client + tests
6. Frontend: dashboard page + StatCard + chart
7. Frontend: uploads list page
8. Frontend: upload form page (UploadDropzone)
9. Frontend: upload detail page (progress + cluster table + filters)
10. Frontend: cluster detail page (review form + CNAE editor + shortlist)
11. Frontend: CNAE taxonomy bundle pipeline
12. Smoke test + DoD verification + memory update

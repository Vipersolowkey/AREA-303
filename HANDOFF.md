# AREA-303 Handoff

## Current branch

`feat/storefront-llm-ollama`

## Active PR

- Upstream PR: `#24`
- URL: `https://github.com/icebearhoho/AREA-303/pull/24`

## Current status

- Backend and frontend run locally.
- PR merge conflict with `upstream/main` was resolved.
- A failing backend test was fixed by making the ideas count test derive from the live registry instead of a hard-coded number.
- CI was re-triggered after the test fix.

## Recently completed

- Removed the negotiation feature from both frontend and backend:
  - deleted negotiation API endpoint/service/schema
  - removed negotiation panel and nav entry
  - removed idea `#14` from the ideas API list
- Improved RecSys / `For You` UX:
  - changed technical ML metrics into shopper-friendly insights
  - fixed recommendation images so they match product types instead of random placeholders
- Kept storefront detail improvements after merging latest `main`:
  - review section on product detail page
  - review tracking in the customer journey flow
  - product detail / similar products still working after conflict resolution

## Important files

- `frontend/components/features/recsys-panel.tsx`
- `frontend/components/genai/product-card.tsx`
- `frontend/lib/mock-data.ts`
- `frontend/lib/nav.ts`
- `frontend/lib/features.ts`
- `frontend/app/shop/store/[id]/page.tsx`
- `backend/app/api/v1/endpoints/ideas.py`
- `backend/app/services/recsys.py`
- `backend/app/services/storefront.py`
- `backend/app/services/journey.py`
- `backend/tests/test_envelope.py`

## Important decisions

- Do not re-add the negotiation feature unless explicitly requested.
- Keep the `For You` page buyer-friendly; avoid exposing raw ML evaluation metrics like `Recall@10` / `NDCG@10` in the shopper UI.
- Recommendation and storefront imagery should use product-matched images, not generic placeholder/random images.
- The ideas API total is now `16` because negotiation was removed from the live app surface.

## Local run commands

### Backend

From repo root:

```powershell
d:\arena\AREA-303\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Docs:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/api/v1/health`

### Frontend

```powershell
cd frontend
npm run dev -- --port 3000
```

App:

- `http://localhost:3000`
- `http://localhost:3000/shop/recsys`

## Local verification already done

- Backend health endpoint returns success.
- Frontend home and shop pages load.
- RecSys images were checked after the image fix.
- Targeted backend pytest passed locally:

```text
14 passed, 1 warning
```

## Known local-only noise

- `backend/.uvicorn.log` is an untracked local runtime file and should not be committed.

## Good next steps

1. Check whether PR `#24` CI is fully green.
2. If green, continue polishing storefront / RecSys / buyer flow on the same branch or a fresh branch from updated `main`.
3. If continuing on another machine or model, read this file first, then inspect PR `#24`.

# apps/mobile — Lawagent iPhone app (Expo / React Native)

A native client for the lawagent FastAPI backend: grounded chat with checkable
citations, project switching, and case-file upload/download. It's a **separate
npm project** (like `apps/web`) and talks to the API directly over HTTP, holding
its own Cognito tokens — there is no Next.js proxy in front of it.

## How it maps to the backend

Every request carries `Authorization: Bearer <cognito_id_token>`. Endpoints used:

| Screen   | API                                                            |
| -------- | ------------------------------------------------------------- |
| Sign-in  | Cognito Hosted UI (PKCE) + Google; then `GET /me`             |
| Chat     | `POST /chat` → `{answer, mode, sources[]}` (non-streaming)    |
| Projects | `GET/POST /projects`, `DELETE /projects/{id}`                 |
| Files    | `GET /files`, `POST /files/presign-upload` (PUT to S3),       |
|          | `GET /files/presign-download`, `DELETE /files`, `/files/convert` |

> `/chat` answers are **not** project-scoped yet — `project_id` is sent only for
> usage attribution. Don't read per-project answers into the UI until vector
> scoping lands.

## Setup

```bash
cd apps/mobile
npm install
cp .env.example .env      # fill in values (see below)
npx expo start --ios      # boots the iOS simulator
```

On the **iOS simulator**, `localhost` reaches your Mac, so a locally-running API
(`uv run lawagent-api`) works as `EXPO_PUBLIC_API_URL=http://localhost:8000`. On a
**physical device**, use your Mac's LAN IP instead.

## Environment (`.env`, all `EXPO_PUBLIC_*`)

| Var                          | Meaning                                                     |
| ---------------------------- | ---------------------------------------------------------- |
| `EXPO_PUBLIC_API_URL`        | FastAPI base URL                                           |
| `EXPO_PUBLIC_COGNITO_DOMAIN` | Hosted UI domain (`terraform output cognito_hosted_ui_domain`) |
| `EXPO_PUBLIC_COGNITO_CLIENT_ID` | Native client id (`terraform output cognito_mobile_client_id`) |
| `EXPO_PUBLIC_SCHEME`         | URI scheme for the OAuth redirect (`lawagent`)            |
| `EXPO_PUBLIC_AUTH_DISABLED`  | Dev-only: skip Cognito; pair with API `LAWAGENT_AUTH_DISABLED=true` |

## Auth prerequisites (one-time)

The native Cognito client (public, PKCE, `lawagent://callback`) is provisioned by
`infra/terraform` (`aws_cognito_user_pool_client.mobile`). Its client id must be
added to the API's `COGNITO_EXTRA_AUDIENCES` so the backend accepts mobile tokens
(it verifies the JWT `aud`). Ship the two together.

## Fast local loop (no Cognito)

```bash
# API: LAWAGENT_AUTH_DISABLED=true uv run lawagent-api
# .env: EXPO_PUBLIC_AUTH_DISABLED=true
```

The sign-in screen then logs in a synthetic dev user without hitting Cognito.

## Quality

```bash
npm run types   # tsc --noEmit
npm run lint    # eslint
```

These also run from the repo root via `make mobile-check`. The mobile app is
intentionally **not** part of `make check` (kept fast + offline).

# IronForgedBot API

A REST API exposing various member data points to authenticated consumers.

## Endpoints

| Method | Path                                       | Required perm              |
| ------ | ------------------------------------------ | -------------------------- |
| GET    | `/health`                                  | _none (public)_            |
| GET    | `/members`                                 | `members:list`             |
| GET    | `/members/{member_id}`                     | `members:read`             |
| GET    | `/members/{member_id}/ingots`              | `ingots:read`              |
| GET    | `/members/{member_id}/ingots/transactions` | `ingots:read:transactions` |
| GET    | `/players/{rsn}/score`                     | `scores:read`              |
| GET    | `/players/{rsn}/score-history`             | `scores:read:history`      |

> **Note:** `/health` is public and does not require authentication. It is
> intended for load balancers, version probes, and operational monitoring.

## Response shapes

### Success

All successful responses share this envelope:

```json
{
    "data": {},
    "meta": {
        "request_id": "8f3a2c1b-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
        "timestamp": "2026-07-12T14:23:11.123456+00:00"
    }
}
```

### Error

All error responses share this envelope. The `code` is a stable string; the
`message` is human-readable and may change.

```json
{
    "error": {
        "code": "not_found",
        "message": "No member with id=123456789012345678"
    },
    "meta": {
        "request_id": "8f3a2c1b-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
        "timestamp": "2026-07-12T14:23:11.123456+00:00"
    }
}
```

### Error codes

| Status | `code`               | When                                                                     |
| ------ | -------------------- | ------------------------------------------------------------------------ |
| 400    | `bad_request`        | Path/query params failed domain validation (e.g. bad `rsn`, bad `days`). |
| 401    | `unauthorized`       | Missing, malformed, or revoked/disabled bearer token.                    |
| 403    | `forbidden`          | Bearer is valid but missing the required perm.                           |
| 404    | `not_found`          | Target member, player, or hiscores record does not exist.                |
| 405    | `method_not_allowed` | Method not supported for the given path.                                 |
| 422    | `validation_error`   | Request validation failed (query type, range, etc.).                     |
| 500    | `internal_error`     | Unhandled server-side exception.                                         |

## Request correlation

Every response (success or error) carries a `meta.request_id`. The same id is
also returned in the `X-Request-ID` response header and is persisted on the
`api_audit` row for the request. When reporting an issue, share the
`X-Request-ID` value to help debugging.

## Endpoint reference

### GET /health

Public health probe. Pings the database.

**Required perm:** none

**Response — 200 (healthy):**

```json
{
    "data": {
        "status": "ok",
        "db": "ok",
        "version": "1.2.3",
        "environment": "dev"
    },
    "meta": { "request_id": "…", "timestamp": "…" }
}
```

**Response — 503 (DB unreachable):**

```json
{
    "data": {
        "status": "degraded",
        "db": "error",
        "version": "1.2.3",
        "environment": "prod"
    },
    "meta": { "request_id": "…", "timestamp": "…" }
}
```

---

### GET /members

Paginated list of members. Default filter returns only active members.

**Required perm:** `members:list`

**Query parameters:**

| Name     | Type   | Default  | Constraints                                              |
| -------- | ------ | -------- | -------------------------------------------------------- |
| `limit`  | int    | `100`    | 1-500                                                    |
| `offset` | int    | `0`      | >= 0                                                     |
| `role`   | string | _none_   | A `ROLE` enum value, e.g. `Member`, `Staff`, `Owner`     |
| `rank`   | string | _none_   | A `RANK` enum value, e.g. `Iron`, `Dragon`, `Myth`       |
| `filter` | string | `active` | `active`, `booster`, `prospect`, `blacklisted`, `banned` |

**Response — 200:**

```json
{
    "data": {
        "members": [
            {
                "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "discord_id": 123456789012345678,
                "nickname": "Zezima",
                "role": "Member",
                "rank": "Dragon",
                "joined_date": "2024-01-15T00:00:00+00:00",
                "is_booster": false,
                "is_prospect": false,
                "is_blacklisted": false,
                "is_banned": false
            }
        ],
        "total": 142,
        "limit": 100,
        "offset": 0
    },
    "meta": { "request_id": "…", "timestamp": "…" }
}
```

**Response — 401 (no token):**

```json
{
    "error": {
        "code": "unauthorized",
        "message": "Missing Authorization header"
    },
    "meta": { "request_id": "…", "timestamp": "…" }
}
```

**Response — 403 (missing perm):**

```json
{
    "error": {
        "code": "forbidden",
        "message": "Missing required permission: members:list"
    },
    "meta": { "request_id": "…", "timestamp": "…" }
}
```

---

### GET /members/{member_id}

Fetch a single member by their Discord snowflake **or** internal UUID.

**Required perm:** `members:read`

**Path parameters:**

| Name        | Type   | Description                                                                        |
| ----------- | ------ | ---------------------------------------------------------------------------------- |
| `member_id` | string | Numeric value → looked up as `discord_id`. Non-numeric → looked up as `id` (UUID). |

**Response — 200:**

```json
{
    "data": {
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "discord_id": 123456789012345678,
        "nickname": "Zezima",
        "role": "Member",
        "rank": "Dragon",
        "joined_date": "2024-01-15T00:00:00+00:00",
        "is_booster": false,
        "is_prospect": false,
        "is_blacklisted": false,
        "is_banned": false
    },
    "meta": { "request_id": "…", "timestamp": "…" }
}
```

**Response — 404 (no such member):**

```json
{
    "error": {
        "code": "not_found",
        "message": "No member with id=123456789012345678"
    },
    "meta": { "request_id": "…", "timestamp": "…" }
}
```

---

### GET /members/{member_id}/ingots

Current ingot balance for a member.

**Required perm:** `ingots:read`

**Path parameters:** see [GET /members/{member_id}](#get-membersmember_id).

**Response — 200:**

```json
{
    "data": {
        "nickname": "Zezima",
        "ingots": 4200
    },
    "meta": { "request_id": "…", "timestamp": "…" }
}
```

**Response — 404:** see [GET /members/{member_id}](#get-membersmember_id).

---

### GET /members/{member_id}/ingots/transactions

Recent ingot add/remove transactions for a member, newest first.

**Required perm:** `ingots:read:transactions`

**Path parameters:** see [GET /members/{member_id}](#get-membersmember_id).

**Query parameters:**

| Name    | Type | Default | Constraints                                                           |
| ------- | ---- | ------- | --------------------------------------------------------------------- |
| `days`  | int  | _none_  | 1-365. If set, only transactions within the last N days are returned. |
| `limit` | int  | `50`    | 1-500                                                                 |

**Response — 200:**

```json
{
    "data": {
        "transactions": [
            {
                "id": 98765,
                "change_type": "ADD_INGOTS",
                "previous_value": "4000",
                "new_value": "4200",
                "comment": "Payroll",
                "admin": {
                    "id": "f0e1d2c3-b4a5-9687-6543-210fedcba987",
                    "discord_id": 111222333444555666,
                    "nickname": "ModBoss"
                },
                "timestamp": "2026-07-01T06:00:00+00:00"
            },
            {
                "id": 98760,
                "change_type": "REMOVE_INGOTS",
                "previous_value": "4050",
                "new_value": "4000",
                "comment": "Raffle tickets",
                "admin": null,
                "timestamp": "2026-06-15T18:42:11+00:00"
            }
        ]
    },
    "meta": { "request_id": "…", "timestamp": "…" }
}
```

> `admin` is `null` when the changelog row has no `admin_id` (e.g. system-driven
> changes). When populated, it is a `MemberRef` containing the admins internal
> UUID, Discord snowflake, and nickname.

**Response — 404:** see [GET /members/{member_id}](#get-membersmember_id).

---

### GET /players/{rsn}/score

Live OSRS hiscores breakdown for a player, converted to in-clan points.

**Required perm:** `scores:read`

**Path parameters:**

| Name  | Type   | Description                                                            |
| ----- | ------ | ---------------------------------------------------------------------- |
| `rsn` | string | The RuneScape name. 1-12 characters. Returns `400` outside this range. |

**Query parameters:**

| Name           | Type | Default | Description                                                       |
| -------------- | ---- | ------- | ----------------------------------------------------------------- |
| `bypass_cache` | bool | `false` | Skip the in-process score cache and force a fresh hiscores fetch. |

**Response — 200:**

```json
{
    "data": {
        "player_name": "Zezima",
        "skills": [
            {
                "name": "Attack",
                "display_name": null,
                "display_order": 1,
                "emoji_key": "Attack",
                "level": 99,
                "xp": 13034431,
                "points": 152
            }
        ],
        "clues": [
            {
                "name": "Clue Scrolls (beginner)",
                "display_name": "Beginner",
                "display_order": 1,
                "emoji_key": "Beginner_Clue",
                "kc": 42,
                "points": 4
            }
        ],
        "raids": [
            {
                "name": "Chambers of Xeric",
                "display_name": null,
                "display_order": 1,
                "emoji_key": "Chambers_of_Xeric",
                "kc": 75,
                "points": 75
            }
        ],
        "bosses": [
            {
                "name": "Zulrah",
                "display_name": null,
                "display_order": 200,
                "emoji_key": "Zulrah",
                "kc": 1200,
                "points": 600
            }
        ],
        "total_points": 12345
    },
    "meta": { "request_id": "…", "timestamp": "…" }
}
```

`total_points` is the sum of `points` across all skills, clues, raids, and
bosses. The `Overall` skill is excluded.

**Response — 400 (bad rsn):**

```json
{
    "error": { "code": "bad_request", "message": "Invalid player name" },
    "meta": { "request_id": "…", "timestamp": "…" }
}
```

**Response — 404 (not on hiscores):**

```json
{
    "error": {
        "code": "not_found",
        "message": "Player not found on hiscores: nope"
    },
    "meta": { "request_id": "…", "timestamp": "…" }
}
```

---

### GET /players/{rsn}/score-history

Historical score snapshots for a registered member, looked up at multiple
periods.

**Required perm:** `scores:read:history`

**Path parameters:** `rsn` — see
[GET /players/{rsn}/score](#get-playersrsnscore). The player must be a
registered clan member; this endpoint will not return data for arbitrary
hiscores users.

**Query parameters:**

| Name   | Type   | Default     | Constraints                                                                                       |
| ------ | ------ | ----------- | ------------------------------------------------------------------------------------------------- |
| `days` | string | `"7,30,90"` | Comma-separated list of day windows. Each value must be 1-365. Returns `400` if any value is bad. |

For each requested period, the endpoint returns the single nearest snapshot
within ±3 days of the target date. If no qualifying snapshot exists, `score` is
`null`.

**Response — 200:**

```json
{
    "data": {
        "discord_id": 123456789012345678,
        "entries": [
            { "period_days": 7, "score": 11800, "snapshot_date": null },
            { "period_days": 30, "score": 10500, "snapshot_date": null },
            { "period_days": 90, "score": 9000, "snapshot_date": null }
        ]
    },
    "meta": { "request_id": "…", "timestamp": "…" }
}
```

> **Note:** `snapshot_date` is currently always `null` — the actual snapshot
> date is not yet serialized in the response.

**Response — 400 (bad `days`):**

```json
{
    "error": {
        "code": "bad_request",
        "message": "Each day value must be between 1 and 365"
    },
    "meta": { "request_id": "…", "timestamp": "…" }
}
```

**Response — 404 (rsn not a registered member):**

```json
{
    "error": {
        "code": "not_found",
        "message": "No member with rsn=Zezima"
    },
    "meta": { "request_id": "…", "timestamp": "…" }
}
```

---

## Quick start

1. Enable the API in `.env`:

   ```sh
   API_ENABLED=True
   API_PORT=8080
   ```

2. Run database migrations:

   ```sh
   make migrate
   ```

3. Create a consumer:

   ```sh
   make api-consumer-interactive
   ```

   The CLI prints a fresh bearer token once. Copy it immediately.

4. Hit an endpoint:

   ```sh
   curl -H "Authorization: Bearer iron_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
        http://localhost:8080/members
   ```

## Authentication

Every request to a non-public endpoint requires a `Bearer` token in the
`Authorization` header:

```sh
curl -H "Authorization: Bearer iron_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
     http://localhost:8080/health
```

**Token format:** `iron_<43 url-safe base64 chars>`. Generated by
`secrets.token_urlsafe(32)` (32 bytes of entropy, ~256 bits, base64-encoded).

**Storage:** SHA-256 hash stored in the `api_consumers.token_hash` column. The
plaintext is shown only once at creation. Rotate the consumer to issue a new
token.

**Disabled or deleted consumers:** lookups return `401 unauthorized`.

## Permissions

Permissions are granular `resource:action` strings stored as a JSON array on
each consumer (`api_consumers.perms`).

| Perm                       | Grants access to                               |
| -------------------------- | ---------------------------------------------- |
| `meta:read`                | _(reserved — not currently enforced)_          |
| `members:list`             | `GET /members`                                 |
| `members:read`             | `GET /members/{member_id}`                     |
| `ingots:read`              | `GET /members/{member_id}/ingots`              |
| `ingots:read:transactions` | `GET /members/{member_id}/ingots/transactions` |
| `scores:read`              | `GET /players/{rsn}/score`                     |
| `scores:read:history`      | `GET /players/{rsn}/score-history`             |

`/health` is public and requires no perm.

Perms are defined in code at `api/permissions.py`. To add a new perm, add it to
both the `PERM` enum and the `KNOWN_PERMS` table in this doc, then redeploy.

## Rate limiting

When a request exceeds a limit, we raise `HTTPException(429)` which flows
through the standard error handler -> audit middleware -> `api_audit` row. The
429 response uses the standard error envelope (`code: "rate_limited"`) and
includes a `Retry-After` header giving the seconds until the current minute
window ends.

## Audit log

Every API request writes one row to the `api_audit` table. Fields captured:

- `timestamp` (indexed)
- `consumer_id`, `consumer_name`, `consumer_perms` (snapshot of full perms array
  at request time, so revocations don't break history)
- `required_perm` (the perm that gated this request, or `null` for public/meta
  endpoints)
- `method`, `path` (path only — query string stripped, truncated to 512 chars)
- `status_code`, `duration_ms`
- `client_ip` (first hop from `X-Forwarded-For` header if present, else socket
  address. The header is trusted unconditionally — only deploy behind a proxy
  that strips inbound `X-Forwarded-For` from untrusted clients.)
- `user_agent` (truncated to 512 chars)
- `error` (truncated to 512 chars; only on failures)

## Bruno collection

A [Bruno](https://www.usebruno.com/) collection lives in `api/bruno/`.

## Consumer management

```sh
make api-consumer-interactive   # guided: create, grant/revoke, enable/disable, rotate, delete
make api-consumer-list          # print a table of consumers and their perms
```

Plaintext tokens are only displayed once at creation or rotation. If you lose a
token, rotate the consumer.

## Permission management

Perms are defined in `api/permissions.py` (`PERM` enum + `KNOWN_PERMS` list).
The `api-consumer-interactive` flow lets you grant or revoke any of those perms
by name on a consumer.

To add a new perm: add the value to the `PERM` enum and a `(name, description)`
entry to `KNOWN_PERMS`, then redeploy. The perm will then be available to grant
to any consumer.

## Configuration

| Env var                 | Default   | Description                                                                |
| ----------------------- | --------- | -------------------------------------------------------------------------- |
| `API_ENABLED`           | `False`   | Master switch. Set `True` to start the API service.                        |
| `API_HOST`              | `0.0.0.0` | Bind address.                                                              |
| `API_PORT`              | `8080`    | Listen port.                                                               |
| `API_AUDIT_LOG_ENABLED` | `True`    | Write `api_audit` rows.                                                    |
| `API_DOCS_ENABLED`      | (auto)    | Expose `/docs` and `/openapi.json`. Auto-disabled when `ENVIRONMENT=prod`. |
| `API_CORS_ORIGINS`      | (empty)   | Comma-separated allowed CORS origins.                                      |
| `API_RATE_LIMIT`        | `30`      | Per-route per-consumer per-minute. `0` disables.                           |

See the main `README.md` Keys table for the full project env var reference.

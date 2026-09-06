# WhatsApp Delivery Contract

The domain uses a provider-neutral delivery port. The production adapter may use
the WhatsApp Business Platform/Cloud API; tests must use a deterministic fake.

## Input

```json
{
  "delivery_id": "uuid",
  "recipient_phone_e164": "+5491112345678",
  "player_display_name": "Jugador",
  "club_name": "Club Demo",
  "field_name": "Cancha 1",
  "highlight_access_url": "https://player.example.invalid/access/token",
  "expires_at": "2026-08-08T00:00:00Z",
  "template_key": "highlight_ready_v1",
  "idempotency_key": "delivery-uuid-v1"
}
```

The adapter must reject requests without recorded messaging consent, a valid
recipient, an unexpired access URL, or an approved template configuration.

## Output

```json
{
  "provider": "whatsapp-cloud-api",
  "provider_message_id": "provider-id",
  "status": "sent",
  "occurred_at": "2026-08-07T20:00:00Z",
  "raw_error": null
}
```

Provider payloads must be redacted before being written to logs. The delivery
record stores only the minimum identifiers and safe error fields required for
support and retry.

## Status Mapping

| Provider outcome | Domain status | Retry |
|---|---|---|
| Accepted for send | `sent` | No, wait for callback |
| Delivered | `delivered` | No |
| Read | `read` | No |
| Temporary provider/network error | `failed` | Yes, exponential backoff |
| Invalid number, missing consent, revoked access, policy rejection | `failed` | No automatic retry; owner action required |

The adapter must use the delivery ID and idempotency key to prevent duplicate
messages after a timeout or worker restart. A provider callback for a revoked or
expired delivery must not make the link accessible again.

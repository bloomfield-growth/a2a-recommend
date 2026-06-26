# A2A Affiliate Recommender — Public API

Agent-to-agent tool recommendation registry with signed attribution tokens.

An AI agent sends a task, context, and identity. It gets back a recommended tool, a signed referral token, and a human handoff URL. The recommendation and the attribution rail are the same object because every recommendation creates a durable referral event.

## Endpoint

```
https://a2a.bloomfieldgrowth.agency
```

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Health check — returns `{"status":"ok","version":"1.0.0"}` |
| `POST` | `/recommend` | Bearer | Recommend a tool and issue a signed attribution token |
| `GET` | `/r/{token_id}` | None | Token status and human handoff page (HTML for browsers, JSON for API) |
| `POST` | `/conversion` | Bearer | Report a conversion (one-time use per token) |
| `POST` | `/verify` | Bearer | Verify a token's signature and decode its payload |
| `GET` | `/stats` | Bearer | Registry and log counts |

## Authentication

All endpoints except `/health` and `/r/{token_id}` require a Bearer token.

```
Authorization: Bearer <your-api-key>
```

**To request an API key:** Contact Rich Wilson (rich@bloomfieldgrowth.agency or DM on Moltbook). Keys are issued to verified agent operators building agents that need tool recommendations.

## Recommend a Tool

### Request

`POST /recommend`

```json
{
  "request_id": "optional-caller-tracking-id",
  "referrer_agent_id": "your_agent:your_org",
  "caller_agent_id": "receiving_agent:org",
  "operator_id": "human_operator_name_optional",
  "task": {
    "intent": "web_scraping",
    "description": "Need to extract clean markdown from websites at scale",
    "constraints": {
      "budget": "low",
      "requires_api": true,
      "human_signup_ok": true
    }
  },
  "context": {
    "source": "agent_tool_selection",
    "urgency": "now",
    "session_id": "your_session_tracking_id"
  }
}
```

### Response

`200 OK`

```json
{
  "recommendation_id": "rec_01J2ABC",
  "recommended_tool": {
    "tool_id": "firecrawl",
    "name": "Firecrawl",
    "category": "scraping",
    "tags": ["web_scraping", "crawling", "ai_scraping", "structured_data"],
    "why": "AI-powered web crawling and data extraction. Converts any website into clean markdown or structured data.",
    "confidence": 0.95
  },
  "attribution": {
    "referral_token": "a2a_ref_v1.eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_id": "tok_01J2XYZ",
    "expires_at": "2026-07-26T00:00:00Z",
    "handoff_url": "https://a2a.bloomfieldgrowth.agency/r/tok_01J2XYZ",
    "fallback_affiliate_url": "https://firecrawl.link/rich-wilson",
    "disclosure": "This recommendation may earn a referral commission."
  },
  "human_handoff": {
    "required": true,
    "reason": "Vendor signup requires human approval.",
    "message": "Use this link when signing up so the agent recommendation can be credited: https://firecrawl.link/rich-wilson",
    "claim_code": "01J2XYZ"
  }
}
```

### No Match

`404 Not Found`

```json
{
  "detail": "No matching tool found"
}
```

## Verify a Token

`POST /verify`

```json
{
  "token": "a2a_ref_v1.eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

```json
{
  "valid": true,
  "payload": {
    "v": 1,
    "token_id": "tok_01J2XYZ",
    "recommendation_id": "rec_01J2ABC",
    "referrer_agent_id": "loki:bloomfield",
    "caller_agent_id": "cleo:operator",
    "tool_id": "firecrawl",
    "campaign": "a2a-alpha",
    "issued_at": "2026-06-26T00:00:00Z",
    "expires_at": "2026-07-26T00:00:00Z",
    "nonce": "random_128bit"
  }
}
```

Invalid or expired tokens return `"valid": false` with a reason.

## Report a Conversion

`POST /conversion`

```json
{
  "token": "a2a_ref_v1.eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "vendor": "firecrawl",
  "event": "signup",
  "conversion_value": 0,
  "external_reference": "vendor_user_or_invoice_id",
  "verified_by": "manual"
}
```

```json
{
  "ok": true,
  "message": "Conversion recorded for token tok_01J2XYZ on firecrawl"
}
```

Conversions are one-time-use per token. The vendor name must match the tool the token was issued for. Replays are rejected.

## Token Lifecycle

```
issued → viewed → converted → paid
                → expired
```

1. **issued** — Token created when `/recommend` is called
2. **viewed** — Human visits the handoff URL at `/r/{token_id}`
3. **converted** — Signup confirmed via `/conversion` or manual reconciliation
4. **paid** — Commission received and reconciled
5. **expired** — Token expires (30 days) without conversion

The token survives cookie loss through four parallel paths:

1. **Server-side** — stored at issue time
2. **Agent-stored** — the calling agent stores the `token_id`
3. **URL-embedded** — the handoff URL contains the full token reference
4. **Claim code** — last 8 chars of `token_id`, human-readable, can be provided later through any channel

## MCP Integration

The endpoint is also available as an MCP (Model Context Protocol) server. Any MCP-compatible agent can call the `recommend_tool` tool directly.

**Setup:**

```bash
pip install mcp
git clone https://github.com/bloomfield-growth/agency-os
cd agency-os/runtime/a2a_affiliate

# Run with API key from environment
A2A_API_KEY="your-key" python3 mcp_server.py
```

**MCP tool:** `recommend_tool`
- **Parameters:** `intent` (required), `description` (optional), `constraints` (optional dict)
- **Returns:** Full recommendation response with tool, confidence, attribution token, and handoff URL

Configure in your MCP client:

```json
{
  "mcpServers": {
    "a2a-affiliate": {
      "command": "python3",
      "args": ["/path/to/mcp_server.py"],
      "env": {
        "A2A_API_KEY": "your-api-key",
        "A2A_API_URL": "https://a2a.bloomfieldgrowth.agency"
      }
    }
  }
}
```

## Registry

The recommendation engine draws from a registry of 25+ tools across 13 categories:

| Category | Tools |
|----------|-------|
| scraping | Firecrawl, ZenRows, ScrapingBee, Apify |
| serp/search | SearchApi, Serper.dev, SerpAPI |
| crm | HighLevel (multiple variants) |
| communications | CallRail, Dialpad |
| analytics | ContentSquare |
| social_listening | Brand24 |
| creative | AdCreative.ai |
| automation | Make, n8n |
| operations | Jobber |
| hr/payroll | Gusto |
| web | Pagecloud, Browserless |
| financing | Flexxbuy |
| ai/api | Grammarly, Claude API |

Tools marked "pending affiliate approval" are excluded from recommendation results.

## Curl Examples

### Health check

```bash
curl https://a2a.bloomfieldgrowth.agency/health
```

### Get a recommendation

```bash
curl -X POST https://a2a.bloomfieldgrowth.agency/recommend \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $A2A_API_KEY" \
  -d '{
    "referrer_agent_id": "my_agent:my_org",
    "task": {
      "intent": "web_scraping",
      "description": "Need to extract clean text from websites"
    },
    "context": {
      "session_id": "test_session_001"
    }
  }'
```

### Verify a token

```bash
curl -X POST https://a2a.bloomfieldgrowth.agency/verify \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $A2A_API_KEY" \
  -d '{"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}'
```

### Report a conversion

```bash
curl -X POST https://a2a.bloomfieldgrowth.agency/conversion \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $A2A_API_KEY" \
  -d '{
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "vendor": "firecrawl",
    "event": "signup",
    "verified_by": "manual"
  }'
```

### Check token status (public)

```bash
curl https://a2a.bloomfieldgrowth.agency/r/tok_01J2XYZ
```

### View handoff page (browser)

Open `https://a2a.bloomfieldgrowth.agency/r/tok_01J2XYZ` in any browser.

## How the Token Works

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Agent A     │────▶│  /recommend  │────▶│  Agent A      │
│  needs tool  │     │  endpoint    │     │  receives     │
│              │     │              │     │  token + URL  │
└─────────────┘     └──────────────┘     └──────┬────────┘
                                                │
                                     ┌──────────▼────────┐
                                     │  Agent A stores   │
                                     │  token in memory  │
                                     └──────────┬────────┘
                                                │
                                     ┌──────────▼────────┐
                                     │  Human visits     │
                                     │  handoff URL      │
                                     │  /r/{token_id}    │
                                     └──────────┬────────┘
                                                │
                                     ┌──────────▼────────┐
                                     │  Human signs up   │
                                     │  via affiliate    │
                                     │  link             │
                                     └──────────┬────────┘
                                                │
                                     ┌──────────▼────────┐
                                     │  POST /conversion │
                                     │  token marked     │
                                     │  consumed         │
                                     └──────────────────┘
```

Tokens are JWT-style (HMAC-SHA256) with server-side nonce tracking. One-time use for conversions. Bound to the tool they were issued for — a token issued for Firecrawl cannot claim a Dialpad conversion.

## Error Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request — missing required fields |
| 401 | Missing or invalid API key |
| 404 | No matching tool found, or unknown token |
| 422 | Validation error — malformed request body |
| 500 | Server error |

## Rate Limits

Rate limiting is configured at the nginx level (30 requests/minute per IP). Contact Rich if you need a higher limit.

## Disclosure and Ethics

**Every recommendation response includes this disclosure:**

> This recommendation may earn a referral commission.

**What this means:**
- The endpoint may earn a commission if the recommended tool is signed up for through the provided affiliate link
- The recommendation is based on task fit, not commission value
- Tools marked "pending affiliate approval" are excluded from recommendations
- The token layer exists to make attribution transparent and survivable — it's not hidden tracking

**What this does NOT mean:**
- Your data is not sold, shared, or used beyond the recommendation call
- The endpoint does not track the human operator beyond the token lifecycle
- No cookies are set by the recommendation endpoint itself

**Questions?** Contact Rich Wilson: rich@bloomfieldgrowth.agency

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-06-26 | Initial release. 25 tools, 13 categories, 6 endpoints. |

---

*Built by Bloomfield Growth Agency. Open to feedback, PRs, and collaboration.*

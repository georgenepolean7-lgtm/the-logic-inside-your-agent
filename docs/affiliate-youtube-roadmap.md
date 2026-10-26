# Affiliate and GOD OF AI YouTube Integration Roadmap

## Confirmed channel target
- User-provided channel URL: https://youtube.com/@godofaiofficial
- Handle: `@godofaiofficial`
- This is the intended channel target for the project. Do not substitute the unrelated SON OF JESUS channel.
- A public channel URL does not itself grant private YouTube Studio analytics or publishing access. Those require the channel owner to authorize Google OAuth in the application.

## Goal
The user creates the video and voice-over manually. The agent researches products, validates evidence, prepares SEO metadata and affiliate disclosures, and helps publish and measure results. Never publish automatically until OAuth is configured, a test is reviewed, and the user explicitly approves publication.

## Current verified state
- The product research project is a Python/Streamlit app with SQLite storage and an autonomous scan loop.
- The separate `instagram-booster` repository is a Next.js/Supabase Instagram content tool. Its documented provider architecture is Meta/Instagram-oriented; it is not evidence of a working YouTube publisher or Meesho affiliate integration.
- Product metrics and social signals that are not actually available must remain unavailable. Never synthesize clicks, conversions, commissions, reviews, ratings, demand, or trend history.
- The data-integrity fix branch has passing GitHub Actions checks; this roadmap branch is based on that fix branch and is not merged or deployed.

## Phase 1 — Affiliate eligibility and link tracking
1. Confirm the official Meesho affiliate/creator program available to this account and its current terms. Do not assume that a product URL can be converted into a commission-earning affiliate URL.
2. Add a provider interface for affiliate networks; keep provider credentials server-side and out of source control.
3. Store product ID, source URL, affiliate URL (only when officially issued), disclosure text, network, and verification timestamp.
4. Add click redirect/tracking with opaque IDs, bot filtering, consent/privacy notice, and append-only click events.
5. Record conversions and commission only from an official network report/API/webhook/import. Never infer earnings from clicks.
6. Dashboard states must distinguish `Unavailable`, `Pending`, `Confirmed`, and `Rejected`. Deduplicate conversion events and preserve source references.

## Phase 2 — YouTube for GOD OF AI
1. Target channel: `@godofaiofficial` (URL above).
2. Implement Google OAuth with least-privilege scopes and encrypted server-side refresh-token storage; do not request credentials in chat or commit secrets.
3. Add a draft/publishing workflow: title, description, tags, thumbnail, affiliate disclosure, visibility, and scheduled time.
4. Upload/publish only after the user reviews and confirms. Handle quota errors, retries, idempotency, token revocation, and upload status.
5. Fetch analytics only from authorized YouTube APIs; label data with the source and reporting window. Do not fabricate views, watch time, clicks, or revenue.
6. Add dry-run mode and tests before enabling any real publishing.

## Phase 3 — Integration and reliability
- Keep the product-research agent as the source of product evidence; use a narrow API/service boundary if connecting to the Next.js Instagram Booster.
- Do not couple this Python agent to Instagram-only assumptions. A YouTube provider should be a separate adapter.
- Add unit tests for missing credentials, OAuth state/CSRF validation, duplicate webhook/report rows, unavailable metrics, API failures, and safe retry behavior.
- Add a local SQLite backup/migration tool before any cleanup. Never delete or overwrite a user's local database without a backup and explicit confirmation.

## Release gates
- No merge or production deployment until tests pass and the user approves.
- No affiliate links presented as commissionable until official eligibility is verified.
- No live publishing until OAuth is connected, a private/unlisted test upload is reviewed, and the user explicitly approves the final publish action.

## Next required setup
The channel URL is now recorded. The next implementation step is Google OAuth / YouTube Data API integration and a secure user-authorized connection flow. The channel owner must complete the Google consent screen inside the application; never send passwords, OAuth tokens, API keys, or recovery codes in chat.

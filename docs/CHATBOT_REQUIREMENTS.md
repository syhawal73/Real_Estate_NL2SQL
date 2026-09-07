# Real-Estate Chatbot — Product Contract

## Goal
A ChatGPT-like conversational real-estate assistant, constrained to the site's property inventory and terminology. The application is LLM-provider agnostic: changing the model/provider must not change the deterministic property selection for the same structured search state.

## Supported capabilities
- Property discovery and natural-language search.
- Conversational clarification only when information is necessary or materially useful.
- Follow-up refinement and modification of the active search.
- New-search reset.
- Rankings, comparison, count and aggregation.
- Property-specific follow-ups and similar-property flows.
- Real-estate general chat; unrelated requests are redirected.
- Intelligent fallback when an exact search returns no listings.

## Search behavior
- Search immediately with available information.
- Preserve the active search across turns.
- Explicitly changed fields replace old values; unrelated fields remain.
- A new search clears previous search filters.
- Search results are site inventory only. No external listing may be presented as a site listing.
- No artificial recommendation score in the first production version.

## Property results
Any response that returns property rows must return structured property results. The frontend renders up to five rich property cards. Every card links to the canonical internal property page: `/properties/{id}`. More than five results expose a `View all` link preserving the active supported search filters.

## LLM boundary
The LLM may be used for natural-language conversation/presentation, but property extraction, conversation routing, query planning, SQL generation and property-card data are deterministic wherever possible. The DB is the source of truth for property facts.

## Data model
The existing `properties` schema remains unchanged. Search state may evolve independently (for example, price range semantics) without adding columns to the property table. Currency is derived for the current inventory because the existing source schema has no currency column.

## Account/session
Chat sessions are now scoped by `user_id`. The current code uses `dev-user` as a development fallback; production must supply the authenticated account ID from the site's real authentication layer rather than accepting a client-generated identity.

## Developer mode
Generated SQL and internal intent/debug details are hidden in production and may be exposed only in an explicitly enabled developer mode.

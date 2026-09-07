# Chatbot implementation notes

Implemented in this pass:

1. Deterministic Level-1 search extraction for the supported inventory, including cities/neighbourhood matching, common real-estate language, price ranges and ranking hints.
2. Deterministic conversation-action routing for refine/modify/new/general chat.
3. Deterministic Level-3 query planning.
4. Search execution with zero-result fallback that relaxes one constraint at a time and explicitly reports the relaxation.
5. Structured property-card payloads now include `property_url`, description and derived currency.
6. Property cards are clickable and route to `/properties/{id}`.
7. A `View all` link is returned for result sets larger than five.
8. Chat sessions are scoped to `user_id`.
9. General chat remains LLM-driven but is explicitly constrained to real-estate topics.
10. Count, aggregation and comparison responses are deterministic.

Verification:
- Python source compilation passes.
- Dependency-light schema/query smoke tests pass.
- Full backend pytest execution is blocked in this environment because the uploaded project does not have its Python runtime dependencies installed (`langgraph`, `langchain-core`, `asyncpg`, `sqlparse`, etc.).
- Frontend source dependency installation was incomplete in this environment, so the production Vite build could not be completed. The initial JSX syntax issue in the modified card was fixed before the dependency/type-definition failure.

Production follow-up:
- Replace the development `user_id` fallback with the site's authenticated user/session identity.
- Use a proper database migration for the new `chat_sessions.user_id` column in an existing deployment; `create_all()` is not a migration strategy.

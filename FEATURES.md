# AutoSocial Feature Log

## 2026-03-11
- Frontend: React + Vite scaffold with routed Login and Sign up pages.
- Frontend: Auth UI shell, form validation UX, and success/error messaging.
- Backend: FastAPI scaffold with CORS enabled.
- Backend: Email/password auth endpoints (/auth/signup, /auth/login) with password hashing.
- Backend: Postgres persistence via SQLAlchemy (users table).
- Config: .env.example with DATABASE_URL and VITE_API_BASE_URL.
- Frontend: Adjusted auth layout alignment and centering for correct orientation on login/signup screens.
- Frontend: Constrained auth layout width and centered the two-column grid to fix wide-screen spacing.
- Frontend: Added a simple landing page with platform description and Log in / Sign up actions.
- Frontend: Added a workspace page and redirect to it after successful login/signup.
- Backend: Added social account connection endpoints and model for Facebook/Instagram connections.\n- Frontend: Added Connected Accounts page for managing linked Facebook/Instagram accounts.
- Frontend: Added Meta login buttons to Connected Accounts and redesigned Workspace UI to match the requested dark layout.
- UI: Unified platform color theme to a consistent dark palette across auth, accounts, and workspace screens.
- Workspace: Removed hardcoded channel counts and now renders connected accounts dynamically with consistent theme colors.
- Post Composer: Added draft creation API endpoints and a composer UI with caption, hashtags, emojis, media URL, and previews.
- Meta OAuth: Added backend OAuth start/callback endpoints, UI triggers, and callback screen wiring for Meta app connection.
- Post Publishing: Added publish endpoint and composer action to publish posts immediately (currently simulated until Meta API calls are wired).
- OAuth UX: Normalized API error messages to avoid [object Object] in Meta login flows.
- Auth UI: Normalized login/signup error handling to avoid [object Object] messages.
- Auth: Switched login/signup to controlled inputs to prevent empty payloads and 422 'Field required' errors.
- Meta OAuth: Added backend redirect-based callback flow and frontend handling for backend-redirected auth.

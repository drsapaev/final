# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Medical Clinic Management System** built with FastAPI (Python backend) and React (Vite frontend). The system manages patient appointments, queues, EMR (Electronic Medical Records), payments, and specialized medical panels (cardiology, dermatology, dentistry, laboratory).

**Key Features:**
- Role-based access control (Admin, Doctor, Registrar, Cashier, Lab, Patient)
- Real-time queue management via WebSocket
- 2FA authentication with blocking flow
- EMR system with AI integration
- Multi-specialty medical panels
- Payment integration (PayMe provider)
- Telegram and Firebase notifications
- GraphQL API support
- PWA capabilities

## Development Commands

### Backend (Python/FastAPI)

**Working Directory:** Always run backend commands from `C:\final\backend`

```bash
# Start development server (from backend directory)
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
python test_role_routing.py
python test_user_management_system.py
python check_system_integrity.py

# Database migrations (if using Alembic)
alembic revision --autogenerate -m "description"
alembic upgrade head

# Create admin user
python app/scripts/ensure_admin.py
```

**API Documentation:** http://localhost:8000/docs (Swagger UI)

### Frontend (React/Vite)

**Working Directory:** `C:\final\frontend`

```bash
# Start development server
npm run dev              # Runs on http://localhost:5173

# Build for production
npm run build

# Preview production build
npm run preview

# Linting
npm run lint             # Fix lint issues
npm run lint:check       # Check only

# Testing
npm run test             # Run Vitest
npm run test:ui          # Vitest UI
npm run test:run         # Run once
npm run test:e2e         # Playwright E2E tests
npm run test:e2e:ui      # Playwright UI mode

# Storybook
npm run storybook        # Run Storybook dev server
npm run build-storybook

# Bundle analysis
npm run analyze
npm run build:analyze
```

### Docker Deployment

```bash
# From ops/ directory
docker compose up --build
docker compose logs -f backend
docker compose logs -f frontend
```

## Architecture Overview

### Backend Structure

**Framework:** FastAPI with SQLAlchemy ORM, Pydantic validation

**Entry Point:** `backend/app/main.py`
- Mounts API routers at `/api/v1`
- Includes WebSocket router for queue updates (`/ws/queue`)
- GraphQL API at `/api/graphql`
- CORS configured via environment variables

**Key Backend Directories:**
- `app/api/v1/endpoints/` - API endpoint modules (100+ endpoint files)
- `app/models/` - SQLAlchemy ORM models
- `app/crud/` - Database operations (CRUD layer)
- `app/core/` - Security, config, roles
- `app/services/` - Business logic services
- `app/ws/` - WebSocket handlers for real-time updates

**Database:** SQLite (`clinic.db`) with SQLAlchemy 2.0+

**Authentication:**
- JWT tokens via `python-jose`
- Password hashing: argon2 (new) + bcrypt (legacy support)
- 2FA with **blocking flow**: `login → pending_2fa_token → verify → access_token`
- Location: `app/core/security.py`, `app/services/authentication_service.py`

**Critical Backend Files:**
- `app/models/role_permission.py` - **SINGLE SOURCE OF TRUTH** for roles
- `app/core/roles.py` - Role enums
- `app/api/v1/api.py` - Main API router that includes all endpoint modules

### Frontend Structure

**Framework:** React 18 with React Router v6, Vite bundler

**Entry Point:** `frontend/src/main.jsx` → `App.jsx`

**Key Frontend Features:**
- **macOS-inspired UI** with custom design system (CSS variables in `styles/macos.css`)
- Theme system with light/dark modes plus custom schemes (vibrant, glass, gradient)
- Code splitting with lazy loading for large pages
- PWA support with install prompts

**Important Frontend Directories:**
- `src/pages/` - Page components (AdminPanel, DoctorPanel, RegistrarPanel, etc.)
- `src/components/` - Reusable UI components
  - `components/auth/` - Authentication forms (**USE LoginFormStyled.jsx, NOT Login.jsx**)
  - `components/medical/` - EMR, medical records
  - `components/ui/macos/` - macOS UI components (Sidebar, Header, Icon)
  - `components/tables/` - Data tables
- `src/contexts/` - React contexts (ThemeContext, AppDataContext)
- `src/api/` - API client with interceptors
- `src/stores/` - State management (auth store)

**Routing:**
- Role-based route protection via `RequireAuth` component
- Soft role checking (doesn't block if no profile)
- AppShell component wraps authenticated routes with macOS header/sidebar

**Theme System:**
- Centralized via `useTheme()` hook - **NEVER import designTokens directly**
- Use helper functions: `getColor()`, `getSpacing()`, `getFontSize()`, `getShadow()`
- Custom color schemes stored in localStorage and applied at app initialization

### Role System

**CRITICAL:** Only use models from `backend/app/models/role_permission.py`

**Available Roles:**
- Admin
- Doctor (general)
- Registrar
- Cashier
- Lab
- Patient
- Specialized: cardio, derma, dentist

**Role Routing:**
- Frontend: `App.jsx` defines role-based routes
- Backend: Role checks in endpoints via dependencies
- Test after changes: `python test_role_routing.py`

### Authentication System

**⚠️ CRITICAL RULES - READ `docs/AUTHENTICATION_LAWS_FOR_AI.md`**

1. **Blocking 2FA Flow:** Never issue `access_token` before 2FA verification
2. **Single Role Source:** Use ONLY `app/models/role_permission.py`
3. **Password Hashing:** argon2 for new passwords, maintain bcrypt compatibility
4. **Login Form:** Use `LoginFormStyled.jsx` as primary, NOT `Login.jsx`
5. **Protected Users:** Never delete: admin, registrar, doctor, cardio, derma, dentist

**Authentication Flow:**
```
1. POST /api/v1/authentication/login
   → Returns: pending_2fa_token (if 2FA enabled) OR access_token (if 2FA disabled)

2. POST /api/v1/2fa/verify
   → Input: pending_2fa_token + verification code
   → Returns: access_token + refresh_token
```

### Real-Time Features

**WebSocket Endpoints:**
- `/ws/queue` - Queue updates for display boards and panels
- `/ws/dev-queue` - Development queue endpoint

**Usage:** See `backend/app/ws/queue_ws.py` for implementation patterns

## Important Development Guidelines

### Code Style

**Python (Backend):**
- Follow PEP 8
- Use type hints for all functions
- Use async/await for I/O operations
- Pydantic models for validation
- Black formatter (line length 88)
- Import order: isort with black profile

**JavaScript/React (Frontend):**
- Functional components with hooks
- ESLint for linting (`npm run lint`)
- Avoid direct CSS class manipulation - use theme system

### Medical Data Compliance

- All medical operations must include audit logging
- Patient data requires permission checks
- Transactions required for critical medical operations
- Follow patterns in existing medical endpoints
- Support Russian language (primary user base)

### Testing Requirements

**Backend:**
```bash
# Always run these tests after authentication/role changes
python test_role_routing.py
python test_user_management_system.py
python check_system_integrity.py
```

**Frontend:**
```bash
npm run test              # Unit tests
npm run test:e2e          # E2E tests
npm run lint:check        # Lint check
```

**Multi-user scenarios:** Clinic systems have concurrent user access patterns - always test with multiple simultaneous users

### API Integration

- RESTful principles at `/api/v1/*`
- GraphQL available at `/api/graphql`
- Use proper HTTP status codes
- Include input validation (Pydantic schemas)
- Rate limiting applied
- OpenAPI/Swagger documentation auto-generated at `/docs`

### File Operations

- Medical document uploads must include virus scanning and format validation
- Follow patterns in `backend/app/api/v1/endpoints/file_*.py`
- File storage handled via `backend/app/crud/file_system.py`

### Database Operations

- Use SQLAlchemy ORM
- Alembic for migrations (if needed)
- Transactions for critical operations
- Audit logging for medical data
- Database indices for query optimization

## Common Pitfalls to Avoid

1. **DON'T** bypass the blocking 2FA flow
2. **DON'T** create duplicate role models outside `role_permission.py`
3. **DON'T** use `Login.jsx` - use `LoginFormStyled.jsx`
4. **DON'T** import designTokens directly - use theme hooks
5. **DON'T** run backend commands from root directory - always use `backend/`
6. **DON'T** hardcode secrets - use environment variables
7. **DON'T** skip tests after authentication/role changes
8. **DON'T** mix password hashing schemes
9. **DON'T** break backward compatibility with existing API endpoints
10. **DON'T** commit sensitive files (.env, credentials.json)

## Key Documentation Files

**Must Read Before Authentication Work:**
- `docs/AUTHENTICATION_LAWS_FOR_AI.md` - **MANDATORY** laws for AI agents
- `docs/AUTHENTICATION_SYSTEM_FINAL_GUIDE.md` - Complete auth system guide
- `docs/ROLE_SYSTEM_PROTECTION.md` - Role system protection rules

**Other Important Docs:**
- `.cursorrules` + `.cursor/rules/*.mdc` - Project-specific rules
- `docs/AI_INTEGRATION_GUIDE.md` - AI feature integration
- `docs/MCP_INTEGRATION_GUIDE.md` - Model Context Protocol integration
- `docs/QUEUE_SYSTEM_IMPROVEMENTS.md` - Queue system architecture
- `ops/README.md` - Docker deployment

## Environment Variables

**Backend Key Variables:**
- `DATABASE_URL` - Database connection (default: SQLite)
- `SECRET_KEY` - JWT secret
- `API_V1_STR` - API prefix (default: `/api/v1`)
- `CORS_ORIGINS` - Allowed CORS origins
- `CORS_ALLOW_ALL` - Allow all origins (dev only)
- `ADMIN_USERNAME`, `ADMIN_PASSWORD` - Default admin credentials

**Frontend:**
- API endpoint configured in `src/api/interceptors.js`
- Uses `http://localhost:8000` for backend in dev mode

## Project-Specific Conventions

### Never Rollback Working Code
- Always treat local changes as source of truth
- Compare with current version (diff) before rewriting files
- Propose merge solutions instead of overwriting
- Ask user before large refactorings

### Russian Language Support
- All user-facing text must support Russian
- Backend runs from `C:\final\backend` directory with uvicorn
- Maintain backward compatibility with existing APIs

### Integration Patterns
- Payment webhooks: Follow patterns in `backend/app/api/v1/endpoints/payment_webhook.py`
- Telegram integration: See `backend/app/api/v1/endpoints/telegram_*.py`
- WebSocket: Follow patterns in `backend/app/ws/`

## Specialized Medical Panels

The system includes specialized unified panels with their own routing:

- **Cardiologist Panel** (`/cardiologist`) - Cardiology examinations, ECG
- **Dermatologist Panel** (`/dermatologist`) - Dermatology, photo archive
- **Dentist Panel** (`/dentist`) - Dental chart, treatment plans, prosthetics
- **Lab Panel** (`/lab-panel`) - Laboratory tests and results

Each panel uses URL parameters (`?tab=`) for internal navigation and includes specialized medical tools.

## GraphQL API

GraphQL endpoint available at `/api/graphql` with schema explorer in admin panel (`?section=graphql-explorer`).

## Notes

- Backend server must always run from `C:\final\backend` directory
- Frontend dev server runs on port 5173, backend on 8000
- Database file: `backend/clinic.db` (SQLite)
- Recent work: macOS UI refactor (current branch: `feat/macos-ui-refactor`)

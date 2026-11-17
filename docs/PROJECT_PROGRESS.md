# Boresha Kipaji League Project Progress

## Current phase

[COMPLETED] Phase 1 — Project audit and test environment
[COMPLETED] Phase 2 — Permissions and authorization
[AWAITING REVIEW] Phase 3 — Player management

## Phase 1

### Completed work

- [COMPLETED] Inspected the configured apps, root URLs, settings, test modules, and migration state.
- [COMPLETED] Added `apps/__init__.py` so root-level unittest discovery can recurse into Django app packages.
- [COMPLETED] Added `config/test_settings.py` with an in-memory SQLite database so test runs do not connect to or alter Supabase.
- [COMPLETED] Verified the model state has no ungenerated migrations with `makemigrations --check --dry-run`.
- [COMPLETED] Confirmed Django's migration listing reports the migrations as applied in the configured database. No migrations were created or applied as part of this phase.

### Partially completed work

- None.

### Outstanding work

- [NOT STARTED] Audit and implement the remaining application workflows and permissions in later phases.
- [NOT STARTED] Add meaningful tests for the currently empty app test modules.
- [NOT STARTED] Review production settings, storage, email, logging, backups, and deployment configuration in Phase 10.

### Tests written and status

- Existing account tests cover registration, authentication, roles, and team access.
- The other app `tests.py` modules are currently empty placeholders.
- The default PostgreSQL-backed test run discovered zero tests before the package fix.
- The prior explicit account test run attempted to create `test_postgres`, which already exists. That database was not deleted, changed, or reused.
- [COMPLETED] `python manage.py test --settings=config.test_settings --verbosity 2`: all 15 discovered account tests passed using in-memory SQLite.
- [COMPLETED] `python manage.py check --settings=config.test_settings`: no issues.
- [COMPLETED] `python manage.py makemigrations --check --dry-run --settings=config.test_settings`: no changes detected.

### Migrations status

- `makemigrations --check --dry-run`: no changes detected.
- `showmigrations --plan`: all listed migrations are marked applied in the configured database.
- No migration files were created or applied during Phase 1.

### Known bugs and blockers

- The default PostgreSQL-backed test runner cannot create its configured `test_postgres` database because a database with that name already exists. Avoid cleanup or reuse of that database; use the isolated test settings instead.
- Test coverage outside accounts is not implemented.

### Decisions requiring client confirmation

- None for Phase 1.
- Later: confirm fantasy scoring values, league tie-break rules, age eligibility, squad composition, budget, and transfer rules before implementation.

### Next recommended task

- Review Phase 2 results. After approval, begin Phase 3 with player and registration workflows.

## Phase 2

### Completed work

- [COMPLETED] Defined distinct model-level permissions for League Admin, Match Official, Team Manager, Fantasy Manager, and Content Manager. Super Admin is represented by Django's `is_superuser`; public visitors receive no management permissions.
- [COMPLETED] Changed role-group synchronization to replace stale direct group permissions with the current least-privilege policy.
- [COMPLETED] Added reusable server-side checks for assigned teams, assigned matches, owned fantasy teams, scoped player visibility, and protected team/match/fantasy-team views.
- [COMPLETED] Scoped Django admin querysets and object permissions for team managers, match officials, and fantasy managers.
- [COMPLETED] Limited team-manager edit fields; restricted player registrations to assigned teams; limited match officials to assigned match score/event/performance operations; protected fantasy-team ownership and selection changes.
- [COMPLETED] Restricted manager assignments, match-official assignments, league configuration, and content workflows to their authorized roles.
- [COMPLETED] Added authorization coverage for permitted and denied operations, ownership, forged fields, role permissions, and anonymous access.

### Partially completed work

- None in the code and isolated test environment.

### Outstanding work

- [NEEDS CLIENT CONFIRMATION] Synchronize the stored role-group permissions in the configured PostgreSQL environment by running `python manage.py create_user_groups`. This was not run because it changes database records; the authorization code and tests were kept isolated from the configured database.
- [NOT STARTED] Add authorization to player, match, statistics, standings, fantasy, and content views when those workflows are implemented in later phases.
- [NOT STARTED] Implement player creation and registration workflows in Phase 3.

### Tests written and status

- [COMPLETED] Added `apps/accounts/test_authorization.py` with tests for role permission assignments, team access, match-official assignment scope, fantasy-team ownership, content-manager access, anonymous access, and forged form fields.
- [COMPLETED] `python manage.py test --settings=config.test_settings --verbosity 2`: all 35 tests passed using in-memory SQLite.
- [COMPLETED] `python manage.py check --settings=config.test_settings`: no issues.
- [COMPLETED] `python manage.py makemigrations --check --dry-run --settings=config.test_settings`: no changes detected.
- [COMPLETED] Python compilation and `git diff --check` passed for Phase 2 changes.

### Migrations status

- No model changes or migrations were made in Phase 2.

### Known bugs and blockers

- The PostgreSQL-backed test runner still cannot create its configured `test_postgres` database because one with that name already exists. It was not deleted or changed; use the isolated test settings for local tests.
- Role-group permission synchronization in the configured database remains an explicit operational step and was not performed.
- Most apps still do not have implemented request workflows; role checks are in place for the existing admin and team workflows and reusable helpers are available for future protected views.

### Decisions requiring client confirmation

- Confirm when it is safe to run `python manage.py create_user_groups` against the configured PostgreSQL environment.
- Later: confirm fantasy scoring values, league tie-break rules, age eligibility, squad composition, budget, and transfer rules before implementation.

### Next recommended task

- Review Phase 3 changes before starting Phase 4.

## Phase 3

### Completed work

- [COMPLETED] Added player list, detail, create, and edit workflows, with registration history, registration, and transfer operations.
- [COMPLETED] Scoped player visibility and management to League Admins and Team Managers assigned to teams with a registration active on the current date; future registrations do not grant access early, and ended registrations stop granting current player access.
- [COMPLETED] Added forms with role-scoped team/player choices and validation for registration dates, shirt numbers, and overlapping player registrations across seasons.
- [COMPLETED] Added atomic service operations for player creation with initial registration, updates, registration, and transfers. Registration operations lock relevant player, team, season, and source-registration rows and call `full_clean()` before saving.
- [COMPLETED] Transfers close the existing registration on the day before the new registration starts and preserve the prior registration row.
- [COMPLETED] Prevented registration history deletion through Django admin and scoped player/registration admin access.
- [COMPLETED] Routed Django Admin registration creation through the same locked registration service; direct Admin edits and inline add/edit/delete are disabled so registration changes preserve the player workflows and history.
- [COMPLETED] Added player URLs under `/players/` and included them in the project URL configuration.
- [COMPLETED] Added tests covering role access, permitted and denied operations, registration validation/history, transfer behavior, and transaction rollback.
- [COMPLETED] Added tests for team-manager access before/on/after a future transfer, Admin registration validation, and historical match-performance validity after transfer.

### Outstanding work

- [NOT STARTED] Match management remains Phase 4 and has not been started.
- [OUT OF SCOPE] Frontend templates were not added; the frontend is handled by another developer.

### Tests written and status

- [COMPLETED] `python manage.py test --settings=config.test_settings`: all 64 tests passed using the isolated in-memory SQLite database.
- [COMPLETED] `python manage.py check`: no issues.
- [COMPLETED] `python manage.py makemigrations --check --dry-run`: no changes detected.
- [COMPLETED] Python compilation passed for the changed permission, service, admin, and test modules.

### Migrations status

- No model fields or migrations were changed in Phase 3.
- No migrations were created or applied.

### Known bugs and blockers

- Registration date-overlap and shirt-number-overlap checks remain application-level validation; the database does not have a general date-range exclusion constraint.
- The service serializes supported writes with row locks on PostgreSQL, but `select_for_update()` is a no-op on SQLite, so the isolated SQLite suite does not prove concurrent-write behavior. Direct ORM writes that bypass the service can also bypass locking and `full_clean()` because Django does not run model validation automatically on `save()`.
- A PostgreSQL exclusion constraint is technically practical using range operators and the `btree_gist` extension. It would require a PostgreSQL-specific migration and extension availability; SQLite would not enforce an equivalent constraint. No such migration was added to avoid backend-specific schema behavior without a separate migration strategy.

### Decisions requiring client confirmation

- None for Phase 3. Transfer operations use the day before the new registration start date as the outgoing registration's end date.

### Next recommended task

- Review Phase 3. After approval, begin Phase 4 match management.

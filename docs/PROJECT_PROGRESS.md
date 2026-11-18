# Boresha Kipaji League Project Progress

## Current phase

[COMPLETED] Phase 1 — Project audit and test environment
[COMPLETED] Phase 2 — Permissions and authorization
[COMPLETED] Phase 3 — Player management
[COMPLETED] Phase 4 — Match management
[AWAITING REVIEW] Phase 5 — League intelligence

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

- Phase 3 is complete. Phase 4 match management is awaiting review.

## Phase 4

### Completed work

- [COMPLETED] Added explicit `SeasonTeam` membership because no season-team participation relationship existed. League Admins can add memberships through the protected Django Admin. Fixture validation requires both teams to be active and enrolled in the selected season.
- [COMPLETED] Added JSON API endpoints for fixture listing, creation, viewing and editing; fixture creation/editing and season enrollment are League Admin-only.
- [COMPLETED] Added fixture validation for distinct home/away teams, season membership, positive matchweek when supplied, and kickoff date within the season.
- [COMPLETED] Added a match lifecycle service supporting scheduled, live, completed, postponed and cancelled transitions. Assigned Match Officials and League Admins can operate the lifecycle; Team Managers cannot modify status or scores.
- [COMPLETED] Set results from recorded goal, penalty-goal and own-goal events. Completion requires an event-derived result; completed and started fixtures cannot be casually edited or reopened.
- [COMPLETED] Added transactional match-official assignment/removal workflows; only League Admins can manage assignments, and only Match Official role users can be assigned. Duplicate assignments remain prevented by the existing database uniqueness constraint.
- [COMPLETED] Added transactional event create/edit/delete workflows with match assignment authorization, live-match restrictions, positive event minutes, registration-on-match-date eligibility, and substitution same-team validation.
- [COMPLETED] Scoring events update the match score transactionally. Own goals are attributed to the opponent of the registered team; cards and substitutions do not affect the score.
- [COMPLETED] Hardened Django Admin writes to use the same services; match status and scores are not editable in the fixture form, unauthorized users cannot change fixtures/events/assignments, and match/event history cannot be deleted from Admin.
- [COMPLETED] Added `started_at` to preserve the fact that a match started even if it is later postponed, preventing fixture edits after play has begun.
- [COMPLETED] Protected match events and official assignments from cascading deletion when a match is removed.
- [COMPLETED] Added migration backfills for existing season-team participation and for `started_at` on existing live/completed and identifiable started-postponed matches.
- [COMPLETED] Added match-management tests covering fixtures, season membership, officials, lifecycle/results, event eligibility/substitutions, authorization, admin permissions, and transaction rollback.

### Files changed

- [CHANGED] `apps/matches/models.py`
- [ADDED] `apps/matches/services.py`
- [ADDED] `apps/matches/forms.py`
- [CHANGED] `apps/matches/views.py`
- [ADDED] `apps/matches/urls.py`
- [CHANGED] `apps/matches/admin.py`
- [CHANGED] `apps/matches/tests.py`
- [CHANGED] `apps/accounts/test_authorization.py` (assert assigned officials can change status but cannot edit scores directly in Admin)
- [ADDED] `apps/matches/migrations/0003_seasonteam.py`
- [ADDED] `apps/matches/migrations/0004_match_started_at.py`
- [ADDED] `apps/matches/migrations/0005_alter_matchevent_match_alter_matchofficial_match.py`
- [CHANGED] `apps/accounts/permissions.py` (League Admin permissions for season-team enrollment)
- [CHANGED] `config/urls.py`
- [CHANGED] `docs/PROJECT_PROGRESS.md`

### Tests written and status

- [COMPLETED] `apps/matches/tests.py` covers fixture create/edit and validation, both team season memberships, matchweek/kickoff validation, League Admin-only official management, duplicate assignment rejection, assigned-official access, lifecycle transitions, completed results, event eligibility and substitutions, unauthorized score changes, Django Admin permissions, and transaction rollback.
- [COMPLETED] `python manage.py test --settings=config.test_settings`: all 88 tests passed using the isolated in-memory SQLite database.
- [COMPLETED] `python manage.py check`: no issues.
- [COMPLETED] `python manage.py makemigrations --check --dry-run`: no ungenerated migrations.
- [COMPLETED] Python compilation passed for all changed Python modules and migrations.
- [COMPLETED] `git diff --check` and focused trailing-whitespace checks passed.

### Migrations status

- Three additive/alteration migrations were added: explicit season-team membership with a backfill from existing registrations and fixtures; match `started_at` with a safe backfill where existing status/events/scores establish that play started; and `PROTECT` behavior for match events and official assignments.
- Migrations have not been applied to the configured database.

### Remaining limitations

- SQLite does not implement effective `select_for_update()` locking; the isolated suite cannot verify PostgreSQL concurrency behavior. Supported workflow writes use transactions and lock the match/season/team/player/registration rows relevant to their operation, but direct ORM writes can bypass service-level validation.
- Validation such as status transitions, event eligibility, matchweek bounds, and team activity remains application-level; there is no database constraint expressing these cross-table rules.
- Existing postponed matches without event or score evidence cannot be reliably classified as previously started. Their `started_at` remains null after backfill.
- Results are derived from recorded scoring events. A non-zero result cannot be entered without corresponding goal events. Completed fixtures cannot be casually edited or reopened; League Admins can correct completed events through the authorized event workflow, which recalculates the result and Phase 5 intelligence. Prior values are not retained in a separate audit log.
- Event minute validation requires minute >= 1 but has no arbitrary upper bound because youth match duration and extra-time rules are not defined.
- Event team is inferred from the player's registration on the match date; an own goal credits the opposing team. For substitutions, `player` is treated as the outgoing player and `related_player` as the incoming player.
- No statistics engine, player season-stat calculation, or standings calculation was implemented in Phase 4.
- The new API is backend-only; no frontend templates were added.

### Client decisions still required

- Decide whether an immutable audit log is required for completed result/event corrections; current corrections are League Admin-only but do not retain prior values.
- Confirm maximum match minutes and whether extra time is used for these youth competitions.
- Confirm the event API convention that `player` is the outgoing substitution player and `related_player` is the incoming player.

### Next recommended task

- Phase 4 was approved; Phase 5 is documented below.

## Phase 5 — League Intelligence

### Completed work

- [COMPLETED] Reused `PlayerMatchPerformance` as the per-match verified performance record and `PlayerSeasonStatistics` as the season aggregate; no duplicate statistics models were introduced.
- [COMPLETED] Match events are the source of truth for goals (including penalty goals), own goals, yellow cards, and red cards. Recalculation overwrites the corresponding per-match fields from events, avoiding event/performance double counting.
- [COMPLETED] Authorized performance records supply minutes, assists, clean-sheet flags, penalties saved, and Player of the Match awards. Event participants and recorded performances each produce at most one appearance per match.
- [COMPLETED] Season statistics are rebuilt from completed-match performances only. Past records remain attached to their season when a player transfers.
- [COMPLETED] Standings are rebuilt from completed match scores and season team memberships. Repeated recalculation replaces totals, includes enrolled teams with zero results, and retains each season's own rows.
- [COMPLETED] Completion and authorized completed-event corrections rebuild both engines inside the match transaction. Corrected scores flow to standings, and failures roll back the match, player statistics, and standings together.
- [COMPLETED] Fixed the completion integration to pass the authorized user and match ID to the keyword-only statistics and standings services.
- [COMPLETED] Removed implicit standings tie-break ordering beyond points. The metadata-only migration `apps/standings/migrations/0002_alter_teamstandings_options.py` changes default ordering to points only; it changes no schema or data.
- [COMPLETED] Added explicit per-match appearance confirmation. New verified entries require `appeared=True` with positive minutes; event/performance rows alone no longer increment appearances. Existing performance rows are backfilled as appearances to preserve historical totals.
- [COMPLETED] Kept clean sheets as authorized manual verification because lineup and on-field intervals are not modeled. A clean sheet requires a verified appearance and is not inferred from the final score.
- [COMPLETED] Added public GET-only JSON endpoints at `/statistics/players/` and `/standings/`. They default to the active season (or latest season if none is active), allow a season ID query, and never trigger writes or recalculation.
- [COMPLETED] Restricted explicit service recalculations to League Admins. Match Officials can record live-match performance and automatic completion still rebuilds intelligence inside the match-management transaction; completed performance corrections are League Admin-only.
- [COMPLETED] Prevented duplicate event facts through event validation in the match-locked service workflow, without adding a uniqueness migration.

### Calculation rules

- Only matches with `status=completed` contribute. Scheduled, live, postponed, and cancelled fixtures are excluded.
- Appearances count one explicitly confirmed `PlayerMatchPerformance` per player and completed match. New confirmations require positive recorded minutes; multiple events never add extra appearances. A performance or event without an explicit confirmation does not count as an appearance.
- Event-derived per-match totals are regenerated from event rows. Goals and cards are not accepted as direct performance inputs. Scoring events are checked against the completed match score.
- Assists, minutes, clean sheets, penalties saved, Player of the Match awards, and appearance confirmation are official-entered performance fields because the current event model does not model these facts. Clean sheets are not derived from final score because it cannot account for substitutions.
- Standings award 3 points for a win and 1 for a draw, with 0 for a loss. Goal difference is goals for minus goals against.
- Standings are ordered by points only. No ranking is asserted between teams tied on points.

### Models, services, and authorization

- Existing models retained: `MatchEvent`, `PlayerMatchPerformance`, `PlayerSeasonStatistics`, `SeasonTeam`, and `TeamStandings`.
- Statistics services: `record_match_performance`, `recalculate_completed_match_statistics`, and `recalculate_player_season_statistics`.
- Standings services: `recalculate_completed_match_standings` and `recalculate_season_standings`.
- Public read-only APIs: `/statistics/players/` and `/standings/`; both return the active season or latest season by default, accept `season_id`, and only expose stored aggregates.
- Match Officials assigned to a match and League Admins may record match performance; authorized operators can rebuild completed-match intelligence, and League Admins can rebuild a whole season. Team Managers cannot modify verified statistics.
- Manual season and per-match recalculation service entry points are League Admin-only. Automatic match-completion and League Admin correction flows call internal rebuild helpers inside their existing transaction. Team Managers have read-only Admin access to aggregate statistics; public JSON endpoints are GET-only.
- Match Officials cannot use Django Admin to change completed performance records. They can enter performance during a live match; only League Admins can correct those records after completion.
- All calculation and correction workflows are transactional and idempotent. Runtime row-lock/concurrency behavior is not established by SQLite tests.

### Tests and results

- [COMPLETED] Player statistics tests cover explicit appearance validation, multiple goals and assists, event aggregation, own goals, cards, manual clean sheets, penalties saved, Player of the Match, minutes, transfers, multiple seasons, canceled/incomplete/postponed matches, recalculation/idempotency, completed-event corrections, public read-only access, authorization, and transaction rollback.
- [COMPLETED] Standings tests cover wins/draws/losses, goals, goal difference, points, zero-match teams, multiple seasons, postponed/cancelled matches, corrections, membership validation, public read-only access, authorization, idempotency, and transaction rollback.
- [COMPLETED] Match tests reject exact duplicate event facts and verify the score is not incremented twice.
- [COMPLETED] Cross-engine tests verify completion/correction synchronization and rollback if either intelligence rebuild fails.
- [COMPLETED] `python manage.py test --settings=config.test_settings`: 113 tests passed using isolated in-memory SQLite.
- [COMPLETED] `python manage.py check`: no issues.
- [COMPLETED] `python manage.py makemigrations --check --dry-run`: no ungenerated migrations after adding the metadata-only migration.
- [COMPLETED] Python compilation and whitespace checks passed.

### Migrations status

- Added `0002_alter_teamstandings_options.py` to remove implicit goal-difference and goals-for default ordering. It has no database schema or data effects.
- Added `apps/statistics/migrations/0003_playermatchperformance_appeared.py` with an `appeared` field and a data backfill marking existing performance rows as appearances. This preserves the prior aggregate interpretation and does not change minutes or other statistics.
- No schema migration was needed for public read-only endpoints, permissions, or event validation.
- The three Phase 4 migrations remain as previously documented. No migration has been applied to Supabase or any configured database as part of Phase 5.

### Client decisions still required

- Define league ranking/tie-break rules for teams level on points. Until confirmed, standings expose points-based ordering only and do not claim a unique rank.
- Confirm whether assists, clean sheets, penalties saved, minutes, and Player of the Match should remain manually verified performance inputs or gain explicit event evidence/workflows.
- Confirm whether penalty saves should eventually be represented by a match event; the current event model has no penalty-save event type.
- Confirm whether two identical event facts for the same player and match minute can represent distinct legitimate events. Current validation treats an exact match of event type, player, related player, minute, and added time as a duplicate.

### Remaining limitations

- Existing performance values are trusted once entered through authorized match workflows; no independent evidence model currently verifies minutes, assists, clean sheets, penalties saved, or awards.
- Appearances require an explicit operator confirmation for new records; event participants are not automatically treated as appearances. Minutes played are manual inputs and are not inferred from substitutions.
- Exact duplicate event detection is application-level, not a database uniqueness constraint. Supported event writes lock the match before validation; SQLite tests do not establish PostgreSQL concurrency behavior. The exact-fact policy could reject two genuinely distinct same-player events recorded in the same minute, pending client confirmation.
- There is no separate publication/approval flag for season statistics or standings. Public endpoints expose only stored aggregates and do not recalculate on read; historical data requires a League Admin recalculation before it is considered current.
- SQLite test results do not prove PostgreSQL locking or concurrency behavior.
- The added migration has not been applied anywhere; deployment and Supabase migration approval remain outside this phase.

### Next recommended task

- Stop after Phase 5 and wait for review.

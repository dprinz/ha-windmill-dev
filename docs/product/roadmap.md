# Delivery roadmap

The ticket IDs encode creation order, not a mandate to implement every ticket strictly one after another. Dependencies define the actual execution graph.

## Phase 0: verified foundation

1. `WMHA-0001` — verify the complete Windmill API, edition, permission and capability contract.
2. `WMHA-0002` — bootstrap the integration and minimal config flow.
3. `WMHA-0003` — implement the typed async client, runtime data and capability model.

## Phase 1: usable operational monitoring

4. `WMHA-0004` — replace the minimal setup with guided onboarding, reauth, reconfigure and options.
5. `WMHA-0005` — expose general instance health and Home Assistant System Health.
6. `WMHA-0006` — add worker-group and optional worker observability.
7. `WMHA-0007` — add bounded run counters, timestamps and event entities.

Tickets 0006 and 0007 may proceed in parallel after their dependencies are accepted.

## Phase 2: controlled automation

8. `WMHA-0008` — discover and explicitly select runnable scripts and flows.
9. `WMHA-0009` — run selected scripts and flows through Home Assistant actions.
10. `WMHA-0010` — track and cancel Home Assistant-started jobs.

## Phase 3: lifecycle and operational maturity

11. `WMHA-0011` — add read-only update visibility for eligible self-hosted instances.
12. `WMHA-0012` — add redacted diagnostics, repairs, recovery and log throttling.
13. `WMHA-0013` — complete German and English translations and user documentation.
14. `WMHA-0014` — add HACS packaging and reproducible release automation.
15. `WMHA-0015` — execute the stable-release quality and compatibility gate.

## Post-v1 experiment

16. `WMHA-0016` — measure and, only when justified, implement SSE or webhook-based job observation.

## v1 cut line

The first stable release includes PR-001 through PR-014 from `requirements.md`. PR-015 and `WMHA-0016` are deliberately outside the v1 critical path.

## Priority rule

A later ticket must not be pulled forward merely because it is visually attractive. Pull it forward only when:

- every declared dependency is accepted,
- the earlier ticket does not provide a smaller releasable increment,
- the change does not obscure API or capability uncertainty,
- tests and review can remain bounded to one outcome.

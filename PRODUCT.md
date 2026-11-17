# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Existing Python 3.12 + Streamlit 1.67 application with Pandas, SQLite, CSV import/export, and a local single-user workflow.

## Users

Evidence-based inference from the repository: agricultural analysts, extension/advisory staff, and field decision-makers who need to inspect waterlogging exposure, crop state, disease evidence, and intervention windows in one bounded workspace. The interface is desktop-first for detailed data review and must remain usable on phones for field-side checks.

## Product Purpose

Support evidence-bound agricultural risk screening after waterlogging. The product separates exposure facts, crop state, field symptoms, laboratory diagnosis, environmental suitability, and operational windows so that missing evidence is not silently converted into zero risk or a definitive recommendation.

## Positioning

The product does not present a disease probability or local yield-loss forecast. Its mechanism is a transparent, case-pack-scoped decision workflow that links quantitative rules, public evidence, explicit data gaps, and intervention constraints while keeping unsupported conclusions visibly unknown.

## Operating Context

Users work with a selected regional case pack, enter or import field observations, compare scenario assumptions with submitted values, inspect intervention timing, and review the evidence and data boundaries behind each result. Public datasets and APSIM simulations are supporting evidence, not substitutes for local field observations.

## Capabilities and Constraints

- Existing functional domains: overview, risk scenario screening, intervention windows, field observation import/export, public data integration, APSIM simulation evidence, and research evidence.
- Preserve the seven pages' factual content, calculations, validation, and data boundaries.
- The user allows consolidating the seven pages into four to five clearer top-level modules without changing business logic.
- Existing case packs, local SQLite history, CSV workflows, and explicit missing-data semantics must remain intact.
- APSIM output must remain labeled as simulation and must not be presented as local observation or forecast.

## Brand Commitments

- The user explicitly requested a complete visual replacement rather than another refinement of the incumbent interface.
- Lead visual direction: hybrid C, combining the gray-white canvas and electric lime accent of the dashboard references with cream and natural green as supporting agricultural accents.
- Use agricultural field, crop, and remote-sensing-style imagery as visual material; imagery must not imply that it is project-measured data.
- The UI should feel rounded, modular, image-rich, spacious, and contemporary while remaining a trustworthy operational tool.

## Evidence on Hand

- Case packs and quantitative inputs under `case_packs/` and `data/`.
- Public evidence CSV/SQLite files and APSIM simulation outputs under `data/`.
- Product behavior and boundaries documented in `README.md`, `docs/`, and enforced by `tests/`.
- The reference images supplied by the user establish visual taste only; they are not factual agricultural evidence.
- The repository does not currently contain project-owned agricultural photography.

## Product Principles

1. Evidence precedes advice; unsupported inference stays visibly unknown.
2. Prioritize operational decisions over decorative data density.
3. Keep assumptions, submitted inputs, simulations, and observations clearly separated.
4. Make limitations and safety constraints discoverable where decisions are made.
5. Preserve a coherent system across every module instead of styling pages independently.

## Accessibility & Inclusion

Maintain keyboard access, visible focus states for standard controls, readable contrast, responsive layouts, and non-color-only status communication.

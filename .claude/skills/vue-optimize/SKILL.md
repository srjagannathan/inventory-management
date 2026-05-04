---
name: vue-optimize
description: Analyzes Vue 3 + Composition API components for performance issues, code-reuse opportunities, and reactivity smells, then produces a structured report with file/line citations, severity, recommended fixes, and estimated impact. Use this skill whenever the user asks to optimize, review, audit, refactor, or speed up Vue components — phrases like "optimize this Vue component", "find reuse opportunities in the frontend", "review Vue performance", "audit our .vue files", "why is this view slow", "find duplicated component logic", or any request to look across client/src/views or client/src/components for problems. Trigger even if the user does not say the word "skill" — if they hand you a .vue file or a frontend directory and ask for an analysis, use this. Do NOT use this skill for writing new components or fixing a single known bug; those go to vue-expert.
---

# Vue 3 Optimization Analysis

This skill analyzes Vue 3 (Composition API) components in this repo and produces an actionable report. The goal is to surface the *highest-leverage* issues — not to enumerate every nit. A short, sharp report that the user will actually act on beats an exhaustive one they'll skim.

## When to use

Use when the user asks to optimize, review, audit, or "look for problems" across `.vue` files. Common framings:
- "Optimize this component" / "review this view"
- "Find places we should extract a composable / component"
- "Why is the Dashboard slow?"
- "Audit client/src for reuse opportunities"

If the user just wants to *implement* a known fix, hand off to the **vue-expert** subagent instead. This skill is for *analysis*.

## Scope inputs

The user may point you at:
- A single `.vue` file → analyze just that file
- A directory (e.g., `client/src/views/`) → analyze every `.vue` file in it
- The whole frontend (`client/src/`) → analyze both views and components, and look for *cross-file* duplication

If the scope is ambiguous, default to `client/src/views/` + `client/src/components/` and say so in the report header.

## Workflow

1. **Enumerate files** with Glob (`**/*.vue` under the scope).
2. **Read each file fully** — don't skim. Many issues only surface when you see template + script + style together.
3. **Run the checks below** mentally as you read. Note findings with line numbers.
4. **For cross-file duplication**, after reading everything, look for repeated template fragments (≥ ~8 lines of similar markup), repeated script logic (≥ ~5 lines of similar reactive setup), and repeated `<style>` blocks.
5. **Rank findings** by impact (see Severity rubric). Drop low-value findings if the report is getting bloated — aim for ≤ ~15 findings total on a medium codebase. Quality over quantity.
6. **Write the report** in the exact format below.

Use Read / Grep / Glob directly. Don't spawn subagents for the analysis itself — you have the full picture and a subagent would lose context.

## What to look for

The checks below are heuristics, not rules. Use judgment: a finding only matters if a developer would actually want to know about it. If you'd rather not bother the user with it, don't include it.

### Performance issues

- **Heavy work in templates.** Inline expressions like `{{ orders.filter(...).reduce(...) }}` re-run on every render. Move to a `computed`. Especially bad inside `v-for`.
- **Method calls in templates** where a `computed` would cache. Methods re-run every render; computeds cache by dependency. If the function is pure and inputs are reactive, prefer `computed`.
- **Missing `v-memo`** on large `v-for` lists where most items don't change between renders. Worth flagging on lists rendering ≥ ~50 rows with stable data.
- **Bad `v-for` keys.** `:key="index"` is a smell whenever the list can reorder, filter, or have items inserted. Look for stable identifiers (`sku`, `id`, `month`). The CLAUDE.md explicitly calls this out as a known issue in this project.
- **Large reactive objects.** `ref()` / `reactive()` on big arrays or deeply-nested objects that are read but never *mutated piecewise* (e.g., whole-array replacement from an API call) should be `shallowRef`. Static config objects passed to charts should be `markRaw`.
- **Expensive watchers.** `watch` with `{ deep: true }` over a large object, or watchers that fire on every keystroke without `{ flush: 'post' }` or debouncing. Also flag watchers that should really be `computed` (they only derive a value).
- **`v-if` + `v-for` on the same element.** Vue 3 makes `v-if` win, which means the filter happens *after* iterating. Move the filter into a computed.
- **Inline object/array literals as props** (`:style="{ color: 'red' }"`, `:items="[1,2,3]"`) — these create a new reference each render and bust child memoization. Lift to a computed or constant.
- **Unstable event handlers** in `v-for` that capture loop vars via inline arrow functions when the child is memoized — same issue as above.

### Code reuse opportunities

- **Repeated template fragments.** If two or more components have ≥ ~8 lines of substantially similar markup (a card, a stat tile, a table row), recommend extracting a component. Cite both file paths.
- **Repeated reactive logic.** If multiple files do the same `ref + watch + fetch` dance, or build the same derived state, recommend a composable. This project already has `client/src/composables/` (useFilters, useAuth, useI18n) — follow that convention and suggest a name like `useSomething.js`.
- **Filter integration.** This project's filter system is centralized in `useFilters`. If you find a view that re-implements filter state locally instead of calling `useFilters()`, flag it. If you find filter-aware fetching duplicated across views, suggest a composable like `useFilteredResource(endpoint)`.
- **Repeated `<style>` blocks.** Identical CSS in multiple SFCs should move to `App.vue` (the project's central stylesheet) or a shared style file.
- **Modal patterns.** This project has many `*DetailModal.vue` components. If they share open/close/escape-key logic, suggest a `useModal` composable.

### Reactivity smells

- **Prop mutation.** `props.foo = ...` or pushing/splicing into a prop array. Always wrong; recommend `emit` + parent ownership, or a local `ref` initialized from the prop.
- **Destructuring `reactive()` or `props`.** `const { a, b } = props` loses reactivity. Use `toRefs(props)` or access as `props.a`.
- **`ref` vs `reactive` misuse.** `reactive([])` for arrays you'll reassign — reassignment breaks reactivity; use `ref([])`. `ref(someObject)` and then mutating `.value.foo.bar` deeply when `reactive` would read more naturally — minor, only flag if it's hurting readability.
- **Missing `toRefs` when returning from a composable.** Returning `reactive({})` from `useX()` and destructuring at the call site silently breaks reactivity.
- **Computeds that mutate.** A `computed(() => { state.x++; return state.x })` is a bug. Flag any side effects inside computeds.
- **Watchers that should be computeds.** `watch(a, () => { b.value = a.value * 2 })` should be `const b = computed(() => a.value * 2)`.

### Project-specific heuristics

This codebase has known patterns documented in CLAUDE.md. Apply these *before* generic Vue heuristics — they reflect real decisions:

- **Filter state lives in `useFilters`.** Local filter refs in a view are a bug, not a style choice.
- **Derived data goes in `computed`, raw data in `ref`.** A view that filters/sorts/aggregates inside the template instead of in a `computed` is a flagged finding.
- **Custom SVG charts.** Don't recommend swapping to a chart library — that's out of scope. But *do* flag if chart math runs every render instead of in a computed.
- **No emojis in UI.** If you encounter emojis in templates, flag as a design-system violation (low severity).
- **Unique keys.** `:key="index"` in v-for is explicitly called out as a project gotcha. Always flag.
- **Date validation.** Calling `.getMonth()` etc. on possibly-invalid dates is a known issue. Flag any unguarded date-method calls in templates or computeds.

## Severity rubric

- **High** — measurable user-visible impact (jank, wrong data, broken reactivity), or a bug that *will* fire under realistic data. Examples: prop mutation, `:key="index"` on a reorderable list, `watch({ deep: true })` over a 1000-row dataset.
- **Medium** — wasted work or maintainability tax that adds up. Examples: method-in-template that should be computed, 12 lines of duplicated markup across two views, missing `toRefs` in a composable return.
- **Low** — cleanup, polish, or theoretical improvements. Examples: a `markRaw` opportunity on a 5-item config object, style cleanup, naming.

When in doubt, downgrade. A report full of "high"s is a report nobody trusts.

## Report format

Use this exact structure. Markdown headings matter — they're how the user navigates the report.

```markdown
# Vue Optimization Report

**Scope:** <files or directories analyzed>
**Files reviewed:** <count>
**Findings:** <high count> high · <medium count> medium · <low count> low

## Summary

<2-4 sentence executive summary. What are the top 1-3 things to fix first, and what's the rough theme — e.g. "Three views re-implement filter state locally; consolidating to useFilters would remove ~80 lines and fix one reactivity bug.">

## Findings

### `client/src/views/Dashboard.vue`

#### [HIGH] Method called in v-for instead of computed — lines 42–48

```vue
<tr v-for="order in orders.filter(o => o.status === selectedStatus)" :key="order.id">
```

`orders.filter(...)` runs on every render, including unrelated reactivity changes. With ~500 orders and a parent watcher that ticks frequently, this is the dominant cost on this view.

**Fix:** Hoist to a computed:
```js
const filteredOrders = computed(() =>
  orders.value.filter(o => o.status === selectedStatus.value)
)
```

**Impact:** Eliminates a per-render array traversal. On the Dashboard's typical update cadence, this is meaningful.

---

#### [MEDIUM] `:key="index"` in reorderable list — line 87

<offending snippet>

**Fix:** Use `:key="row.sku"` — `sku` is unique per inventory item.

**Impact:** Prevents DOM reuse bugs when filters reorder the list (already documented as a project gotcha in CLAUDE.md).

---

### `client/src/views/Orders.vue`

<...>

## Cross-file opportunities

### [MEDIUM] Filter state duplicated across Spending.vue and Reports.vue

Both views declare local `selectedWarehouse` / `selectedCategory` refs and wire them to FilterBar manually (Spending.vue:18-34, Reports.vue:22-38). The project's `useFilters` composable already exposes this state globally.

**Fix:** Replace local refs with `const { warehouse, category } = useFilters()`. Removes ~30 lines, fixes the bug where the two views' filter state can drift apart.

**Impact:** High — currently the two views can show inconsistent data after a filter change.

---

### [LOW] Modal open/close logic duplicated across 5 *DetailModal.vue files

<...>

## Notes & non-findings

<Optional. Things you considered but didn't flag, or context the user might be wondering about. e.g. "I considered v-memo on the inventory table but the row count is small enough (~40) that it wouldn't matter.">
```

## Editing rules

- **Don't modify any files** unless the user explicitly asks for fixes after seeing the report. Analysis first, then fix on request.
- **Cite real line numbers** from the actual files. If you're unsure, re-read.
- **Quote real snippets** — paraphrasing loses precision. Use a 1-3 line excerpt.
- **Keep the report scannable.** A developer should be able to read the Summary and immediately know what to do first.

## Anti-patterns for this skill

Things to *not* do — these dilute the report's value:

- Don't list every `.value` access as if it's a finding. It's how Vue works.
- Don't recommend rewrites for stylistic preferences (Options API → Composition, etc.) unless the project is mid-migration.
- Don't recommend third-party libraries (Pinia, Vueuse, chart libs) unless the user asked.
- Don't pad with "consider adding tests" unless test gaps are the actual subject.
- Don't restate Vue documentation. Cite a specific issue in *this* file.

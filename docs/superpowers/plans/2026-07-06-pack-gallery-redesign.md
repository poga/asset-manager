# Pack Gallery Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the center pack gallery (`PackGallery.vue`) into a calm, professional grid — larger cards, clear hierarchy, quiet tag editing — with zero behavior changes.

**Architecture:** All changes live in one Vue SFC: `web/frontend/src/components/PackGallery.vue` (template, one small image-load handler, scoped CSS). Existing class names and event contracts are preserved so the 9 existing component tests pass unchanged. Spec: `docs/superpowers/specs/2026-07-06-pack-gallery-redesign-design.md`.

**Tech Stack:** Vue 3 SFC (script setup), scoped CSS with the app's existing CSS variables, Vitest + @vue/test-utils (jsdom).

## Global Constraints

- Only `web/frontend/src/components/PackGallery.vue` and `web/frontend/tests/PackGallery.test.js` may change. Do NOT touch `PackList.vue` (the left sidebar is off-limits).
- All 9 pre-existing tests in `tests/PackGallery.test.js` must pass unchanged — do not edit existing test cases.
- Use only existing CSS variables (`--color-*`, `--shadow-*`) plus the hardcoded cover stage `#1a1a2e`. No new fonts, tokens, or dependencies.
- Test command (run from `web/frontend/`): `npx vitest run tests/PackGallery.test.js`
- Comments: max 1 line / 80 chars.
- Commit after each task from the repo root.

---

### Task 1: Crisp cover stage (aspect-ratio + pixelated upscale)

**Files:**
- Modify: `web/frontend/src/components/PackGallery.vue`
- Test: `web/frontend/tests/PackGallery.test.js`

**Interfaces:**
- Consumes: current `PackGallery.vue` (`failedCovers` reactive map, `previewUrl()`).
- Produces: `smallCovers` reactive map + `onCoverLoad(packName, event)` in the script; `.card-cover img.pixelated` CSS hook. Template `<img>` gains `:class="{ pixelated: smallCovers[pack.name] }"` and `@load="onCoverLoad(pack.name, $event)"`. Later tasks don't depend on these names but must not remove them.

- [ ] **Step 1: Write the failing test**

Append inside the `describe('PackGallery', ...)` block in `web/frontend/tests/PackGallery.test.js`:

```js
  it('upscales small covers crisply, leaves large covers smooth', async () => {
    const wrapper = mount(PackGallery, { props: { packs } })
    const imgs = wrapper.findAll('.card-cover img')

    Object.defineProperty(imgs[0].element, 'naturalWidth', { value: 64 })
    await imgs[0].trigger('load')
    expect(imgs[0].classes()).toContain('pixelated')

    Object.defineProperty(imgs[1].element, 'naturalWidth', { value: 512 })
    await imgs[1].trigger('load')
    expect(imgs[1].classes()).not.toContain('pixelated')
  })
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `web/frontend/`): `npx vitest run tests/PackGallery.test.js`
Expected: 1 FAIL (`expected [] to include 'pixelated'`), 9 pass.

- [ ] **Step 3: Implement**

In `web/frontend/src/components/PackGallery.vue`:

3a. Script — after the `const failedCovers = reactive({})` line, add:

```js
// sprites below this width are upscaled; pixelated keeps them crisp
const smallCovers = reactive({})

function onCoverLoad(packName, event) {
  if (event.target.naturalWidth < 200) smallCovers[packName] = true
}
```

3b. Template — replace the `<img ...>` element inside `.card-cover` with:

```html
            <img
              v-if="!failedCovers[pack.name]"
              :src="previewUrl(pack.name)"
              :alt="formatPackName(pack.name)"
              :class="{ pixelated: smallCovers[pack.name] }"
              loading="lazy"
              @load="onCoverLoad(pack.name, $event)"
              @error="failedCovers[pack.name] = true"
            />
```

3c. Scoped CSS — replace the `.card-cover`, `.card-cover img`, and `.cover-placeholder` rules with:

```css
.card-cover {
  aspect-ratio: 5 / 3;
  background: #1a1a2e;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 0.5rem;
}

.card-cover img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.card-cover img.pixelated {
  image-rendering: pixelated;
}

.cover-placeholder {
  font-size: 2rem;
  opacity: 0.4;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run (from `web/frontend/`): `npx vitest run tests/PackGallery.test.js`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/PackGallery.vue web/frontend/tests/PackGallery.test.js
git commit -m "feat: fluid cover stage with crisp pixel-art upscaling"
```

---

### Task 2: Card meta and section headers

**Files:**
- Modify: `web/frontend/src/components/PackGallery.vue`

**Interfaces:**
- Consumes: template structure from Task 1 (`.card-cover` untouched here).
- Produces: `.card-meta` becomes a column (`.card-name` + `.card-count` sublines); each section gains a `.dim-header` row containing `.dim-title`, `.dim-count`, `.dim-rule`. A test asserts `.dim-title` text is exactly `2D`/`3D` — the count MUST stay outside `.dim-title`.

- [ ] **Step 1: Restructure the template**

2 changes in `web/frontend/src/components/PackGallery.vue`:

1a. Replace `<h2 class="dim-title">{{ s.label }}</h2>` with:

```html
      <div class="dim-header">
        <h2 class="dim-title">{{ s.label }}</h2>
        <span class="dim-count">{{ s.packs.length }} {{ s.packs.length === 1 ? 'pack' : 'packs' }}</span>
        <span class="dim-rule" aria-hidden="true"></span>
      </div>
```

1b. Replace the `.card-meta` block with:

```html
          <div class="card-meta">
            <span class="card-name" :title="formatPackName(pack.name)">{{ formatPackName(pack.name) }}</span>
            <span class="card-count">{{ pack.count }} {{ pack.count === 1 ? 'asset' : 'assets' }}</span>
          </div>
```

- [ ] **Step 2: Restyle meta and headers**

In the scoped CSS, replace the `.dim-title` rule with:

```css
.dim-header {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  margin: 1.75rem 0 1rem;
}

.dim-section:first-of-type .dim-header {
  margin-top: 1.25rem;
}

.dim-title {
  margin: 0;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-secondary);
}

.dim-count {
  font-size: 0.75rem;
  color: var(--color-text-muted);
  flex-shrink: 0;
}

.dim-rule {
  flex: 1;
  height: 1px;
  background: var(--color-border);
}
```

and replace the `.card-meta`, `.card-name`, `.card-count` rules with:

```css
.card-meta {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  padding: 0.625rem 0.75rem 0;
}

.card-name {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-text-primary);
  line-height: 1.35;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-count {
  font-size: 0.75rem;
  color: var(--color-text-muted);
}
```

- [ ] **Step 3: Run tests (regression gate)**

Run (from `web/frontend/`): `npx vitest run tests/PackGallery.test.js`
Expected: 10 passed — especially `groups packs into 2D and 3D sections` (exact `.dim-title` text) and the two cards-found-by-text tests.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/components/PackGallery.vue
git commit -m "feat: typographic card meta and eyebrow section headers"
```

---

### Task 3: Quiet tag editor and toolbar-style filter bar

**Files:**
- Modify: `web/frontend/src/components/PackGallery.vue`

**Interfaces:**
- Consumes: template from Tasks 1–2 (no template changes in this task; `.tag-add`, `.tag-remove`, `.tag-chip`, `.tag-input`, `.tag-chips`, `.chip`, `.chip-count` all stay in the DOM unconditionally — tests click them).
- Produces: CSS-only hover/focus reveal for tag controls; restyled sticky filter bar.

- [ ] **Step 1: Restyle the filter bar**

Replace the `.pack-gallery`, `.tag-chips`, `.chip`, `.chip:hover`, `.chip.active`, `.chip-count` rules with (the bar's negative margin must mirror the gallery's horizontal padding):

```css
.pack-gallery {
  flex: 1;
  overflow-y: auto;
  padding: 0 1.25rem 2rem;
}

.tag-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin: 0 -1.25rem;
  padding: 1rem 1.25rem 0.875rem;
  position: sticky;
  top: 0;
  background: var(--color-bg-surface);
  border-bottom: 1px solid var(--color-border);
  z-index: 1;
}

.chip {
  padding: 0.25rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-bg-surface);
  color: var(--color-text-primary);
  font-size: 0.75rem;
  cursor: pointer;
  transition: border-color 120ms, background-color 120ms;
}

.chip:hover {
  border-color: var(--color-accent);
}

.chip.active {
  border-color: var(--color-accent);
  background: var(--color-accent-light);
}

.chip-count {
  color: var(--color-text-muted);
  margin-left: 0.25rem;
}
```

- [ ] **Step 2: Quiet the per-card tag editor**

Replace the `.card-tags`, `.tag-chip`, `.tag-remove`, `.tag-remove:hover`, `.tag-add`, `.tag-add:hover`, `.tag-input` rules with:

```css
.card-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.25rem;
  padding: 0.5rem 0.75rem 0.75rem;
  cursor: default;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.6875rem;
  padding: 0.125rem 0.4375rem;
  border-radius: 999px;
  background: var(--color-bg-elevated);
  color: var(--color-text-secondary);
}

.tag-remove {
  border: none;
  background: none;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 0.75rem;
  padding: 0;
  line-height: 1;
  opacity: 0;
  transition: opacity 120ms;
}

.tag-chip:hover .tag-remove,
.tag-remove:focus-visible {
  opacity: 1;
}

.tag-remove:hover {
  color: var(--color-danger);
}

.tag-add {
  border: 1px dashed var(--color-border);
  background: none;
  color: var(--color-text-secondary);
  border-radius: 999px;
  font-size: 0.6875rem;
  padding: 0.125rem 0.4375rem;
  cursor: pointer;
  line-height: 1.2;
  opacity: 0;
  transition: opacity 120ms;
}

.gallery-card:hover .tag-add,
.tag-add:focus-visible {
  opacity: 1;
}

.tag-add:hover {
  border-color: var(--color-accent);
  color: var(--color-text-primary);
}

.tag-input {
  width: 6rem;
  font-size: 0.6875rem;
  padding: 0.125rem 0.4375rem;
  border: 1px solid var(--color-accent);
  border-radius: 999px;
  background: var(--color-bg-surface);
  color: var(--color-text-primary);
}
```

- [ ] **Step 3: Run tests (regression gate)**

Run (from `web/frontend/`): `npx vitest run tests/PackGallery.test.js`
Expected: 10 passed — tag add/remove tests click the now-hover-revealed controls; they stay in the DOM so jsdom clicks still land.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/components/PackGallery.vue
git commit -m "feat: hover-revealed tag editing and toolbar filter bar"
```

---

### Task 4: Grid geometry, card hover, reduced motion

**Files:**
- Modify: `web/frontend/src/components/PackGallery.vue`

**Interfaces:**
- Consumes: everything above (`.pack-gallery` was finalized in Task 3 — do not change it here).
- Produces: final `.card-grid` and `.gallery-card` rules.

- [ ] **Step 1: Restyle grid and card shell**

Replace the `.card-grid`, `.gallery-card`, `.gallery-card:hover` rules with:

```css
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1.25rem 1rem;
}

.gallery-card {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 150ms, box-shadow 150ms, transform 150ms;
}

.gallery-card:hover {
  border-color: var(--color-accent);
  box-shadow: var(--shadow-card);
  transform: translateY(-1px);
}

@media (prefers-reduced-motion: reduce) {
  .gallery-card {
    transition: none;
  }

  .gallery-card:hover {
    transform: none;
  }
}
```

- [ ] **Step 2: Run the full frontend suite**

Run (from `web/frontend/`): `npm test`
Expected: 8 files, 119 passed (118 pre-existing + 1 from Task 1).

- [ ] **Step 3: Commit**

```bash
git add web/frontend/src/components/PackGallery.vue
git commit -m "feat: airy pack gallery grid with calm card hover"
```

---

### Task 5: Visual verification (coordinator)

Performed by the coordinating session, not a subagent (it owns the browser tab).

- [ ] **Step 1: Serve the worktree frontend**

From `web/frontend/` in the worktree: `npx vite --port 5199` (background). The dev proxy targets the live API on :38471, so real packs render. Do NOT use ports 5173/8000/38472.

- [ ] **Step 2: Inspect both themes**

Open `http://localhost:5199/assets/`, screenshot the gallery; toggle dark/light via the header button; scroll through 2D and 3D sections. Check: ~5 columns, aligned card heights, crisp small sprites, quiet tag rows (controls appear on hover), toolbar-style sticky filter bar, eyebrow section headers.

- [ ] **Step 3: Kill the dev server**

`lsof -ti:5199 | xargs kill`

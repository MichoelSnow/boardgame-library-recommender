# Board Game Library Recommender — UI Redesign Specification

**Status:** Living design specification; partial, not implementation-ready in its entirety  
**Last updated:** 2026-11-19
**Project:** [boardgame-library-recommender](https://github.com/MichoelSnow/boardgame-library-recommender)

## Purpose and scope

Redesign the game-discovery UI for **phones and convention tablets**, with desktop compatibility. The application is a hobby project maintained by one developer; favor familiar React/MUI patterns, simple behavior, and incremental changes over extensive new infrastructure.

The primary purpose is to help convention attendees find games in the available physical library that fit their group—for example, games for four players of medium complexity that are cooperative. The library is physically beside the kiosk. **Ordinary catalog filtering is the core experience**; the preference-based recommender (liking/disliking familiar games to get personalized recommendations) is a useful secondary feature, not the main entry point.

Catalog filters are **hard constraints**, not partial-match suitability scores. Qualifying games can retain the existing BGG ranking/sort behavior. Do not design a new suitability scoring system as part of this UI revamp.

### Goals

- Make game discovery and filtering easy for casual first-time attendees on phones and tablets.
- Keep the results list prominent; avoid the existing dense desktop-style filter row at the top of the screen.
- Expose useful options without overwhelming users with the full BGG taxonomy.
- Make active filters easy to identify and remove with touch.
- Preserve advanced access to the full set of mechanics and categories.
- Preserve the existing personalized recommendation workflow during this browsing/filtering redesign; a separate redesign can address its discoverability later.
- Reuse existing application logic and components where practical; scope work appropriately for a solo developer.

### Current app behavior to preserve or revisit explicitly

- Catalog browsing, text search, sorting, game details, and like/dislike controls already exist.
- The personalized recommendation flow uses liked/disliked game IDs; it is distinct from boolean catalog filtering.
- Filtering from tags in game details should navigate back to the game list, apply the chosen filter, and clear existing search keywords. This is intentionally different from changing filters while already browsing.
- The current app has convention/library-specific behavior; preserve it when revising the UI.
- **Known redesign decision:** Existing catalog filters remain disabled while viewing personalized recommendations. Preserve this behavior; changing it is outside the current scope.

## Overall UI direction — agreed

### Main browsing screen — agreed direction

Use **Option A: compact top toolbar**, a browse-first design rather than a search-first layout or an up-front questionnaire. The main screen contains, in order:

1. **Compact header:** PAX Game Library title, search icon, and existing navigation access. Search expands from the icon into a field and remains open until explicitly closed. Enter, keyboard dismissal, and result updates do not close it; clearing the field removes the query while keeping the field open. Closing the search interface clears the query and collapses the field. Preserve the existing debounced search behavior.
2. **Filter/sort toolbar:** prominent **Filters** button alongside a compact **Sort** control.
3. **Active-filter chips:** up to three visible selections, followed by a **+N more** control if others are active.
4. **Result count:** show the number of matching games directly above the game results.
5. **Game results:** retain the existing cards and like/dislike controls; responsive number of columns can continue to follow existing behavior.

The original personalized recommendation flow and its UI are **out of scope for this phase**. Do not add a recommendation explanation banner, questionnaire, or redesigned recommendations entry point as part of the browsing toolbar work. Preserve existing functionality.

#### Filter button and active chips — agreed

- The Filters button displays the number of active filter selections, such as **Filters (5)**.
- Display **at most three** removable active chips on the results screen. Prioritize practical requirements (such as player count and maximum play time) rather than simply the order in which filters were selected.
- When more than three filters are active, show **+N more**. Tapping it opens the filter drawer, where the full selections are visible in their respective controls.
- The **entire chip** is a usable touch target for removing its filter, with a visible, sufficiently large × icon. No tiny standalone clear target.
- Collapsed drawer section headings display the number of selections inside them so users can locate hidden selections.
- Avoid a second, redundant list of every active chip inside the drawer.
- Exact chip priority ordering and whether the three-chip cap should adjust on very narrow screens can be tuned during implementation review.

#### Sort control — agreed

- Position **Sort** beside **Filters** in the top toolbar.
- Default remains the app's existing **BGG Rank** ordering, with the compact button labeled **Sort**.
- A non-default sort makes its state obvious by displaying its name on the button, e.g., **Rating** or **Name**, rather than just **Sort**.
- Tapping the button opens a small dropdown/popover (not a second drawer), indicating the current selection.
- Selecting an option immediately updates the results and closes the menu.
- **Preserve the actual available sort options and underlying behavior from the current application.** Names in mockups are examples, not an instruction to delete or invent sort modes.

### Decision: Header navigation and responsive layout

Use a consistent, compact header across mobile, tablet, and desktop.

**Header layout**

- Display the application name on the left.
- Display the search icon and hamburger menu on the right.
- Keep the header to a single row when search is collapsed.
- Use touch-friendly controls with sufficiently large tap targets (approximately 44×44px).
- Adapt spacing and sizing responsively, but preserve the same navigation structure across devices.

**Hamburger menu**

- Move secondary navigation into the hamburger menu, using descriptive text labels rather than relying on icons alone.
- Include Help / Tour, Suggestions, and applicable account and administrative actions.
- Preserve existing functionality, permissions, and conditional visibility, including kiosk-specific behavior.
- Use the same hamburger menu on desktop, tablet, and mobile.

**Search**

- Preserve the previously agreed expandable search behavior.
- The search field stays open until explicitly dismissed.
- Clearing the query does not close the field; closing the search interface clears the query.
- Search must not close automatically when results update, Enter is pressed, or the keyboard is dismissed.
- Preserve existing debounced search functionality.

**Filtering and sorting**

- Place the prominent Filters button and Sort control together in a toolbar below the header.
- Use the same left-side filter drawer on all devices, with responsive width (90% on phones, capped at 420px).
- Do not introduce a permanently visible desktop filter sidebar.

**Implementation guidance**

Reuse existing MUI components and responsive styling. Keep the design compact, avoid unnecessary navigation complexity, and preserve all existing actions.

The agent may determine exact spacing, breakpoints, and component structure, provided these requirements are met.

### Filter drawer

- Use a **left-side drawer** at all screen sizes.
- Its width should be approximately 90% on phones and capped at 420px on larger screens.
- The drawer has a **fixed header** containing **Filter Games** and **Clear All**; only the filter sections scroll.
- Use a **single scrollable drawer with accordion sections**, not separate screens for each filter.
- Default expanded state: **Group & Requirements** expanded; **Game Type** and **Theme & Setting** collapsed.
- Filters can use different control types inside an accordion; they do not all need to be checkboxes.
- **No required “Show Games” button.** Changing filters updates a temporary draft while the drawer is open; closing the drawer commits the draft and returns users to the filtered game list. The X, backdrop, Escape, and browser/Android Back close paths all commit the draft. This avoids a separate apply button while preventing a query for every intermediate selection.
- The drawer closes through the header X, backdrop tap, or browser/Android Back. Drawer visibility is temporary UI state and must not be stored in URL parameters.
- Touch targets should be comfortably large. Active chips on the results screen should allow removal by tapping the chip, with a sufficiently large visible × affordance; this addresses repeated feedback that the current × is too small.

## Filter taxonomy — agreed structure

The UI does **not** have to mirror BGG's split between mechanics and categories. Use user-facing groups and plain-language labels, mapping them to the underlying BGG fields. Avoid duplicate independent entries for the same logical filter.

### A. Group & Requirements — expanded by default

| Filter | Agreed UI / behavior | Data / mapping | Notes |
|---|---|---|---|
| **Players** | Single player count using a stepper: **Any, 1–8, 9+**. Also choose **Allowed** (default), **Recommended**, or **Best**. | Existing player-count filtering modes | Only one player count at a time. **9+** Allowed includes games supporting at least one player count of nine or more. Recommended and Best include games identified at that level at any player count of nine or more; compatibility with existing data must be verified. |
| **Maximum Play Time** | Single-select buttons: **Any, 15, 30, 45, 60, 90, 120, 180, 240 minutes**. Default Any. | `games.max_playtime <= selected limit` | Exclude unknown/zero durations when active. Exact choices are provisional. |
| **Minimum Age** | Single-select buttons: **Any, 5+, 6+, 8+, 10+, 12+, 14+**. Default Any. | `games.min_age <= selected age` | Cumulative thresholds based on the youngest player, not exclusive age ranges. Exclude unknown/zero ages when active. |
| **Complexity** | Multiselect **Light / Medium / Heavy**; default none. | `average_weight`: Light `< 2`, Medium `2–4` inclusive, Heavy `> 4` | Rename existing “Weight” label to **Complexity**. |
| **Game Style** | **Single-select:** Any (default) / Family Games / Children's Games / Party Games. | Mappings below | Mutually exclusive UI choices for now, although the underlying sets of games may overlap. |
| **Cooperative** | Independent checkbox; may combine with any other filter. | BGG mechanic `Cooperative Game` | Do not label games lacking the mechanic “Competitive.” |

All controls should be touch-friendly and remain visible within this section when expanded. The section is intentionally larger than the others; its layout can be revisited if usability testing reveals excessive scrolling.

#### Game Style definitions — agreed

| Choice | Filter logic | Rationale |
|---|---|---|
| **Any** | No style constraint | Default. |
| **Family Games** | `games.family_games_rank IS NOT NULL` | Family-oriented games that adults and children may enjoy together; not a guarantee of suitability for a particular child's age. |
| **Children's Games** | Membership in `categories` where `boardgamecategory_name = 'Children''s Game'` | Games classified as specifically for children. Use category rather than `childrens_games_rank`, which misses many plausible titles. |
| **Party Games** | `games.party_games_rank IS NOT NULL` **OR** membership in category `Party Game` | Includes credible titles captured by either BGG source. |

Combine the chosen Game Style with Cooperative and other independent filters using **AND**. Game Style is single-select specifically to avoid ambiguity about combining Family/Children's/Party as independent checkboxes.

#### Supporting data / conclusions

The analyzed convention snapshot was older and smaller than a future library. It contained **1,410 games** and was used to inform design, not as a permanent threshold:

- Family-ranked: **405**.
- Children's category: **50** in the overlap query; children's-ranked: **10**; **9** both, **41** category only, **1** rank only.
- Party category: **168**; party-ranked: **85**; **60** both, **108** category only, **25** rank only; **193** in the union.
- Library playtime distribution is concentrated at ≤60 minutes, with relatively few unknown max durations; using `max_playtime` avoids manufacturing an “average” field.

These classifications are imperfect; the goal is useful filtering that broadly matches attendees' expectations, not building a new model or manually labeling the catalog.

### B. Game Type — collapsed by default

Show the following **10 featured choices** before the expanded full list:

1. Deduction
2. Bluffing
3. Deck Building
4. Push Your Luck
5. Trick-taking
6. Word Games
7. Trivia
8. Dexterity
9. Worker Placement
10. Racing

**Show All Game Types** expands the **same accordion inline**, revealing additional options and a search box. **Set Collection** stays in the full list, not the featured ten. Include technical/non-featured BGG mechanics (such as Hexagon Grid) in the complete searchable list, even when they are poor featured discovery options. Collapse again without losing selections.

**Underlying mappings identified in discussion:**

| Label | BGG mapping / caveat |
|---|---|
| Deduction | BGG category **or** mechanic `Deduction` (one logical UI choice). |
| Bluffing | Category `Bluffing` or mechanic `Betting and Bluffing` (one logical UI choice). |
| Deck Building | Mechanic `Deck, Bag, and Pool Building`; covers bags/pools too, **not** `Deck Construction`. |
| Push Your Luck | Mechanic `Push Your Luck`. |
| Trick-taking | Mechanic `Trick-taking`. |
| Word Games | Category `Word Game`. |
| Trivia | Category `Trivia`. |
| Dexterity | Category `Action / Dexterity`. |
| Worker Placement | Mechanic `Worker Placement`. |
| Racing | Category `Racing` **only**; do **not** add the BGG `Race` mechanic, which includes any race to a fixed objective (such as reaching 10 points in Catan). |

**Approved taxonomy details:** The complete category/mechanic crosswalk, approved merges, stable option IDs, full-list labels, and source IDs are recorded in the [Filter Taxonomy Contract](../core/filter-taxonomy-contract.md). Multiple selections within Game Type use OR semantics; independent filter groups use AND semantics. Merged options expand their underlying category/mechanic sources with OR semantics, never AND. Set Collection remains in the full list; technical classifications remain searchable; Party, Children's, Cooperative, and Solo / Solitaire are not duplicated because they are represented by independent controls. Race remains a distinct full-list option and is not merged with Racing.

### C. Theme & Setting — collapsed by default

Show the following **10 featured themes**:

1. Fantasy
2. Science Fiction
3. Animals
4. Medieval
5. World War II
6. Movies & TV
7. Mystery
8. Mythology
9. Zombies
10. Horror

- Keep **Medieval and World War II separate**; do not combine into a broad Historical option.
- Keep **Zombies and Horror separate**.
- Use a **Show All Themes** control to reveal a searchable complete list inline, with selections retained when collapsed.
- BGG category labels may be simplified where the meaning is preserved (e.g., `Murder / Mystery` → Mystery, `Movies / TV / Radio theme` → Movies & TV).
- Reassign categories that are really *game types* rather than settings (e.g., Abstract Strategy, Wargame) to the appropriate user-facing set rather than blindly listing them under Theme.
- The complete crosswalk from every BGG category/mechanic to Game Type or Theme, including source IDs and approved combination semantics, is recorded in the [Filter Taxonomy Contract](../core/filter-taxonomy-contract.md).

### Labels and explanations

- Use **short, recognizable labels** rather than showing every full technical BGG classification name in the featured view.
- For terminology a casual user may not recognize (e.g., Deck Building, Worker Placement, Push Your Luck), offer a **short plain-language explanation**, potentially via an information icon/popover.
- Do **not** automatically add an information icon beside every entry; obvious terms such as Trivia or Racing generally need no explanation.
- The BGG category/mechanic definitions should be checked when drafting these explanations and when unifying labels. Do not assume similarly named concepts have equivalent definitions.

## Behavior and usability requirements

### Applying and clearing filters

- Filter selections remain in a temporary drawer draft; closing the drawer commits the complete selection and updates the underlying results, **without a separate apply button**.
- The drawer **Clear All** clears only filter constraints. It preserves text search, sorting, library scope, liked/disliked games, and recommendation state.
- On the main results screen, show active selections as accessible, touch-friendly chips. Tapping an active chip removes that filter; show a prominent × on the chip.
- Preserve selection state when accordion sections collapse or the drawer is reopened.
- In a compound control such as Players, the active chip text should accurately describe the number and mode (e.g., `4 players · Best`).
- The main screen shows at most three chips and a **+N more** drawer shortcut; see the agreed main browsing screen section above.

### From game details versus from the list

User feedback established a deliberate distinction:

- Selecting a category/mechanic tag **from game details**: navigate back to the game list, filter by the selected tag, and clear prior text-search keywords.
- Selecting the equivalent option **while browsing the game list**: retain the current browsing/filter context rather than forcibly resetting it.

Selecting a category or mechanic tag immediately returns to the game list, adds the selected filter without duplicating existing selections, preserves all other active filters, clears text search, and applies the updated filters automatically.

### Recommendations

Keep the existing like/dislike → personalized recommendation controls and workflow intact during the present browsing/filtering redesign. Improving the recommendation workflow may be considered separately later; it is **not part of the currently agreed main-screen changes**.

### Expansions

Do not exclude expansions by default, add an expansion filter, or otherwise change existing expansion behavior. Convention expansions are generally physically bundled with their base games.

## Maintenance and decisions still open

1. Future changes to the approved BGG crosswalk, duplicate handling, or full-list labels require an explicit update to the [Filter Taxonomy Contract](../core/filter-taxonomy-contract.md) and corresponding implementation review.
2. Final tooltip/help text for technical game types and overall accessibility review.

These remaining decisions do not block the approved taxonomy implementation. Existing recommendation-mode filtering behavior is preserved and is not an open decision for this redesign.

## Working process

This is a **living design specification**: record agreed UX decisions and unresolved behavior. It is **not** an implementation roadmap or a request to build everything at once.

Recommended workflow:

1. Review or prototype a small area of the interface.
2. Update this specification when a design decision is made or changed.
3. Give the repository coding agent a **small, separately scoped implementation task** that cites the relevant sections here.
4. Review the result on a narrow phone viewport and convention-size tablet viewport before moving to the next task.

**Immediate next activity:** Perform the planned narrow-device keyboard, touch-target, drawer-scrolling, accordion, and chip-removal smoke review. Record any accessibility or tooltip decisions before the redesign is considered fully complete.

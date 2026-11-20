# Filter Taxonomy Contract

**Status:** Approved and implementation reference

This is the canonical contract for the application's user-facing BGG
taxonomy. Changes to stable option IDs, source mappings, grouping, labels,
featured status, or selection semantics require an explicit contract update
and corresponding implementation review.

**Scope:** The unified Game Type and Theme & Setting filter taxonomy for the UI redesign.

**Sources reviewed:**

- [Archived UI redesign specification](../archive/ui-redesign/ui-redesign.md), especially the taxonomy sections and presentation decisions.
- The local catalog snapshot at `backend/database/boardgames.db`.
- `backend/app/models.py`, which stores BGG source IDs in `boardgamemechanic_id` and `boardgamecategory_id`.
- The current option endpoints in `backend/app/main.py` and `backend/app/crud.py`.
- BGG's [category reference](https://boardgamegeek.com/wiki/page/Category) and [mechanics reference](https://boardgamegeek.com/wiki/page/mechanics) for meaning checks.

This document records the approved crosswalk and option contract. It is the current implementation reference for the UI redesign taxonomy; the archived specification provides the historical UX context.

## Review boundary

The local snapshot contains 192 distinct mechanics and 85 distinct categories. The inventory below is a snapshot, not a permanent assertion that BGG will never add or rename a source classification.

The stable source identifiers are the BGG IDs in `boardgamemechanic_id` and `boardgamecategory_id`. The database row `id` on `mechanics` and `categories` is an internal relationship-row ID and must not be used as the filter contract.

The proposal uses these rules:

- A logical option has one stable application ID, such as `game-type:deduction` or `theme:fantasy`.
- A logical option may contain one or more category and/or mechanic source IDs.
- Multiple selected options in one taxonomy group use OR semantics. Game Type and Theme are independent groups and combine with AND semantics.
- Sources already represented by the independent Game Style or Cooperative controls are not duplicated in the taxonomy lists.
- Technical mechanics remain available in the full Game Type list unless they are explicitly reserved or excluded by an approved independent control.
- Every source classification is assigned to one stable option, except Party, Children's, and Cooperative sources represented by existing independent controls and Solo / Solitaire Game represented by the player-count filter.

## Final option contract

The server-provided `GET /api/filter-taxonomy/` response provides records with this shape.

| Field | Meaning |
|---|---|
| `option_id` | Stable application ID, independent of database row IDs. |
| `label` | Short user-facing label. |
| `group` | `game_type` or `theme`. Reserved style/behavior controls are not taxonomy options. |
| `featured` | Whether the option appears in the initial ten-item view. |
| `sources` | One or more `{type, id, name}` records, where `type` is `category` or `mechanic`. |
| `explanation` | Optional short plain-language help text for technical terms. |

The frontend should search `label` and source names but submit `option_id` values. It should not need to know whether an option maps to a category, a mechanic, or both.

## Featured Game Type options

These preserve the ten choices already approved in the design specification.

| Option ID | Display label | Group | Featured | Underlying BGG sources | Explanation |
|---|---|---|---|---|---|
| `game-type:deduction` | Deduction | Game Type | yes | Category `1039` Deduction; mechanic `3002` Deduction | Use one logical option for the category and mechanic. |
| `game-type:bluffing` | Bluffing | Game Type | yes | Category `1023` Bluffing; mechanic `2014` Betting and Bluffing | The mechanic's technical label should not appear as a second option. |
| `game-type:deck-building` | Deck Building | Game Type | yes | Mechanic `2664` Deck, Bag, and Pool Building | Deliberately excludes mechanic `3004` Deck Construction. |
| `game-type:push-your-luck` | Push Your Luck | Game Type | yes | Mechanic `2661` Push Your Luck | Exact source match. |
| `game-type:trick-taking` | Trick-taking | Game Type | yes | Mechanic `2009` Trick-taking | Exact source match. |
| `game-type:word-games` | Word Games | Game Type | yes | Category `1025` Word Game; mechanic `3113` Spelling | Approved logical merge. |
| `game-type:trivia` | Trivia | Game Type | yes | Category `1027` Trivia | Keep separate from the broader Questions and Answers mechanic. |
| `game-type:dexterity` | Dexterity | Game Type | yes | Category `1032` Action / Dexterity; mechanic `2860` Flicking | Approved logical merge. |
| `game-type:worker-placement` | Worker Placement | Game Type | yes | Mechanic `2082` Worker Placement; `2933` Worker Placement, Different Worker Types; `2935` Worker Placement with Dice Workers | Approved logical merge for the Worker Placement family. |
| `game-type:racing` | Racing | Game Type | yes | Category `1031` Racing only | Featured category option; mechanic `2876` is preserved separately as `game-type:race-mechanic`. |

## Featured Theme & Setting options

These preserve the ten choices already approved in the design specification.

| Option ID | Display label | Group | Featured | Underlying BGG sources | Explanation |
|---|---|---|---|---|---|
| `theme:fantasy` | Fantasy | Theme | yes | Category `1010` Fantasy | Exact source match. |
| `theme:science-fiction` | Science Fiction | Theme | yes | Category `1016` Science Fiction | Exact source match. |
| `theme:animals` | Animals | Theme | yes | Category `1089` Animals | Exact source match. |
| `theme:medieval` | Medieval | Theme | yes | Category `1035` Medieval | Must remain separate from World War II. |
| `theme:world-war-ii` | World War II | Theme | yes | Category `1049` World War II | Must remain separate from Medieval. |
| `theme:movies-tv` | Movies & TV | Theme | yes | Category `1064` Movies / TV / Radio theme | Concise label; radio is retained in the source mapping. |
| `theme:mystery` | Mystery | Theme | yes | Category `1040` Murder / Mystery | Simplified label with preserved meaning. |
| `theme:mythology` | Mythology | Theme | yes | Category `1082` Mythology | Exact source match. |
| `theme:zombies` | Zombies | Theme | yes | Category `2481` Zombies | Must remain separate from Horror. |
| `theme:horror` | Horror | Theme | yes | Category `1024` Horror | Must remain separate from Zombies. |

## Additional approved logical options

These are full-list options or source merges approved to avoid duplicate selectable entries. They are not part of the initial featured ten unless marked otherwise above.

| Option ID | Display label | Group | Featured | Underlying sources | Status / rationale |
|---|---|---|---|---|---|
| `game-type:card-games` | Card Games | Game Type | no | Category `1002` Card Game | Format-oriented but useful for browsing. |
| `game-type:abstract-strategy` | Abstract Strategy | Game Type | no | Category `1009` Abstract Strategy | Game type, not a setting. |
| `game-type:civilization` | Civilization | Game Type | no | Category `1015` Civilization | Strategy/genre label. |
| `game-type:dice-games` | Dice Games | Game Type | no | Category `1017` Dice; mechanic `2072` Dice Rolling | Approved logical merge. |
| `game-type:wargames` | Wargames | Game Type | no | Category `1019` Wargame | Game type; do not place under Theme. |
| `game-type:exploration` | Exploration | Game Type | no | Category `1020` Exploration | Activity/game type. |
| `game-type:economic` | Economic | Game Type | no | Category `1021` Economic | Keep as a technical full-list option. |
| `game-type:adventure` | Adventure | Game Type | no | Category `1022` Adventure | Genre/game type; not a specific setting. |
| `game-type:negotiation` | Negotiation | Game Type | no | Category `1026` Negotiation; mechanic `2915` Negotiation | Exact cross-source merge. |
| `game-type:puzzle` | Puzzle | Game Type | no | Category `1028` Puzzle | Activity/game type. |
| `game-type:city-building` | City Building | Game Type | no | Category `1029` City Building | Game type. |
| `game-type:real-time` | Real-time | Game Type | no | Category `1037` Real-time; mechanic `2831` Real-Time | Exact conceptual merge despite capitalization difference. |
| `game-type:memory` | Memory | Game Type | no | Category `1045` Memory; mechanic `2047` Memory | Exact cross-source merge. |
| `game-type:collectible-components` | Collectible Components | Game Type | no | Category `1044` Collectible Components | Format/component option. |
| `game-type:fighting` | Fighting | Game Type | no | Category `1046` Fighting | Game type. |
| `game-type:miniatures` | Miniatures | Game Type | no | Category `1047` Miniatures | Component/game type. |
| `game-type:maze` | Maze | Game Type | no | Category `1059` Maze | Spatial game type. |
| `game-type:electronic` | Electronic Games | Game Type | no | Category `1072` Electronic | Preserve as a complete-taxonomy option. |
| `game-type:territory-building` | Territory Building | Game Type | no | Category `1086` Territory Building | Game type. |
| `game-type:educational` | Educational | Game Type | no | Category `1094` Educational | Game type/purpose. |
| `game-type:number` | Number Games | Game Type | no | Category `1098` Number | Concise label. |
| `game-type:math` | Math Games | Game Type | no | Category `1104` Math | Concise label. |
| `game-type:print-and-play` | Print & Play | Game Type | no | Category `1120` Print & Play | Preserve as a complete-taxonomy format option. |
| `game-type:drafting` | Drafting | Game Type | no | Mechanics `2041` Open Drafting; `2984` Closed Drafting | Approved family merge. |
| `game-type:auction-bidding` | Auction & Bidding | Game Type | no | Mechanics `2012`, `2827`, `2918`–`2932` | Approved core auction-family merge. |
| `game-type:campaign-battle-card-driven` | Campaign / Battle Card Driven | Game Type | no | Mechanic `2018` Campaign / Battle Card Driven | Approved separate option. |
| `game-type:scenario-mission-campaign` | Scenario / Mission / Campaign | Game Type | no | Mechanic `2822` Scenario / Mission / Campaign Game | Approved separate option. |

## Complete category inventory and final assignment

The table is the source-level crosswalk. A source that shares an option ID with another row is intentionally combined and must not appear as a duplicate selectable option.

| Category ID | BGG category | Option ID / handling | Group | Featured | Status / note |
|---:|---|---|---|:---:|---|
| 1001 | Political | `theme:political` | Theme | no | Approved setting. |
| 1002 | Card Game | `game-type:card-games` | Game Type | no | Format/game type. |
| 1008 | Nautical | `theme:nautical` | Theme | no | Setting. |
| 1009 | Abstract Strategy | `game-type:abstract-strategy` | Game Type | no | Game type. |
| 1010 | Fantasy | `theme:fantasy` | Theme | yes | Featured. |
| 1011 | Transportation | `theme:transportation` | Theme | no | Theme/subject; BGG notes that this category can also describe activity. Review scope. |
| 1013 | Farming | `theme:farming` | Theme | no | Setting/subject. |
| 1015 | Civilization | `game-type:civilization` | Game Type | no | Game type. |
| 1016 | Science Fiction | `theme:science-fiction` | Theme | yes | Featured. |
| 1017 | Dice | `game-type:dice-games` | Game Type | no | Approved merge with Dice Rolling mechanic. |
| 1019 | Wargame | `game-type:wargames` | Game Type | no | Game type, not Theme. |
| 1020 | Exploration | `game-type:exploration` | Game Type | no | Activity/game type. |
| 1021 | Economic | `game-type:economic` | Game Type | no | Game type. |
| 1022 | Adventure | `game-type:adventure` | Game Type | no | Genre/game type. |
| 1023 | Bluffing | `game-type:bluffing` | Game Type | yes | Combined with Betting and Bluffing. |
| 1024 | Horror | `theme:horror` | Theme | yes | Featured; separate from Zombies. |
| 1025 | Word Game | `game-type:word-games` | Game Type | yes | Featured; label pluralized. |
| 1026 | Negotiation | `game-type:negotiation` | Game Type | no | Combined with Negotiation mechanic. |
| 1027 | Trivia | `game-type:trivia` | Game Type | yes | Featured. |
| 1028 | Puzzle | `game-type:puzzle` | Game Type | no | Game type. |
| 1029 | City Building | `game-type:city-building` | Game Type | no | Game type. |
| 1030 | Party Game | `style:party` | Reserved style control | no | Do not duplicate the approved Party Games style filter. |
| 1031 | Racing | `game-type:racing` | Game Type | yes | Featured; category only. |
| 1032 | Action / Dexterity | `game-type:dexterity` | Game Type | yes | Featured; approved merge with Flicking. |
| 1033 | Mafia | `game-type:mafia` | Game Type | no | Preserve as a distinct social game type; do not merge with Deduction. |
| 1034 | Trains | `theme:trains` | Theme | no | Subject/setting. |
| 1035 | Medieval | `theme:medieval` | Theme | yes | Featured; separate from World War II. |
| 1036 | Prehistoric | `theme:prehistoric` | Theme | no | Setting. |
| 1037 | Real-time | `game-type:real-time` | Game Type | no | Combined with Real-Time mechanic. |
| 1038 | Sports | `theme:sports` | Theme | no | Subject/setting. |
| 1039 | Deduction | `game-type:deduction` | Game Type | yes | Combined with Deduction mechanic. |
| 1040 | Murder / Mystery | `theme:mystery` | Theme | yes | Simplified to Mystery. |
| 1041 | Children's Game | `style:children` | Reserved style control | no | Do not duplicate the approved Children's Games style filter. |
| 1042 | Expansion for Base-game | `game-type:category-1042` / Expansion for Base-game | Game Type | no | Full technical category; do not exclude from the complete taxonomy. |
| 1044 | Collectible Components | `game-type:collectible-components` | Game Type | no | Component/game type. |
| 1045 | Memory | `game-type:memory` | Game Type | no | Combined with Memory mechanic. |
| 1046 | Fighting | `game-type:fighting` | Game Type | no | Game type. |
| 1047 | Miniatures | `game-type:miniatures` | Game Type | no | Component/game type. |
| 1048 | American Civil War | `theme:american-civil-war` | Theme | no | Historical setting. |
| 1049 | World War II | `theme:world-war-ii` | Theme | yes | Featured; separate from Medieval. |
| 1050 | Ancient | `theme:ancient` | Theme | no | Historical setting. |
| 1051 | Napoleonic | `theme:napoleonic` | Theme | no | Historical setting. |
| 1052 | Arabian | `theme:arabian` | Theme | no | Setting. |
| 1054 | Music | `theme:music` | Theme | no | Subject. |
| 1055 | American West | `theme:american-west` | Theme | no | Historical setting. |
| 1059 | Maze | `game-type:maze` | Game Type | no | Spatial game type. |
| 1064 | Movies / TV / Radio theme | `theme:movies-tv` | Theme | yes | Simplified to Movies & TV. |
| 1065 | World War I | `theme:world-war-i` | Theme | no | Historical setting. |
| 1069 | Modern Warfare | `theme:modern-warfare` | Theme | no | Preserve as a setting; separate from Wargames. |
| 1070 | Renaissance | `theme:renaissance` | Theme | no | Historical setting. |
| 1072 | Electronic | `game-type:electronic` | Game Type | no | Full format classification. |
| 1075 | American Revolutionary War | `theme:american-revolutionary-war` | Theme | no | Historical setting. |
| 1079 | Humor | `theme:humor` | Theme | no | Subject/tone. |
| 1081 | Spies / Secret Agents | `theme:spies-secret-agents` | Theme | no | Setting/subject. |
| 1082 | Mythology | `theme:mythology` | Theme | yes | Featured. |
| 1084 | Environmental | `theme:environmental` | Theme | no | Subject. |
| 1086 | Territory Building | `game-type:territory-building` | Game Type | no | Game type. |
| 1088 | Industry / Manufacturing | `theme:industry-manufacturing` | Theme | no | Approved Theme & Setting assignment. |
| 1089 | Animals | `theme:animals` | Theme | yes | Featured. |
| 1090 | Pirates | `theme:pirates` | Theme | no | Setting. |
| 1091 | Korean War | `theme:korean-war` | Theme | no | Historical setting. |
| 1093 | Novel-based | `theme:novel-based` | Theme | no | Source-material theme. |
| 1094 | Educational | `game-type:educational` | Game Type | no | Purpose/game type. |
| 1097 | Travel | `theme:travel` | Theme | no | Subject/setting. |
| 1098 | Number | `game-type:number` | Game Type | no | Concise label: Number Games. |
| 1101 | Video Game Theme | `theme:video-game` | Theme | no | Simplified label. |
| 1102 | Civil War | `theme:civil-war` | Theme | no | Historical setting; distinguish from American Civil War. |
| 1104 | Math | `game-type:math` | Game Type | no | Concise label: Math Games. |
| 1108 | American Indian Wars | `theme:american-indian-wars` | Theme | no | Historical setting; wording needs sensitivity review. |
| 1109 | Vietnam War | `theme:vietnam-war` | Theme | no | Historical setting. |
| 1113 | Space Exploration | `theme:space-exploration` | Theme | no | Setting/subject. |
| 1115 | Religious | `theme:religious` | Theme | no | Subject; review wording and discoverability. |
| 1116 | Comic Book / Strip | `theme:comic-book` | Theme | no | Simplified label. |
| 1117 | Book | `theme:book` | Theme | no | Source-material theme. |
| 1118 | Mature / Adult | `theme:mature-adult` | Theme | no | Preserve as a searchable content descriptor; wording remains a content-review concern. |
| 1119 | Game System | `game-type:category-1119` / Game System | Game Type | no | Full technical category; do not exclude from the complete taxonomy. |
| 1120 | Print & Play | `game-type:print-and-play` | Game Type | no | Full format option. |
| 2145 | Medical | `theme:medical` | Theme | no | Subject/setting. |
| 2481 | Zombies | `theme:zombies` | Theme | yes | Featured; separate from Horror. |
| 2650 | Aviation / Flight | `theme:aviation-flight` | Theme | no | Setting/subject. |
| 2687 | Fan Expansion | `game-type:category-2687` / Fan Expansion | Game Type | no | Full technical category; do not exclude from the complete taxonomy. |
| 2710 | Post-Napoleonic | `theme:post-napoleonic` | Theme | no | Historical setting. |
| 2725 | Pike and Shot | `theme:pike-and-shot` | Theme | no | Historical setting. |
| 2726 | Age of Reason | `theme:age-of-reason` | Theme | no | Historical setting. |
| 3129 | Third-party Expansion | `game-type:category-3129` / Third-party Expansion | Game Type | no | Full technical category; do not exclude from the complete taxonomy. |

## Complete mechanic inventory and final assignment

Mechanics use the Game Type full list because they describe play activity or structure rather than subject matter. The exceptions are reserved controls and the approved Solo exclusion.

| Mechanic ID | BGG mechanic | Option ID / label | Group | Featured | Status / note |
|---:|---|---|---|:---:|---|
| 2001 | Action Points | `game-type:mechanic-2001` / Action Points | Game Type | no | Full technical option. |
| 2002 | Tile Placement | `game-type:mechanic-2002` / Tile Placement | Game Type | no | Full technical option. |
| 2003 | Rock-Paper-Scissors | `game-type:mechanic-2003` / Rock-Paper-Scissors | Game Type | no | Full technical option. |
| 2004 | Set Collection | `game-type:mechanic-2004` / Set Collection | Game Type | no | Required full-list option; not featured. |
| 2005 | Stock Holding | `game-type:mechanic-2005` / Stock Holding | Game Type | no | Full technical option. |
| 2007 | Pick-up and Deliver | `game-type:mechanic-2007` / Pick-up and Deliver | Game Type | no | Full technical option. |
| 2008 | Trading | `game-type:mechanic-2008` / Trading | Game Type | no | Full technical option. |
| 2009 | Trick-taking | `game-type:trick-taking` / Trick-taking | Game Type | yes | Consumed by featured option. |
| 2010 | Crayon Rail System | `game-type:mechanic-2010` / Crayon Rail System | Game Type | no | Technical option; explanation may be needed. |
| 2011 | Modular Board | `game-type:mechanic-2011` / Modular Board | Game Type | no | Full technical option. |
| 2012 | Auction / Bidding | `game-type:auction-bidding` / Auction & Bidding | Game Type | no | Approved core auction-family merge. |
| 2013 | Commodity Speculation | `game-type:mechanic-2013` / Commodity Speculation | Game Type | no | Full technical option. |
| 2014 | Betting and Bluffing | `game-type:bluffing` / Bluffing | Game Type | yes | Combined with Bluffing category. |
| 2015 | Variable Player Powers | `game-type:mechanic-2015` / Variable Player Powers | Game Type | no | Full technical option. |
| 2016 | Secret Unit Deployment | `game-type:mechanic-2016` / Secret Unit Deployment | Game Type | no | Full technical option. |
| 2017 | Voting | `game-type:mechanic-2017` / Voting | Game Type | no | Full technical option. |
| 2018 | Campaign / Battle Card Driven | `game-type:campaign-battle-card-driven` / Campaign / Battle Card Driven | Game Type | no | Separate approved option. |
| 2019 | Team-Based Game | `game-type:mechanic-2019` / Team-Based Games | Game Type | no | Concise label. |
| 2020 | Simultaneous Action Selection | `game-type:mechanic-2020` / Simultaneous Action Selection | Game Type | no | Technical option. |
| 2021 | Area-Impulse | `game-type:mechanic-2021` / Area-Impulse | Game Type | no | Technical option. |
| 2023 | Cooperative Game | reserved `cooperative=true` | Reserved behavior | no | Existing independent Cooperative control; no duplicate taxonomy option. |
| 2026 | Hexagon Grid | `game-type:mechanic-2026` / Hexagon Grid | Game Type | no | Must remain searchable in the full list. |
| 2027 | Storytelling | `game-type:mechanic-2027` / Storytelling | Game Type | no | Full option. |
| 2028 | Role Playing | `game-type:mechanic-2028` / Role Playing | Game Type | no | Full option. |
| 2035 | Roll / Spin and Move | `game-type:mechanic-2035` / Roll, Spin & Move | Game Type | no | Concise label. |
| 2038 | Singing | `game-type:mechanic-2038` / Singing | Game Type | no | Full option. |
| 2039 | Line Drawing | `game-type:mechanic-2039` / Line Drawing | Game Type | no | Full option. |
| 2040 | Hand Management | `game-type:mechanic-2040` / Hand Management | Game Type | no | Full option. |
| 2041 | Open Drafting | `game-type:drafting` / Drafting | Game Type | no | Approved merge with Closed Drafting. |
| 2043 | Enclosure | `game-type:mechanic-2043` / Enclosure | Game Type | no | Technical option. |
| 2046 | Area Movement | `game-type:mechanic-2046` / Area Movement | Game Type | no | Full option. |
| 2047 | Memory | `game-type:memory` / Memory | Game Type | no | Combined with Memory category. |
| 2048 | Pattern Building | `game-type:mechanic-2048` / Pattern Building | Game Type | no | Full option. |
| 2055 | Paper-and-Pencil | `game-type:mechanic-2055` / Paper-and-Pencil | Game Type | no | Full option. |
| 2057 | Chit-Pull System | `game-type:mechanic-2057` / Chit-Pull System | Game Type | no | Technical option. |
| 2060 | Pattern Recognition | `game-type:mechanic-2060` / Pattern Recognition | Game Type | no | Full option. |
| 2070 | Simulation | `game-type:mechanic-2070` / Simulation | Game Type | no | Full option. |
| 2072 | Dice Rolling | `game-type:dice-games` / Dice Games | Game Type | no | Approved merge with Dice category. |
| 2073 | Acting | `game-type:mechanic-2073` / Acting | Game Type | no | Full option. |
| 2078 | Point to Point Movement | `game-type:mechanic-2078` / Point-to-Point Movement | Game Type | no | Concise label. |
| 2079 | Variable Phase Order | `game-type:mechanic-2079` / Variable Phase Order | Game Type | no | Full option. |
| 2080 | Area Majority / Influence | `game-type:mechanic-2080` / Area Majority & Influence | Game Type | no | Concise label. |
| 2081 | Network and Route Building | `game-type:mechanic-2081` / Network & Route Building | Game Type | no | Concise label. |
| 2082 | Worker Placement | `game-type:worker-placement` / Worker Placement | Game Type | yes | Featured family option. |
| 2661 | Push Your Luck | `game-type:push-your-luck` / Push Your Luck | Game Type | yes | Featured. |
| 2663 | Turn Order: Time Track | `game-type:mechanic-2663` / Turn Order: Time Track | Game Type | no | Technical option. |
| 2664 | Deck, Bag, and Pool Building | `game-type:deck-building` / Deck Building | Game Type | yes | Required mapping; excludes Deck Construction. |
| 2676 | Grid Movement | `game-type:mechanic-2676` / Grid Movement | Game Type | no | Full option. |
| 2685 | Player Elimination | `game-type:mechanic-2685` / Player Elimination | Game Type | no | Full option. |
| 2686 | Take That | `game-type:mechanic-2686` / Take That | Game Type | no | Full option. |
| 2689 | Action Queue | `game-type:mechanic-2689` / Action Queue | Game Type | no | Full option. |
| 2813 | Rondel | `game-type:mechanic-2813` / Rondel | Game Type | no | Technical option. |
| 2814 | Traitor Game | `game-type:mechanic-2814` / Traitor Game | Game Type | no | Full option. |
| 2819 | Solo / Solitaire Game | excluded | Excluded | no | Solo play is represented by the player-count filter. |
| 2820 | Semi-Cooperative Game | `game-type:mechanic-2820` / Semi-Cooperative Games | Game Type | no | Keep distinct from Cooperative control; review. |
| 2821 | Single Loser Game | `game-type:mechanic-2821` / Single Loser Game | Game Type | no | Technical option; review discoverability. |
| 2822 | Scenario / Mission / Campaign Game | `game-type:scenario-mission-campaign` / Scenario / Mission / Campaign | Game Type | no | Separate approved option. |
| 2823 | Score-and-Reset Game | `game-type:mechanic-2823` / Score-and-Reset Game | Game Type | no | Technical option. |
| 2824 | Legacy Game | `game-type:mechanic-2824` / Legacy Game | Game Type | no | Full option. |
| 2826 | Turn Order: Stat-Based | `game-type:mechanic-2826` / Turn Order: Stat-Based | Game Type | no | Technical option. |
| 2827 | Turn Order: Auction | `game-type:auction-bidding` / Auction & Bidding | Game Type | no | Approved core auction-family merge. |
| 2828 | Turn Order: Progressive | `game-type:mechanic-2828` / Turn Order: Progressive | Game Type | no | Full option. |
| 2829 | Turn Order: Claim Action | `game-type:mechanic-2829` / Turn Order: Claim Action | Game Type | no | Full option. |
| 2830 | Turn Order: Pass Order | `game-type:mechanic-2830` / Turn Order: Pass Order | Game Type | no | Full option. |
| 2831 | Real-Time | `game-type:real-time` / Real-time | Game Type | no | Combined with Real-time category. |
| 2833 | Turn Order: Role Order | `game-type:mechanic-2833` / Turn Order: Role Order | Game Type | no | Full option. |
| 2834 | Action Timer | `game-type:mechanic-2834` / Action Timer | Game Type | no | Full option. |
| 2835 | Passed Action Token | `game-type:mechanic-2835` / Passed Action Token | Game Type | no | Technical option. |
| 2836 | Lose a Turn | `game-type:mechanic-2836` / Lose a Turn | Game Type | no | Full option. |
| 2837 | Interrupts | `game-type:mechanic-2837` / Interrupts | Game Type | no | Full option. |
| 2838 | Action Drafting | `game-type:mechanic-2838` / Action Drafting | Game Type | no | Keep distinct from card drafting; review. |
| 2839 | Action Retrieval | `game-type:mechanic-2839` / Action Retrieval | Game Type | no | Full option. |
| 2840 | Action / Event | `game-type:mechanic-2840` / Action & Event | Game Type | no | Concise label. |
| 2841 | Command Cards | `game-type:mechanic-2841` / Command Cards | Game Type | no | Full option. |
| 2843 | Follow | `game-type:mechanic-2843` / Follow | Game Type | no | Technical option. |
| 2844 | Order Counters | `game-type:mechanic-2844` / Order Counters | Game Type | no | Technical option. |
| 2846 | Once-Per-Game Abilities | `game-type:mechanic-2846` / Once-Per-Game Abilities | Game Type | no | Full option. |
| 2847 | Advantage Token | `game-type:mechanic-2847` / Advantage Token | Game Type | no | Technical option. |
| 2849 | Tech Trees / Tech Tracks | `game-type:mechanic-2849` / Tech Trees & Tracks | Game Type | no | Concise label. |
| 2850 | Events | `game-type:mechanic-2850` / Events | Game Type | no | Full option. |
| 2851 | Narrative Choice / Paragraph | `game-type:mechanic-2851` / Narrative Choice | Game Type | no | Concise label; explanation may help. |
| 2853 | Stat Check Resolution | `game-type:mechanic-2853` / Stat Check Resolution | Game Type | no | Technical option. |
| 2854 | Critical Hits and Failures | `game-type:mechanic-2854` / Critical Hits & Failures | Game Type | no | Concise label. |
| 2855 | Ratio / Combat Results Table | `game-type:mechanic-2855` / Combat Results Table | Game Type | no | Concise label; review. |
| 2856 | Die Icon Resolution | `game-type:mechanic-2856` / Die Icon Resolution | Game Type | no | Technical option. |
| 2857 | Card Play Conflict Resolution | `game-type:mechanic-2857` / Card Play Conflict Resolution | Game Type | no | Technical option. |
| 2858 | Prisoner's Dilemma | `game-type:mechanic-2858` / Prisoner's Dilemma | Game Type | no | Full option. |
| 2860 | Flicking | `game-type:dexterity` / Dexterity | Game Type | yes | Approved merge with Action / Dexterity category. |
| 2861 | Static Capture | `game-type:mechanic-2861` / Static Capture | Game Type | no | Technical option. |
| 2863 | Minimap Resolution | `game-type:mechanic-2863` / Minimap Resolution | Game Type | no | Technical option; review usefulness. |
| 2864 | Force Commitment | `game-type:mechanic-2864` / Force Commitment | Game Type | no | Technical option. |
| 2865 | Player Judge | `game-type:mechanic-2865` / Player Judge | Game Type | no | Full option. |
| 2866 | Targeted Clues | `game-type:mechanic-2866` / Targeted Clues | Game Type | no | Full option. |
| 2870 | Re-rolling and Locking | `game-type:mechanic-2870` / Re-rolling & Locking | Game Type | no | Concise label. |
| 2871 | Kill Steal | `game-type:mechanic-2871` / Kill Steal | Game Type | no | Full option. |
| 2874 | Victory Points as a Resource | `game-type:mechanic-2874` / Victory Points as a Resource | Game Type | no | Technical option. |
| 2875 | End Game Bonuses | `game-type:mechanic-2875` / End Game Bonuses | Game Type | no | Full option. |
| 2876 | Race | `game-type:race-mechanic` / Race Mechanic | Game Type | no | Distinct full-list option; not merged with Racing. |
| 2882 | Elapsed Real Time Ending | `game-type:mechanic-2882` / Elapsed Real-Time Ending | Game Type | no | Do not merge automatically with Real-time play. |
| 2883 | Connections | `game-type:mechanic-2883` / Connections | Game Type | no | Full option. |
| 2884 | Sudden Death Ending | `game-type:mechanic-2884` / Sudden Death Ending | Game Type | no | Full option. |
| 2885 | Finale Ending | `game-type:mechanic-2885` / Finale Ending | Game Type | no | Full option. |
| 2886 | King of the Hill | `game-type:mechanic-2886` / King of the Hill | Game Type | no | Full option. |
| 2887 | Catch the Leader | `game-type:mechanic-2887` / Catch the Leader | Game Type | no | Full option. |
| 2888 | Tug of War | `game-type:mechanic-2888` / Tug of War | Game Type | no | Full option. |
| 2889 | Highest-Lowest Scoring | `game-type:mechanic-2889` / Highest-Lowest Scoring | Game Type | no | Technical option. |
| 2891 | Hidden Roles | `game-type:mechanic-2891` / Hidden Roles | Game Type | no | Full option. |
| 2892 | Roles with Asymmetric Information | `game-type:mechanic-2892` / Asymmetric Roles | Game Type | no | Concise label. |
| 2893 | Communication Limits | `game-type:mechanic-2893` / Communication Limits | Game Type | no | Full option. |
| 2897 | Variable Set-up | `game-type:mechanic-2897` / Variable Setup | Game Type | no | Concise label. |
| 2900 | Market | `game-type:mechanic-2900` / Market | Game Type | no | Full option. |
| 2901 | Delayed Purchase | `game-type:mechanic-2901` / Delayed Purchase | Game Type | no | Technical option. |
| 2902 | Income | `game-type:mechanic-2902` / Income | Game Type | no | Full option. |
| 2903 | Automatic Resource Growth | `game-type:mechanic-2903` / Automatic Resource Growth | Game Type | no | Technical option. |
| 2904 | Loans | `game-type:mechanic-2904` / Loans | Game Type | no | Full option. |
| 2906 | I Cut, You Choose | `game-type:mechanic-2906` / I Cut, You Choose | Game Type | no | Full option. |
| 2909 | Random Production | `game-type:mechanic-2909` / Random Production | Game Type | no | Full option. |
| 2910 | Investment | `game-type:mechanic-2910` / Investment | Game Type | no | Full option. |
| 2911 | Ownership | `game-type:mechanic-2911` / Ownership | Game Type | no | Full option. |
| 2912 | Contracts | `game-type:mechanic-2912` / Contracts | Game Type | no | Full option. |
| 2913 | Bribery | `game-type:mechanic-2913` / Bribery | Game Type | no | Full option. |
| 2914 | Increase Value of Unchosen Resources | `game-type:mechanic-2914` / Increase Value of Unchosen Resources | Game Type | no | Technical option. |
| 2915 | Negotiation | `game-type:negotiation` / Negotiation | Game Type | no | Combined with Negotiation category. |
| 2916 | Alliances | `game-type:mechanic-2916` / Alliances | Game Type | no | Full option. |
| 2918 | Auction: English | `game-type:auction-bidding` / Auction & Bidding | Game Type | no | Approved core auction-family merge. |
| 2919 | Auction: Turn Order Until Pass | `game-type:auction-bidding` / Auction & Bidding | Game Type | no | Approved core auction-family merge. |
| 2920 | Auction: Sealed Bid | `game-type:auction-bidding` / Auction & Bidding | Game Type | no | Approved core auction-family merge. |
| 2922 | Constrained Bidding | `game-type:auction-bidding` / Auction & Bidding | Game Type | no | Approved core auction-family merge. |
| 2923 | Auction: Once Around | `game-type:auction-bidding` / Auction & Bidding | Game Type | no | Approved core auction-family merge. |
| 2924 | Auction: Dutch | `game-type:auction-bidding` / Auction & Bidding | Game Type | no | Approved core auction-family merge. |
| 2926 | Selection Order Bid | `game-type:auction-bidding` / Auction & Bidding | Game Type | no | Approved core auction-family merge. |
| 2927 | Auction: Multiple Lot | `game-type:auction-bidding` / Auction & Bidding | Game Type | no | Approved core auction-family merge. |
| 2928 | Closed Economy Auction | `game-type:auction-bidding` / Auction & Bidding | Game Type | no | Approved core auction-family merge. |
| 2930 | Auction: Dexterity | `game-type:auction-bidding` / Auction & Bidding | Game Type | no | Approved core auction-family merge. |
| 2931 | Auction: Fixed Placement | `game-type:auction-bidding` / Auction & Bidding | Game Type | no | Approved core auction-family merge. |
| 2932 | Auction: Dutch Priority | `game-type:auction-bidding` / Auction & Bidding | Game Type | no | Approved core auction-family merge. |
| 2933 | Worker Placement, Different Worker Types | `game-type:worker-placement` / Worker Placement | Game Type | yes | Approved merge with featured Worker Placement. |
| 2935 | Worker Placement with Dice Workers | `game-type:worker-placement` / Worker Placement | Game Type | yes | Approved merge with featured Worker Placement. |
| 2939 | Track Movement | `game-type:mechanic-2939` / Track Movement | Game Type | no | Full option. |
| 2940 | Square Grid | `game-type:mechanic-2940` / Square Grid | Game Type | no | Technical option. |
| 2944 | Three Dimensional Movement | `game-type:mechanic-2944` / 3D Movement | Game Type | no | Concise label. |
| 2946 | Pattern Movement | `game-type:mechanic-2946` / Pattern Movement | Game Type | no | Full option. |
| 2947 | Movement Points | `game-type:mechanic-2947` / Movement Points | Game Type | no | Full option. |
| 2948 | Resource to Move | `game-type:mechanic-2948` / Resource to Move | Game Type | no | Technical option. |
| 2949 | Measurement Movement | `game-type:mechanic-2949` / Measurement Movement | Game Type | no | Technical option. |
| 2950 | Different Dice Movement | `game-type:mechanic-2950` / Different Dice Movement | Game Type | no | Technical option. |
| 2952 | Impulse Movement | `game-type:mechanic-2952` / Impulse Movement | Game Type | no | Full option. |
| 2953 | Programmed Movement | `game-type:mechanic-2953` / Programmed Movement | Game Type | no | Full option. |
| 2954 | Relative Movement | `game-type:mechanic-2954` / Relative Movement | Game Type | no | Full option. |
| 2955 | Mancala | `game-type:mechanic-2955` / Mancala | Game Type | no | Full option. |
| 2956 | Chaining | `game-type:mechanic-2956` / Chaining | Game Type | no | Technical option. |
| 2957 | Bias | `game-type:mechanic-2957` / Bias | Game Type | no | Technical option; review clarity. |
| 2958 | Moving Multiple Units | `game-type:mechanic-2958` / Moving Multiple Units | Game Type | no | Full option. |
| 2959 | Map Addition | `game-type:mechanic-2959` / Map Addition | Game Type | no | Full option. |
| 2960 | Map Reduction | `game-type:mechanic-2960` / Map Reduction | Game Type | no | Full option. |
| 2961 | Map Deformation | `game-type:mechanic-2961` / Map Deformation | Game Type | no | Full option. |
| 2962 | Move Through Deck | `game-type:mechanic-2962` / Move Through Deck | Game Type | no | Full option. |
| 2963 | Movement Template | `game-type:mechanic-2963` / Movement Template | Game Type | no | Technical option. |
| 2964 | Pieces as Map | `game-type:mechanic-2964` / Pieces as Map | Game Type | no | Technical option. |
| 2965 | Multiple Maps | `game-type:mechanic-2965` / Multiple Maps | Game Type | no | Full option. |
| 2967 | Hidden Movement | `game-type:mechanic-2967` / Hidden Movement | Game Type | no | Full option. |
| 2974 | Zone of Control | `game-type:mechanic-2974` / Zone of Control | Game Type | no | Technical option. |
| 2975 | Line of Sight | `game-type:mechanic-2975` / Line of Sight | Game Type | no | Full option. |
| 2978 | Grid Coverage | `game-type:mechanic-2978` / Grid Coverage | Game Type | no | Technical option. |
| 2980 | Ladder Climbing | `game-type:mechanic-2980` / Ladder Climbing | Game Type | no | Full option. |
| 2981 | Melding and Splaying | `game-type:mechanic-2981` / Melding & Splaying | Game Type | no | Concise label. |
| 2984 | Closed Drafting | `game-type:drafting` / Drafting | Game Type | no | Approved merge with Open Drafting. |
| 2985 | Turn Order: Random | `game-type:mechanic-2985` / Turn Order: Random | Game Type | no | Full option. |
| 2987 | Hidden Victory Points | `game-type:mechanic-2987` / Hidden Victory Points | Game Type | no | Full option. |
| 2988 | Stacking and Balancing | `game-type:mechanic-2988` / Stacking & Balancing | Game Type | no | Concise label. |
| 2989 | Physical Removal | `game-type:mechanic-2989` / Physical Removal | Game Type | no | Full option. |
| 2990 | Cube Tower | `game-type:mechanic-2990` / Cube Tower | Game Type | no | Full option. |
| 2991 | Speed Matching | `game-type:mechanic-2991` / Speed Matching | Game Type | no | Full option. |
| 2999 | Bingo | `game-type:mechanic-2999` / Bingo | Game Type | no | Full option. |
| 3000 | Hot Potato | `game-type:mechanic-3000` / Hot Potato | Game Type | no | Full option. |
| 3001 | Layering | `game-type:mechanic-3001` / Layering | Game Type | no | Technical option. |
| 3002 | Deduction | `game-type:deduction` / Deduction | Game Type | yes | Combined with featured Deduction category. |
| 3003 | Induction | `game-type:mechanic-3003` / Induction | Game Type | no | Full option. |
| 3004 | Deck Construction | `game-type:mechanic-3004` / Deck Construction | Game Type | no | Must remain separate from Deck Building. |
| 3005 | Slide / Push | `game-type:mechanic-3005` / Slide & Push | Game Type | no | Concise label. |
| 3006 | Predictive Bid | `game-type:mechanic-3006` / Predictive Bid | Game Type | no | Technical option. |
| 3007 | Matching | `game-type:mechanic-3007` / Matching | Game Type | no | Full option. |
| 3096 | Drawing | `game-type:mechanic-3096` / Drawing | Game Type | no | Full option. |
| 3097 | Bids As Wagers | `game-type:mechanic-3097` / Bids As Wagers | Game Type | no | Approved separate full-list option. |
| 3098 | Auction Compensation | `game-type:mechanic-3098` / Auction Compensation | Game Type | no | Approved separate full-list option. |
| 3099 | Multi-Use Cards | `game-type:mechanic-3099` / Multi-Use Cards | Game Type | no | Full option. |
| 3100 | Tags | `game-type:mechanic-3100` / Tags | Game Type | no | Technical option. |
| 3101 | Ordering | `game-type:mechanic-3101` / Ordering | Game Type | no | Full option. |
| 3102 | Questions and Answers | `game-type:mechanic-3102` / Questions & Answers | Game Type | no | Keep separate from Trivia. |
| 3103 | Resource Queue | `game-type:mechanic-3103` / Resource Queue | Game Type | no | Technical option. |
| 3104 | Neighbor Scope | `game-type:mechanic-3104` / Neighbor Scope | Game Type | no | Technical option. |
| 3113 | Spelling | `game-type:word-games` / Word Games | Game Type | yes | Approved merge with Word Game category. |

## Finalized mapping decisions

The following decisions are applied by this implementation:

| Topic | Final decision | Rationale |
|---|---|---|
| Word Games + Spelling | Approved merge. | Spelling is a natural subset of word play. |
| Dexterity + Flicking | Approved merge for discovery, while retaining both source IDs. | Flicking is a strong physical-dexterity signal. |
| Auction family | Approved one `Auction & Bidding` option for core variants. | Bids As Wagers and Auction Compensation remain separate as instructed. |
| Campaign / Scenario | Keep `2018` and `2822` separate. | The terms overlap but are not identical. |
| Dice Games | Approved merge of category `1017` and mechanic `2072`. | The union is the intended attendee-facing discovery option. |
| Transportation and Industry / Manufacturing | Assign both to Theme. | These are primarily subjects/settings in this taxonomy. |
| Mafia and Hidden Roles / Deduction | Keep separate. | Avoids broadening Deduction with a social-game label. |
| Real-time and Elapsed Real Time Ending | Keep separate. | A real-time game is not the same as a game that merely ends after elapsed real time. |
| Cooperative and Semi-Cooperative | Keep Cooperative as the existing independent checkbox; retain Semi-Cooperative as a full Game Type option. | Combining them would violate the meaning of “cooperative games only.” |
| Solo / Solitaire | Exclude from taxonomy. | Solo play is already represented by the player-count filter. |
| Electronic, Print & Play, Mature / Adult, and Medical | Preserve as full-list classifications. | The approved principle is to retain uncommon or technical classifications. |
| Expansion categories, Game System, and Race | Preserve as full-list classifications, with Race labeled `Race Mechanic`. | Complete taxonomy coverage is preferred; Race must remain distinct from Racing. |

## Mappings requiring developer review

No source-to-group or merge decision remains unapproved. The following are presentation/content reviews only; the implementation preserves the source as a selectable full-list option:

- **American Indian Wars (`1108`):** retain the BGG source mapping, but review attendee-facing wording with the project’s accessibility/content guidance before launch.
- **Mature / Adult (`1118`) and Medical (`2145`):** retain as searchable classifications; review whether these labels need explanatory copy or visibility guidance for the convention audience.
- **Technical full-list labels:** retain the BGG-derived labels and stable IDs; add short explanations only for terms that usability review shows are unclear. Do not create alternate duplicate options.

## Technical concerns for the current API

1. **Mixed-source logical options use server-side expansion.** The request submits stable taxonomy option IDs through `game_types=` and `themes=`; the backend expands each option into OR predicates across its category/mechanic sources.
2. **Taxonomy groups need separate parameters.** Use one parameter for selected Game Type option IDs and one for Theme option IDs, with OR within each parameter and AND between them. Preserve the existing raw `mechanics=` and `categories=` parameters for detail-tag filtering and compatibility unless they are explicitly replaced.
3. **The taxonomy endpoint is cached and server-provided.** `/api/filter-taxonomy/` adds friendly labels, grouping, featured status, explanations, and source mappings without a new service or database tables. The raw endpoints remain for compatibility.
4. **Stable IDs must be source IDs plus application IDs.** Do not expose the relationship-row `id` from `mechanics` or `categories` as a filter contract. Cache keys must include the taxonomy option selections, just as the current Stage 3 cache key includes the raw filter parameters.
5. **Search should operate on the option contract.** The frontend should search friendly labels and source names from the cached option payload. It should retain selections when the list is collapsed and must not create a second selection state for the expanded list.
6. **Unknown options should fail safely.** The API should reject malformed application option IDs or ignore unknown source rows according to an explicit policy. A stale client must not cause an unbounded query or silently select an unrelated option.
7. **The taxonomy contract is now server-provided.** `GameList.js` consumes `/api/filter-taxonomy/`; legacy raw mechanics/categories remain supported for existing detail links and independent controls while stable taxonomy IDs drive the redesigned lists.

## Approval checklist

- [x] Approve the ten featured Game Type mappings.
- [x] Approve the ten featured Theme mappings.
- [x] Approve the merged logical options and their source ID sets.
- [x] Resolve Auction, Dice, Dexterity, Word Games, Campaign / Scenario, and category placement decisions.
- [x] Confirm that uncommon, technical, format, and sensitive classifications remain searchable in the full list, except for the separately approved Solo exclusion and independent-control duplicates.
- [x] Approve the option response shape and taxonomy query parameter names before implementation.
- [x] Implement and verify the server-provided crosswalk and UI behavior with focused backend/frontend checks. Manual responsive/accessibility review was completed during the redesign handoff.

## References

- [Archived UI redesign specification](../archive/ui-redesign/ui-redesign.md)
- [Archived UI redesign implementation plan](../archive/ui-redesign/ui-redesign-implementation-plan.md)
- [BGG Category reference](https://boardgamegeek.com/wiki/page/Category)
- [BGG mechanics reference](https://boardgamegeek.com/wiki/page/mechanics)
- [BGG game entry classification overview](https://boardgamegeek.com/wiki/page/game_entry)

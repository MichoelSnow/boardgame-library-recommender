"""Server-provided UI taxonomy options for the game browser."""

from typing import Any

from sqlalchemy.orm import Session

from . import models


# option_id, label, group, featured, explanation
CATEGORY_OPTIONS: dict[int, tuple[str, str, str, bool, str | None]] = {
    1001: ("theme:political", "Political", "theme", False, None),
    1002: ("game-type:card-games", "Card Games", "game_type", False, None),
    1008: ("theme:nautical", "Nautical", "theme", False, None),
    1009: (
        "game-type:abstract-strategy",
        "Abstract Strategy",
        "game_type",
        False,
        None,
    ),
    1010: ("theme:fantasy", "Fantasy", "theme", True, None),
    1011: ("theme:transportation", "Transportation", "theme", False, None),
    1013: ("theme:farming", "Farming", "theme", False, None),
    1015: ("game-type:civilization", "Civilization", "game_type", False, None),
    1016: ("theme:science-fiction", "Science Fiction", "theme", True, None),
    1017: ("game-type:dice-games", "Dice Games", "game_type", False, None),
    1019: ("game-type:wargames", "Wargames", "game_type", False, None),
    1020: ("game-type:exploration", "Exploration", "game_type", False, None),
    1021: ("game-type:economic", "Economic", "game_type", False, None),
    1022: ("game-type:adventure", "Adventure", "game_type", False, None),
    1023: ("game-type:bluffing", "Bluffing", "game_type", True, None),
    1024: ("theme:horror", "Horror", "theme", True, None),
    1025: ("game-type:word-games", "Word Games", "game_type", True, None),
    1026: ("game-type:negotiation", "Negotiation", "game_type", False, None),
    1027: ("game-type:trivia", "Trivia", "game_type", True, None),
    1028: ("game-type:puzzle", "Puzzle", "game_type", False, None),
    1029: ("game-type:city-building", "City Building", "game_type", False, None),
    1031: ("game-type:racing", "Racing", "game_type", True, None),
    1032: ("game-type:dexterity", "Dexterity", "game_type", True, None),
    1033: ("game-type:mafia", "Mafia", "game_type", False, None),
    1034: ("theme:trains", "Trains", "theme", False, None),
    1035: ("theme:medieval", "Medieval", "theme", True, None),
    1036: ("theme:prehistoric", "Prehistoric", "theme", False, None),
    1037: ("game-type:real-time", "Real-time", "game_type", False, None),
    1038: ("theme:sports", "Sports", "theme", False, None),
    1039: ("game-type:deduction", "Deduction", "game_type", True, None),
    1040: ("theme:mystery", "Mystery", "theme", True, None),
    1042: (
        "game-type:category-1042",
        "Expansion for Base-game",
        "game_type",
        False,
        None,
    ),
    1044: (
        "game-type:collectible-components",
        "Collectible Components",
        "game_type",
        False,
        None,
    ),
    1045: ("game-type:memory", "Memory", "game_type", False, None),
    1046: ("game-type:fighting", "Fighting", "game_type", False, None),
    1047: ("game-type:miniatures", "Miniatures", "game_type", False, None),
    1048: ("theme:american-civil-war", "American Civil War", "theme", False, None),
    1049: ("theme:world-war-ii", "World War II", "theme", True, None),
    1050: ("theme:ancient", "Ancient", "theme", False, None),
    1051: ("theme:napoleonic", "Napoleonic", "theme", False, None),
    1052: ("theme:arabian", "Arabian", "theme", False, None),
    1054: ("theme:music", "Music", "theme", False, None),
    1055: ("theme:american-west", "American West", "theme", False, None),
    1059: ("game-type:maze", "Maze", "game_type", False, None),
    1064: ("theme:movies-tv", "Movies & TV", "theme", True, None),
    1065: ("theme:world-war-i", "World War I", "theme", False, None),
    1069: ("theme:modern-warfare", "Modern Warfare", "theme", False, None),
    1070: ("theme:renaissance", "Renaissance", "theme", False, None),
    1072: ("game-type:electronic", "Electronic Games", "game_type", False, None),
    1075: (
        "theme:american-revolutionary-war",
        "American Revolutionary War",
        "theme",
        False,
        None,
    ),
    1079: ("theme:humor", "Humor", "theme", False, None),
    1081: ("theme:spies-secret-agents", "Spies / Secret Agents", "theme", False, None),
    1082: ("theme:mythology", "Mythology", "theme", True, None),
    1084: ("theme:environmental", "Environmental", "theme", False, None),
    1086: (
        "game-type:territory-building",
        "Territory Building",
        "game_type",
        False,
        None,
    ),
    1088: (
        "theme:industry-manufacturing",
        "Industry / Manufacturing",
        "theme",
        False,
        None,
    ),
    1089: ("theme:animals", "Animals", "theme", True, None),
    1090: ("theme:pirates", "Pirates", "theme", False, None),
    1091: ("theme:korean-war", "Korean War", "theme", False, None),
    1093: ("theme:novel-based", "Novel-based", "theme", False, None),
    1094: ("game-type:educational", "Educational", "game_type", False, None),
    1097: ("theme:travel", "Travel", "theme", False, None),
    1098: ("game-type:number", "Number Games", "game_type", False, None),
    1101: ("theme:video-game", "Video Game Theme", "theme", False, None),
    1102: ("theme:civil-war", "Civil War", "theme", False, None),
    1104: ("game-type:math", "Math Games", "game_type", False, None),
    1108: ("theme:american-indian-wars", "American Indian Wars", "theme", False, None),
    1109: ("theme:vietnam-war", "Vietnam War", "theme", False, None),
    1113: ("theme:space-exploration", "Space Exploration", "theme", False, None),
    1115: ("theme:religious", "Religious", "theme", False, None),
    1116: ("theme:comic-book", "Comic Book / Strip", "theme", False, None),
    1117: ("theme:book", "Book", "theme", False, None),
    1118: ("theme:mature-adult", "Mature / Adult", "theme", False, None),
    1119: ("game-type:category-1119", "Game System", "game_type", False, None),
    1120: ("game-type:print-and-play", "Print & Play", "game_type", False, None),
    2145: ("theme:medical", "Medical", "theme", False, None),
    2481: ("theme:zombies", "Zombies", "theme", True, None),
    2650: ("theme:aviation-flight", "Aviation / Flight", "theme", False, None),
    2687: ("game-type:category-2687", "Fan Expansion", "game_type", False, None),
    2710: ("theme:post-napoleonic", "Post-Napoleonic", "theme", False, None),
    2725: ("theme:pike-and-shot", "Pike and Shot", "theme", False, None),
    2726: ("theme:age-of-reason", "Age of Reason", "theme", False, None),
    3129: (
        "game-type:category-3129",
        "Third-party Expansion",
        "game_type",
        False,
        None,
    ),
}


# Sources that already have independent controls and must not be duplicated.
RESERVED_CATEGORY_IDS = {1030, 1041}  # Party Game, Children's Game
RESERVED_MECHANIC_IDS = {2023}  # Cooperative Game
EXCLUDED_MECHANIC_IDS = {2819}  # Solo / Solitaire Game


# mechanic_id: option_id, label, featured, explanation
MECHANIC_OPTIONS: dict[int, tuple[str, str, bool, str | None]] = {
    2009: ("game-type:trick-taking", "Trick-taking", True, None),
    2012: ("game-type:auction-bidding", "Auction & Bidding", False, None),
    2014: ("game-type:bluffing", "Bluffing", True, None),
    2018: (
        "game-type:campaign-battle-card-driven",
        "Campaign / Battle Card Driven",
        False,
        None,
    ),
    2041: ("game-type:drafting", "Drafting", False, None),
    2047: ("game-type:memory", "Memory", False, None),
    2072: ("game-type:dice-games", "Dice Games", False, None),
    2082: ("game-type:worker-placement", "Worker Placement", True, None),
    2661: ("game-type:push-your-luck", "Push Your Luck", True, None),
    2664: ("game-type:deck-building", "Deck Building", True, None),
    2822: (
        "game-type:scenario-mission-campaign",
        "Scenario / Mission / Campaign",
        False,
        None,
    ),
    2827: ("game-type:auction-bidding", "Auction & Bidding", False, None),
    2831: ("game-type:real-time", "Real-time", False, None),
    2860: ("game-type:dexterity", "Dexterity", True, None),
    2876: ("game-type:race-mechanic", "Race Mechanic", False, None),
    2933: ("game-type:worker-placement", "Worker Placement", True, None),
    2935: ("game-type:worker-placement", "Worker Placement", True, None),
    2984: ("game-type:drafting", "Drafting", False, None),
    3002: ("game-type:deduction", "Deduction", True, None),
    3097: ("game-type:mechanic-3097", "Bids As Wagers", False, None),
    3098: ("game-type:mechanic-3098", "Auction Compensation", False, None),
    3113: ("game-type:word-games", "Word Games", True, None),
}

for _mechanic_id in (
    2918,
    2919,
    2920,
    2922,
    2923,
    2924,
    2926,
    2927,
    2928,
    2930,
    2931,
    2932,
):
    MECHANIC_OPTIONS[_mechanic_id] = (
        "game-type:auction-bidding",
        "Auction & Bidding",
        False,
        None,
    )


def _add_source(
    options: dict[str, dict[str, Any]],
    *,
    option_id: str,
    label: str,
    group: str,
    featured: bool,
    source_type: str,
    source_id: int,
    source_name: str,
    explanation: str | None,
) -> None:
    option = options.setdefault(
        option_id,
        {
            "option_id": option_id,
            "label": label,
            "group": group,
            "featured": featured,
            "sources": [],
            "explanation": explanation,
        },
    )
    option["featured"] = option["featured"] or featured
    if explanation and not option["explanation"]:
        option["explanation"] = explanation
    if not any(
        source["type"] == source_type and source["id"] == source_id
        for source in option["sources"]
    ):
        option["sources"].append(
            {"type": source_type, "id": source_id, "name": source_name}
        )


def get_taxonomy_options(db: Session) -> list[dict[str, Any]]:
    """Build stable, cacheable taxonomy options from the current catalog sources."""
    categories = (
        db.query(
            models.Category.boardgamecategory_id,
            models.Category.boardgamecategory_name,
        )
        .distinct()
        .all()
    )
    mechanics = (
        db.query(
            models.Mechanic.boardgamemechanic_id,
            models.Mechanic.boardgamemechanic_name,
        )
        .distinct()
        .all()
    )

    options: dict[str, dict[str, Any]] = {}
    for source_id, source_name in categories:
        if source_id in RESERVED_CATEGORY_IDS:
            continue
        config = CATEGORY_OPTIONS.get(source_id)
        if config is None:
            continue
        option_id, label, group, featured, explanation = config
        _add_source(
            options,
            option_id=option_id,
            label=label,
            group=group,
            featured=featured,
            source_type="category",
            source_id=source_id,
            source_name=source_name,
            explanation=explanation,
        )

    for source_id, source_name in mechanics:
        if source_id in RESERVED_MECHANIC_IDS or source_id in EXCLUDED_MECHANIC_IDS:
            continue
        option_id, label, featured, explanation = MECHANIC_OPTIONS.get(
            source_id,
            (f"game-type:mechanic-{source_id}", source_name, False, None),
        )
        _add_source(
            options,
            option_id=option_id,
            label=label,
            group="game_type",
            featured=featured,
            source_type="mechanic",
            source_id=source_id,
            source_name=source_name,
            explanation=explanation,
        )

    return sorted(
        options.values(),
        key=lambda option: (
            option["group"],
            not option["featured"],
            option["label"].casefold(),
        ),
    )


def get_taxonomy_source_ids(
    db: Session,
    option_ids: str | None,
    group: str,
) -> tuple[set[int], set[int]]:
    """Resolve known application option IDs to category and mechanic source IDs."""
    if not option_ids:
        return set(), set()

    requested = {value.strip() for value in option_ids.split(",") if value.strip()}
    if not requested:
        return set(), set()

    source_categories: set[int] = set()
    source_mechanics: set[int] = set()
    for option in get_taxonomy_options(db):
        if option["group"] != group or option["option_id"] not in requested:
            continue
        for source in option["sources"]:
            if source["type"] == "category":
                source_categories.add(source["id"])
            else:
                source_mechanics.add(source["id"])
    return source_categories, source_mechanics

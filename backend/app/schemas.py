from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional


class ArtistBase(BaseModel):
    boardgameartist_id: int
    boardgameartist_name: str

    model_config = ConfigDict(from_attributes=True)


class CategoryBase(BaseModel):
    boardgamecategory_id: int
    boardgamecategory_name: str

    model_config = ConfigDict(from_attributes=True)


class CompilationBase(BaseModel):
    boardgamecompilation_id: int
    boardgamecompilation_name: str

    model_config = ConfigDict(from_attributes=True)


class DesignerBase(BaseModel):
    boardgamedesigner_id: int
    boardgamedesigner_name: str

    model_config = ConfigDict(from_attributes=True)


class ExpansionBase(BaseModel):
    boardgameexpansion_id: int
    boardgameexpansion_name: str

    model_config = ConfigDict(from_attributes=True)


class FamilyBase(BaseModel):
    boardgamefamily_id: int
    boardgamefamily_name: str

    model_config = ConfigDict(from_attributes=True)


class ImplementationBase(BaseModel):
    boardgameimplementation_id: int
    boardgameimplementation_name: str

    model_config = ConfigDict(from_attributes=True)


class IntegrationBase(BaseModel):
    boardgameintegration_id: int
    boardgameintegration_name: str

    model_config = ConfigDict(from_attributes=True)


class MechanicBase(BaseModel):
    boardgamemechanic_id: int
    boardgamemechanic_name: str

    model_config = ConfigDict(from_attributes=True)


class PublisherBase(BaseModel):
    boardgamepublisher_id: int
    boardgamepublisher_name: str

    model_config = ConfigDict(from_attributes=True)


class SuggestedPlayerBase(BaseModel):
    player_count: int
    recommendation_level: str

    model_config = ConfigDict(from_attributes=True)


class LanguageDependenceBase(BaseModel):
    level: Optional[str] = None
    votes: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class VersionBase(BaseModel):
    version_id: int
    width: Optional[float] = None
    length: Optional[float] = None
    depth: Optional[float] = None
    year_published: Optional[int] = None
    thumbnail: Optional[str] = None
    image: Optional[str] = None
    language: Optional[str] = None
    version_nickname: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BoardGameBase(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    thumbnail: Optional[str] = None
    image: Optional[str] = None
    min_players: Optional[int] = None
    max_players: Optional[int] = None
    playing_time: Optional[int] = None
    min_playtime: Optional[int] = None
    max_playtime: Optional[int] = None
    min_age: Optional[int] = None
    year_published: Optional[int] = None
    average: Optional[float] = None
    num_ratings: Optional[int] = None
    num_comments: Optional[int] = None
    num_weights: Optional[int] = None
    average_weight: Optional[float] = None
    stddev: Optional[float] = None
    median: Optional[float] = None
    owned: Optional[int] = None
    trading: Optional[int] = None
    wanting: Optional[int] = None
    wishing: Optional[int] = None
    bayes_average: Optional[float] = None
    users_rated: Optional[int] = None
    is_expansion: Optional[bool] = None
    rank: Optional[int] = None
    abstracts_rank: Optional[int] = None
    cgs_rank: Optional[int] = None
    childrens_games_rank: Optional[int] = None
    family_games_rank: Optional[int] = None
    party_games_rank: Optional[int] = None
    strategy_games_rank: Optional[int] = None
    thematic_rank: Optional[int] = None
    wargames_rank: Optional[int] = None
    avg_box_volume: Optional[int] = None
    recommendation_score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class BoardGameCreate(BoardGameBase):
    pass


class BoardGameOut(BoardGameBase):
    mechanics: Optional[List[MechanicBase]]
    categories: Optional[List[CategoryBase]]
    designers: Optional[List[DesignerBase]]
    artists: Optional[List[ArtistBase]]
    publishers: Optional[List[PublisherBase]]
    suggested_players: Optional[List[SuggestedPlayerBase]]
    language_dependence: Optional[LanguageDependenceBase]
    integrations: Optional[List[IntegrationBase]]
    implementations: Optional[List[ImplementationBase]]
    compilations: Optional[List[CompilationBase]]
    expansions: Optional[List[ExpansionBase]]
    families: Optional[List[FamilyBase]]
    versions: Optional[List[VersionBase]]

    model_config = ConfigDict(from_attributes=True)


class RecommendationGameOut(BoardGameBase):
    """Lightweight recommendation payload used by list recommendation endpoints."""

    model_config = ConfigDict(from_attributes=True)


class FilterOptions(BaseModel):
    designers: List[str]
    mechanics: List[str]
    categories: List[str]
    publishers: List[str]

    model_config = ConfigDict(from_attributes=True)


class MechanicFrequency(BaseModel):
    boardgamemechanic_id: int
    boardgamemechanic_name: str
    frequency: int

    class Config:
        from_attributes = True


class Mechanic(MechanicBase):
    id: int
    game_id: int

    class Config:
        from_attributes = True


class BoardGameList(BoardGameBase):
    mechanics: List[MechanicBase] = []
    categories: List[CategoryBase] = []
    suggested_players: List[SuggestedPlayerBase] = []

    model_config = ConfigDict(from_attributes=True)


class GameListResponse(BaseModel):
    games: List[BoardGameList]
    total: int

    model_config = ConfigDict(from_attributes=True)


class LibraryGameBase(BaseModel):
    name: str
    name_raw: Optional[str] = None
    bgg_id: Optional[int] = None
    publisher: Optional[str] = None
    min_titles_id: Optional[int] = None
    titles_id_list: Optional[str] = None
    convention_name: Optional[str] = None
    convention_year: Optional[int] = None
    year_title_first_added: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class LibraryGameCreate(LibraryGameBase):
    pass


class LibraryGameOut(LibraryGameBase):
    id: int
    board_game: Optional[BoardGameOut] = None

    model_config = ConfigDict(from_attributes=True)


class SuggestedPlayer(BaseModel):
    id: int
    game_id: int
    player_count: str
    best: int
    recommended: int
    not_recommended: int
    recommendation_level: Optional[str] = None

    class Config:
        from_attributes = True


class Category(BaseModel):
    id: int
    game_id: int
    boardgamecategory_id: int
    boardgamecategory_name: str

    class Config:
        from_attributes = True


class Designer(BaseModel):
    id: int
    game_id: int
    boardgamedesigner_id: int
    boardgamedesigner_name: str

    class Config:
        from_attributes = True


class Artist(BaseModel):
    id: int
    game_id: int
    boardgameartist_id: int
    boardgameartist_name: str

    class Config:
        from_attributes = True


class Publisher(BaseModel):
    id: int
    game_id: int
    boardgamepublisher_id: int
    boardgamepublisher_name: str

    class Config:
        from_attributes = True


class BoardGame(BoardGameBase):
    id: int
    mechanics: List[Mechanic] = []
    categories: List[Category] = []
    designers: List[Designer] = []
    artists: List[Artist] = []
    publishers: List[Publisher] = []
    suggested_players: List[SuggestedPlayer] = []

    class Config:
        from_attributes = True


class CategoryFrequency(BaseModel):
    boardgamecategory_id: int
    boardgamecategory_name: str
    frequency: int

    class Config:
        from_attributes = True


# User Schemas
class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    password: str
    is_admin: Optional[bool] = False


class User(UserBase):
    id: int
    is_active: bool
    is_admin: bool

    class Config:
        from_attributes = True


# Password Change Schemas
class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(
        min_length=6, description="Password must be at least 6 characters"
    )

    model_config = ConfigDict(from_attributes=True)


class PasswordChangeResponse(BaseModel):
    message: str

    model_config = ConfigDict(from_attributes=True)


# User Suggestion Schemas
class UserSuggestionCreate(BaseModel):
    comment: str

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        str_min_length=1,
        str_max_length=1000,
    )


class UserSuggestionResponse(BaseModel):
    id: int
    comment: str
    timestamp: str
    username: str

    model_config = ConfigDict(from_attributes=True)


class UserSuggestion(BaseModel):
    id: int
    user_id: int
    comment: str
    timestamp: str
    user: User

    model_config = ConfigDict(from_attributes=True)


# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None

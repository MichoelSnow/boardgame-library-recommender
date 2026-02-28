from sqlalchemy import Column, Integer, String, Float, Table, ForeignKey, JSON, DateTime, Boolean, Index, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column
from .database import Base
from typing import Optional
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to UserSuggestion
    suggestions = relationship("UserSuggestion", back_populates="user")

class UserSuggestion(Base):
    __tablename__ = "user_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    comment = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationship to User
    user = relationship("User", back_populates="suggestions")

class BoardGame(Base):
    __tablename__ = 'games'
    __allow_unmapped__ = True
    recommendation_score: Optional[float] = None

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)  # Indexed for name sorting and search
    description = Column(String)
    thumbnail = Column(String)
    image = Column(String)
    min_players = Column(Integer, index=True)  # Indexed for player filtering
    max_players = Column(Integer, index=True)  # Indexed for player filtering
    playing_time = Column(Integer)
    min_playtime = Column(Integer)
    max_playtime = Column(Integer)
    min_age = Column(Integer)
    year_published = Column(Integer, index=True)  # Indexed for year filtering
    
    # Statistics
    average = Column(Float, index=True)  # average_rating - indexed for sorting
    num_ratings = Column(Integer)  # num_ratings
    num_comments = Column(Integer)  # num_comments
    num_weights = Column(Integer)  # num_weights
    average_weight = Column(Float, index=True)  # average_weight - indexed for weight filtering
    stddev = Column(Float)
    median = Column(Float)
    owned = Column(Integer)
    trading = Column(Integer)
    wanting = Column(Integer)
    wishing = Column(Integer)
    bayes_average = Column(Float, index=True)  # bayes_average - indexed for sorting
    users_rated = Column(Integer)  # number of users who rated the game
    is_expansion = Column(Boolean)
    
    # Rankings - all indexed for sorting
    rank = Column(Integer, index=True)  # Primary sort field - indexed
    abstracts_rank = Column(Integer, index=True)
    cgs_rank = Column(Integer, index=True)
    childrens_games_rank = Column(Integer, index=True)
    family_games_rank = Column(Integer, index=True)
    party_games_rank = Column(Integer, index=True)
    strategy_games_rank = Column(Integer, index=True)
    thematic_rank = Column(Integer, index=True)
    wargames_rank = Column(Integer, index=True)
    avg_box_volume = Column(Integer, index=True)
    
    # Relationships - all lazy loaded by default
    mechanics = relationship("Mechanic", back_populates="game", lazy="select")
    categories = relationship("Category", back_populates="game", lazy="select")
    designers = relationship("Designer", back_populates="game", lazy="select")
    artists = relationship("Artist", back_populates="game", lazy="select")
    publishers = relationship("Publisher", back_populates="game", lazy="select")
    suggested_players = relationship("SuggestedPlayer", back_populates="game", lazy="select")
    language_dependence = relationship("LanguageDependence", back_populates="game", uselist=False, lazy="select")
    integrations = relationship("Integration", back_populates="game", lazy="select")
    implementations = relationship("Implementation", back_populates="game", lazy="select")
    compilations = relationship("Compilation", back_populates="game", lazy="select")
    expansions = relationship("Expansion", back_populates="game", lazy="select")
    families = relationship("Family", back_populates="game", lazy="select")
    versions = relationship("Version", back_populates="game", lazy="select")

class Mechanic(Base):
    __tablename__ = 'mechanics'
    __table_args__ = (
        UniqueConstraint(
            'game_id',
            'boardgamemechanic_name',
            name='uq_mechanics_game_id_name',
        ),
    )
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'), index=True)  # Indexed for joins
    boardgamemechanic_id = Column(Integer, index=True)  # Indexed for filtering
    boardgamemechanic_name = Column(String)
    game = relationship("BoardGame", back_populates="mechanics")

class Category(Base):
    __tablename__ = 'categories'
    __table_args__ = (
        UniqueConstraint(
            'game_id',
            'boardgamecategory_name',
            name='uq_categories_game_id_name',
        ),
    )
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'), index=True)  # Indexed for joins
    boardgamecategory_id = Column(Integer, index=True)  # Indexed for filtering
    boardgamecategory_name = Column(String)
    game = relationship("BoardGame", back_populates="categories")

class Designer(Base):
    __tablename__ = 'designers'
    __table_args__ = (
        UniqueConstraint(
            'game_id',
            'boardgamedesigner_name',
            name='uq_designers_game_id_name',
        ),
    )
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'), index=True)  # Indexed for joins
    boardgamedesigner_id = Column(Integer, index=True)  # Indexed for filtering
    boardgamedesigner_name = Column(String)
    game = relationship("BoardGame", back_populates="designers")

class Artist(Base):
    __tablename__ = 'artists'
    __table_args__ = (
        UniqueConstraint(
            'game_id',
            'boardgameartist_name',
            name='uq_artists_game_id_name',
        ),
    )
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'), index=True)  # Indexed for joins
    boardgameartist_id = Column(Integer, index=True)  # Indexed for filtering
    boardgameartist_name = Column(String)
    game = relationship("BoardGame", back_populates="artists")

class Publisher(Base):
    __tablename__ = 'publishers'
    __table_args__ = (
        UniqueConstraint(
            'game_id',
            'boardgamepublisher_name',
            name='uq_publishers_game_id_name',
        ),
    )
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'), index=True)  # Indexed for joins
    boardgamepublisher_id = Column(Integer)
    boardgamepublisher_name = Column(String)
    game = relationship("BoardGame", back_populates="publishers")

class SuggestedPlayer(Base):
    __tablename__ = 'suggested_players'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'), index=True)  # Indexed for joins
    player_count = Column(Integer, index=True)  # Indexed for player filtering
    best = Column(Integer)
    recommended = Column(Integer)
    not_recommended = Column(Integer)
    game_total_votes = Column(Integer)
    player_count_total_votes = Column(Integer)  # total votes for this player count
    recommendation_level = Column(String, index=True)  # 'best', 'recommended', or 'not_recommended' - indexed for filtering
    game = relationship("BoardGame", back_populates="suggested_players")

class LanguageDependence(Base):
    __tablename__ = 'language_dependence'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'))
    level_1 = Column(Integer)
    level_2 = Column(Integer)
    level_3 = Column(Integer)
    level_4 = Column(Integer)
    level_5 = Column(Integer)
    total_votes = Column(Integer)
    language_dependency = Column(Integer)  # 1-5 scale
    game = relationship("BoardGame", back_populates="language_dependence")

class Integration(Base):
    __tablename__ = 'integrations'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'))
    boardgameintegration_id = Column(Integer)
    boardgameintegration_name = Column(String)
    game = relationship("BoardGame", back_populates="integrations")

class Implementation(Base):
    __tablename__ = 'implementations'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'))
    boardgameimplementation_id = Column(Integer)
    boardgameimplementation_name = Column(String)
    game = relationship("BoardGame", back_populates="implementations")

class Compilation(Base):
    __tablename__ = 'compilations'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'))
    boardgamecompilation_id = Column(Integer)
    boardgamecompilation_name = Column(String)
    game = relationship("BoardGame", back_populates="compilations")

class Expansion(Base):
    __tablename__ = 'expansions'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'))
    boardgameexpansion_id = Column(Integer)
    boardgameexpansion_name = Column(String)
    game = relationship("BoardGame", back_populates="expansions")

class Family(Base):
    __tablename__ = 'families'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'))
    boardgamefamily_id = Column(Integer)
    boardgamefamily_name = Column(String)
    game = relationship("BoardGame", back_populates="families")

class Version(Base):
    __tablename__ = 'versions'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'))
    version_id = Column(Integer)
    width = Column(Float)
    length = Column(Float)
    depth = Column(Float)
    year_published = Column(Integer)
    thumbnail = Column(String)
    image = Column(String)
    language = Column(String)
    version_nickname = Column(String)
    game = relationship("BoardGame", back_populates="versions")

class PAXGame(Base):
    __tablename__ = 'pax_games'
    
    id = Column(Integer, primary_key=True)
    name = Column(String)
    name_raw = Column(String)
    bgg_id = Column(Integer, ForeignKey('games.id'), nullable=True, index=True)  # Links to BoardGame if exists - indexed for pax_only filtering
    publisher = Column(String)
    min_titles_id = Column(Integer)
    titles_id_list = Column(String)  # Comma-separated list of title IDs
    convention_name = Column(String)
    convention_year = Column(Integer)
    year_title_first_added = Column(Integer)
    
    # Relationship to BoardGame if bgg_id exists
    board_game = relationship("BoardGame", foreign_keys=[bgg_id])


# Composite Performance Indexes
# These indexes exist in production and improve query performance for common operations

# Categories composite index - for efficient category filtering per game
Index('ix_categories_composite', Category.game_id, Category.boardgamecategory_id)

# Games player range index - for efficient player count range queries
Index('ix_games_player_range', BoardGame.min_players, BoardGame.max_players)

# Mechanics composite index - for efficient mechanic filtering per game
Index('ix_mechanics_composite', Mechanic.game_id, Mechanic.boardgamemechanic_id)

# Suggested players composite index - for complex player recommendation queries
Index('ix_suggested_players_composite', SuggestedPlayer.game_id, SuggestedPlayer.player_count, SuggestedPlayer.recommendation_level)

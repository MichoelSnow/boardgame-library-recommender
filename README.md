# PAX Tabletop Recommender

A board game recommendation system that crawls BoardGameGeek.com data and provides game recommendations using collaborative filtering with special integration for PAX convention games. Built with FastAPI, React, and sparse matrix embeddings.

## Key Features

- **Collaborative Filtering Recommendations**: Uses sparse matrix embeddings and cosine similarity for game suggestions based on user rating patterns
- **PAX Integration**: Special filtering and highlighting for PAX tabletop convention games
- **BoardGameGeek Data**: Comprehensive game database with ratings, mechanics, categories, and detailed metadata
- **User Authentication**: Secure login system with admin roles and user management
- **Advanced Filtering**: Search by mechanics, categories, player count, complexity, and more
- **Real-time Performance**: Optimized database queries with caching and thread pool execution
- **Production Ready**: Dockerized deployment on Fly.io with persistent data storage

## Project Structure

```
pax_tt_recommender/
├── backend/                    # FastAPI backend with ML recommendations
│   ├── app/                   # Backend application code
│   │   ├── main.py            # FastAPI app with auth, CORS, compression
│   │   ├── models.py          # SQLAlchemy models (15+ entities)
│   │   ├── schemas.py         # Pydantic schemas for API serialization
│   │   ├── crud.py            # Database operations with ML integration
│   │   ├── database.py        # Database config with custom StaticFiles
│   │   ├── recommender.py     # ML recommendation engine
│   │   ├── security.py        # JWT authentication and password hashing
│   │   ├── import_data.py     # Main data import with batch processing
│   │   └── import_pax_data.py # PAX convention games import
│   ├── database/              # SQLite database and ML files
│   │   ├── boardgames.db      # Main SQLite database
│   │   ├── images/            # Game cover images (1000+ files)
│   │   ├── *.npz              # Sparse matrix embeddings
│   │   └── *.json             # Game-to-index mappings
│   ├── tests/                 # Comprehensive test suite
│   │   ├── test_db_queries.py # Database connectivity tests
│   │   ├── test_performance.py # API performance benchmarks
│   │   └── create_indexes.py  # Database optimization
│   ├── logs/                  # Application logs with rotation
│   ├── alembic/               # Database migrations
│   └── run_tests.py           # Test runner with batch execution
├── crawler/                   # BGG data collection pipeline
│   ├── src/                   # 3-stage crawler implementation
│   │   ├── get_ranks.py       # BGG rankings scraper (Selenium)
│   │   ├── get_game_data.py   # Detailed game info (BGG API)
│   │   ├── get_ratings.py     # User ratings collection
│   │   ├── data_processor.py  # Data normalization and CSV generation
│   │   ├── create_embeddings.py # ML embeddings generation
│   │   └── download_images.py # Game image downloader
│   └── notebooks/             # Development and analysis notebooks
├── frontend/                  # React SPA with Material-UI
│   ├── src/
│   │   ├── components/        # Reusable React components
│   │   │   ├── GameList.js    # Main game listing with filters
│   │   │   ├── GameDetails.js # Game detail modal with recommendations
│   │   │   ├── Navbar.js      # Navigation with auth integration
│   │   │   └── *.js           # Additional UI components
│   │   ├── context/           # React Context providers
│   │   │   └── AuthContext.js # Authentication state management
│   │   ├── pages/             # Page-level components
│   │   │   └── LoginPage.js   # User authentication page
│   │   └── services/          # API service layer
│   └── build/                 # Production build output
├── data/                      # Data storage and processing
│   ├── crawler/               # Raw BGG data (Parquet files)
│   ├── processed/             # Normalized CSV files (12+ types)
│   └── pax/                   # PAX convention game data
├── scripts/                   # Build and deployment scripts
│   ├── build-for-production.sh # Frontend build automation
│   └── upload_to_fly_volume.sh # Fly.io deployment helper
└── fly.toml                   # Fly.io deployment configuration
```

## Architecture Overview

### System Architecture
The application follows a modern microservices-inspired architecture with clear separation of concerns:

1. **Data Pipeline**: Multi-stage BGG crawler → Data processing → Collaborative filtering embeddings → Database import
2. **Backend API**: FastAPI with SQLAlchemy, JWT auth, and collaborative filtering recommendation engine
3. **Frontend SPA**: React with Material-UI, React Query caching, and authentication context
4. **Deployment**: Dockerized application on Fly.io with persistent data volumes

### Key Components

#### Recommendation Engine (`backend/app/recommender.py`)
- **ModelManager Singleton**: Lazy-loading of sparse matrix embeddings
- **Cosine Similarity**: Game-to-game recommendations using CSR matrices
- **Anti-Recommendations**: Support for games users want to avoid
- **Fallback System**: Random recommendations when embeddings unavailable
- **PAX Integration**: Filters recommendations for PAX convention games

#### Authentication System (`backend/app/security.py`)
- **JWT Tokens**: Secure stateless authentication
- **Password Hashing**: Bcrypt for secure password storage
- **Role-Based Access**: Admin and regular user permissions
- **Token Refresh**: Automatic token renewal for persistent sessions

#### Data Processing Pipeline
1. **Rankings Collection**: Selenium-based BGG ranking scraper
2. **Game Data**: BGG API integration with batch processing and rate limiting
3. **User Ratings**: Community rating data collection
4. **Normalization**: CSV generation for 12+ entity types (mechanics, categories, etc.)
5. **Embeddings**: Sparse matrix generation for collaborative filtering recommendations

#### Performance Optimizations
- **Thread Pool Executor**: 25-second timeout for database operations
- **In-Memory Caching**: TTL cache for filter options and mechanics
- **Database Indexes**: Composite indexes for complex queries
- **React Query**: 24-hour GC with 30-minute stale time
- **Lazy Loading**: On-demand embedding and relationship loading

## Technology Stack

### Backend
- **FastAPI**: High-performance web framework with automatic API documentation
- **SQLAlchemy**: ORM with SQLite database for data persistence
- **Collaborative Filtering**: SciPy, scikit-learn for recommendation embeddings
- **Authentication**: JWT tokens with bcrypt password hashing
- **Data Processing**: Pandas, NumPy for data manipulation and analysis

### Frontend
- **React 18**: Modern React with hooks and functional components
- **Material-UI (MUI)**: Comprehensive React component library
- **React Query**: Data fetching, caching, and synchronization
- **React Router**: Client-side routing and navigation
- **Axios**: HTTP client for API communication

### Data Collection
- **Selenium**: Web scraping for BoardGameGeek rankings
- **Requests**: HTTP client for BGG API data collection
- **BeautifulSoup**: HTML parsing and data extraction

### Deployment
- **Docker**: Containerized application deployment
- **Fly.io**: Cloud platform with persistent volumes
- **Alembic**: Database migration management

## Prerequisites

- Python 3.10+
- Node.js 16+
- Chrome/Chromium (for web scraping)
```bash
sudo apt-get update
sudo apt-get install -y chromium-browser chromium-chromedriver
```
- Poetry (Python package manager)
- Docker (for deployment)

## Quick Start

For development, both servers are typically running. The backend serves the API at `http://localhost:8000` and the frontend at `http://localhost:3000`.

## Setup

### 1. Python Environment Setup

```bash
# Install Poetry if you haven't already
curl -sSL https://install.python-poetry.org | python3 -

# Setup Python environment
poetry install
eval $(poetry env activate)  # Activate environment (use this instead of poetry shell)
```

**Important**: Always use `eval $(poetry env activate)` before running backend commands. This ensures proper environment activation for all Python operations.

### 2. Frontend Setup

```bash
cd frontend
npm install
```

### 3. Environment Configuration

Create a `.env` file in the project root for local development:

```env
# Database configuration
DATABASE_PATH=backend/database/boardgames.db

# JWT authentication
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Development settings
DEBUG=true

# BoardGameGeek credentials
BGG_USERNAME=
BGG_PASSWORD=
```

## Data Collection and Processing

The crawler collects data from BoardGameGeek.com in a 3-stage pipeline. Always activate the Poetry environment first:

```bash
eval $(poetry env activate)
```

### 1. Collect Board Game Rankings

```bash
python crawler/src/get_ranks.py
```

This will:
- Authenticate with BoardGameGeek
- Download current board game rankings
- Save to `data/crawler/boardgame_ranks_YYYYMMDD.csv`

### 2. Collect Detailed Game Data

```bash
python crawler/src/get_game_data.py
```

This will:
- Process games in batches of 20 (BGG API limit)
- Collect detailed information for each game
- Save to `data/crawler/boardgame_data_TIMESTAMP.parquet`

### 3. Collect User Ratings

```bash
python crawler/src/get_ratings.py
```

This will:
- Process games in batches
- Collect user ratings for each game
- Persist ratings to a DuckDB database at `data/crawler/ratings.duckdb` during crawling
- After completion, export a snapshot to `data/crawler/boardgame_ratings_TIMESTAMP.parquet`

The `get_game_data` and `get_ratings` scripts support the `--continue-from-last` flag to resume from the most recent output file if the process was interrupted:

```bash
python crawler/src/get_game_data.py --continue-from-last
python crawler/src/get_ratings.py --continue-from-last
```

#### DuckDB Ratings Backend

The ratings crawler now writes all raw ratings into a persistent DuckDB database. This exists alongside the main SQLite backend and is used only for ratings collection and snapshots.

- Location: `data/crawler/ratings.duckdb`
- Table: `boardgame_ratings(game_id BIGINT, rating_round DOUBLE, username TEXT)`
- Index: `idx_boardgame_ratings` on `(game_id, rating_round, username)`

Setup (one-time):

```bash
# Ensure poetry env is active
eval $(poetry env activate)

# DuckDB is installed via Poetry dependencies automatically
poetry install
```

Usage notes:
- Crawling streams inserts to DuckDB and de-duplicates on `(game_id, rating_round, username)`.
- On completion, a Parquet snapshot in the previous "wide" format is exported to `boardgame_ratings_TIMESTAMP.parquet` so downstream processing remains unchanged.
- `--continue-from-last` prefers the DuckDB snapshot as the resume seed if present, otherwise falls back to the latest Parquet file.

### 4. Process the Data

```bash
python crawler/src/data_processor.py
```

This will:
- Combine rankings and detailed game data
- Process relationships (mechanics, categories, etc.)
- Generate 12+ normalized CSV files in `data/processed/`:
  - `processed_games_data_TIMESTAMP.csv` - Basic game info
  - `processed_games_boardgamecategory_TIMESTAMP.csv` - Categories
  - `processed_games_boardgamemechanic_TIMESTAMP.csv` - Mechanics
  - `processed_games_boardgamedesigner_TIMESTAMP.csv` - Designers
  - `processed_games_boardgameartist_TIMESTAMP.csv` - Artists
  - `processed_games_boardgamepublisher_TIMESTAMP.csv` - Publishers
  - Plus 6 additional relationship files (families, expansions, etc.)

### 5. Generate Collaborative Filtering Embeddings

```bash
python crawler/src/create_embeddings.py
```

This creates:
- Sparse matrix embeddings (`.npz` files) for collaborative filtering recommendations
- Game-to-index mapping files (`.json`) for lookups
- Embeddings are stored in `backend/database/` for the recommendation engine

## Importing Data to Backend

Ensure the Poetry environment is activated:

```bash
eval $(poetry env activate)
```

Then run the import script:

```bash
python backend/app/import_data.py
```

This will:
- Find the most recent processed games files
- Import all games and related entities into the database
- Process data in batches of 200 games
- Log progress to `backend/logs/import_data.log`

You can also delete the existing database before import:

```bash
python backend/app/import_data.py --delete-existing
```

### PAX Convention Data Import

Import PAX tabletop games data for special filtering:

```bash
python backend/app/import_pax_data.py
```

This will:
- Find the most recent PAX games file in `data/pax/`
- Import PAX games and link them to existing BoardGame records via BGG ID
- Enable PAX-only filtering in the application
- Log progress to `backend/logs/import_pax_data.log`

## Testing

### Running Tests

From the backend directory:

```bash
# Using the test runner script
python run_tests.py test_db_queries
python run_tests.py create_indexes
python run_tests.py all

# Or directly
python tests/test_db_queries.py
python tests/create_indexes.py
```

### Test Files

- **`test_db_queries.py`**: Tests basic database queries to ensure they work without hanging
- **`test_performance.py`**: Tests API endpoint performance improvements (requires server running)
- **`create_indexes.py`**: Creates database indexes for better query performance

### Expected Performance Benchmarks

- Simple games query: ~60-100ms
- Games with search: ~150-200ms
- Games with filters: ~100-150ms
- Mechanics query: ~50-100ms

## Logging

### Viewing Logs

```bash
# View recent logs
tail -f backend/logs/import_data.log
tail -f backend/logs/import_pax_data.log
```

### Log Files

- **`backend/logs/import_data.log`**: Main data import process logs
- **`backend/logs/import_pax_data.log`**: PAX games import process logs
- **`backend/logs/data_processor.log`**: Data processing operations
- **`backend/logs/get_ratings.log`**: Rating data collection
- **`backend/logs/get_game_data.log`**: Game data collection
- **`backend/logs/image_downloader.log`**: Image download operations

### Log Rotation

For production, consider implementing log rotation:

```bash
# Add to crontab for weekly log cleanup
0 0 * * 0 find backend/logs -name "*.log" -mtime +30 -delete
```

## Running the Development Servers

### Backend Server

Activate the Poetry environment and start the server:

```bash
eval $(poetry env activate)
uvicorn backend.app.main:app --reload
```

**Development Features**:
- Auto-reload on file changes (no manual restart needed)
- Interactive API documentation at `http://localhost:8000/docs`
- Thread pool execution with 25-second timeouts
- CORS enabled for frontend development
- JWT authentication endpoints available

### Frontend Server

```bash
cd frontend
npm start
```

**Development Features**:
- Hot-reload React development server
- Material-UI theming and components
- React Query caching with offline support
- Authentication context with automatic token refresh
- Available at `http://localhost:3000`

## API Endpoints

The FastAPI backend provides a comprehensive REST API with automatic OpenAPI documentation at `/docs`.

### Game Endpoints
```
GET /games                              # List games with filtering and pagination
GET /games/{game_id}                    # Get detailed game information
GET /games/{game_id}/recommendations    # Get collaborative filtering recommendations
```

**Game Filtering Parameters**:
- `search`: Text search in game names and descriptions
- `mechanics`: Filter by game mechanics (comma-separated)
- `categories`: Filter by game categories
- `min_players`, `max_players`: Player count filtering
- `min_playtime`, `max_playtime`: Game duration filtering
- `min_weight`, `max_weight`: Complexity filtering (1-5 scale)
- `min_rating`: Minimum BGG rating
- `pax_only`: Show only PAX convention games
- `limit`, `offset`: Pagination controls

### Filter Options Endpoints
```
GET /mechanics      # List all available game mechanics
GET /categories     # List all game categories
GET /designers      # List all game designers
GET /artists        # List all game artists
GET /publishers     # List all game publishers
```

### Authentication Endpoints
```
POST /auth/register              # Create new user account
POST /auth/login                 # User login (returns JWT token)
POST /auth/change-password       # Change user password (authenticated)
GET /auth/me                     # Get current user information
```

### User Management (Admin Only)
```
GET /users                       # List all users
POST /users                      # Create new user
DELETE /users/{user_id}          # Delete user account
```

### User Suggestions
```
POST /suggestions                # Submit game suggestions
GET /suggestions                 # List suggestions (admin only)
```

### Performance
- **Expected Response Times**: 60-200ms for most endpoints
- **Caching**: In-memory TTL cache for filter options
- **Timeouts**: 25-second timeout protection
- **Rate Limiting**: Implemented for data collection endpoints

## Deployment & Production

### Production Build

Build the frontend for production deployment:

```bash
# Build frontend and prepare for deployment
./scripts/build-for-production.sh
```

This script:
- Builds the React frontend with production optimizations
- Copies build files to backend static directory
- Prepares the application for containerized deployment

### Fly.io Deployment

The application is configured for deployment on Fly.io with persistent data storage:

```bash
# Deploy to Fly.io
flyctl deploy
```

**Deployment Features**:
- **Dockerized Application**: Multi-stage build with Python and Node.js
- **Persistent Volumes**: Database and embeddings stored on mounted volume
- **Health Checks**: Automatic restart on failure
- **Auto-scaling**: Stop/start machines based on traffic
- **Environment Configuration**: Production environment variables

### Docker Configuration

The application uses a multi-stage Dockerfile:
1. **Frontend Build Stage**: Node.js environment for React build
2. **Python Runtime Stage**: Poetry-based Python environment
3. **Production Stage**: Optimized runtime with frontend and backend

### Environment Variables (Production)

```env
# Database (Fly.io)
DATABASE_PATH=/data/boardgames.db

# Authentication
SECRET_KEY=production-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Production settings
DEBUG=false
ALLOWED_HOSTS=your-app.fly.dev
```

### Production Data Management

```bash
# Upload data to Fly.io volume
./scripts/upload_to_fly_volume.sh

# Connect to production database
flyctl ssh console
```

### Monitoring & Maintenance

- **Logs**: Access via `flyctl logs`
- **Health Checks**: Built-in HTTP health endpoints
- **Database Backups**: Automatic volume snapshots
- **Performance Monitoring**: Response time tracking
- **Error Handling**: Comprehensive exception management

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Key Features

### Collaborative Filtering Recommendations
- **Recommendation Engine**: Uses collaborative filtering with sparse matrix embeddings
- **Cosine Similarity**: Finds games with similar user rating patterns
- **Anti-Recommendations**: Avoids suggesting games users explicitly dislike
- **Fallback System**: Provides random recommendations when embedding data unavailable
- **Real-time Performance**: Sub-200ms recommendation generation

### User Authentication & Management
- **Secure Authentication**: JWT tokens with bcrypt password hashing
- **Role-Based Access**: Admin users can manage all users and view suggestions
- **User Registration**: Self-service account creation
- **Password Management**: Secure password change functionality
- **Session Management**: Automatic token refresh and logout

### PAX Convention Integration
- **PAX Game Database**: Special collection of PAX tabletop games
- **PAX-Only Filtering**: View only games available at PAX conventions
- **BGG Integration**: Links PAX games to full BoardGameGeek data
- **Convention Planning**: Helps attendees discover games at events

### Advanced Game Discovery
- **Multi-Criteria Search**: Name, description, mechanics, categories
- **Smart Filtering**: Player count, playtime, complexity, rating
- **Dynamic UI**: Material-UI components with responsive design
- **Performance Optimization**: React Query caching and lazy loading
- **Guided Tours**: Interactive help system for new users

### Data Pipeline & Quality
- **3-Stage Crawler**: Rankings → Game Data → User Ratings
- **BGG API Integration**: Respects rate limits with batch processing
- **Data Normalization**: 12+ entity types properly normalized
- **Error Resilience**: Robust error handling and retry mechanisms
- **Incremental Updates**: Resume interrupted crawls with `--continue-from-last`

## Maintenance & Development

### Testing
```bash
# Run comprehensive test suite
python backend/run_tests.py all

# Performance benchmarks
python backend/run_tests.py test_performance

# Database optimization
python backend/run_tests.py create_indexes
```

### Monitoring
- **Performance Benchmarks**: Expected API response times documented
- **Database Optimization**: Composite indexes for complex queries
- **Log Management**: Structured logging with rotation support
- **Health Checks**: Built-in application health monitoring

## License

This project is licensed under the MIT License - see the LICENSE file for details.

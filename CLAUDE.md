# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a full-stack board game recommendation system that crawls BoardGameGeek.com data and provides AI-powered recommendations. The system consists of:

- **Backend**: FastAPI with SQLAlchemy, recommendation engine using sparse matrix embeddings
- **Frontend**: React with Material-UI and React Query for state management
- **Data Pipeline**: Multi-stage BGG crawler with processing and embedding generation
- **Deployment**: Dockerized application deployed on Fly.io

## Essential Commands

### Environment Setup
```bash
# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Setup Python environment
poetry install
eval $(poetry env activate)  # Always activate this before running backend commands

# Frontend setup
cd frontend && npm install
```

### Development Servers
```bash
# Backend server (requires eval $(poetry env activate))
eval $(poetry env activate)
uvicorn backend.app.main:app --reload

# Frontend server
cd frontend && npm start
```

### Data Collection Pipeline (3-step process)
```bash
# Step 1: Collect rankings
python crawler/src/get_ranks.py

# Step 2: Collect detailed game data
python crawler/src/get_game_data.py

# Step 3: Collect user ratings
python crawler/src/get_ratings.py

# Process collected data
python crawler/src/data_processor.py

# Import into database
python backend/app/import_data.py
```

### Testing
```bash
# Run all tests
python backend/run_tests.py all

# Run specific tests
python backend/run_tests.py test_db_queries
python backend/run_tests.py test_performance
python backend/run_tests.py create_indexes
```

### Production Build
```bash
# Build frontend and prepare for deployment
./scripts/build-for-production.sh

# Deploy to Fly.io
flyctl deploy
```

## Architecture Overview

### Backend Architecture (`backend/app/`)
- **main.py**: FastAPI application with CORS, compression, caching, and timeout handling
- **models.py**: SQLAlchemy models for BoardGame and 15+ related entities (mechanics, categories, designers, etc.)
- **crud.py**: Database operations with complex filtering and recommendation logic
- **recommender.py**: Recommendation engine using sparse matrix embeddings with ModelManager singleton
- **schemas.py**: Pydantic models for API serialization
- **database.py**: Database configuration with custom StaticFiles handling

### Frontend Architecture (`frontend/src/`)
- **App.js**: Main React app with routing, theming, and React Query setup
- **components/GameList.js**: Primary game listing component with filtering and pagination
- **components/GameDetails.js**: Game detail modal with recommendation integration
- React Query for caching with 24-hour GC time and 30-minute stale time

### Data Pipeline Architecture (`crawler/src/`)
- **get_ranks.py**: Scrapes BGG rankings using Selenium
- **get_game_data.py**: Collects detailed game info via BGG API (batch processing)
- **get_ratings.py**: Collects user ratings data
- **data_processor.py**: Processes raw data into normalized CSV files
- **create_embeddings.py**: Generates sparse matrix embeddings for recommendations

### Database Schema
- **BoardGame**: Primary entity with ratings, rankings, and metadata
- **Related entities**: Mechanics, Categories, Designers, Artists, Publishers, etc.
- **PAXGame**: Links PAX convention games to BoardGame records via bgg_id
- **User/Auth**: Basic user authentication with admin roles
- **Alembic migrations**: Database versioning in `backend/alembic/`

### Recommendation System
- Uses sparse matrix embeddings (CSR format) stored in `.npz` files
- Game-to-index mapping stored in JSON files
- Cosine similarity for recommendations with anti-recommendation support
- Fallback to random games when embeddings unavailable
- Integrated with PAX-only filtering

## Key Technical Patterns

### Performance Optimizations
- Thread pool executor for database operations with 25-second timeouts
- In-memory caching with TTL for filter options and mechanics
- Lazy loading of relationships in SQLAlchemy models
- React Query caching with offline-first strategy

### Error Handling
- Comprehensive exception handlers in FastAPI
- Timeout wrappers for database operations
- Fallback mechanisms for missing embeddings
- Detailed logging throughout the application

### Development Workflow
1. **Data Collection**: Run 3-step crawler pipeline to collect BGG data
2. **Processing**: Process raw data into normalized format
3. **Import**: Load processed data into SQLite database
4. **Embeddings**: Generate recommendation embeddings
5. **Testing**: Run performance and query tests
6. **Development**: Use hot-reload servers for frontend/backend

### Production Deployment
- Dockerized with multi-stage build
- Fly.io deployment with persistent volumes for data
- Health checks and automatic restarts
- Environment-based configuration for database and image paths

## File Structure Context

```
├── backend/app/          # FastAPI backend with ML recommendations
├── frontend/src/         # React frontend with Material-UI
├── crawler/src/          # BGG data collection pipeline
├── data/                 # Raw and processed data storage
│   ├── crawler/         # BGG crawler outputs
│   ├── processed/       # Normalized CSV files
│   └── pax/            # PAX convention game data
├── backend/database/    # SQLite database and embeddings
├── backend/tests/       # Database and performance tests
└── scripts/             # Build and deployment scripts
```

## Common Development Tasks

### Adding New Filters
1. Add filter logic to `crud.py` get_games function
2. Update `schemas.py` FilterOptions model
3. Add UI components to `GameList.js`
4. Test with performance benchmarks

### Modifying Recommendation Logic
1. Update `recommender.py` get_recommendations function
2. Test with dummy data fallback
3. Regenerate embeddings if needed
4. Update API endpoints in `main.py`

### Database Schema Changes
1. Create Alembic migration: `alembic revision --autogenerate -m "description"`
2. Update `models.py` with new fields/relationships
3. Run migration: `alembic upgrade head`
4. Update import scripts if needed

### Performance Monitoring
- Expected API response times: 60-200ms for most endpoints
- Database query optimization through indexes
- Monitor thread pool utilization
- React Query cache hit rates
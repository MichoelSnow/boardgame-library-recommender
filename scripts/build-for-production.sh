#!/bin/bash

echo "Building for production..."

# 1. Build frontend
echo "Building frontend..."
cd frontend
npm run build
cd ..

# 2. Copy frontend build to backend
echo "Copying frontend build..."
cp -r frontend/build backend/

echo "Build complete!" 
You're absolutely right. Let me revise the plan with clear pass/fail conditions and decision paths for each step:

# Systematic Troubleshooting Plan with Decision Paths

## 1. Verify Server Status
```
ps aux | grep uvicorn
pkill -f uvicorn
lsof -i :8000
```
- **PASS**: No processes using port 8000
  → Proceed to step 2
- **FAIL**: Processes still using port 8000
  → Run `sudo fuser -k 8000/tcp` to forcibly free the port, then retry

## 2. Start Fresh Server
```
uvicorn backend.app.main:app --reload
```
- **PASS**: Server starts without errors
  → Proceed to step 3
- **FAIL**: Server fails to start
  → Check error messages. If port conflict, return to step 1. If code errors, fix them first.

## 3. Verify API Documentation
```
curl http://localhost:8000/docs
```
- **PASS**: Returns HTML content with Swagger UI
  → Look for token endpoints in the documentation. Are both `/token` and `/api/token` listed?
  - If yes → Proceed to step 4
  - If no → Skip to step 5
- **FAIL**: Returns error or empty response
  → Server is not running properly. Return to step 2.

## 4. Test Token Endpoints with Form Data
```
curl -X POST http://localhost:8000/token -F "username=admin" -F "password=admin123" -v
```
- **PASS**: Returns JSON with access_token
  → The root token endpoint works. Proceed to step 7 to test frontend.
- **FAIL**: Returns 405 Method Not Allowed
  → There's a route conflict. Proceed to step 5.
- **FAIL**: Returns 401 Unauthorized
  → Authentication works but credentials are wrong. Try creating a new admin user in step 6.

## 5. Examine Route Conflicts
```
python -c "from backend.app.main import app; print([{'path': r.path, 'methods': getattr(r, 'methods', None), 'name': r.name} for r in app.routes if hasattr(r, 'path')])"
```
- **PASS**: Shows `/token` with POST method
  → Check the order of route definitions. Proceed to step 6.
- **FAIL**: No `/token` route or it doesn't have POST method
  → The endpoint is not properly defined. Fix the route definition in main.py:
  ```python
  @app.post("/token", response_model=schemas.Token)
  async def login_for_access_token_root(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
      # ...authentication logic...
  ```

## 6. Check Static Files Mount
Examine main.py for the order of route definitions:
```
grep -A 10 "app.mount" backend/app/main.py
```
- **PASS**: Static files mount comes after token endpoint definition
  → Proceed to step 7
- **FAIL**: Static files mount comes before token endpoint
  → Move the static files mount after all API route definitions:
  ```python
  # Define all API routes first
  # ...
  
  # Then mount static files
  if os.path.exists(STATIC_DIR):
      app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="frontend")
  ```

## 7. Create New Admin User
```
python -c "from backend.app.security import create_initial_admin; create_initial_admin('newadmin', 'newpassword')"
```
- **PASS**: Message "Admin user created" or "already exists"
  → Proceed to step 8
- **FAIL**: Database error
  → Fix database connection issues first

## 8. Test Token Endpoint with New User
```
curl -X POST http://localhost:8000/token -F "username=newadmin" -F "password=newpassword" -v
```
- **PASS**: Returns JSON with access_token
  → Authentication works. Proceed to step 9.
- **FAIL**: Still getting 405 or other errors
  → The issue is deeper in the FastAPI routing. Proceed to step 10.

## 9. Test Frontend Login Form
Open browser developer tools (Network tab) and attempt login with the new credentials.
- **PASS**: Network request succeeds with 200 status
  → Frontend authentication works. Problem solved!
- **FAIL**: Network request fails with 405 status
  → Check the request URL. Is it using the correct endpoint? Proceed to step 10.

## 10. Debug OAuth2 Configuration
```
grep -A 3 "OAuth2PasswordBearer" backend/app/security.py
```
- **PASS**: Shows `tokenUrl="api/token"` or `tokenUrl="token"`
  → If it's `"api/token"`, change to `"token"` or vice versa to match the endpoint that works
- **FAIL**: OAuth2 configuration is missing or incorrect
  → Fix the OAuth2 configuration:
  ```python
  oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
  ```

## 11. Create Minimal Test Form
Create a simple HTML file (test_login.html):
```html
<!DOCTYPE html>
<html>
<body>
<form action="http://localhost:8000/token" method="post" enctype="application/x-www-form-urlencoded">
  <input type="text" name="username" value="newadmin">
  <input type="password" name="password" value="newpassword">
  <input type="submit" value="Submit">
</form>
</body>
</html>
```
Open this file in a browser and submit the form.
- **PASS**: Redirects with token response
  → The issue is specific to the React frontend. Check frontend API configuration.
- **FAIL**: Shows 405 error
  → The issue is with the backend endpoint. Return to step 5.

## 12. Final Resort - Bypass FastAPI Routing
If all else fails, implement a direct Flask-style route handler:
```python
@app.route("/token", methods=["POST"])
async def raw_token_endpoint(request: Request):
    form_data = await request.form()
    username = form_data.get("username")
    password = form_data.get("password")
    
    # Manual authentication
    db = SessionLocal()
    try:
        user = crud.authenticate_user(db, username, password)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"detail": "Incorrect username or password"}
            )
        
        access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = security.create_access_token(
            data={"sub": username}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}
    finally:
        db.close()
```

This step-by-step plan should help systematically identify and fix the login issue by eliminating potential causes one by one.
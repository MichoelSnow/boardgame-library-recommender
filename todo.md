# Data
- download all images into a database for faster calling
    - script finished, partially downloaded games
- precompute recommendations for all games for the dialog boxes


# UI 
- IN the dialog see the preferred and best player counts

# Code
- Move to python 3.12
- After the Python upgrade, simplify backend/app/versioning.py to rely on stdlib tomllib only (remove the fallback parser path if no longer needed)

# App
- Allow for multiple selection in player count
- Sort categories and mechanics alphabetically
- align the categories and mechanics into a fixed grid if possible
- The ability to send yourself the list of recs via email or SMS
- heavier lift: add a tag search

# Fly.io
- Add redundancy to the server of having multiple volumes at the same time, in case one volume goes down
- Add user logging, e.g., last login time

# Notebooks
- Add back in google-api-python-client, google-auth-httplib2, and google-auth-oauthlib for crawler/notebooks/pax_tabletop_library.ipynb

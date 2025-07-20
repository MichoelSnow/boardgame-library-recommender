# Data
- download all images into a database for faster calling
    - script finished, partially downloaded games
- precompute recommendations for all games for the dialog boxes


# UI 
- IN the dialog see the preferred and best player counts

# Code
- Move to python 3.12

# App
- Allow for multiple selection in player count
- Sort categories and mechanics alphabetically
- align the categories and mechanics into a fixed grid if possible
- The ability to send yourself the list of recs via email or SMS
- Add "+" to last player count option, as it returns all games with player counts of 12 or more
    - That's actually not true.  If a game has a min player count of 13, the 12 player count will not return that game, e.g., "Court in the Act" and "CreaCity"
- heavier lift: add a tag search

# Fly.io
- Add redundancy to the server of having multiple volumes at the same time, in case one volume goes down
- Add user logging, e.g., last login time

# 2025-09-20
- backend changes
    - get_ratings now builds ratings using duckdb, writing all data to the database file instead of keeping everything in memory. This makes the script much faster and requires a lot less memory
    - Switched to using .env for BGG login creds when downloading rank data
    - Added functionality to import_data script to run SQL scripts post import such as calculate avg_box_volume
    - when updating the database through the import script only delete the boardgame data, not user data


# 2025-09-09
- changed the app config to auto-stop the machine
    - If there is no traffic to the site for a few minutes then the site will shut down.  When someone visits the site it will start up again.  The start up time is about a minute.

# 2025-08-17
- small games section indicator
    - created a new column in the games table called avg_box_volume which calculates the average box volume in inches
    - added avg_box_volume to the BoardGame(Base) model
    - modified the library icon with an asterisk for games in the library which have a volume of 100 inches cubed or less to indicate that they are in the small games section of the library

# 2025-07-20
- updated the mechanics and categories filters
    - alphabetized the values
    - changed from tiling to grid
- added results count on the bottom of the page next to the pagination

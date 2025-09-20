-- Calculate and update the avg_box_volume for all games
-- This script calculates the average box volume from English versions
-- and updates the games table with the calculated values.

-- Note: This script assumes the avg_box_volume column already exists.
-- If it doesn't exist, the script will fail with an error.
-- The column should be created by the database schema or migrations.

-- Update the avg_box_volume values
UPDATE games
SET avg_box_volume = (
    WITH vol AS (
        SELECT game_id,
               ROUND(AVG(length * width * depth)) AS volume_avg
        FROM versions
        WHERE language = 'english'
        GROUP BY 1
    )
    SELECT vol.volume_avg
    FROM vol
    WHERE vol.game_id = games.id
);

-- Ensure the index exists (will be ignored if it already exists)
CREATE INDEX IF NOT EXISTS ix_games_avg_box_volume ON games (avg_box_volume);

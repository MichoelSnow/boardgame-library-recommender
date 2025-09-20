"""
BoardGameGeek (BGG) Rankings Crawler

This script crawls the current board game rankings from BoardGameGeek.com.
This is the first script in the data collection pipeline and should be run before get_game_data.py.

Execution order:
1. get_ranks.py - Gets the current board game rankings
2. get_game_data.py - Gets detailed game information
3. get_ratings.py - Gets user ratings for each game

Usage:
    python get_ranks.py 
"""

from bs4 import BeautifulSoup
import os
import requests
from zipfile import ZipFile
from io import BytesIO
from datetime import datetime
import pandas as pd
import logging
import csv
from pathlib import Path
from time import sleep

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from dotenv import load_dotenv, find_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("get_ranks.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

def get_driver_and_cookies():
    """
    Initialize Selenium WebDriver and authenticate with BoardGameGeek.
    Returns authentication cookies needed for subsequent API requests.

    Returns:
        dict: Authentication cookies for BGG API requests
    """
    logger.info("Initializing web driver and getting cookies")
    LOGIN_USERNAME_FIELD = '//*[@id="inputUsername"]'
    LOGIN_PASSWORD_FIELD = '//*[@id="inputPassword"]'
    LOGIN_BUTTON = '//*[@id="mainbody"]/div/div/gg-login-page/div[1]/div/gg-login-form/form/fieldset/div[3]/button[1]'

    load_dotenv(find_dotenv())
    USERNAME = os.getenv("BGG_USERNAME")
    PASSWORD = os.getenv("BGG_PASSWORD")
    if not USERNAME or not PASSWORD:
        logger.error("Missing BGG_USERNAME or BGG_PASSWORD in environment")
        raise ValueError("Missing BGG_USERNAME or BGG_PASSWORD in environment")

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    cookies = {}

    driver = webdriver.Chrome(
        service=Service("/usr/lib/chromium-browser/chromedriver"),
        options=chrome_options,
    )
    logger.info("Chrome driver initialized successfully")

    driver.get("https://boardgamegeek.com/login")
    login = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, LOGIN_USERNAME_FIELD))
    )
    password = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, LOGIN_PASSWORD_FIELD))
    )

    login_button = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, LOGIN_BUTTON))
    )

    login.send_keys(USERNAME)
    password.send_keys(PASSWORD)

    login_button.click()
    sleep(1)
    logger.info("Successfully logged in to BoardGameGeek")

    selenium_cookies = driver.get_cookies()
    for cookie in selenium_cookies:
        cookies[cookie["name"]] = cookie["value"]
    logger.info("Successfully retrieved cookies")
    return cookies

def get_boardgame_ranks(cookies: dict, save_file: bool = False):
    """
    Download the current board game rankings from BGG.

    Args:
        cookies (dict): Authentication cookies from get_driver_and_cookies()
        save_file (bool): Whether to save the rankings to a CSV file

    Returns:
        pd.DataFrame: DataFrame containing board game rankings
    """
    logger.info("Fetching boardgame ranks")
    bg_ranks_pg_url = "https://boardgamegeek.com/data_dumps/bg_ranks"
    resp = requests.get(bg_ranks_pg_url, cookies=cookies)
    soup = BeautifulSoup(resp.content, "html.parser")
    bg_ranks_url = soup.find("div", {"id": "maincontent"})("a")[0]["href"]
    bg_ranks_zip = requests.get(bg_ranks_url)
    queried_at_utc = datetime.now().replace(microsecond=0).isoformat()
    
    with ZipFile(BytesIO(bg_ranks_zip.content)) as archive:
        with archive.open("boardgames_ranks.csv") as csv_file:
            df_bg_ranks = pd.read_csv(csv_file)
            df_bg_ranks["name"] = df_bg_ranks["name"].str.replace("[“”]", '"', regex=True)
            df_bg_ranks["queried_at_utc"] = queried_at_utc
            logger.info(f"Successfully loaded {len(df_bg_ranks)} boardgames")
            if save_file:
                # Create data directory if it doesn't exist
                data_dir = Path(__file__).parent.parent.parent / "data" / "crawler"
                data_dir.mkdir(parents=True, exist_ok=True)
                
                output_file = data_dir / f"boardgame_ranks_{queried_at_utc[:10].replace('-','')}.csv"
                df_bg_ranks.to_csv(
                    output_file,
                    index=False,
                    sep="|",
                    escapechar="\\",
                    quoting=csv.QUOTE_NONE,
                )
                logger.info(f"Saved rankings to {output_file}")
            return df_bg_ranks

def main():
    """Main function to get board game rankings."""
    try:
        cookies = get_driver_and_cookies()
        _ = get_boardgame_ranks(cookies, save_file=True)
        logger.info("Successfully completed getting board game rankings")
    except Exception as e:
        logger.error(f"Error getting board game rankings: {str(e)}")
        raise

if __name__ == "__main__":
    main() 
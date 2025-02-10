# Refactored and Improved Lutris Cover Art Downloader

import requests
import sqlite3
import os
import inquirer

# Constants - Define configuration at the top for easy modification
API_KEY_FILE = './apikey.txt'
LUTRIS_DB_PATH_TEMPLATE = '/home/{user}/.local/share/lutris/pga.db'
BANNER_CACHE_PATH_TEMPLATE = '/home/{user}/.cache/lutris/banners/'
COVERART_CACHE_PATH_TEMPLATE = '/home/{user}/.cache/lutris/coverart/'
BANNER_DIMENSIONS = '460x215'
VERTICAL_DIMENSIONS = '600x900'
STEAMGRIDDB_API_BASE_URL = 'https://www.steamgriddb.com/api/v2'
COVER_ART_EXTENSIONS = ['.png', '.jpeg', '.jpg'] # Added list of extensions to check


def get_username():
    """
    Attempts to get the current user's username.

    Returns:
        str: The username if successful.
        None: If the username cannot be retrieved.
    """
    try:
        return os.getlogin()
    except OSError:
        print("Error: Could not get session username.")
        return None

def get_cover_type():
    """
    Prompts the user to choose between Steam banners or vertical covers.

    Returns:
        tuple: A tuple containing:
            - str: Dimensions string (e.g., '460x215').
            - str: Cover cache path.
    """
    questions = [
        inquirer.List(
            'cover_type',
            message="Select the type of cover art to download:",
            choices=['Banner', 'Vertical'],
        ),
    ]
    answers = inquirer.prompt(questions)
    if not answers:  # Handle user cancellation (e.g., Ctrl+C)
        print("Operation cancelled by user.")
        return None, None

    cover_type = answers['cover_type']
    print(f'Cover type set to {cover_type}\n')

    if cover_type == 'Banner':
        dimensions = BANNER_DIMENSIONS
        cache_path = BANNER_CACHE_PATH_TEMPLATE.format(user=username)
    else:  # 'Vertical'
        dimensions = VERTICAL_DIMENSIONS
        cache_path = COVERART_CACHE_PATH_TEMPLATE.format(user=username)
    return dimensions, cache_path

def save_api_key(api_key):
    """
    Saves the SteamGridDB API key to a file.

    Args:
        api_key (str): The API key to save.
    """
    try:
        with open(API_KEY_FILE, 'w') as f:
            f.write(api_key)
        print("API key saved successfully.")
    except IOError:
        print(f"Error: Could not save API key to '{API_KEY_FILE}'.")

def get_api_key_from_file():
    """
    Retrieves the SteamGridDB API key from the file.

    Returns:
        dict: Authorization header dictionary if API key is found, otherwise None.
    """
    if os.path.isfile(API_KEY_FILE):
        try:
            with open(API_KEY_FILE, 'r') as f:
                api_key = f.read().strip() # remove leading/trailing whitespaces
                return {'Authorization': 'Bearer ' + api_key}
        except IOError:
            print(f"Warning: Could not read API key from '{API_KEY_FILE}'.")
            return None
    return None

def set_api_key():
    """
    Prompts the user to enter their SteamGridDB API key and tests its validity.

    Returns:
        dict: Authorization header dictionary if API key is valid and saved, otherwise None.
    """
    print("API key not found.")
    print('You need a SteamGridDB API key to use this script.')
    print('You can get one by using your Steam account at: https://www.steamgriddb.com/profile/preferences/api\n')
    api_key = input("Enter your SteamGridDB API key: ").strip() # remove leading/trailing whitespaces
    if not api_key: # Handle empty input
        print("API key cannot be empty. Exiting.")
        return None

    auth_header = {'Authorization': 'Bearer ' + api_key}
    if test_api_key(auth_header):
        save_api_key(api_key)
        return auth_header
    return None

def test_api_key(auth_header):
    """
    Tests the validity of the SteamGridDB API key by making a request to the API.

    Args:
        auth_header (dict): Authorization header dictionary.

    Returns:
        bool: True if the API key is valid, False otherwise.
    """
    test_url = f'{STEAMGRIDDB_API_BASE_URL}/grids/game/1?dimensions={VERTICAL_DIMENSIONS}' # Using vertical as default test dimension
    try:
        response = requests.get(test_url, headers=auth_header)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        if response.status_code == 200:
            print("API key is valid.")
            return True
    except requests.exceptions.RequestException as e:
        print(f"Error testing API key: {e}")
    print("API key is invalid.")
    return False

def connect_to_db(db_path):
    """
    Connects to the Lutris SQLite database.

    Args:
        db_path (str): Path to the Lutris database file (pga.db).

    Returns:
        sqlite3.Connection: Database connection object if successful, None otherwise.
    """
    try:
        conn = sqlite3.connect(db_path)
        return conn
    except sqlite3.Error as e:
        print(f"Error: Could not connect to Lutris database '{db_path}'.")
        print(f"       Details: {e}")
        print("       Please ensure the path is correct or manually edit the script's path if necessary.")
        return None

def search_game_id(game_name, auth_header):
    """
    Searches for a game ID on SteamGridDB using the game name.

    Args:
        game_name (str): The name of the game to search for.
        auth_header (dict): Authorization header dictionary.

    Returns:
        int: The game ID if found, None otherwise.
    """
    search_url = f'{STEAMGRIDDB_API_BASE_URL}/search/autocomplete/{game_name}'
    try:
        response = requests.get(search_url, headers=auth_header)
        response.raise_for_status()
        data = response.json().get("data")
        if data and len(data) > 0:
            print(f"Found game: {game_name.replace('-', ' ').title()}")
            return data[0]["id"]
        else:
            print(f"Warning: Could not find a cover for game '{game_name}' on SteamGridDB.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error searching for game '{game_name}': {e}")
        return None

def download_cover(game_name, game_id, dimensions, cache_path, auth_header):
    """
    Downloads the cover art for a game from SteamGridDB.

    Args:
        game_name (str): The slug name of the game (from Lutris DB).
        game_id (int): The SteamGridDB game ID.
        dimensions (str): The desired dimensions of the cover art (e.g., '460x215').
        cache_path (str): The local path to save the cover art.
        auth_header (dict): Authorization header dictionary.
    """
    if not game_id:
        return

    print(f"Downloading cover for {game_name.replace('-', ' ').title()}...")
    grids_url = f'{STEAMGRIDDB_API_BASE_URL}/grids/game/{game_id}?dimensions={dimensions}'
    try:
        response = requests.get(grids_url, headers=auth_header)
        response.raise_for_status()
        grids_data = response.json().get("data")

        if grids_data and len(grids_data) > 0:
            cover_url = grids_data[0]["url"]
            cover_response = requests.get(cover_url, stream=True) # Use stream=True for efficient downloading
            cover_response.raise_for_status()

            filepath = os.path.join(cache_path, f'{game_name}.jpg')

            # **CREATE DIRECTORY IF IT DOESN'T EXIST:**
            os.makedirs(cache_path, exist_ok=True)

            with open(filepath, 'wb') as f:
                for chunk in cover_response.iter_content(chunk_size=8192): # Download in chunks
                    f.write(chunk)
            print(f"Cover saved to: {filepath}")
        else:
            print(f"Warning: Could not find a cover with dimensions '{dimensions}' for game '{game_name}' on SteamGridDB.")

    except requests.exceptions.RequestException as e:
        print(f"Error downloading cover for '{game_name}': {e}")


def get_games_list_from_db(db_conn, cache_path, dimensions, auth_header):
    """
    Retrieves the list of games from the Lutris database and downloads covers if they are missing.

    Args:
        db_conn (sqlite3.Connection): Database connection object.
        cache_path (str): The local path to save the cover art.
        dimensions (str): The desired dimensions of the cover art.
        auth_header (dict): Authorization header dictionary.
    """
    cursor = db_conn.cursor()
    cursor.execute('SELECT slug FROM games')
    games = cursor.fetchall()

    if not games:
        print("No games found in Lutris database.")
        return

    print("Checking and downloading covers...")
    for entry in games:
        game_slug = entry[0]
        cover_exists = False # Flag to track if a cover already exists

        for ext in COVER_ART_EXTENSIONS: # Iterate through extensions
            cover_filepath = os.path.join(cache_path, f'{game_slug}{ext}')
            if os.path.isfile(cover_filepath):
                cover_exists = True
                break # If one extension exists, no need to check others

        if not cover_exists:
            game_id = search_game_id(game_slug, auth_header)
            download_cover(game_slug, game_id, dimensions, cache_path, auth_header)
        else:
            print(f"Cover for '{game_slug.replace('-', ' ').title()}' already exists.")

    print('\nAll done! Restart Lutris for the changes to take effect.')


def main():
    """
    Main function to run the Lutris Cover Art Downloader script.
    """
    global username # Still using global here for initial username retrieval, can be passed around if preferred
    username = get_username()
    if not username:
        exit(1)
    print(f"Welcome {username} to Lutris Cover Art Downloader!\n")

    dimensions, cover_cache_path = get_cover_type()
    if not dimensions or not cover_cache_path: # Exit if user cancelled or error in cover type selection
        exit(0)

    lutris_db_path = LUTRIS_DB_PATH_TEMPLATE.format(user=username)
    db_conn = connect_to_db(lutris_db_path)
    if not db_conn:
        exit(1)

    print("Getting API Key...\n")
    auth_header = get_api_key_from_file()
    if not auth_header:
        auth_header = set_api_key()
        if not auth_header: # Exit if API key setup failed
            exit(1)

    get_games_list_from_db(db_conn, cover_cache_path, dimensions, auth_header)

    db_conn.close()


if __name__ == '__main__':
    main()
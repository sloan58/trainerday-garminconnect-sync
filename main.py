import logging.handlers
import os
import json
from datetime import datetime

import requests
import dropbox
from dotenv import load_dotenv
from garminconnect import Garmin, GarminConnectAuthenticationError
from garth.exc import GarthHTTPError

# Load environment variables from .env
load_dotenv()

# ------------------------------------------------------------------------------
# Set up logging
# ------------------------------------------------------------------------------
os.makedirs("logs", exist_ok=True)

# Rotate logs daily and keep the last 7 days
file_handler = logging.handlers.TimedRotatingFileHandler(
    filename="logs/app.log",
    when="D",   # Rotate every day
    interval=1, # 1 day interval
    backupCount=7
)
log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")
file_handler.setFormatter(log_formatter)

# (Optional) Also log to console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(log_formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# ------------------------------------------------------------------------------
# Environment Variables
# ------------------------------------------------------------------------------
GARMIN_USERNAME = os.getenv("GARMIN_USERNAME")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD")
GARMINTOKENS = os.getenv("GARMINTOKENS") or "~/.garminconnect"
GARMINTOKENS_BASE64 = os.getenv("GARMINTOKENS_BASE64") or "~/.garminconnect_base64"

# Dropbox OAuth settings
DROPBOX_APP_KEY = os.getenv("DROPBOX_APP_KEY")
DROPBOX_APP_SECRET = os.getenv("DROPBOX_APP_SECRET")
DROPBOX_TOKEN_FILE = os.getenv("DROPBOX_TOKEN_FILE", "~/.dropbox_token.json")
# Expand the user path once and store it here:
DROPBOX_TOKEN_FILEPATH = os.path.expanduser(DROPBOX_TOKEN_FILE)

# Post-upload strategy
POST_UPLOAD_STRATEGY = os.getenv("POST_UPLOAD_STRATEGY", "move").lower()  # "move" or "delete"

# Dropbox folder settings
DROPBOX_FOLDER = "/Apps/TrainerDay"
PROCESSED_FOLDER = DROPBOX_FOLDER + "/Processed"

# ------------------------------------------------------------------------------
# Garmin Initialization
# ------------------------------------------------------------------------------
def init_garmin_api():
    """Initializes the Garmin API. If a token file exists, use it; otherwise, login and dump a new token."""
    try:
        garmin = Garmin()
        garmin.login(GARMINTOKENS)
    except (FileNotFoundError, GarthHTTPError, GarminConnectAuthenticationError):
        try:
            garmin = Garmin(email=GARMIN_USERNAME, password=GARMIN_PASSWORD, is_cn=False)
            garmin.login()
            garmin.garth.dump(GARMINTOKENS)
            token_base64 = garmin.garth.dumps()
            tokenstore_path = os.path.expanduser(GARMINTOKENS_BASE64)
            with open(tokenstore_path, "w") as token_file:
                token_file.write(token_base64)
        except (
            FileNotFoundError,
            GarthHTTPError,
            GarminConnectAuthenticationError,
            requests.exceptions.HTTPError,
        ) as err:
            logger.error("Garmin API init error: %s", err)
            return None
    return garmin

# ------------------------------------------------------------------------------
# Dropbox OAuth
# ------------------------------------------------------------------------------
def first_time_dropbox_oauth():
    """
    Prompts the user to authorize this app with Dropbox (no-redirect flow).
    Requests offline access (refresh token) and saves the tokens to DROPBOX_TOKEN_FILEPATH.
    """
    flow = dropbox.DropboxOAuth2FlowNoRedirect(
        consumer_key=DROPBOX_APP_KEY,
        consumer_secret=DROPBOX_APP_SECRET,
        token_access_type='offline'
    )

    authorize_url = flow.start()
    logger.info("1. Go to: %s", authorize_url)
    logger.info("2. Click 'Allow' (you may need to log in).")
    logger.info("3. Copy the authorization code.")
    auth_code = input("Enter the authorization code here: ").strip()

    oauth_result = flow.finish(auth_code)

    # Convert expires_at to a numeric timestamp if it's a datetime object
    expires_at_value = oauth_result.expires_at
    if isinstance(expires_at_value, datetime):
        expires_at_value = expires_at_value.timestamp()

    tokens = {
        "access_token": oauth_result.access_token,
        "refresh_token": oauth_result.refresh_token,
        "expires_at": expires_at_value,
    }

    with open(DROPBOX_TOKEN_FILEPATH, "w") as f:
        json.dump(tokens, f, indent=2)

    logger.info("Dropbox OAuth tokens saved to %s", DROPBOX_TOKEN_FILEPATH)
    return tokens

def load_dropbox_tokens():
    """Load Dropbox tokens from the local JSON file, if it exists."""
    if not os.path.exists(DROPBOX_TOKEN_FILEPATH):
        return None
    try:
        with open(DROPBOX_TOKEN_FILEPATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Error reading token file '%s': %s", DROPBOX_TOKEN_FILEPATH, e)
        return None

def init_dropbox_api():
    """
    Initializes a Dropbox client using either:
    1) Existing tokens from DROPBOX_TOKEN_FILEPATH, or
    2) A first-time OAuth flow if no tokens are found.
    """
    if not DROPBOX_APP_KEY or not DROPBOX_APP_SECRET:
        logger.error("DROPBOX_APP_KEY or DROPBOX_APP_SECRET is not set. Cannot proceed with OAuth.")
        return None

    tokens = load_dropbox_tokens()
    if not tokens:
        logger.info("No Dropbox tokens found. Running first-time OAuth flow...")
        tokens = first_time_dropbox_oauth()

    # Create a Dropbox client with refresh token support
    dbx = dropbox.Dropbox(
        oauth2_access_token=tokens["access_token"],
        oauth2_refresh_token=tokens["refresh_token"],
        app_key=DROPBOX_APP_KEY,
        app_secret=DROPBOX_APP_SECRET
    )

    # The SDK will automatically refresh short-lived tokens as needed.
    return dbx

# ------------------------------------------------------------------------------
# Main Logic
# ------------------------------------------------------------------------------
def process_file(dbx, garmin, file_metadata, local_dir="downloads"):
    """
    Downloads a file from Dropbox, uploads it to Garmin, and then
    either moves or deletes the file from Dropbox based on POST_UPLOAD_STRATEGY.
    """
    file_path = file_metadata.path_lower
    file_name = file_metadata.name
    local_file = os.path.join(local_dir, file_name)
    logger.info("Processing file: %s", file_name)

    # Download file from Dropbox
    try:
        _, response = dbx.files_download(file_path)
        with open(local_file, "wb") as f:
            f.write(response.content)
        logger.info("Downloaded '%s' to '%s'", file_name, local_file)
    except Exception as e:
        logger.error("Error downloading '%s': %s", file_name, e)
        return

    # Upload file to Garmin
    try:
        garmin.upload_activity(local_file)
        logger.info("Uploaded '%s' to Garmin.", file_name)
    except GarthHTTPError as e:
        # Determine if error is due to duplicate upload (HTTP 409)
        status_code = None
        if hasattr(e, "response") and e.response is not None:
            status_code = e.response.status_code
        else:
            if "409" in str(e):
                status_code = 409

        if status_code == 409:
            logger.info("Activity already exists (409) for '%s'.", file_name)
        else:
            logger.error("Error uploading '%s': %s", file_name, e)
            return

    # Post-upload processing in Dropbox: Move or Delete
    if POST_UPLOAD_STRATEGY == "move":
        # Ensure that the Processed folder exists; create it if it doesn't.
        try:
            dbx.files_get_metadata(PROCESSED_FOLDER)
        except dropbox.exceptions.ApiError as e:
            if "not_found" in str(e):
                try:
                    dbx.files_create_folder_v2(PROCESSED_FOLDER)
                    logger.info("Created folder: %s", PROCESSED_FOLDER)
                except Exception as ex:
                    logger.error("Error creating folder '%s': %s", PROCESSED_FOLDER, ex)
                    return

        dest_path = PROCESSED_FOLDER + "/" + file_name
        try:
            dbx.files_move_v2(file_path, dest_path)
            logger.info("Moved '%s' to '%s'.", file_name, dest_path)
        except Exception as e:
            logger.error("Error moving '%s': %s", file_name, e)
    elif POST_UPLOAD_STRATEGY == "delete":
        try:
            dbx.files_delete_v2(file_path)
            logger.info("Deleted '%s' from Dropbox.", file_name)
        except Exception as e:
            logger.error("Error deleting '%s': %s", file_name, e)
    else:
        logger.error("Unknown POST_UPLOAD_STRATEGY: %s", POST_UPLOAD_STRATEGY)

def main():
    # Initialize Dropbox via OAuth
    dbx = init_dropbox_api()
    if not dbx:
        logger.error("Failed to initialize Dropbox API.")
        return

    logger.info("Connected to Dropbox.")

    # Initialize Garmin API
    garmin = init_garmin_api()
    if garmin is None:
        logger.error("Failed to initialize Garmin API.")
        return

    # Create a local directory for temporary file storage
    download_dir = "downloads"
    os.makedirs(download_dir, exist_ok=True)

    # List files in the Dropbox folder
    try:
        result = dbx.files_list_folder(DROPBOX_FOLDER)
        activities = [entry for entry in result.entries if isinstance(entry, dropbox.files.FileMetadata)]
        logger.info(f"Found {len(activities)} activities in Dropbox folder '{DROPBOX_FOLDER}'.")
    except Exception as e:
        logger.error("Error listing Dropbox folder '%s': %s", DROPBOX_FOLDER, e)
        return

    # Process each file
    for activity in activities:
        process_file(dbx, garmin, activity, local_dir=download_dir)

    logger.info("Finished processing files.")

if __name__ == "__main__":
    main()
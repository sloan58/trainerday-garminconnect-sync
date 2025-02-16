# TrainerDay -> Garmin Connect Sync

Currently TrainerDay rides do not get synced to Garmin Connect.  To work around this, we can enable TrainerDay to send activities
to Dropbox and then use the Dropbox and Garmin Connect API's to put the activities in Garmin Connect.

This Python CLI app downloads `.tcx` files from the Dropbox folder created by TrainerDay and uploads them to Garmin Connect.  
After uploading, it either **moves** or **deletes** the files from Dropbox, depending on your chosen strategy.

---

## Table of Contents

1. [Requirements](#requirements)
2. [TrainerDay Setup](#trainerday)
3. [Dropbox Setup](#dropbox-setup)  
4. [Garmin Setup](#garmin-setup)  
5. [Environment Variables](#environment-variables)  
6. [Installation](#installation)  
7. [Usage](#usage)  
8. [How It Works](#how-it-works)  
9. [Troubleshooting](#troubleshooting)

---

## Requirements

- **Python 3.7+** (Tested on Python 3.12, but 3.7 or later should work.)
- **Pip** or similar package manager.
- A Dropbox account with a Dropbox App configured for **Scoped Access**.
- A Garmin Connect account (with valid credentials).

---

## TrainerDay Setup

In your TrainerDay app or their website, go to the **Connections** section and enable the Dropbox integration.
This will enable TrainerDay to put activities into your Dropbox account in the /Apps/TrainerDay folder.

---

## Dropbox Setup

1. **Create a Dropbox App**  
   - Go to [Dropbox App Console](https://www.dropbox.com/developers/apps).
   - Click **"Create app"** and choose **Scoped access**.
   - Select **"Full Dropbox"** to gain access to the TrainerDay folder.
   

2. **Select Permissions**  
   Before generating your token, **make sure** you select at least the following permissions:
   - `files.metadata.read`
   - `files.metadata.write`
   - `files.content.read`
   - `files.content.write`

   > **Important**: These scopes must be checked **before** you generate the access token.  
   > You **cannot** upgrade or regenerate the same token later if you forget to include these scopes.

3. **Select Settings and Generate Your Access Token**  
   - Scroll down to the **OAuth 2** section in your app's settings.
   - Click **"Generate access token"**.
   - Copy and store it securely. This token will be used by the script to access your Dropbox.

---

## Garmin Setup

1. **Create (or Use) a Garmin Account**  
   You will need valid **username** and **password** credentials to upload activities.

2. **No Extra Configuration Needed**  
   The script uses the `garminconnect` and `garth` libraries to handle authentication and token storage.

---

## Environment Variables

This script reads credentials and configuration from environment variables. You can store them in a `.env` file (loaded by [python-dotenv](https://pypi.org/project/python-dotenv/)) or set them manually in your shell.

**Required Variables:**

- **`DROPBOX_ACCESS_TOKEN`**  
  Your Dropbox API token (with the correct scopes).

- **`GARMIN_USERNAME`**  
  Your Garmin Connect username (usually an email).

- **`GARMIN_PASSWORD`**  
  Your Garmin Connect password.

**Optional Variables:**

- **`POST_UPLOAD_STRATEGY`**  
  Determines how files are handled after a successful (or duplicate) upload to Garmin.  
  Possible values:
  - `move` — Move files from `/Apps/TrainerDay` to `/Apps/TrainerDay/Processed`.
  - `delete` — Delete files from Dropbox entirely.  
  Default is `delete`.

- **`GARMINTOKENS`** and **`GARMINTOKENS_BASE64`**  
  Paths where the Garmin tokens are cached. Defaults are:
  - `~/.garminconnect`
  - `~/.garminconnect_base64`

**Example `.env` file:**

DROPBOX_ACCESS_TOKEN=sl.ABCD1234XYZ  
GARMIN_USERNAME=myemail@example.com  
GARMIN_PASSWORD=MyGarminPassword  
POST_UPLOAD_STRATEGY=move  
GARMINTOKENS=/Users/Me/.garminconnect  
GARMINTOKENS_BASE64=/Users/Me/.garminconnect_base64  

---

## Installation

1. **Clone or Download** this repository to your local machine.

2. **Install Dependencies (create virtual env if desired)**  
   pip install -r requirements.txt
   or  
   pip install dropbox python-dotenv requests garminconnect garth  

3. **Set Environment Variables**  
   - Either create a `.env` file with the values mentioned above.
   - Or export them directly in your shell:  
     export DROPBOX_ACCESS_TOKEN="sl.ABCD1234XYZ"  
     export GARMIN_USERNAME="myemail@example.com"  
     export GARMIN_PASSWORD="MyGarminPassword"  
     export POST_UPLOAD_STRATEGY="move"  

---

## Usage

1. **Run the Script**  
   python main.py  

   (Assuming the script is named `main.py` or similar.)

2. **What Happens**  
   - The script connects to Dropbox using `DROPBOX_ACCESS_TOKEN`.
   - It lists all files in `/Apps/TrainerDay`.
   - For each file:
     - Downloads it locally into a `downloads` folder.
     - Uploads it to Garmin Connect.
     - If the upload is successful or a duplicate, applies the `POST_UPLOAD_STRATEGY`:
       - **move**: Moves file to `/Apps/TrainerDay/Processed`
       - **delete**: Deletes file from Dropbox

3. **Logging**  
   The script will log activity in the logs folder for the past 7 days as well as the console.

---

## How It Works

1. **Garmin Authentication**  
   - The script tries to use cached tokens from `GARMINTOKENS`.  
   - If no token file is found or if an error occurs, it logs in using `GARMIN_USERNAME` and `GARMIN_PASSWORD`, then stores new tokens.

2. **Dropbox File Operations**  
   - `dropbox.Dropbox` is initialized with `DROPBOX_ACCESS_TOKEN`.
   - `files_list_folder` is called on `/Apps/TrainerDay`.
   - For each file, `files_download` is used to pull the `.tcx` file locally.
   - After uploading to Garmin, `files_move_v2` or `files_delete_v2` is called, depending on your strategy.

3. **Duplicate Activity Handling**  
   - If Garmin returns an HTTP 409 error, the script interprets that as a duplicate activity.  
   - The script logs that the activity already exists and proceeds with the post-upload strategy (move/delete).

---

## Troubleshooting

- **Token Scopes**:  
  If you see errors like `AuthError('missing_scope', ...)`, it usually means your Dropbox token does not have the correct permissions. Make sure you selected `files.metadata.read`, `files.metadata.write`, `files.content.read`, and `files.content.write` **before** generating the token. You **cannot** add scopes to an existing token after it’s created.

- **Garmin Authentication**:  
  If Garmin credentials fail, ensure your `GARMIN_USERNAME` and `GARMIN_PASSWORD` are correct. Also, watch for multi-factor authentication requirements that might not be supported by this script.

- **Permission Denied**:  
  If you’re using a folder outside of `/Apps/TrainerDay` with an “App folder” permission, your Dropbox app won’t have access. Use the correct path or set your app to **Full Dropbox** if needed.

- **Local File Overwrites**:  
  The script overwrites any existing file with the same name in the local `downloads` folder. Adjust logic if you want to rename or skip duplicates locally.

- **Unexpected Errors**:  
  Check the console logs for stack traces. You can enable more verbose logging by editing the `logging.basicConfig(level=logging.INFO)` line to `logging.DEBUG`.

## Scheduling a Cron Job

To run this script automatically every hour on a Unix-like system, you can set up a cron job:

1. Open your crontab:
   ```bash
   crontab -e
   ```
2. Add a line like this (adjust paths as needed):
   ```bash
   0 * * * * /usr/bin/python /path/to/your/main.py >> /path/to/logs/cron.log 2>&1
   ```
   This runs the script at the top of every hour. The output is appended to `cron.log`, which can help you debug any cron-related issues.
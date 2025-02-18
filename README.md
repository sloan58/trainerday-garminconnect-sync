# TrainerDay -> Garmin Connect Sync

TrainerDay rides aren’t automatically synced with Garmin Connect. To bridge this gap, we can have TrainerDay export activities to Dropbox, then use the Dropbox and Garmin Connect APIs to upload them into Garmin Connect.

This Python CLI app downloads `.tcx` files from the Dropbox folder created by TrainerDay and uploads them to Garmin Connect.  
After uploading, it either **moves** or **deletes** the files from Dropbox, depending on your chosen strategy.

---

## Table of Contents

1. [Requirements](#requirements)  
2. [Dropbox Setup](#dropbox-setup)  
3. [TrainerDay Setup](#trainerday-setup)  
4. [Garmin Setup](#garmin-setup)  
5. [Environment Variables](#environment-variables)  
6. [Installation](#installation)  
7. [Usage](#usage)  
8. [How It Works](#how-it-works)  
9. [Troubleshooting](#troubleshooting)  
10. [Scheduling a Cron Job](#scheduling-a-cron-job)

---

## Requirements

- **Python 3.7+** (Tested on Python 3.12, but 3.7 or later should work.)
- **Pip** or similar package manager.
- A Dropbox account with a Dropbox App configured for **Scoped Access**.
- A Garmin Connect account (with valid credentials).

---

## Dropbox Setup

1. **Create a Dropbox App**  
   - Go to [Dropbox App Console](https://www.dropbox.com/developers/apps).
   - Click **"Create app"** and choose **Scoped access**.
   - Select **"Full Dropbox"** to ensure you can access the `/Apps/TrainerDay` folder created by TrainerDay.

2. **Configure Permissions**  
   Under **"Permissions"**, ensure you enable:
   - `files.metadata.read`
   - `files.metadata.write`
   - `files.content.read`
   - `files.content.write`

3. **Set Redirect URIs (Optional)**  
   If you plan on using a redirect-based OAuth flow, set an appropriate redirect URI.  
   However, this script uses a **no-redirect** OAuth flow by default (it prints a URL, you authorize, then paste back a code).

4. **Store Your App Key & Secret**  
   - In your app’s settings, locate your **App key** and **App secret**.  
   - You’ll set them as `DROPBOX_APP_KEY` and `DROPBOX_APP_SECRET` environment variables (see [Environment Variables](#environment-variables)).

---

## TrainerDay Setup

In your TrainerDay app or their website, go to the **Connections** section and enable the Dropbox integration.  
This will enable TrainerDay to put `.tcx` files into your Dropbox account in the `/Apps/TrainerDay` folder.

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

- **`DROPBOX_APP_KEY`**  
  Your Dropbox App Key (from the App Console).
- **`DROPBOX_APP_SECRET`**  
  Your Dropbox App Secret (from the App Console).
- **`GARMIN_USERNAME`**  
  Your Garmin Connect username (usually an email).
- **`GARMIN_PASSWORD`**  
  Your Garmin Connect password.

**Optional Variables:**

- **`POST_UPLOAD_STRATEGY`**  
  Determines how files are handled after a successful (or duplicate) upload to Garmin.  
  Possible values:
  - `move` — Move files from `/Apps/TrainerDay` to `/Apps/TrainerDay/Processed` (default).
  - `delete` — Delete files from Dropbox entirely.

- **`DROPBOX_TOKEN_FILE`**  
  The path (supports `~`) where the script will store and read your Dropbox refresh tokens.  
  Defaults to `~/.dropbox_token.json`.

- **`GARMINTOKENS`** and **`GARMINTOKENS_BASE64`**  
  Paths where the Garmin tokens are cached. Defaults are:
  - `~/.garminconnect`
  - `~/.garminconnect_base64`

**Example `.env` file:**

```
DROPBOX_APP_KEY=abc123
DROPBOX_APP_SECRET=def456
DROPBOX_TOKEN_FILE=~/.dropbox_token.json
GARMIN_USERNAME=myemail@example.com
GARMIN_PASSWORD=MyGarminPassword
GARMINTOKENS=~/.garminconnect
GARMINTOKENS_BASE64=~/.garminconnect_base64
POST_UPLOAD_STRATEGY=move
```

---

## Installation

1. **Clone or Download** this repository to your local machine.

2. **Install Dependencies (create virtual env if desired)**  
   ```bash
   pip install -r requirements.txt
   ```
   or  
   ```bash
   pip install dropbox python-dotenv requests garminconnect garth
   ```

3. **Set Environment Variables**  
   - Either create a `.env` file with the values mentioned above.
   - Or export them directly in your shell:
     ```bash
     export DROPBOX_APP_KEY="abc123"
     export DROPBOX_APP_SECRET="def456"
     export GARMIN_USERNAME="myemail@example.com"
     export GARMIN_PASSWORD="MyGarminPassword"
     export POST_UPLOAD_STRATEGY="move"
     ```
4. **First-Time Authorization**  
   - On your first run, the script will detect no local token file for Dropbox.  
   - It will print a URL for you to open in your browser.  
   - Approve access to your Dropbox, then copy/paste the authorization code back into the script.  
   - The script will store a refresh token in `~/.dropbox_token.json` (or the path you set in `DROPBOX_TOKEN_FILE`).  
   - Subsequent runs will automatically refresh your token without any user intervention.

---

## Usage

1. **Run the Script**  
   ```bash
   python main.py
   ```

2. **What Happens**  
   - The script uses your Dropbox **refresh token** to obtain a short-lived access token as needed.  
   - It lists all files in `/Apps/TrainerDay`.  
   - For each file:
     - Downloads it locally into a `downloads` folder.
     - Uploads it to Garmin Connect.
     - If the upload is successful or a duplicate, applies the `POST_UPLOAD_STRATEGY`:
       - **move**: Moves file to `/Apps/TrainerDay/Processed`
       - **delete**: Deletes file from Dropbox

3. **Logging**  
   The script will log activity in the `logs` folder for the past 7 days, as well as the console.

---

## How It Works

1. **Dropbox OAuth Flow**  
   - On first run, you’ll be prompted to visit a URL and paste back an authorization code.  
   - The script saves a **refresh token** in a JSON file (default `~/.dropbox_token.json`).  
   - Future runs automatically refresh short-lived tokens behind the scenes.

2. **Garmin Authentication**  
   - The script tries to use cached tokens from `GARMINTOKENS`.  
   - If no token file is found or if an error occurs, it logs in using `GARMIN_USERNAME` and `GARMIN_PASSWORD`, then stores new tokens locally.

3. **Dropbox File Operations**  
   - The script lists files in `/Apps/TrainerDay`, downloads each `.tcx`, and uploads to Garmin Connect.  
   - After upload, the file is either moved or deleted from Dropbox (depending on `POST_UPLOAD_STRATEGY`).

4. **Duplicate Activity Handling**  
   - If Garmin returns an HTTP 409 error, the script interprets that as a duplicate activity.  
   - The script logs that the activity already exists and proceeds with the post-upload strategy (move/delete).

---

## Troubleshooting

- **Missing or Invalid OAuth**:  
  If you skip the authorization step or revoke the app in Dropbox, you may need to delete your local token file (`~/.dropbox_token.json`) and re-run the script to generate a new refresh token.

- **Token Scopes**:  
  If you see errors like `AuthError('missing_scope', ...)`, it usually means your Dropbox app is missing required permissions. Make sure you selected the correct scopes **before** using the app in the script.

- **Garmin Authentication**:  
  If Garmin credentials fail, ensure your `GARMIN_USERNAME` and `GARMIN_PASSWORD` are correct. Also, watch for multi-factor authentication requirements that might not be supported by this script.

- **Local File Overwrites**:  
  The script overwrites any existing file with the same name in the local `downloads` folder. Adjust logic if you want to rename or skip duplicates locally.

- **Unexpected Errors**:  
  Check the console logs or `logs/app.log` for stack traces. You can enable more verbose logging by editing `logging.basicConfig(level=logging.INFO)` to `logging.DEBUG`.

---

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
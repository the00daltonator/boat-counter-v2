# Google Sheets API Setup Guide

This guide will help you create and configure Google Sheets API credentials for use with the Boat Counter application.

## 📄 How to Set Up Google Sheets API Credentials

To use Google Sheets with this script, you must create a **Google Service Account**, download the credentials file, and **share access to your Google Sheet** with the service account email.

## ✅ Step-by-Step Instructions

### 1. **Create a Google Cloud Project**

1. Visit: [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. Click the dropdown at the top and choose **"New Project"**
3. Give your project a name (e.g., `BoatCounterLogs`)
4. Click **Create**

### 2. **Enable the Google Sheets API**

1. In the Google Cloud Console, go to **APIs & Services > Library**
2. Search for **Google Sheets API**
3. Click it and press **Enable**
4. Repeat for **Google Drive API** (needed for file access)

### 3. **Create a Service Account**

1. Go to **APIs & Services > Credentials**
2. Click **"+ CREATE CREDENTIALS" → "Service Account"**
3. Name it (e.g., `boat-counter-writer`)
4. Click **Create and Continue** (no need to assign roles)
5. Click **Done**

### 4. **Create a JSON Key**

1. Find your service account under **"Service Accounts"**
2. Click the account name → **Keys** tab
3. Click **"Add Key" → "Create new key"**
4. Select **JSON** and press **Create**
5. Save the file as `gsheets_creds.json` in the `config/` directory of your Boat Counter installation

### 5. **Share Your Google Sheet**

1. Create a new Google Sheet named `"Boat Counter Logs"`
   - You can use a different name, but you'll need to update the script configuration
2. Click **Share**
3. Copy the **client email** from your `gsheets_creds.json` file (look for the `client_email` field)
4. Paste that email into the sharing dialog (as if you're sharing with a person)
5. Give **Editor** access
6. Click **Share**

## 🔐 Example of `client_email` field:

```json
"client_email": "boat-counter-writer@your-project-id.iam.gserviceaccount.com"
```

## ✅ You're Done!

* Your script will now be able to append rows to your Google Sheet!
* Make sure your sheet has headers in the first row (optional but helpful).
* Recommended headers: `Date`, `Time`, `Count`, `Location`

## 🧪 Testing the Connection

Run the script once and check for this line:

```
[✅] Connected to Google Sheets
```

If you see a warning like:

```
[⚠️ WARN] Google Sheets not connected: ...
```

Make sure:

* Your sheet is named exactly `"Boat Counter Logs"` (or update the script configuration)
* The service account has been shared correctly with Editor permissions
* Your `gsheets_creds.json` file is in the correct directory (`config/` folder)
* You have an active internet connection

## 📊 Sheet Structure

For best results, set up your Google Sheet with these columns:

| Date | Time | Count | Direction | Location | Notes |
|------|------|-------|-----------|----------|-------|
|      |      |       |           |          |       |

The script will automatically populate these columns when boats are detected. 
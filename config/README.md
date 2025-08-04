# Configuration Files

This directory contains configuration files for the boat counter application.

## Google Sheets Credentials

The boat counter application can log counts to Google Sheets. To use this feature, you need to:

1. Create a Google Cloud project
2. Enable the Google Sheets API and Google Drive API
3. Create a service account
4. Download the service account credentials as JSON
5. Rename the downloaded file to `gsheets_creds.json` and place it in this directory

### Using the Template

A template file `gsheets_creds_template.json` is provided to show the required structure.

To create your own credentials:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to "APIs & Services" > "Enable APIs and Services"
4. Enable the "Google Sheets API" and "Google Drive API"
5. Go to "APIs & Services" > "Credentials"
6. Click "Create Credentials" > "Service Account"
7. Fill in the required information and click "Create"
8. Give the service account the "Editor" role
9. Click "Done"
10. Click on the newly created service account
11. Go to the "Keys" tab
12. Click "Add Key" > "Create new key"
13. Select "JSON" and click "Create"
14. The key file will be downloaded to your computer
15. Rename it to `gsheets_creds.json` and place it in this directory

## Requirements Files

This directory also contains Python requirements files:

- `requirements.txt` - Main requirements for the application
- `requirements_new.txt` - Updated requirements for newer Python versions
- `requirements_jetson.txt` - Requirements specific to the Jetson Nano platform

Use the appropriate requirements file for your deployment environment. 
# Gmail API Setup Guide

This guide walks you through setting up Gmail API access for the Gmail to Podcast tool.

## Prerequisites

- A Google account
- Access to [Google Cloud Console](https://console.cloud.google.com/)

## Step-by-Step Setup

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" dropdown at the top
3. Click "New Project"
4. Enter a project name (e.g., "Gmail to Podcast")
5. Click "Create"

### 2. Enable Gmail API

1. In the Cloud Console, go to "APIs & Services" > "Library"
2. Search for "Gmail API"
3. Click on "Gmail API"
4. Click "Enable"

### 3. Configure OAuth Consent Screen

1. Go to "APIs & Services" > "OAuth consent screen"
2. Select "External" user type (unless you have a Google Workspace account)
3. Click "Create"
4. Fill in the required fields:
   - App name: "Gmail to Podcast"
   - User support email: Your email
   - Developer contact: Your email
5. Click "Save and Continue"
6. On the Scopes page:
   - Click "Add or Remove Scopes"
   - Search for and select: `https://www.googleapis.com/auth/gmail.readonly`
   - Click "Update"
7. Click "Save and Continue"
8. Add test users (your email address)
9. Click "Save and Continue"

### 4. Create OAuth 2.0 Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. Select "Desktop app" as the application type
4. Name it "Gmail to Podcast Client"
5. Click "Create"
6. Click "Download JSON" on the popup
7. Save the file as `credentials.json` in your project root

### 5. First Authentication

When you run the tool for the first time:

1. It will open a browser window
2. Sign in with your Google account
3. Click "Continue" when warned about unverified app
4. Grant permission to read your emails
5. The tool will save the authentication token as `token.pickle`

## Security Notes

- **Keep `credentials.json` secure** - Don't commit it to version control
- **Keep `token.pickle` secure** - It contains your access token
- The tool only requests read-only access to Gmail
- You can revoke access anytime in your [Google Account settings](https://myaccount.google.com/permissions)

## Troubleshooting

### "Access blocked" error
- Make sure you're logged in with the correct Google account
- Check that you added your email as a test user in the OAuth consent screen

### "Quota exceeded" error
- Gmail API has usage limits
- Wait a bit and try again
- Consider implementing rate limiting in your usage

### Token expired
- Delete `token.pickle` and authenticate again
- The tool will automatically refresh tokens when possible

## API Quotas

Gmail API has the following default quotas:
- 250 quota units per user per second
- 1,000,000,000 quota units per day

Each operation costs different quota units:
- List messages: 5 units
- Get message: 5 units
- Get message (metadata only): 1 unit

The tool is designed to work within these limits for normal usage.
#!/bin/bash
Purpose: Create/renew Microsoft Graph mail webhook subscription for MCC Portfolio Intelligence
Usage: ./graph_subscribe.sh [--tenant-id XXX] [--client-id XXX] [--client-secret XXX] [--webhook-url XXX] [--hmac-secret XXX]
Dependencies: curl, jq
set -euo pipefail
Configuration from env vars or CLI args
TENANT_ID="{GRAPH_TENANT_ID:-
{1:-}}"
CLIENT_ID="{GRAPH_CLIENT_ID:-
{2:-}}"
CLIENT_SECRET="{GRAPH_CLIENT_SECRET:-
{3:-}}"
WEBHOOK_URL="{WEBHOOK_URL:-
{4:-
https://your-function.azurewebsites.net/api/graph-webhook}}"
HMAC_SECRET="{GRAPH_SUBSCRIPTION_SECRET:-
{5:-}}"

Validate required parameters
if [[ -z "TENANTID"∣∣−z"TENANT_ID" || -z "
TENANTI​D"∣∣−z"CLIENT_ID" || -z "CLIENTSECRET"∣∣−z"CLIENT_SECRET" || -z "
CLIENTS​ECRET"∣∣−z"HMAC_SECRET" ]]; then
    echo "Error: Missing required parameters"
    echo "Usage: $0 [--tenant-id XXX] [--client-id XXX] [--client-secret XXX] [--webhook-url XXX] [--hmac-secret XXX]"
    echo "Or set env vars: GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, GRAPH_SUBSCRIPTION_SECRET"
    exit 1
fi

Get access token
echo "Acquiring access token..."
TOKEN_RESPONSE=$(curl -s -X POST 
"https://login.microsoftonline.com/$TENANT_ID/oauth2/v2.0/token" 
-H "Content-Type: application/x-www-form-urlencoded" 
-d "client_id=$CLIENT_ID" 
-d "client_secret=$CLIENT_SECRET" 
-d "scope=https://graph.microsoft.com/.default" 
-d "grant_type=client_credentials")
ACCESS_TOKEN=(echo"(echo "
(echo"TOKEN_RESPONSE" | jq -r '.access_token')
if [[ "ACCESSTOKEN"=="null"∣∣−z"ACCESS_TOKEN" == "null" || -z "
ACCESST​OKEN"=="null"∣∣−z"ACCESS_TOKEN" ]]; then
    echo "Error: Failed to acquire access token"
    echo "$TOKEN_RESPONSE" | jq .
    exit 1
fi

Calculate expiration (4230 minutes = 70.5 hours, just under the 72-hour maximum)
EXPIRATION_DATETIME=$(date -u -v+4230M '+%Y-%m-%dT%H:%M:%S.0000000Z' 2>/dev/null || 
date -u -d '+4230 minutes' '+%Y-%m-%dT%H:%M:%S.0000000Z')
Create subscription
echo "Creating/updating Graph webhook subscription..."
SUBSCRIPTION_BODY=$(cat <<EOF
{
"changeType": "created",
"notificationUrl": "$WEBHOOK_URL",
"resource": "me/mailFolders/inbox/messages",
"expirationDateTime": "$EXPIRATION_DATETIME",
"clientState": "$HMAC_SECRET",
"latestSupportedTlsVersion": "v1_2"
}
EOF
)
SUBSCRIPTION_RESPONSE=$(curl -s -X POST 
"https://graph.microsoft.com/v1.0/subscriptions" 
-H "Authorization: Bearer $ACCESS_TOKEN" 
-H "Content-Type: application/json" 
-d "$SUBSCRIPTION_BODY")
SUBSCRIPTION_ID=(echo"(echo "
(echo"SUBSCRIPTION_RESPONSE" | jq -r '.id')
SUBSCRIPTION_EXPIRATION=(echo"(echo "
(echo"SUBSCRIPTION_RESPONSE" | jq -r '.expirationDateTime')

if [[ "SUBSCRIPTIONID"=="null"∣∣−z"SUBSCRIPTION_ID" == "null" || -z "
SUBSCRIPTIONI​D"=="null"∣∣−z"SUBSCRIPTION_ID" ]]; then
    echo "Error: Failed to create subscription"
    echo "$SUBSCRIPTION_RESPONSE" | jq .

# Try to renew existing subscription
echo "Attempting to find and renew existing subscription..."
EXISTING_SUBS=$(curl -s -X GET \
    "https://graph.microsoft.com/v1.0/subscriptions" \
    -H "Authorization: Bearer $ACCESS_TOKEN")

EXISTING_ID=$(echo "$EXISTING_SUBS" | jq -r '.value[] | select(.resource == "me/mailFolders/inbox/messages") | .id' | head -1)

if [[ -n "$EXISTING_ID" && "$EXISTING_ID" != "null" ]]; then
    echo "Found existing subscription: $EXISTING_ID"
    RENEW_RESPONSE=$(curl -s -X PATCH \
        "https://graph.microsoft.com/v1.0/subscriptions/$EXISTING_ID" \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"expirationDateTime\": \"$EXPIRATION_DATETIME\"}")
    
    SUBSCRIPTION_ID=$(echo "$RENEW_RESPONSE" | jq -r '.id')
    SUBSCRIPTION_EXPIRATION=$(echo "$RENEW_RESPONSE" | jq -r '.expirationDateTime')
fi
fi
if [[ "SUBSCRIPTIONID"=="null"∣∣−z"SUBSCRIPTION_ID" == "null" || -z "
SUBSCRIPTIONI​D"=="null"∣∣−z"SUBSCRIPTION_ID" ]]; then
    echo "Error: Could not create or renew subscription"
    exit 1
fi

echo "Success!"
echo "Subscription ID: $SUBSCRIPTION_ID"
echo "Expires: $SUBSCRIPTION_EXPIRATION"
echo ""
echo "Note: Renew this subscription before expiration by running this script again"

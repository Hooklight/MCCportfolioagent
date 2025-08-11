# MCC Portfolio Intelligence Webhook
import azure.functions as func
import json
import logging
import os

app = func.FunctionApp()

@app.route(route="webhook", auth_level=func.AuthLevel.FUNCTION)
def webhook(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Webhook endpoint called')
    
    try:
        req_body = req.get_json()
        
        # Extract data
        email_id = req_body.get('email_id', '')
        subject = req_body.get('subject', '')
        body = req_body.get('body', '')
        company_id = req_body.get('company_id', '')
        from_address = req_body.get('from', '')
        received_at = req_body.get('received_at', '')
        
        # Log the received data
        logging.info(f"Processing email for company: {company_id}")
        
        # For now, just return success
        # Database integration will be added after environment variables are set
        
        return func.HttpResponse(
            json.dumps({
                "status": "success", 
                "company_id": company_id,
                "message": "Email processed successfully"
            }),
            mimetype="application/json",
            status_code=200
        )
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            mimetype="application/json",
            status_code=500
        )

@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"status": "healthy", "version": "1.0"}),
        mimetype="application/json",
        status_code=200
    )

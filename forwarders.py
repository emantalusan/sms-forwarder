# forwarders.py
import time
import requests
import smtplib
from email.mime.text import MIMEText
import logging
from utils import failed_services, notify_failure, api_queue, sms_queue, email_queue
from database import mark_as_forwarded

logger = logging.getLogger('SMSForwarder')

def send_to_api_providers(api_providers_list, sender, timestamp, message, provider_name=None, default_timeout=10):
    success = False
    
    logger.debug(f"API providers list: {api_providers_list}")
    selected_providers = [p for p in api_providers_list if (provider_name and p["name"] == provider_name) or 
                         (not provider_name and p.get("default", False))]
    logger.debug(f"Selected API providers: {selected_providers}")
    
    for provider in selected_providers:
        try:
            method = provider.get("method", "POST").upper()
            endpoint = provider["endpoint"].format(sender=sender, timestamp=timestamp, message=message)
            headers = {k: v.format(sender=sender, timestamp=timestamp, message=message) 
                      for k, v in provider.get("headers", {}).items()}
            payload = {k: v.format(sender=sender, timestamp=timestamp, message=message) if isinstance(v, str) else v 
                      for k, v in provider.get("payload", {}).items()}
            timeout = provider.get("timeout", default_timeout)

            logger.debug(f"Sending to API {provider['name']}: method={method}, endpoint={endpoint}, headers={headers}, payload={payload}")
            if method == "POST":
                response = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
            elif method == "GET":
                response = requests.get(endpoint, headers=headers, params=payload if payload else None, timeout=timeout)
            elif method == "PUT":
                response = requests.put(endpoint, headers=headers, json=payload, timeout=timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            logger.info(f"Successfully sent to API {provider['name']}")
            success = True
        except Exception as e:
            logger.error(f"Failed to send to {provider['name']} API: {e}")
    return success

def api_forward_worker(config, db_file):
    max_retries = config.get("max_retries", 3)
    api_providers_list = config["api_providers"]
    default_timeout = config.get("default_timeout", 10)
    
    logger.debug(f"API forwarder started with max_retries={max_retries}, providers={api_providers_list}")
    while True:
        queue_item = api_queue.get()
        if len(queue_item) == 6:
            sender, timestamp, message, sms_id, retry_count, provider = queue_item
        else:
            sender, timestamp, message, sms_id, retry_count = queue_item
            provider = None
        
        logger.info(f"Processing API queue item: sender={sender}, sms_id={sms_id}, retry={retry_count}, message={message}, provider={provider}")
        
        if not api_providers_list:
            logger.warning("No API providers configured, skipping")
            api_queue.task_done()
            continue
            
        success = send_to_api_providers(api_providers_list, sender, timestamp, message, provider, default_timeout)
        
        if success:
            failed_services.discard("API")  # Mark API as available immediately
            logger.debug("API marked as available after successful send")
            if sms_id:
                mark_as_forwarded(db_file, sms_id, api_forwarded=True)
                logger.info(f"API forwarding succeeded for SMS ID={sms_id}")
            else:
                logger.info("API notification sent successfully")
        elif retry_count < max_retries:
            failed_services.add("API")  # Mark API as unavailable on each retry
            logger.debug(f"API marked as unavailable after retry {retry_count + 1}/{max_retries}")
            logger.warning(f"API forwarding failed, retrying ({retry_count + 1}/{max_retries})")
            time.sleep(5 * retry_count)
            api_queue.put((sender, timestamp, message, sms_id, retry_count + 1, provider))
        else:
            failed_services.add("API")  # Ensure it’s marked unavailable after max retries
            logger.debug(f"API marked as unavailable after max retries")
            if sms_id:
                notify_failure("API", sms_id, config)
            logger.error(f"API forwarding failed after {max_retries} retries for SMS ID={sms_id}")
        
        api_queue.task_done()

def sms_forward_worker(modem, db_file, config):
    max_retries = config.get("sms_max_retries", config.get("max_retries", 3))
    recipients = config["sms_recipients"]
    
    logger.debug(f"SMS forwarder started with max_retries={max_retries}, recipients={recipients}")
    while True:
        sender, timestamp, message, sms_id, retry_count = sms_queue.get()
        logger.info(f"Processing SMS queue item: sender={sender}, sms_id={sms_id}, retry={retry_count}, message={message}")
        
        if not recipients:
            logger.debug("No SMS recipients configured, skipping")
            sms_queue.task_done()
            continue
            
        success = False
        for recipient in recipients:
            try:
                logger.debug(f"Attempting to send SMS to {recipient}")
                modem.sendSms(recipient, f"From: {sender}\nTime: {timestamp}\nMessage: {message}")
                logger.info(f"Successfully sent SMS to {recipient}")
                success = True
            except Exception as e:
                logger.error(f"Failed to send SMS to {recipient}: {e}")
        
        if success:
            failed_services.discard("SMS")  # Mark SMS as available immediately
            logger.debug("SMS marked as available after successful send")
            if sms_id:
                mark_as_forwarded(db_file, sms_id, sms_forwarded=True)
                logger.info(f"SMS forwarding succeeded for SMS ID={sms_id}")
        elif retry_count < max_retries:
            failed_services.add("SMS")  # Mark SMS as unavailable on each retry
            logger.debug(f"SMS marked as unavailable after retry {retry_count + 1}/{max_retries}")
            logger.warning(f"SMS forwarding failed, retrying ({retry_count + 1}/{max_retries})")
            time.sleep(5 * retry_count)
            sms_queue.put((sender, timestamp, message, sms_id, retry_count + 1))
        else:
            failed_services.add("SMS")  # Ensure it’s marked unavailable after max retries
            logger.debug(f"SMS marked as unavailable after max retries")
            if sms_id:
                notify_failure("SMS", sms_id, config)
            logger.error(f"SMS forwarding failed after {max_retries} retries for SMS ID={sms_id}")
        
        sms_queue.task_done()

def email_forward_worker(email_config, db_file, full_config):
    max_retries = email_config.get("max_retries", full_config.get("max_retries", 3))
    recipients = email_config["recipients"]
    
    logger.debug(f"Email forwarder started with max_retries={max_retries}, recipients={recipients}")
    while True:
        sender, timestamp, message, sms_id, retry_count = email_queue.get()
        logger.info(f"Processing Email queue item: sender={sender}, sms_id={sms_id}, retry={retry_count}, message={message}")
        
        if not recipients:
            logger.debug("No email recipients configured, skipping")
            email_queue.task_done()
            continue
            
        try:
            msg = MIMEText(f"From: {sender}\nTime: {timestamp}\nMessage: {message}")
            msg['Subject'] = f"SMS from {sender} at {timestamp}" if sms_id else "System Notification"
            msg['From'] = email_config.get("sender", email_config["smtp_user"])
            msg['To'] = ", ".join(recipients)
            
            logger.debug(f"Attempting to send email to {recipients}")
            with smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"]) as server:
                server.starttls()
                server.login(email_config["smtp_user"], email_config["smtp_password"])
                server.send_message(msg)
            logger.info(f"Successfully sent email to {recipients}")
            failed_services.discard("Email")  # Mark Email as available immediately
            logger.debug("Email marked as available after successful send")
            
            if sms_id:
                mark_as_forwarded(db_file, sms_id, email_forwarded=True)
        except Exception as e:
            logger.error(f"Email forwarding failed: {e}")
            if retry_count < max_retries:
                failed_services.add("Email")  # Mark Email as unavailable on each retry
                logger.debug(f"Email marked as unavailable after retry {retry_count + 1}/{max_retries}")
                logger.warning(f"Email forwarding failed, retrying ({retry_count + 1}/{max_retries})")
                time.sleep(5 * retry_count)
                email_queue.put((sender, timestamp, message, sms_id, retry_count + 1))
            else:
                failed_services.add("Email")  # Ensure it’s marked unavailable after max retries
                logger.debug(f"Email marked as unavailable after max retries")
                if sms_id:
                    notify_failure("Email", sms_id, full_config)
                logger.error(f"Email forwarding failed after {max_retries} retries for SMS ID={sms_id}")
        
        email_queue.task_done()
# utils.py
import logging
import time
import queue
import os

logger = logging.getLogger('SMSForwarder')
failed_services = set()
api_queue = queue.Queue()
sms_queue = queue.Queue()
email_queue = queue.Queue()

def setup_logging():
    logger.setLevel(logging.INFO)
    log_file = 'sms_forwarder.log'
    file_handler = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

def notify_failure(service_name, sms_id, config):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    message = f"Service {service_name} failed after max retries for SMS ID: {sms_id} at {timestamp}"
    logger.info(f"Generating failure notification: {message}")
    
    # Queue to available services based on real-time failed_services status
    if "SMS" not in failed_services and config["sms_recipients"]:
        logger.debug(f"Queuing SMS notification to {config['sms_recipients']}")
        sms_queue.put(("System", timestamp, message, None, 0))
    if "Email" not in failed_services and config["email"]["recipients"]:
        logger.debug(f"Queuing Email notification to {config['email']['recipients']}")
        email_queue.put(("System", timestamp, message, None, 0))
    if "API" not in failed_services and config["api_providers"]:
        logger.debug(f"Queuing API notification to {config['api_providers']}")
        api_queue.put(("System", timestamp, message, None, 0))
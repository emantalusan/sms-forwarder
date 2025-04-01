# main.py
import threading
from gsmmodem.modem import GsmModem
import logging
from config import load_config
from database import init_database
from forwarders import api_forward_worker, sms_forward_worker, email_forward_worker
from sms_handler import handle_sms
from utils import setup_logging
import warnings
from urllib3.exceptions import NotOpenSSLWarning

logger = logging.getLogger('SMSForwarder')

def main():
    warnings.filterwarnings("ignore", category=NotOpenSSLWarning)
    setup_logging()
    config = load_config()
    init_database(config["database"]["file"])
    
    try:
        logger.info(f"Attempting to connect to modem on port {config['modem']['port']}")
        modem = GsmModem(config["modem"]["port"], config["modem"]["baudrate"], 
                        smsReceivedCallbackFunc=lambda sms: handle_sms(sms, config=config))
        modem.smsTextMode = False
        logger.info("Connecting to modem...")
        modem.connect(config["modem"]["pin"])
        logger.info("Waiting for network coverage...")
        modem.waitForNetworkCoverage(30)
        logger.info("Modem successfully initialized")
        
        threading.Thread(target=api_forward_worker, args=(config, config["database"]["file"]), 
                        daemon=True, name="API-Forwarder").start()
        threading.Thread(target=sms_forward_worker, args=(modem, config["database"]["file"], config), 
                        daemon=True, name="SMS-Forwarder").start()
        threading.Thread(target=email_forward_worker, args=(config["email"], config["database"]["file"], config),  # Added full config
                        daemon=True, name="Email-Forwarder").start()
        
        logger.info("Started forwarding threads")
        try:
            modem.rxThread.join(2**31)
        finally:
            modem.close()
            logger.info("Modem closed")
    except Exception as e:
        logger.error(f"Failed to initialize modem: {str(e)}")
        raise

if __name__ == '__main__':
    main()
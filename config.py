# config.py
import json
import os
import logging
import logging.handlers  # Added explicit import

logger = logging.getLogger('SMSForwarder')

def load_config(config_file="config.json", sample_file="config.json.sample"):
    if not os.path.exists(config_file):
        if not os.path.exists(sample_file):
            raise FileNotFoundError(f"Neither {config_file} nor {sample_file} found")
        with open(sample_file, 'r') as f:
            default_config = json.load(f)
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=4)
        logger.info(f"Created default config file {config_file}")
        return default_config
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        required_keys = ["modem", "sms_recipients", "email", "api_providers", "database", "default_timeout"]
        if not all(key in config for key in required_keys):
            raise ValueError(f"Invalid config format: missing one of {required_keys}")
        if config.get("debug", False):
            logger.setLevel(logging.DEBUG)
        logger.info("Config loaded successfully")
        return config
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Error loading config: {e}. Using default config")
        with open(sample_file, 'r') as f:
            return json.load(f)
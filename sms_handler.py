# sms_handler.py
from collections import defaultdict
import logging
from database import save_or_update_sms
from utils import api_queue, sms_queue, email_queue
from gsmmodem.pdu import Concatenation

logger = logging.getLogger('SMSForwarder')
multipart_messages = defaultdict(lambda: defaultdict(dict))

def handle_sms(sms, provider=None, config=None):
    sender = sms.number
    timestamp = sms.time
    text = sms.text
    db_file = config["database"]["file"]
    
    if hasattr(sms, 'udh') and sms.udh:
        for udh_element in sms.udh:
            if isinstance(udh_element, Concatenation):
                ref_num = udh_element.reference
                total_parts = udh_element.parts
                part_num = udh_element.number
                
                sms_id = save_or_update_sms(sender, timestamp, text, db_file, ref_num, total_parts, part_num)
                message_data = multipart_messages[sender][ref_num]
                
                if 'parts' not in message_data:
                    message_data.update({'parts': [], 'total_parts': total_parts, 'timestamp': timestamp})
                
                message_data['parts'].append((part_num, text))
                
                if len(message_data['parts']) == total_parts:
                    complete_message = ''.join(part[1] for part in sorted(message_data['parts']))
                    api_queue.put((sender, timestamp, complete_message, sms_id, 0, provider))
                    sms_queue.put((sender, timestamp, complete_message, sms_id, 0))
                    email_queue.put((sender, timestamp, complete_message, sms_id, 0))
                    del multipart_messages[sender][ref_num]
                    if not multipart_messages[sender]:
                        del multipart_messages[sender]
                return
    
    sms_id = save_or_update_sms(sender, timestamp, text, db_file)
    api_queue.put((sender, timestamp, text, sms_id, 0, provider))
    sms_queue.put((sender, timestamp, text, sms_id, 0))
    email_queue.put((sender, timestamp, text, sms_id, 0))
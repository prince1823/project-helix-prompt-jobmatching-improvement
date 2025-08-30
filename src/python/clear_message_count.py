from datetime import datetime
from configs import config
from services.db_service import db_service

for recruiter in config["whatsapp"]:
    db_service.reset_message_counts(recruiter["recruiter_id"])
    print(
        f"[{datetime.now().isoformat()}] Cleared active counts for {recruiter['recruiter_id']}"
    )

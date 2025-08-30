from app.core.config import config
from app.services.redis_service import Service

if __name__ == "__main__":
    redis_service = Service(config["redis"]["multiline"]["db"])
    redis_service.handle_expiry()

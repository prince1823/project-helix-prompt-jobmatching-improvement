from app.services.kafka_service import Service

if __name__ == "__main__":
    kafka_service = Service()
    kafka_service.consume_candidate_messages()

import re
import hashlib
from datetime import datetime, timezone
from dateutil.parser import isoparse
from typing import List, Optional

import shortuuid
from sqlalchemy import and_
from sqlalchemy.exc import NoResultFound

from my_logger import logger
from exceptions import MyException, ErrorMessages
from models import Applicant, LanguageEnum, UserWorkflowStatus, DisabledBy
from schema import (
    get_db,
    ApplicantTable,
    DocumentsTable,
    RecruiterTable,
    ConversationsTable,
    UserLogin,
    WhatsmeowContact,
)


class DBService:
    def get_user_in_db(self, user: Applicant, key: str) -> Optional[Applicant]:
        """
        Retrieves a user from the database by applicant_id and recruiter_id.
        If the user does not exist, it creates a new user with the provided applicant_id and recruiter_id.
        If applicant already exists it sends a notification to current recruiter and disable the chat with applicant.
        :param applicant_id: The ID of the applicant.
        :param recruiter_id: The ID of the recruiter.
        :return: An Applicant object containing user information.
        """
        try:
            logger.info(
                f"[get_user_in_db] Retrieving user with applicant_id: {user.applicant_id} and recruiter_id: {user.recruiter_id}"
            )
            session = get_db()
            db_user = (
                session.query(ApplicantTable)
                .filter(
                    ApplicantTable.applicant_id == user.applicant_id,
                    ApplicantTable.recruiter_id == user.recruiter_id,
                    ApplicantTable.user_workflow_status != UserWorkflowStatus.RETIRED,
                )
                .first()
            )
            if db_user:
                logger.info(
                    f"[get_user_in_db] User with applicant_id: {user.applicant_id} against recruiter_id: {user.recruiter_id} found in database."
                )
                return Applicant(**db_user.__dict__)
            else:
                logger.info(
                    f"[get_user_in_db] User with applicant_id: {user.applicant_id} against recruiter_id: {user.recruiter_id} not found in database."
                )
                db_user = (
                    session.query(ApplicantTable)
                    .filter(
                        ApplicantTable.applicant_id == user.applicant_id,
                        ApplicantTable.user_workflow_status
                        != UserWorkflowStatus.RETIRED,
                    )
                    .first()
                )
                if not db_user:
                    logger.info(
                        f"[get_user_in_db] User with applicant_id: {user.applicant_id} not found in database against any recruiter."
                    )
                    raise NoResultFound
                else:
                    try:
                        if db_user.user_workflow_status in [
                            UserWorkflowStatus.DETAILS_IN_PROGRESS,
                            UserWorkflowStatus.INITIATED,
                        ]:
                            logger.info(
                                f"[get_user_in_db] User with applicant_id: {user.applicant_id} exists with status: {db_user.user_workflow_status} against recruiter {db_user.recruiter_id}."
                            )
                            # Create a new record with the same data but different recruiter_id
                            original_data = {
                                c.name: getattr(db_user, c.name)
                                for c in db_user.__table__.columns
                            }
                            original_data.update(
                                {
                                    "recruiter_id": user.recruiter_id,
                                    "created_at": datetime.now().isoformat(),
                                    "updated_at": None,
                                }
                            )
                            new_record = ApplicantTable(**original_data)
                            session.add(new_record)
                            # Update the original user's status to RETIRED
                            db_user.user_workflow_status = UserWorkflowStatus.RETIRED  # type: ignore
                            db_user.updated_at = datetime.now().isoformat()  # type: ignore
                            session.add(db_user)
                            session.commit()
                            session.refresh(db_user)
                            logger.info(
                                f"[get_user_in_db] Retired user with applicant_id: {user.applicant_id} and recruiter_id: {db_user.recruiter_id} status: {db_user.user_workflow_status}."
                            )
                            self.disable_chat(
                                applicant_ids=[user.applicant_id],
                                recruiter_id=db_user.recruiter_id,  # type: ignore
                                disabled_by=DisabledBy.USER,
                            )
                            return Applicant(**original_data)
                        if (
                            db_user.user_workflow_status
                            == UserWorkflowStatus.DETAILS_COMPLETED
                        ):  # type: ignore
                            logger.info(
                                f"[get_user_in_db] User with applicant_id: {user.applicant_id} exists with status: {db_user.user_workflow_status} against recruiter {db_user.recruiter_id}."
                            )
                            from services.util_service import (
                                send_message,
                                applicant_completion_data,
                            )

                            self.disable_chat(
                                applicant_ids=[user.applicant_id],
                                recruiter_id=user.recruiter_id,
                                disabled_by=DisabledBy.SYSTEM,
                            )
                            send_message(
                                response={
                                    "chat_id": f"{user.recruiter_id}@s.whatsapp.net",
                                    "content": applicant_completion_data(
                                        Applicant(**db_user.__dict__)
                                    ),
                                    "msg_type": "text",
                                    "receiver_id": str(user.recruiter_id),
                                    "sender_id": str(user.applicant_id),
                                    "timestamp": datetime.now().strftime(
                                        "%Y-%m-%dT%H:%M:%SZ"
                                    ),
                                    "mid": shortuuid.uuid(),
                                },
                                key=key,
                                locale=LanguageEnum.ENGLISH,
                            )
                    except Exception as e:
                        logger.error(
                            f"[get_user_in_db] Error processing existing user: {e}"
                        )
        except NoResultFound:
            logger.info(
                f"[get_user_in_db] Creating new user with applicant_id: {user.applicant_id} and recruiter_id: {user.recruiter_id}"
            )
            db_source = ApplicantTable(
                applicant_id=user.applicant_id,
                recruiter_id=user.recruiter_id,
                user_workflow_status=UserWorkflowStatus.INITIATED,
                created_at=datetime.now().isoformat(),
            )
            session.add(db_source)
            session.commit()
            session.refresh(db_source)
            return Applicant(**db_source.__dict__)
        except MyException as me:
            logger.error(f"[get_user_in_db] MyException occurred: {me}")
            raise me
        except Exception as e:
            logger.error(f"[get_user_in_db] Error retrieving user: {e}")
            raise MyException(
                block="get_user_in_db",
                error_code=ErrorMessages.USER_NOT_FOUND,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )
        finally:
            session.close()

    def update_user_in_db(self, user: Applicant) -> ApplicantTable | None:
        """
        Updates an existing user in the database with the provided Applicant object.
        :param user: An Applicant object containing the updated user data.
        :return: The updated ApplicantTable object from the database.
        """
        try:
            session = get_db()
            logger.info(
                f"[update_user_in_db] Updating user with applicant_id: {user.applicant_id}"
            )
            db_source = (
                session.query(ApplicantTable)
                .filter(
                    ApplicantTable.applicant_id == user.applicant_id,
                    ApplicantTable.recruiter_id == user.recruiter_id,
                    ApplicantTable.user_workflow_status != UserWorkflowStatus.RETIRED,
                )
                .first()
            )
            if not db_source:
                raise NoResultFound
            for key, value in user.model_dump(exclude_unset=True).items():
                if key in ["applicant_id", "recruiter_id", "created_at", "updated_at"]:
                    continue
                setattr(db_source, key, value)
                logger.info(
                    f"[update_user_in_db] Setting {key} to {value} for user with applicant_id: {user.applicant_id}"
                )
            setattr(db_source, "updated_at", datetime.now().isoformat())
            session.commit()
            session.refresh(db_source)
            session.close()
            return db_source
        except NoResultFound:
            logger.error(
                f"[update_user_in_db] User with applicant_id: {user.applicant_id} not found in database."
            )
        except Exception as e:
            logger.error(f"[update_user_in_db] Error updating user: {e}")
            raise MyException(
                block="update_user_in_db",
                error_code=ErrorMessages.USER_UPDATE_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )

    def update_response(self, response: dict):
        """
        Updates the response message in the database and sends it to the Kafka output topic.
        :param event: A dictionary containing the event data.
        :param key: The key for the Kafka message.
        """
        try:
            logger.info(f"[update_response] Updating response for event: {response}")
            user = Applicant(
                applicant_id=response["receiver_id"],
                recruiter_id=response["sender_id"],
                response=response["content"],
            )
            self.update_user_in_db(user)
            self.increment_message_count(user)
        except MyException as me:
            logger.error(f"[get_user_in_db] MyException occurred: {me}")
            raise me
        except Exception as e:
            logger.error(f"[update_response] Error updating response in database: {e}")
            raise MyException(
                block="update_response",
                error_code=ErrorMessages.USER_RESPONSE_UPDATE_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )

    def update_document_in_db(self, event: dict) -> DocumentsTable | None:
        """
        Updates or inserts the document record for the applicant:
        - If record exists: appends file_url to the s3_file_urls JSON array if not present.
        - If record does not exist: creates a new record with the file_url.
        """
        try:
            applicant_id = int(event["sender_id"])
            recruiter_id = int(event["receiver_id"])
            file_name = event["file_name"]
            logger.info(
                f"Updating document URL in database for applicant_id: {applicant_id}, recruiter_id: {recruiter_id}, file_name: {file_name}"
            )
            session = get_db()
            db_source = (
                session.query(DocumentsTable)
                .join(
                    ApplicantTable,
                    and_(
                        DocumentsTable.applicant_id == ApplicantTable.applicant_id,
                        DocumentsTable.recruiter_id == ApplicantTable.recruiter_id,
                    ),
                )
                .filter(
                    ApplicantTable.applicant_id == applicant_id,
                    ApplicantTable.recruiter_id == recruiter_id,
                    ApplicantTable.user_workflow_status != UserWorkflowStatus.RETIRED,
                )
                .first()
            )
            if not db_source:
                db_source = DocumentsTable(
                    applicant_id=applicant_id,
                    recruiter_id=recruiter_id,
                    file_paths=[file_name],
                    updated_at=datetime.now().isoformat(),
                )
                session.add(db_source)
                logger.info(
                    f"Created new document record for applicant_id: {applicant_id}"
                )
            else:
                file_paths = db_source.file_paths + [file_name]
                setattr(db_source, "file_paths", file_paths)
                setattr(db_source, "updated_at", datetime.now().isoformat())
                session.add(db_source)
                logger.info(
                    f"Updated existing document record for applicant_id: {applicant_id}"
                )
            session.commit()
            session.refresh(db_source)
            return db_source
        except Exception as e:
            logger.error(f"Error updating document URL in database: {e}")
            session.rollback()
            raise MyException(
                block="update_document_url_in_db",
                error_code=ErrorMessages.DOCUMENT_DB_UPDATE_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )
        finally:
            session.close()

    def get_users(self, recruiter: Applicant) -> List[Applicant] | None:
        try:
            logger.info(
                f"[get_users] Retrieving all users for recruiter_id: {recruiter.recruiter_id}"
            )
            session = get_db()
            db_users = (
                session.query(ApplicantTable)
                .filter_by(recruiter_id=recruiter.recruiter_id)
                .all()
            )
            if not db_users:
                logger.info(
                    f"[get_users] No Users with recruiter_id: {recruiter.recruiter_id} found in database."
                )
                raise NoResultFound
            return [Applicant(**user.__dict__) for user in db_users]
        except NoResultFound:
            # TODO: send message no users found
            pass
        except MyException as me:
            logger.error(f"[get_users] MyException occurred: {me}")
            raise me
        except Exception as e:
            logger.error(f"[get_users] Error retrieving user: {e}")
            raise MyException(
                block="get_users",
                error_code=ErrorMessages.USER_NOT_FOUND,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )
        finally:
            session.close()

    def disable_chat(
        self, recruiter_id: int, applicant_ids: List[int], disabled_by: str
    ):
        try:
            logger.info(
                f"[db_disable_chat] Disabling chat for recruiter_id: {recruiter_id} with applicant_id: {applicant_ids}"
            )
            updated_by = (
                disabled_by if disabled_by == DisabledBy.SYSTEM else str(recruiter_id)
            )
            session = get_db()
            for applicant_id in applicant_ids:
                chat = (
                    session.query(RecruiterTable)
                    .filter_by(recruiter_id=recruiter_id, applicant_id=applicant_id)
                    .first()
                )
                if not chat:
                    logger.info(
                        f"[db_disable_chat] Entry with applicant_id: {applicant_id} and recruiter_id: {recruiter_id} not found in database."
                    )
                    chat = RecruiterTable(
                        applicant_id=applicant_id,
                        recruiter_id=recruiter_id,
                        is_blocked=True,
                        created_at=datetime.now().isoformat(),
                        updated_by=updated_by,
                    )
                    session.add(chat)
                else:
                    logger.info(
                        f"[db_disable_chat] Updating entry with applicant_id: {applicant_id} and recruiter_id: {recruiter_id}"
                    )
                    setattr(chat, "is_blocked", True)
                    setattr(chat, "updated_at", datetime.now().isoformat())
                    setattr(chat, "updated_by", updated_by)
                session.commit()
        except Exception as e:
            logger.error(f"[db_disable_chat] Error updating user: {e}")
            raise MyException(
                block="db_disable_chat",
                error_code=ErrorMessages.CHAT_DISABLE_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )
        finally:
            session.close()

    def increment_message_count(self, user: Applicant):
        """
        Increment the message counter for chat
        :param user: chat representation for recruiter and applicant
        """
        try:
            session = get_db()
            logger.info(
                f"[increment_chat_count] Incrementing chat count for applicant_id: {user.applicant_id}"
            )
            chat_config = (
                session.query(RecruiterTable)
                .filter_by(
                    applicant_id=user.applicant_id, recruiter_id=user.recruiter_id
                )
                .first()
            )
            if not chat_config:
                raise NoResultFound
            setattr(chat_config, "message_count", chat_config.message_count + 1)
            logger.info(
                f"[increment_chat_count] Setting message_count to {chat_config.message_count + 1} for user with applicant_id: {user.applicant_id}"
            )
            setattr(chat_config, "updated_at", datetime.now().isoformat())
            session.commit()
        except NoResultFound:
            logger.error(
                f"[increment_chat_count] User with applicant_id: {user.applicant_id} not found in database."
            )
            chat_config = RecruiterTable(
                recruiter_id=user.recruiter_id,
                applicant_id=user.applicant_id,
                is_blocked=False,
                message_count=1,
                created_at=datetime.now().isoformat(),
            )
            session.add(chat_config)
            session.commit()
        except Exception as e:
            logger.error(f"[increment_chat_count] Error updating user: {e}")
            raise MyException(
                block="increment_chat_count",
                error_code=ErrorMessages.MESSAGE_COUNT_INCREMENT_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )
        finally:
            session.close()

    def reset_message_counts(self, recruiter_id: int):
        """
        Reset the message counter for all enabled chats
        """
        try:
            session = get_db()
            logger.info(f"[reset_message_counts] Resetting message counts for the day")
            chat_configs = (
                session.query(RecruiterTable)
                .filter_by(recruiter_id=recruiter_id, is_blocked=False)
                .all()
            )
            if not chat_configs:
                raise NoResultFound
            for chat_config in chat_configs:
                setattr(chat_config, "message_count", 0)
                logger.info(
                    f"[increment_chat_count] Setting message_count to 0 for user with applicant: {chat_config['applicant_id']}"
                )
                setattr(chat_config, "updated_at", datetime.now().isoformat())
            session.commit()
        except Exception as e:
            logger.error(f"[reset_message_counts] Error resetting message counter: {e}")
            raise MyException(
                block="reset_message_counts",
                error_code=ErrorMessages.MESSAGE_COUNT_RESET_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )
        finally:
            session.close()

    def store_conversation(self, topic: str, event: dict):
        """
        Store the conversation in the database.
        :param conversation: A dictionary containing the conversation data.
        """
        try:
            logger.info(f"[store_conversation] Storing conversation: {event}")
            recruiter_id = int(
                event["sender_id"] if topic == "output" else event["receiver_id"]
            )
            applicant_id = int(
                event["receiver_id"] if topic == "output" else event["sender_id"]
            )
            conversation = {
                "sender_id": event["sender_id"],
                "ts": event["timestamp"],
                "content": event["content"],
                "mid": event.get("mid", shortuuid.uuid()),
                "msg_type": event["msg_type"],
            }
            if event.get("llm_version"):
                conversation["llm_version"] = event["llm_version"]
            session = get_db()
            existing_conversation = (
                session.query(ConversationsTable)
                .filter_by(
                    applicant_id=applicant_id,
                    recruiter_id=recruiter_id,
                )
                .first()
            )
            if existing_conversation:
                logger.info(
                    f"[store_conversation] Found existing conversation for recruiter {recruiter_id} and applicant {applicant_id}"
                )
                setattr(
                    existing_conversation,
                    "conversations",
                    existing_conversation.conversations + [conversation],
                )
                if isoparse(event["timestamp"]).astimezone(timezone.utc) < isoparse(
                    str(existing_conversation.created_at)
                ).astimezone(timezone.utc):
                    logger.info(
                        f"[store_conversation] Updating created_at for existing conversation: {existing_conversation.created_at} to {event['timestamp']}"
                    )
                    setattr(existing_conversation, "created_at", isoparse(event["timestamp"]).astimezone(timezone.utc))
                if isoparse(event["timestamp"]).astimezone(timezone.utc) > isoparse(
                    str(existing_conversation.updated_at)
                ).astimezone(timezone.utc):
                    logger.info(
                        f"[store_conversation] Updating updated_at for existing conversation: {existing_conversation.updated_at} to {event['timestamp']}"
                    )
                    setattr(existing_conversation, "updated_at", isoparse(event["timestamp"]).astimezone(timezone.utc))
                session.commit()
                session.refresh(existing_conversation)
            else:
                logger.info(
                    f"[store_conversation] No existing conversation found for recruiter {event['receiver_id']} and applicant {event['sender_id']}, creating new one."
                )
                new_conversation = ConversationsTable(
                    recruiter_id=int(event["receiver_id"]),
                    applicant_id=int(event["sender_id"]),
                    conversations=[conversation],
                    created_at=isoparse(event["timestamp"]).astimezone(timezone.utc),
                    updated_at=isoparse(event["timestamp"]).astimezone(timezone.utc),
                )
                session.add(new_conversation)
                session.commit()
        except Exception as e:
            logger.error(f"[store_conversation] Error retrieving user: {e}")
            raise MyException(
                block="store_conversation",
                error_code=ErrorMessages.CONVERSATION_STORE_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )
        finally:
            session.close()

    def create_ui_user(self, username: str, password: str, role: str) -> bool:
        """
        Create a new user with the given username, password, and role.
        :param username: The username of the user.
        :param password: The plain text password of the user.
        :param role: The role of the user (e.g., 'admin', 'annotator').
        :return: A dictionary containing the created user's details.
        """
        try:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            logger.info(f"[create_ui_user] Creating user {username} with role {role}")
            session = get_db()
            existing_user = (
                session.query(UserLogin).filter_by(username=username).first()
            )
            if existing_user:
                logger.error(
                    f"[create_ui_user] User with username {username} already exists. Updating password and role."
                )
                setattr(existing_user, "password", password_hash)
                setattr(existing_user, "role", role)
                setattr(existing_user, "updated_at", datetime.now().isoformat())
                session.commit()
                session.refresh(existing_user)
                return True
            # Create a new user
            logger.info(
                f"[create_ui_user] User with username {username} does not exist. Creating new user."
            )
            new_user = UserLogin(
                username=username,
                password=password_hash,
                role=role,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
            )
            session.add(new_user)
            session.commit()
            session.refresh(new_user)
            return True
        except Exception as e:
            logger.error(f"[create_ui_user] Error creating user: {e}")
            raise MyException(
                block="create_ui_user",
                error_code=ErrorMessages.USER_UPDATE_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )

    def get_user_status_in_db(self, user: Applicant) -> UserWorkflowStatus:
        """
        Retrieves a user from the database by applicant_id and recruiter_id.
        If the user does not exist, it creates a new user with the provided applicant_id and recruiter_id.
        :param applicant_id: The ID of the applicant.
        :param recruiter_id: The ID of the recruiter.
        :return: An Applicant object containing user information.
        """
        try:
            logger.info(
                f"[get_user_status_in_db] Retrieving user with applicant_id: {user.applicant_id} and recruiter_id: {user.recruiter_id}"
            )
            session = get_db()
            db_user = (
                session.query(ApplicantTable)
                .filter(
                    ApplicantTable.applicant_id == user.applicant_id,
                    ApplicantTable.recruiter_id == user.recruiter_id,
                )
                .first()
            )
            if not db_user:
                logger.info(
                    f"[get_user_status_in_db] User with applicant_id: {user.applicant_id}, recruiter_id: {user.recruiter_id} not found in database."
                )
                db_user = (
                    session.query(ApplicantTable)
                    .filter(
                        ApplicantTable.applicant_id == user.applicant_id,
                        ApplicantTable.user_workflow_status
                        != UserWorkflowStatus.RETIRED,
                    )
                    .first()
                )
                if not db_user:
                    logger.info(
                        f"[get_user_status_in_db] User with applicant_id: {user.applicant_id} not found in database against any recruiter."
                    )
                    return UserWorkflowStatus.NOT_INITIATED
                else:
                    logger.info(
                        f"[get_user_status_in_db] User with applicant_id: {user.applicant_id} exists with status: {db_user.user_workflow_status} against recruiter {db_user.recruiter_id}."
                    )
                    return UserWorkflowStatus(db_user.user_workflow_status)
            else:
                return UserWorkflowStatus(db_user.user_workflow_status)
        except MyException as me:
            logger.error(f"[get_user_status_in_db] MyException occurred: {me}")
            raise me
        except Exception as e:
            logger.error(f"[get_user_status_in_db] Error retrieving user: {e}")
            raise MyException(
                block="get_user_status_in_db",
                error_code=ErrorMessages.USER_NOT_FOUND,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )
        finally:
            session.close()

    def get_contacts(self, recruiter_id: str):
        session = get_db()
        try:
            # Fetch all their_jid values where recruiter_id matches and full_name is not null
            results = (
                session.query(WhatsmeowContact.their_jid)
                .filter(
                    WhatsmeowContact.our_jid.like(f"{recruiter_id}%"),
                    WhatsmeowContact.full_name.isnot(None),
                )
                .all()
            )

            # Regex to extract 12-digit number from the start of the JID
            # Match exactly 12 digits at the beginning of the string
            pattern = re.compile(r"^(\d{12})")

            result_list = [
                int(match.group(1))
                for row in results
                if (match := pattern.match(row[0]))
            ]
            logger.info(f"[get_contacts] Total Contacts  : {len(result_list)} ")
            logger.info(f"[get_contacts] Contacts extracted : {result_list} ")
            return result_list

        except Exception as e:
            logger.error(f"[get_contacts] Error: {e}")
            raise
        finally:
            session.close()


db_service = DBService()

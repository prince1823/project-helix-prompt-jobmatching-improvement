import os
import base64
from uuid import uuid4
from datetime import datetime, timedelta

import boto3
import shortuuid
from fastapi import HTTPException, status as http_status
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

from app.db.postgres import get_db

from app.core.logger import logger
from app.core.config import config
from app.core.authorization import get_user_details
from app.core.exception import MyException, ErrorMessages
from app.repositories.documents import Repository
from app.repositories.config import Repository as ConfigRepository
from app.core.constants import DOCUMENT_SAVED, INTRODUCTION_MESSAGE
from app.repositories.applicants import Repository as ApplicantRepository

from app.models.utils import Event
from app.models.configs import Model as Config
from app.models.user_login import UserDetails, Role
from app.models.applicants import Status as ApplicantStatus
from app.models.documents import Model, Request, Response, Document

from app.services.util_service import send_message
from app.services.applicants import Service as ApplicantService
from app.services.job_service import job_service


class Service:
    def __init__(self, repo: Repository):
        self.repo = repo
        self.config_repo = ConfigRepository(self.repo.db)

    def create(self, user_details: UserDetails, body: Request) -> Response:
        model = Model(
            recruiter_id=user_details.id,
            applicant_id=body.request.applicant_id,
            file_paths=body.request.file_paths,
        )
        table = self.repo.create(model)
        if not table:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND, detail="Document not found"
            )
        model = Model.model_validate(table)
        return Response(mid=body.mid, ts=datetime.now(), data=[model])

    def get_all(self, user_details: UserDetails) -> Response:
        admin = False
        if user_details.role == Role.ADMIN:
            admin = True
        documents = self.repo.get_all(id=user_details.id, admin=admin)
        return Response(
            mid=uuid4(),
            ts=datetime.now(),
            data=[Model.model_validate(doc) for doc in documents],
        )

    def get(self, user_details: UserDetails, id: int) -> Response:
        table = self.repo.get(id=id)
        if not table:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )
        model = Model.model_validate(table)
        if model.recruiter_id != user_details.id and user_details.role != Role.ADMIN:  # type: ignore
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this document",
            )
        return Response(
            data=[model],
            mid=uuid4(),
            ts=datetime.now(),
        )

    def get_by_recruiter_applicant(
        self, user_details: UserDetails, recruiter_id: int, applicant_id: int
    ) -> Response:
        table = self.repo.get_by_recruiter_and_applicant(recruiter_id, applicant_id)
        if not table:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND, detail="Documents not found"
            )
        model = Model.model_validate(table)
        if model.recruiter_id != user_details.id and user_details.role != Role.ADMIN:  # type: ignore
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this document",
            )
        return Response(
            data=[model],
            mid=uuid4(),
            ts=datetime.now(),
        )

    def update(self, user_details: UserDetails, body: Request) -> Response:
        table = self.repo.update_document(
            recruiter_id=user_details.id,
            applicant_id=body.request.applicant_id,
            file_path=body.request.file_paths,
        )
        model = Model.model_validate(table)
        if model.recruiter_id != user_details.id and user_details.role != Role.ADMIN:  # type: ignore
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this document",
            )
        return Response(data=[model], mid=uuid4(), ts=datetime.now())

    def create_or_update(self, user_details: UserDetails, body: Document) -> Model:
        repo = Repository(get_db())
        config_repo = ConfigRepository(get_db())
        applicant_id = body.applicant_id
        table = repo.get_by_recruiter_and_applicant(user_details.id, applicant_id)
        logger.info(
            f"Checking document for recruiter {user_details.id} and applicant {applicant_id}"
        )
        if not table:
            config = config_repo.get_by_recruiter_and_applicant(
                user_details.id, applicant_id
            )
            logger.info(f"Config found: {config}")
            if not config:
                config = Config(
                    recruiter_id=user_details.id,
                    applicant_id=applicant_id,
                )  # type: ignore
                config = config_repo.create(config)
            model = Model(
                recruiter_id=user_details.id,
                applicant_id=body.applicant_id,
                file_paths=body.file_paths,
            )
            table = repo.create(model)
        else:
            logger.info(
                f"Document found for recruiter {user_details.id} and applicant {applicant_id}"
            )
            table = repo.update_document(
                recruiter_id=user_details.id,
                applicant_id=body.applicant_id,
                file_path=body.file_paths,
            )
        logger.info(f"Document updated or created: {table.__dict__}")
        model = Model.model_validate(table)
        logger.info(f"Document found or created: {model}")
        if model.recruiter_id != user_details.id and user_details.role != Role.ADMIN:  # type: ignore
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this document",
            )
        logger.info(f"Document created/updated successfully: {model}")
        repo.close()
        config_repo.close()
        return model

    def process_document(self, event: Event) -> Model:
        user_details = get_user_details(x_user_id=str(event.receiver_id), db=get_db())
        file_extension = event.mime_type.split("/")[1]  # type: ignore
        if file_extension not in ["pdf", "docx", "txt", "csv", "xlsx"]:
            raise ValueError(
                f"Unsupported file type: {file_extension}. Supported types are pdf, docx, txt, csv, xlsx."
            )

        file_name = f"{event.receiver_id}/{event.sender_id}/{str(int(datetime.now().timestamp() * 1000))}.{file_extension}"
        file_bytes = base64.b64decode(event.content)  # type: ignore
        upload_response = self.azure_upload_file(
            {
                "mime_type": event.mime_type,
                "content": file_bytes,
                "file_name": file_name,
            }
        )
        if not upload_response:
            raise Exception("Failed to upload file to S3.")
        else:
            logger.info(
                f"File uploaded successfully to Azure Blob Storage: {file_name}"
            )
            document = Document(
                applicant_id=event.sender_id,
                file_paths=[file_name],
            )
            document = self.create_or_update(
                user_details=user_details,
                body=document,
            )
            logger.info(f"Document processed successfully: {document}")
            response_event = Event(
                mid=shortuuid.uuid(),
                chat_id=event.chat_id,
                content=DOCUMENT_SAVED,
                msg_type="text",
                receiver_id=event.sender_id,
                sender_id=event.receiver_id,
                timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            send_message(
                user_details=user_details,
                applicant_id=event.sender_id,
                event=response_event,
                key=f"{event.receiver_id}_{event.sender_id}",
            )
            applicants_repo = ApplicantRepository(get_db())
            applicants_service = ApplicantService(applicants_repo)
            applicant_status = applicants_service.get_applicant_status(
                user_details=user_details, applicant_id=event.sender_id
            )
            if applicant_status == ApplicantStatus.NOT_INITIATED:
                response_event = Event(
                    mid=shortuuid.uuid(),
                    chat_id=event.chat_id,
                    content=INTRODUCTION_MESSAGE,
                    msg_type="text",
                    receiver_id=event.sender_id,
                    sender_id=event.receiver_id,
                    timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                )
                send_message(
                    user_details=user_details,
                    applicant_id=event.sender_id,
                    event=response_event,
                    key=f"{event.receiver_id}_{event.sender_id}",
                )
            # elif applicant_status == ApplicantStatus.DETAILS_COMPLETED:
            #     applicants_service.update_status(
            #         user_details=user_details,
            #         applicant_id=event.sender_id,
            #         status=ApplicantStatus.DETAILS_COMPLETED,
            #     )
            #     job_service.get_matching_jobs(
            #         user_details=user_details, applicant_id=event.sender_id
            #     )
            #     job_service.offer_new_job(
            #         user_details=user_details, applicant_id=event.sender_id
            #     )
        return document

    def azure_upload_file(self, event: dict, return_url: bool = False) -> bool | str:
        """
        Uploads a file to Azure Blob Storage.
        :param event: Dictionary containing 'mime_type', 'content', 'file_name'.
        """
        try:
            blob_service_client = BlobServiceClient(
                account_url=f"https://{os.getenv('AZURE_ACCOUNT_NAME', '')}.blob.core.windows.net/",
                credential=os.getenv("AZURE_ACCOUNT_KEY", ""),
            )
            blob_client = blob_service_client.get_blob_client(
                container=os.getenv("AZURE_CONTAINER_NAME", ""), blob=event["file_name"]
            )
            blob_client.upload_blob(
                event["content"],
                metadata={"mime_type": event["mime_type"]},
                overwrite=True,
            )
            if return_url:
                blob_sas_token = generate_blob_sas(
                    account_name=os.getenv("AZURE_ACCOUNT_NAME", ""),
                    container_name=os.getenv("AZURE_CONTAINER_NAME", ""),
                    blob_name=event["file_name"],
                    account_key=os.getenv("AZURE_ACCOUNT_KEY", ""),
                    expiry=datetime.now() + timedelta(minutes=5),
                    permission=BlobSasPermissions(read=True),
                )
                return f"https://{os.getenv('AZURE_ACCOUNT_NAME', '')}.blob.core.windows.net/{os.getenv('AZURE_CONTAINER_NAME', '')}/{event['file_name']}?{blob_sas_token}"
            return True
        except Exception as e:
            raise MyException(
                block="upload_file_azure",
                error_code=ErrorMessages.AZURE_UPLOAD_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )

    def s3_upload_file(self, event: dict) -> bool:
        """
        Uploads a file to S3 and returns the file URL.
        :param event: Dictionary containing 'mime_type', 'content', 'receiver_id', 'sender_id'.
        :return: Dict with 'file_url', 'file_name', 'file_extension'.
        """
        try:
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=os.getenv("AWS_REGION"),
            )
            response = s3_client.put_object(
                Bucket=config["cloud"]["storage"]["bucket"],
                Key=event["file_name"],
                Body=event["content"],
                ContentType=event["mime_type"],
                IfNoneMatch="*",
            )
            if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
                return True
            else:
                return False
        except Exception as e:
            raise MyException(
                block="upload_file_s3",
                error_code=ErrorMessages.S3_UPLOAD_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )

    def delete(self, applicant_id: int, recruiter_id: int) -> None:
        repo = Repository(get_db())
        logger.info(f"[delete] Deleting applicant {applicant_id}")
        repo.delete(recruiter_id=recruiter_id, applicant_id=applicant_id)
        repo.close()

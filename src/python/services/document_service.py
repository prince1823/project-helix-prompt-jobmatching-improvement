import os
import base64
from datetime import datetime, timedelta

import boto3
import shortuuid
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

from configs import config
from my_logger import logger
from models import LanguageEnum
from constants import DOCUMENT_SAVED
from services.util_service import send_message
from exceptions import MyException, ErrorMessages


class DocumentService:
    def azure_upload_file(self, event: dict, return_url: bool = False) -> bool | str:
        """
        Uploads a file to Azure Blob Storage.
        :param event: Dictionary containing 'mime_type', 'content', 'file_name'.
        """
        try:
            logger.info(
                f"[azure_upload_file] Uploading file to Azure Blob Storage for event: {event}"
            )
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
            logger.error(
                f"[azure_upload_file] Error uploading file to Azure Blob Storage: {e}"
            )
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
            logger.info(f"[s3_upload_file] Uploading file for event: {event}")
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
                logger.error(
                    f"[s3_upload_file] Failed to upload file to S3: {response}"
                )
                return False
        except Exception as e:
            logger.error(f"[s3_upload_file] Error uploading file to S3: {e}")
            raise MyException(
                block="upload_file_s3",
                error_code=ErrorMessages.S3_UPLOAD_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )

    def save_documents(self, event: dict, key: str):
        """
        Saves a file to cloud storage and returns the file URL.
        :param event: Dictionary containing 'mime_type', 'content', 'receiver_id', 'sender_id'.
        :return: Dict with 'file_url', 'file_name', 'file_extension'.
        """
        try:
            logger.info(f"[save_documents] Uploading document for event: {event}")
            file_extension = event["mime_type"].split("/")[1]
            if file_extension not in ["pdf", "docx", "txt", "csv", "xlsx"]:
                logger.error(
                    f"[save_documents] Unsupported file type: {file_extension}"
                )
                raise ValueError(
                    f"Unsupported file type: {file_extension}. Supported types are pdf, docx, txt, csv, xlsx."
                )

            file_name = f"{event['receiver_id']}/{event['sender_id']}/{str(int(datetime.now().timestamp() * 1000))}.{file_extension}"
            file_bytes = base64.b64decode(event["content"])
            upload_response = self.azure_upload_file(
                {
                    "mime_type": event["mime_type"],
                    "content": file_bytes,
                    "file_name": file_name,
                }
            )
            if not upload_response:
                logger.error("[save_documents] Failed to upload file to S3.")
                raise Exception("Failed to upload file to S3.")
            else:
                logger.info(
                    f"[save_documents] File uploaded successfully to S3: {file_name}"
                )
                event["file_name"] = file_name
                from services import db_service

                document = db_service.update_document_in_db(event)
                logger.info(
                    f"[save_documents] Document record updated in database: {document.__dict__}"
                )
                send_message(
                    response={
                        "chat_id": event["chat_id"],
                        "content": DOCUMENT_SAVED,
                        "msg_type": "text",
                        "receiver_id": event["sender_id"],
                        "sender_id": event["receiver_id"],
                        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "mid": shortuuid.uuid(),
                    },
                    key=key,
                    locale=event.get("locale", LanguageEnum.ENGLISH),
                )
        except MyException as me:
            logger.error(f"[save_documents] MyException occurred: {me}")
            raise me
        except Exception as e:
            logger.error(f"[save_documents] Error saving document: {e}")
            raise MyException(
                block="save_documents",
                error_code=ErrorMessages.DOCUMENT_UPLOAD_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )


document_service = DocumentService()

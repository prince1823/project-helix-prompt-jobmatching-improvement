from enum import StrEnum

from app.models.requests import ErrorResponse


class InternalException(Exception):
    def __init__(self, error_response: ErrorResponse, status_code: int):
        self.error_response = error_response
        self.status_code = status_code
        super().__init__(error_response.error.message)


class MyException(Exception):
    def __init__(
        self,
        block: str,
        error_code: str,
        error_type: str,
        error_message: str,
        timestamp: str,
    ):
        self.block = block
        self.error_code = error_code
        self.error_message = error_message
        self.error_type = error_type
        self.timestamp = timestamp


class ErrorMessages(StrEnum):
    """
    This class contains error messages for various operations.
    """

    AUDIO_TRANSLATION_FAILED = "Audio translation failed. Please try again later."
    AUDIO_SPEECH_GENERATION_FAILED = (
        "Audio speech generation failed. Please try again later."
    )
    TEXT_TRANSLATION_FAILED = "Text translation failed. Please try again later."
    USER_NOT_FOUND = "User not found. Please check the provided user ID."
    USER_UPDATE_FAILED = "User update failed. Please try again later."
    USER_LOCALE_UPDATE_FAILED = "User locale update failed. Please try again later."
    USER_RESPONSE_UPDATE_FAILED = "User response update failed. Please try again later."
    DOCUMENT_DB_UPDATE_FAILED = "Document upload failed. Please try again later."
    S3_UPLOAD_FAILED = "File upload to S3 failed. Please try again later."
    AZURE_UPLOAD_FAILED = "File upload to Azure failed. Please try again later."
    DOCUMENT_UPLOAD_FAILED = "Document upload failed. Please try again later."
    LOCALE_INFERENCE_FAILED = "Locale inference failed. Please try again later."
    USER_DETAIL_EXTRACTION_FAILED = (
        "User detail extraction failed. Please try again later."
    )
    KAFKA_MESSAGE_SEND_FAILED = (
        "Failed to send message to Kafka. Please try again later."
    )
    REPORT_GENERATION_FAILED = (
        "There was an error in generating your report. Please try again later."
    )
    CHAT_DISABLE_FAILED = "Failed to disable chat."
    DATA_EXPORT_FAILED = "Failed to export recruiter data"
    MESSAGE_COUNT_INCREMENT_FAILED = (
        "Failed to increment chat counts for recruiter: {} and applicant: {}"
    )
    MESSAGE_COUNT_RESET_FAILED = (
        "Failed to increment chat counts for recruiter: {} and applicant: {}"
    )
    CONVERSATION_STORE_FAILED = "Failed to store conversation. Please try again later."
    USER_PARSING_FAILED = (
        "Failed to parse user details from the message. Please try again later."
    )
    TRANSCRIPTION_ERROR = "Failed to transcribe audio."
    MEDIA_NOT_SUPPORTED = "Unsupported media type."
    COMMAND_PARSING_FAILED = (
        "Failed to parse command from the message. Please try again later."
    )

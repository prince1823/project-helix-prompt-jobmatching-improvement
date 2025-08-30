import os
import json
from io import BytesIO
from datetime import datetime, timedelta

import pandas as pd
from azure.storage.blob import BlobServiceClient


def update_conversation_data(file_path: str) -> None:
    df = pd.read_csv(file_path)
    conversations = df.conversations.values.tolist()
    conversations = [json.loads(i) for i in conversations]
    recruiter_ids = df.recruiter_id.values.tolist()
    applicant_ids = df.applicant_id.values.tolist()
    result = []
    for idx, conversation in enumerate(conversations):
        messages = [recruiter_ids[idx], applicant_ids[idx]]
        sorted_data_robust = sorted(
            conversation,
            key=lambda item: datetime.fromisoformat(
                item["ts"].replace(" ", "").replace("Z", "+00:00")
            ),
        )
        for item in sorted_data_robust:
            if item["msg_type"] != "text":
                item["content"] = "Shared a document"
            if int(item["sender_id"]) == recruiter_ids[idx]:
                messages.append({"Recruiter": item["content"]})
            else:
                messages.append({"Applicant": item["content"]})
        result.append(messages)
    rdf = pd.DataFrame(result)
    cols = [f"message_{i + 1}" for i in range(rdf.shape[1] - 2)]
    rdf.columns = ["recruiter_id", "applicant_id"] + cols
    rdf = rdf[
        ~rdf["applicant_id"].isin(
            [919886770667, 919113211151, 919986585314, 916362597564, 919108677020]
        )
    ]
    rdf = rdf.dropna(axis=1, how="all")  # Drop columns that are null
    rdf.sort_values(by=["recruiter_id", "applicant_id"], inplace=True)
    rdf.to_csv(file_path, index=False)

def merge_blocked_metrics():
    created_df = pd.read_csv("/app/config/app/pgdump_blocked_metrics_created.csv")
    updated_df = pd.read_csv("/app/config/app/pgdump_blocked_metrics_updated.csv")
    merged_df = pd.concat([created_df, updated_df]).sort_values(by=["date", "recruiter_id", "updated_by"])
    merged_df.to_csv("/app/config/app/pgdump_blocked_metrics.csv", index=False)

def data_export(file_path: str, blob_name: str) -> None:
    df = pd.read_csv(file_path)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Data")
    buffer.seek(0)
    byte_data = buffer.getvalue()
    blob_service_client = BlobServiceClient(
        account_url=f"https://{os.getenv('AZURE_ACCOUNT_NAME', '')}.blob.core.windows.net/",
        credential=os.getenv("AZURE_ACCOUNT_KEY", ""),
    )
    blob_client = blob_service_client.get_blob_client(
        container=os.getenv("AZURE_CONTAINER_NAME", ""), blob=blob_name
    )
    blob_client.upload_blob(
        byte_data,
        metadata={
            "mime_type": "application/vnd.openxmlformatsofficedocument.spreadsheetml.sheet"
        },
        overwrite=True,
    )


if __name__ == "__main__":
    uploads = {
        "applicant_data.xlsx": "/app/config/app/pgdump_applicants_table.csv",
        "daily_metrics.xlsx": "/app/config/app/pgdump_daily_metrics.csv",
        "annotations_data.xlsx": "/app/config/app/pgdump_annotations.csv",
        f"conversation_data_{(datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')}.xlsx": "/app/config/app/pgdump_conversations_table.csv",
        f"annotation_data_{(datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')}.xlsx": "/app/config/app/pgdump_annotations_table.csv",
        "blocked_metrics.xlsx": "/app/config/app/pgdump_blocked_metrics.csv",
    }
    merge_blocked_metrics()
    update_conversation_data(
        uploads[
            f"conversation_data_{(datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')}.xlsx"
        ]
    )
    for key, value in uploads.items():
        data_export(value, key)
        print(f"Data exported to Azure Blob Storage as {key}.")

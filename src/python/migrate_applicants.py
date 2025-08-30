from schema import get_db, ApplicantTable
from models import UserWorkflowStatus, Applicant
from services.util_service import completion_validator

session = get_db()
applicants = session.query(ApplicantTable).all()
applicant_ids = [applicant.applicant_id for applicant in applicants]
session.close()
for applicant_id in applicant_ids:
    session = get_db()
    applicant = (
        session.query(ApplicantTable)
        .filter(ApplicantTable.applicant_id == applicant_id)
        .first()
    )
    tbd = applicant.__dict__
    tbd["user_workflow_status"] = UserWorkflowStatus.NOT_INITIATED
    user = Applicant(**tbd)
    print(f"Processing applicant: {user.model_dump()}")
    if completion_validator(user):
        setattr(applicant, "user_workflow_status", UserWorkflowStatus.DETAILS_COMPLETED)
        print(
            f"Applicant {user.applicant_id} workflow status updated to DETAILS_COMPLETED"
        )
    elif user.name:
        setattr(
            applicant, "user_workflow_status", UserWorkflowStatus.DETAILS_IN_PROGRESS
        )
        print(
            f"Applicant {user.applicant_id} workflow status updated to DETAILS_IN_PROGRESS"
        )
    else:
        setattr(applicant, "user_workflow_status", UserWorkflowStatus.INITIATED)
        print(f"Applicant {user.applicant_id} workflow status updated to INITIATED")
    session.add(applicant)
    session.commit()
    session.close()

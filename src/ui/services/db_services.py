import json
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any

import streamlit as st
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from configs import config

# Database connection using st.connection
def init_connection():
    """Initialize database connection using st.connection"""
    return st.connection(
        "postgresql",
        type="sql",
        url=f"postgresql+psycopg://{config["postgres"]["user"]}:{config["postgres"]["password"]}@{config["postgres"]["host"]}:{config["postgres"]["port"]}/{config["postgres"]["database"]}"
    )

def get_applicants_for_recruiter(recruiter_id: int, only_show_anotated: bool = False, user_workflow_status: str = "All"):
    """Get all applicants for a specific recruiter"""
    conn = init_connection()
    work_flow_options = {"All": "ALL", "Initiated": "INITIATED", "In Progress": "DETAILS_IN_PROGRESS", "Completed": "DETAILS_COMPLETED"}
    try:
        base_query = """
            SELECT DISTINCT c.applicant_id 
            FROM conversations c
            JOIN applicants a 
            ON c.recruiter_id = a.recruiter_id 
            AND c.applicant_id = a.applicant_id
            WHERE c.recruiter_id = :recruiter_id
        """
        conditions = []
        params = {"recruiter_id": recruiter_id}
        if user_workflow_status != "All":
            conditions.append("a.user_workflow_status = :user_workflow_status")
            params["user_workflow_status"] = work_flow_options[user_workflow_status] # type: ignore
        if only_show_anotated:
            conditions.append("c.annotations IS NOT NULL")
        if conditions:
            base_query += " AND " + " AND ".join(conditions)
        result = conn.query(base_query, params=params)
        applicants=[row['applicant_id'] for row in result.to_dict('records')]
        if st.session_state.user_role == 'annotator':
            applicants=get_applicants_for_annotators(applicants,recruiter_id, only_show_anotated )
        return applicants
    except Exception as e:
        st.error(f"Error fetching applicants for recruiter {recruiter_id}: {e}")
        return []

def get_applicants_for_annotators(applicants:list ,recruiter_id: int, only_show_anotated: bool = False):
    """Get all applicants for a specific recruiter"""
    conn = init_connection()
    try:
        params = {"recruiter_id": recruiter_id,"username":st.session_state.username}
        if only_show_anotated:
            base_query = """
                SELECT DISTINCT c.applicant_id
                FROM conversations c
                LEFT JOIN LATERAL jsonb_array_elements(c.annotations) AS annotation_json ON TRUE
                WHERE (annotation_json IS NOT NULL
                AND annotation_json ->>'annotator_id'=:username)
                AND c.recruiter_id = :recruiter_id
            """
        else:
            base_query = """
                SELECT DISTINCT c.applicant_id
                FROM conversations c
                WHERE c.recruiter_id = :recruiter_id
                AND (
                    c.annotations IS NULL
                    OR c.applicant_id NOT IN (
                        SELECT c2.applicant_id
                        FROM conversations c2,
                        LATERAL jsonb_array_elements(c2.annotations) AS annotation_json
                        WHERE annotation_json ->> 'annotator_id' = :username
                        AND c2.recruiter_id = :recruiter_id
                    )
                )
            """
        result = conn.query(base_query, params=params)
        # Here we are only taking the intersection of both the list.
        annotator_applicants=[row['applicant_id'] for row in result.to_dict('records')]
        final_applicants=[a_a for a_a in annotator_applicants if a_a in applicants ]
        return final_applicants
    except Exception as e:
        st.error(f"Error fetching applicants for recruiter {recruiter_id}: {e}")
        return []

def update_annotations(recruiter_id: int, applicant_id: int, new_annotation: Dict[str, Any]) -> bool:
    """
    Update annotations for a specific recruiter-applicant pair by appending new annotation
    to existing annotations and updating the database.
    
    Args:
        recruiter_id (int): ID of the recruiter
        applicant_id (int): ID of the applicant
        new_annotation (dict): New annotation to append
    
    Returns:
        bool: True if update was successful, False otherwise
    """
    try:
        # Initialize database connection
        conn = init_connection()
        # Get SQLAlchemy engine from streamlit connection
        engine = conn._instance.engine
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            # First, fetch the current record
            query = """
                SELECT annotations FROM conversations 
                WHERE recruiter_id = :recruiter_id AND applicant_id = :applicant_id
            """
            result = conn.query(query, params={
                'recruiter_id': recruiter_id,
                'applicant_id': applicant_id
            })
            if not result.shape[0]:
                st.error(f"No conversation found for recruiter_id {recruiter_id} and applicant_id {applicant_id}")
                return False
            # Get existing annotations
            existing_annotations = result.iloc[0]["annotations"] if result.iloc[0]["annotations"] else []
            existing_annotations.append(new_annotation)
            # Update the database
            update_query = text("""
                UPDATE conversations 
                SET annotations = :annotations,
                    updated_at = :updated_at
                WHERE recruiter_id = :recruiter_id AND applicant_id = :applicant_id
            """)
            session.execute(update_query, {
                'annotations': json.dumps(existing_annotations),
                'updated_at': datetime.now().isoformat(),
                'recruiter_id': recruiter_id,
                'applicant_id': applicant_id
            })
            session.commit()
            st.success(f"Successfully updated annotations for recruiter {recruiter_id} and applicant {applicant_id}")
            return True
        except Exception as e:
            session.rollback()
            st.error(f"Error updating annotations: {str(e)}")
            return False
        finally:
            session.close()
    except Exception as e:
        st.error(f"Database connection error: {str(e)}")
        return False
    
def get_all_conversation_pairs():
    """Get all unique recruiter-applicant pairs"""
    conn = init_connection()
    try:
        query = """
        SELECT DISTINCT recruiter_id, applicant_id 
        FROM conversations 
        ORDER BY recruiter_id, applicant_id
        """
        result = conn.query(query)
        return result.to_dict('records')
    except Exception as e:
        st.error(f"Error fetching conversation pairs: {e}")
        return []
    
def get_all_recruiters():
    """Get all unique recruiter IDs"""
    conn = init_connection()
    try:
        query = """
        SELECT DISTINCT recruiter_id 
        FROM conversations 
        ORDER BY recruiter_id
        """
        result = conn.query(query)
        return [row['recruiter_id'] for row in result.to_dict('records')]
    except Exception as e:
        st.error(f"Error fetching recruiters: {e}")
        return []
    
def get_conversations_data(recruiter_id: int, applicant_id: int):
    """Fetch conversation data from database"""
    conn = init_connection()
    try:
        query = """
        SELECT * FROM conversations 
        WHERE recruiter_id = :recruiter_id AND applicant_id = :applicant_id
        """
        result = conn.query(query, params={"recruiter_id": recruiter_id, "applicant_id": applicant_id})
        if not result.empty:
            return result.iloc[0].to_dict()
        return None
    except Exception as e:
        st.error(f"Error fetching conversation data: {e}")
        return None

def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate user against database"""
    conn = init_connection()
    try:
        # Hash the password (assuming passwords are stored hashed)
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        query = """
        SELECT username, role 
        FROM user_login 
        WHERE username = :username AND password = :password
        """
        result = conn.query(query, params={"username": username, "password": password_hash})
        if not result.empty:
            user_data = result.iloc[0].to_dict()
            return user_data
        return None
    except Exception as e:
        st.error(f"Authentication error: {e}")
        return None

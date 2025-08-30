import time
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import  Dict, Any

import streamlit as st

from services.db_services import authenticate_user, get_all_recruiters, get_applicants_for_recruiter, get_conversations_data, update_annotations

# Set page config
st.set_page_config(
    page_title="Conversations Annotator",
    page_icon="💬",
    layout="wide"
)


def format_timestamp(ts_str: str) -> str:
    """Format timestamp for display"""
    try:
        # Assuming timestamp is in ISO format or similar
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        dt = dt.astimezone(ZoneInfo("Asia/Kolkata"))  # Convert to local timezone
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return ts_str

def login_page():
    """Display login page"""
    st.title("🔐 Chat Viewer Login")
    st.markdown("---")
    with st.form("login_form"):
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("### Please enter your credentials")
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submit_button = st.form_submit_button("Login", use_container_width=True, type="primary")
    if submit_button:
        if username and password:
            user_data = authenticate_user(username, password)
            if user_data:
                st.session_state.logged_in = True
                st.session_state.username = user_data['username']
                st.session_state.user_role = user_data['role']
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid username or password")
        else:
            st.warning("⚠️ Please enter both username and password")

def display_message(message: Dict[str, Any], recruiter_id: int):
    """Display a single message using st.chat_message with proper alignment"""
    is_recruiter = int(message['sender_id']) == recruiter_id
    timestamp = format_timestamp(message['ts'])
    if is_recruiter:
        # Recruiter messages on the left (assistant role)
        with st.chat_message("assistant", avatar="🏢"):
            st.markdown(f"**Recruiter** • {timestamp}")
            st.markdown(message['content'])
            # if message.get('mid'):
            #     st.caption(f"ID: {message['mid']}")
    else:
        # Applicant messages on the right (user role) 
        with st.chat_message("user", avatar="👤"):
            st.markdown(f"**Applicant** • {timestamp}")
            if message["msg_type"] == "text":
                st.markdown(message['content'])
            else:
                st.markdown(f"📄 User sent a {message["msg_type"]}")
            # if message.get('mid'):
            #     st.caption(f"ID: {message['mid']}")

def chat_viewer_page():
    """Display chat viewer page"""
    st.title("💬 Conversation Chat Viewer")
    # Header with user info and logout
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"👋 Welcome, **{st.session_state.username}** ({st.session_state.user_role})")
    with col2:
        if st.button("🚪 Logout", type="secondary", use_container_width=True):
            # Clear all session state
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    st.markdown("---")
    # Sidebar for conversation selection
    with st.sidebar:
        st.header("🔍 Select Conversation")
        # Initialize session state for selections
        if 'selected_recruiter_id' not in st.session_state:
            st.session_state.selected_recruiter_id = None
        if 'selected_applicant_id' not in st.session_state:
            st.session_state.selected_applicant_id = None
        if 'selected_applicant_index' not in st.session_state:
            st.session_state.selected_applicant_index = 0
        if 'only_show_annotated' not in st.session_state:
            st.session_state.only_show_annotated = False
        if 'selected_work_flow_status' not in st.session_state:
            st.session_state.selected_work_flow_status = None
        st.markdown("---")
        # Recruiter-first selection mode
        all_recruiters = get_all_recruiters()
        if not all_recruiters:
            st.warning("No conversations found in the database.")
            st.stop()
        # Recruiter selection
        recruiter_options = ["Select a recruiter..."] + [str(r) for r in all_recruiters]
        # work_flow_status
        work_flow_options =["All", "Initiated", "In Progress", "Completed"]
        # Find current index of selected recruiter
        try:
            current_recruiter_index = recruiter_options.index(str(st.session_state.selected_recruiter_id)) if st.session_state.selected_recruiter_id else 0
            current_work_flow_index = work_flow_options.index(str(st.session_state.selected_work_flow_status)) if st.session_state.selected_work_flow_status else 0
        except ValueError:
            current_recruiter_index = 0
        selected_recruiter_str = st.selectbox(
            "📞 Select Recruiter:",
            options=recruiter_options,
            index=current_recruiter_index,
            help="Choose a recruiter to view their conversations",
        )
        # Update selected recruiter
        if selected_recruiter_str != "Select a recruiter...":
            new_recruiter_id = int(selected_recruiter_str)
            if st.session_state.selected_recruiter_id != new_recruiter_id:
                st.session_state.selected_recruiter_id = new_recruiter_id
                st.session_state.selected_applicant_id = None
                st.session_state.selected_applicant_index = 0
                st.rerun()
        else:
            if st.session_state.selected_recruiter_id is not None:
                st.session_state.selected_recruiter_id = None
                st.session_state.selected_applicant_id = None
                st.rerun()
        # Applicant selection (based on selected recruiter)
        if st.session_state.selected_recruiter_id:
            selected_work_flow_str = st.selectbox(
            " Select Work Flow Status:",
            options=work_flow_options,
            index=current_work_flow_index,
            help="Choose a filter to view conversation",
            )
            # Store checkbox state in session state to persist across reruns
            if 'only_show_annotated' not in st.session_state:
                st.session_state.only_show_annotated = False
            if st.session_state.user_role == "admin":
                only_show_annotated = st.checkbox(
                    "Annotated Chats", 
                    value=st.session_state.only_show_annotated,
                    help="This will filter the conversation which has only annotations"
                )
            elif st.session_state.user_role == "annotator":
                radio_annotated = st.radio(
                    label= "Annotated Chats", 
                    options=['Annotated','Not Annotated'],
                    index=1,
                    help="This will filter the conversation which has only annotations with"
                )
                #st.session_state.username
                only_show_annotated= True if radio_annotated=='Annotated' else False
            else:
                only_show_annotated = False
            # If checkbox state changed, update session state and reset applicant selection
            if only_show_annotated != st.session_state.only_show_annotated:
                st.session_state.only_show_annotated = only_show_annotated
                st.session_state.selected_applicant_id = None
                st.session_state.selected_applicant_index = 0
                st.rerun()
            available_applicants = get_applicants_for_recruiter(st.session_state.selected_recruiter_id, only_show_annotated,selected_work_flow_str)
            if available_applicants:
                applicant_options = [str(a) for a in available_applicants]
                # Clamp index to be within bounds
                if st.session_state.selected_applicant_index >= len(applicant_options):
                    st.session_state.selected_applicant_index = len(applicant_options) - 1
                # Set the applicant based on the index, which is the source of truth
                if applicant_options:
                    st.session_state.selected_applicant_id = int(applicant_options[st.session_state.selected_applicant_index])
                # The selectbox now reflects the state
                selected_applicant_str = st.selectbox(
                    "👤 Select Applicant:",
                    options=applicant_options,
                    index=st.session_state.selected_applicant_index,
                    help="Choose an applicant to view the conversation",
                )
                # If user manually selects a different applicant, update the index
                if selected_applicant_str and int(selected_applicant_str) != st.session_state.selected_applicant_id:
                    st.session_state.selected_applicant_id = int(selected_applicant_str)
                    st.session_state.selected_applicant_index = applicant_options.index(selected_applicant_str)
                    st.rerun()
                # Back/Next buttons modify the index and rerun
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("⬅️ Back", use_container_width=True, disabled=st.session_state.selected_applicant_index == 0):
                        st.session_state.selected_applicant_index -= 1
                        st.rerun()
                with col2:
                    if st.button("Next ➡️", use_container_width=True, disabled=st.session_state.selected_applicant_index >= len(applicant_options) - 1):
                        st.session_state.selected_applicant_index += 1
                        st.rerun()
            else:
                st.warning("No applicants found for this recruiter.")
                st.session_state.selected_applicant_id = None
        else:
            st.info("👆 Please select a recruiter first.")
        # Display current selection
        if st.session_state.selected_recruiter_id and st.session_state.selected_applicant_id:
            applicant_count = len(get_applicants_for_recruiter(st.session_state.selected_recruiter_id, only_show_annotated,selected_work_flow_str))
            if applicant_count > 0:
                st.info(f"Viewing applicant {st.session_state.selected_applicant_index + 1} of {applicant_count}")
            # Add refresh button
            if st.button("🔄 Refresh Conversation", use_container_width=True):
                st.rerun()
            # Set variables for the main area
            recruiter_id = st.session_state.selected_recruiter_id
            applicant_id = st.session_state.selected_applicant_id
            conversation_selected = True
        else:
            conversation_selected = False
    # Main conversation area
    if conversation_selected:
        conversation_data = get_conversations_data(recruiter_id, applicant_id) # type: ignore
        if conversation_data:
            # Conversation header
            if str(recruiter_id)==str(applicant_id):
                st.subheader(f"💬 (Self Chat): {recruiter_id} ")
            else:
                st.subheader(f"💬 Chat: Recruiter {recruiter_id} ↔ Applicant {applicant_id}")
            # Chat metadata
            col1, col2 = st.columns(2)
            with col1:
                st.metric("📅 Last Updated", format_timestamp(conversation_data['updated_at']))
            with col2:
                if conversation_data.get('conversations'):
                    st.metric("💬 Total Messages", len(conversation_data['conversations']))
            st.markdown("---")
            # Parse and sort conversations by timestamp
            if conversation_data.get('conversations'):
                conversations = conversation_data['conversations']
                # Sort conversations by timestamp
                try:
                    conversations_sorted = sorted(conversations, key=lambda x: x['ts'])
                except Exception as e:
                    st.error(f"Error sorting conversations: {e}")
                    conversations_sorted = conversations
                # Display conversations in a scrollable container
                st.markdown("### 📝 Conversation History")
                # Create chat container
                chat_container = st.container()
                with chat_container:
                    for message in conversations_sorted:
                        display_message(message, recruiter_id)
                # Conversation statistics
                st.markdown("---")
                with st.expander("📊 Conversation Statistics", expanded=False):
                    recruiter_msg_count = sum(1 for msg in conversations_sorted if int(msg['sender_id']) == recruiter_id)
                    applicant_msg_count = len(conversations_sorted) - recruiter_msg_count
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("🏢 Recruiter Messages", recruiter_msg_count)
                    with col2:
                        st.metric("👤 Applicant Messages", applicant_msg_count)
                    with col3:
                        st.metric("📊 Total Messages", len(conversations_sorted))
                if st.session_state.user_role in ["annotator", "admin"]:
                    st.markdown("---")
                    # Display annotations if present
                    st.markdown("### 📝 Annotations")
                    annotations = conversation_data.get('annotations', [])
                    if annotations:
                        for idx, annotation in enumerate(annotations, 1):
                            if (annotation["annotator_id"] == st.session_state.username and st.session_state.only_show_annotated) or st.session_state.user_role == "admin":
                                with st.chat_message("assistant", avatar="📝"):
                                    st.markdown(f"**{annotation["annotator_id"]}** • {annotation["ts"]}")
                                    st.markdown(annotation["content"])
                                    st.caption("Good" if annotation["rating"] else "Bad")
                    else:
                        st.info("No annotations yet.")
                    # Annotation form
                    with st.form("add_annotation_form"):
                        st.markdown("#### ➕ Add New Annotation")
                        annotation_text = st.text_area("Annotation", placeholder="Enter your annotation here...", key="annotation_text")
                        feedback_rating = st.feedback(key="feedback_rating")
                        submit_annotation = st.form_submit_button("Add Annotation", use_container_width=True, type="primary")
                    if submit_annotation:
                        if annotation_text.strip():
                            new_annotation = {
                                "annotator_id": st.session_state.username,
                                "rating": True if feedback_rating == 1 else False,
                                "content": annotation_text.strip(),
                                "ts": datetime.now().isoformat()
                            }
                            success = update_annotations(recruiter_id, applicant_id, new_annotation) # type: ignore
                            if success:
                                st.success("✅ Annotation added successfully!")
                                time.sleep(1)  # Delay to allow user to see success message
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error("❌ Failed to add annotation.")
                        else:
                            st.warning("⚠️ Please enter annotation text before submitting.")
            else:
                st.warning("No messages found in this conversation.")        
        else:
            st.error("❌ No conversation data found for the selected pair.")
    else:
        st.info("👆 Please select a conversation from the sidebar to view the chat.")

def main():
    """Main application logic"""
    # Initialize session state with default values
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'user_role' not in st.session_state:
        st.session_state.user_role = None
    # Route to appropriate page
    if st.session_state.logged_in:
        chat_viewer_page()
    else:
        login_page()

if __name__ == "__main__":
    main()

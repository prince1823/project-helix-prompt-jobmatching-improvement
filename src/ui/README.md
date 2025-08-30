# Conversation Chat Viewer

A Streamlit-based web application to view WhatsApp conversations between recruiters and applicants in a chat-like interface.

## Features

- 🔐 **Database Authentication**: Login with credentials stored in the database
- 💬 **Chat Interface**: View conversations using st.chat_message with proper left/right alignment
- 📊 **Conversation Selection**: Select recruiter-applicant pairs from dropdown in sidebar
- 🔄 **Real-time Data**: Uses st.connections for efficient database connectivity
- 📈 **Statistics**: View conversation statistics and metadata
- 📝 **Annotations**: Add and view annotations for conversations with ratings and timestamps
- 👥 **User Tracking**: Track who added each annotation with user identification

## Setup

### 1. Install Dependencies

```bash
# Using uv (recommended)
uv pip install -e .

# Or using pip
pip install -e .
```

### 2. Configure Database

Update the database configuration in `.streamlit/secrets.toml`:

```toml
[database]
host = "localhost"
port = "5432"
name = "quess"
user = "quess"
password = ""
```

### 3. Setup Users

Run the setup script to create sample users in the database:

```bash
python setup_users.py
```

This will create the following test users:
- Username: `admin`, Password: `admin123` (role: admin)
- Username: `annotator`, Password: `annotator123` (role: annotator)
- Username: `viewer`, Password: `viewer123` (role: viewer)

### 4. Run the Application

```bash
streamlit run main.py
```

## Usage

1. **Login**: Use any of the created user credentials to login
2. **Select Conversation**: Choose a recruiter-applicant pair from the sidebar dropdown
3. **View Chat**: See the conversation displayed in a chat interface with:
   - Recruiter messages on the left (🏢 assistant)
   - Applicant messages on the right (👤 user)
   - Timestamps and message IDs
   - Conversation statistics
   - Annotations displayed as chat messages (📝 assistant)
4. **Add Annotations**: Use the annotation form to add feedback with:
   - Text content for detailed feedback
   - Rating system (thumbs up/down)
   - Automatic timestamp and user tracking

## Database Schema

The application expects the following tables:

- `user_login`: User authentication data
- `conversations`: Conversation data between recruiters and applicants with annotations support
- `recruiters`: Recruiter information
- `applicants`: Applicant information

### Conversations Table Schema

The `conversations` table should include:
- `recruiter_id`: Foreign key to recruiter
- `applicant_id`: Foreign key to applicant
- `conversations`: JSON array of message objects
- `annotations`: JSON array of annotation objects with structure:
  - `annotator_id`: Username of the person who added the annotation
  - `content`: Text content of the annotation
  - `rating`: Boolean value (true for positive, false for negative)
  - `ts`: ISO timestamp of when annotation was added
- `updated_at`: Timestamp of last update

## Authentication

Passwords are hashed using SHA256 before storing in the database. The application authenticates users against the `user_login` table.

## Notes

- Messages are sorted by timestamp (`ts` field) chronologically
- The chat interface uses Streamlit's native `st.chat_message` component
- Database connections are managed efficiently using `st.connections`
- Annotations are displayed as chat messages with 📝 avatar for clear distinction
- All annotations include user tracking and timestamps for audit trail
- The application automatically refreshes to show new annotations immediately
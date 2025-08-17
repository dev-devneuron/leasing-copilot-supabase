# Lease Bot - Real Estate Leasing Copilot Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Technology Stack and Components](#technology-stack)
4. [Database Schema](#database-schema)
5. [API Endpoints](#api-endpoints)
6. [Core Modules](#core-modules)
7. [Authentication & Security](#authentication--security)
8. [Calendar Integration](#calendar-integration)
9. [RAG (Retrieval-Augmented Generation) System](#rag-retrieval-augmented-generation-system)
10. [File Management](#file-management)
11. [Configuration](#configuration)
12. [Deployment](#deployment)
13. [Realtor Onboarding](#realtor-onboarding)
14. [Usage Examples](#usage-examples)


---

## Project Overview

**Lease Bot** is an intelligent real estate leasing copilot that automates customer interactions, manages property listings, and handles appointment scheduling. The system integrates with Google Calendar, WhatsApp (via Twilio), and provides AI-powered responses using RAG (Retrieval-Augmented Generation) technology.

### Key Features
- **AI-Powered Customer Support**: Automated responses using RAG system
- **Calendar Management**: Google Calendar integration for appointment scheduling
- **WhatsApp Integration**: Customer communication via Twilio
- **Property Management**: Apartment listing management and search
- **Multi-tenant Architecture**: Support for multiple realtors
- **File Management**: Document storage and retrieval via Supabase

---

## System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   FastAPI       │    │   Main DB       │    │   Secondary DB  │
│   (React)       │◄──►│   Backend       │◄──►│   (PostgreSQL)  │◄──►│   (PostgreSQL)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
                              ^
                              │
                              ▼
                       ┌─────────────────┐
                       │   External      │
                       │   Services      │
                       │   (VAPI,        |
                       |  Google Cloud,  │ 
                       │    Twilio,      │
                       │    Supabase)    │
                       └─────────────────┘
```

### Component Overview
- **VAPI**: Call and chat hosting with llm selection (`dev.devneuron@gmail.com -> Vapi`)
- **FastAPI Application**: Main backend server (`vapi/app.py`)
- **Main Database Layer**: PostgreSQL with pgvector for embeddings (`db.py`)(contains main tables discussed below)
- **Secondary Database Layer**: PostgreSQL with pgvector (`secondary_db.py`) (contains individual table for each realtor, from where we sync to main DB)
- **RAG Engine**: AI-powered response generation (`vapi/rag.py`)
- **Calendar Integration**: Google Calendar management (`calendar_utils.py`)
- **Authentication**: JWT-based auth with Supabase (`auth_module.py`)
- **File Storage**: Supabase bucket for document storage

---

## Technology Stack

### Backend
- **Framework**: FastAPI
- **Database**: PostgreSQL with pgvector extension
- **ORM**: SQLModel (SQLAlchemy-based)
- **AI/ML**: 
  - LangChain  (for making document for RAG)
  - Google Generative AI
  - VAPI (for Voice and chat Assistant , tool calling, llm and voice selection)

### External Services
- **Calendar**: Google Calendar API
- **Communication**: Twilio (WhatsApp, programmable voice)
- **File Storage and DB**: Supabase
- **Vector Database**: pgvector in supabase(PostgreSQL extension)
- **Embeddings Model**: gemini-embeddings-001


### Dependencies
```
Given in Requirements.py
```

---

# VAPI Configuration
### Assistant: Leassing copilot (Chat):
* It manages chat bot
* Has different system prompt from Calling assistant
### Assistant: Leassing copilot :
* It manages calling bot
* Has different system prompt from Chat assistant

### We have tools in vapi (which calls the backend (FastApi) endpoints to perform the actions): 
### To check: GOTO: VAPI -> TOOLS
### Tools List
- *CreateCust* (This tool is invoked just in the beginning after collect user's info {Name, Email, Contact Number} to update the database to create a new customer. )
- *confirmAddress* (This tool is called to extract the correct address from the vague address provided by the user during booking visit workflow.)
- *queryDocs* (This is a information retrieval tool based which returns the related text back to LLM. It takes the search query as parameter and returns the search result.)
- *searchApartments* (This tool takes the preferences from the user (city, state, bedrooms, bathrooms, budget, square feet) from the user and will return the matched apartment by using semantic search. This is basically used to provide the preferred apartments to tenants.)
- *getAvailableSlots* (It is used to get the free available time slot for a given date in ISO format (YYYY-MM-DD). It will be used when user asks the available time slots for any specific date.)
- *bookVisit* (It will be used to book a google cloud calendar schedule for the tenants. It will take name, email, address of apartment and date for scheduling. All the parameters should be provided by the tenants.)
- *getDate* (This tool is used to get the current date and day. When user says "Tomorrow","2 days from now" or something like that, this tool will be called.)

* Both assistant use same tools which are created in tool tab in vapi. 


# Google Cloud Configuration (for google calendar)

- Use google cloud from (dev.devneuron@gmail.com)
- Search for calendar API
- Goto: Calendar API -> Audience to add the user (realtor) who will use the api. (This is for testing phase only. will be automated in production)
- Set the redirect URL from Google Cloud -> Client -> Fast API Calendar -> Set Redirect URL (set here {your backend url/oauth2callback})

### /authorize end point:
- Ask realtor to hit it this end point each time when a new realtor onboards e.g. https://leasing-copilot-mvp.onrender.com/authorize?realtor_id=5

### /Oath2callback end point:
- Called by /authorize to authnticate the realtor.

# Twilio
* Cloud platform for communications APIs (SMS, calls, WhatsApp).
* It manages the call and messages hosting 
### Configuration:
- Use dev.devneuron@gmail.com for login into twilio.
- Explore side pannel to view options (Voice, Messaging).
- Set Urls to which voice stream and messages are redirected.


# Vyke
- VOIP to make calls to US numbers.

# Supabase (For DB, Vector Store, File storing)
- Main DB:  dev.devneuron@gmail.com
- Secondary DB: afraz.devneuron@gmail.com
* We are using 2 DB
- Main DB -- Contains main tables and realtor files  (Schema is given below)
- Secondary DB -- Contains individual tables for realtors from where data is synced to the main DB.  
- Using JWT based authentication system using emial and password in supabase.



## Database Schema

### Core Tables

#### 1. Realtor
```sql
CREATE TABLE realtor (
    realtor_id SERIAL PRIMARY KEY,
    auth_user_id UUID NOT NULL,
    name VARCHAR NOT NULL,
    email VARCHAR NOT NULL,
    contact VARCHAR NOT NULL,
    twilio_contact VARCHAR,
    credentials TEXT  -- Google Calendar credentials (JSON)
);
```

#### 2. Customer
```sql
CREATE TABLE customer (
    cust_id SERIAL PRIMARY KEY,
    name VARCHAR,
    email VARCHAR,
    contact VARCHAR NOT NULL,
    if_tenant VARCHAR
);
```

#### 3. Booking
```sql
CREATE TABLE booking (
    id SERIAL PRIMARY KEY,
    address VARCHAR NOT NULL,
    date DATE NOT NULL,
    time TIME NOT NULL,
    visited BOOLEAN DEFAULT FALSE,
    cust_feedback TEXT,
    cust_id INTEGER REFERENCES customer(cust_id),
    realtor_id INTEGER REFERENCES realtor(realtor_id)
);
```

#### 4. Source (Document Management)
```sql
CREATE TABLE source (
    id SERIAL PRIMARY KEY,
    realtor_id INTEGER REFERENCES realtor(realtor_id),
    name VARCHAR NOT NULL,
    file_path VARCHAR,
    file_type VARCHAR,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### 5. RuleChunk (RAG System)
```sql
CREATE TABLE rule_chunk (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES source(id),
    content TEXT NOT NULL,
    embedding vector(768)  -- pgvector column
);
```

#### 6. ApartmentListing
```sql
CREATE TABLE apartment_listing (
    id SERIAL PRIMARY KEY,
    realtor_id INTEGER REFERENCES realtor(realtor_id),
    address VARCHAR NOT NULL,
    bedrooms INTEGER,
    bathrooms INTEGER,
    price DECIMAL,
    square_feet INTEGER,
    property_type VARCHAR,
    features JSONB,
    embedding vector(768)
);
```

---

## API Endpoints

### Authentication & User Management

#### 1. Create Realtor
```
POST /CreateRealtor
Content-Type: multipart/form-data

Parameters:
- name (str, required): Realtor name
- email (str, required): Realtor email
- contact (str, required): Contact number
- files (List[UploadFile], required): Policy/rule documents
- listing_file (UploadFile, optional): Property listings file
- listing_api_url (str, optional): External listing API URL

Response: JSON with auth_link for Google Calendar authorization
```

#### 2. Google Calendar Authorization
```
GET /authorize?realtor_id={id}
Response: Redirects to Google OAuth flow
```

#### 3. OAuth Callback
```
GET /oauth2callback
Response: Handles OAuth callback and stores credentials
```

### Customer Management

#### 4. Create Customer
```
POST /create_customer/
Content-Type: application/json

Body: VapiRequest with tool calls
Response: Customer creation confirmation
```

#### 5. Get Customer
```
GET /get_customer/
Content-Type: application/json

Body: VapiRequest with customer search parameters
Response: Customer information
```

### Booking Management

#### 6. Create Booking
```
POST /create_booking/
Content-Type: application/json

Body: VapiRequest with booking details
Response: Booking confirmation with calendar event
```

#### 7. Get Available Slots
```
POST /get_available_slots/
Content-Type: application/json

Body: VapiRequest with date and realtor_id
Response: Available time slots
```

### Property Management

#### 8. Get Apartment Listings
```
POST /get_apartment_listings/
Content-Type: application/json

Body: VapiRequest with search criteria
Response: Matching apartment listings
```

### WhatsApp Integration

#### 9. WhatsApp Webhook
```
POST /webhook
Content-Type: application/x-www-form-urlencoded

Body: Twilio webhook data
Response: TwiML response for WhatsApp
```

---

## Core Modules

### 1. Main Application (`vapi/app.py`)

**Purpose**: FastAPI application with all endpoints and business logic

**Key Components**:
- FastAPI app initialization with CORS middleware
- Lifespan management for database initialization
- Endpoint definitions for all API routes
- Integration with external services (Twilio, Google Calendar)

**Key Functions**:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_vector_db()  # Initialize vector database
    yield
    print("Shutting down fastapi app...")
```

### 2. Database Layer (`db.py`)

**Purpose**: Database models, connections, and operations

**Key Features**:
- SQLModel-based ORM models
- pgvector integration for embeddings
- Supabase integration for file storage
- Database session management

**Key Models**:
- `Realtor`: Real estate agent information
- `Customer`: Customer/client information
- `Booking`: Appointment scheduling
- `Source`: Document management
- `RuleChunk`: RAG system chunks
- `ApartmentListing`: Property listings

### 3. RAG Engine (`vapi/rag.py`)

**Purpose**: AI-powered response generation using retrieval-augmented generation

**Key Features**:
- Document chunking and embedding
- Semantic search for relevant content
- Integration with LangChain
- Support for both rules and apartment listings

**Key Methods**:
```python
def query(self, question: str, source_id: int, k: int = 3) -> str:
    """Finds top-k relevant rule chunks for a question"""

def search_apartments(self, query: str, k: int = 5):
    """Finds top-k apartment listings matching the query"""
```

### 4. Calendar Integration (`calendar_utils.py`)

**Purpose**: Google Calendar integration for appointment management

**Key Features**:
- OAuth2 authentication flow
- Event creation and management
- Time slot availability checking
- Multi-realtor support

**Key Classes**:
```python
class GoogleCalendar(BaseCalendar):
    def create_event(self, start_time_str, summary, email, description)
    def is_time_available(self, start_time_str)
    def get_free_slots(self, date_str, tz_str=None)
```

### 5. Authentication (`auth_module.py`)

**Purpose**: JWT-based authentication using Supabase

**Key Features**:
- JWT token validation
- Realtor identification
- Secure credential management

**Key Function**:
```python
def get_current_realtor_id(credentials: HTTPAuthorizationCredentials):
    """Validates JWT token and returns realtor ID"""
```

---

## Authentication & Security

### JWT Authentication Flow
1. **Token Generation**: Supabase generates JWT tokens
2. **Token Validation**: Backend validates tokens using `SUPABASE_JWT_SECRET`
3. **User Lookup**: Maps JWT `sub` to realtor ID in database
4. **Authorization**: Returns realtor ID for protected endpoints

### Security Features
- **CORS Protection**: Configured for specific origins
- **Input Validation**: Pydantic models for request validation
- **Error Handling**: Comprehensive error responses
- **Rate Limiting**: Message limiter for API usage

### Environment Variables Required
```bash
VAPI_API_KEY=39678b47-2034-4a07-82e3-d5bef6c1123b
VAPI_ASSISTANT_ID=bb9ccb21-789d-413a-8697-189e7b9ba391
TWILIO_AUTH_TOKEN=d07d70c3fa14541a3198f5d775e895e2
TWILIO_ACCOUNT_SID=ACb89687ae7bfbccfbaf4c5ad9b89c56df
GEMINI_API_KEY=AIzaSyA_kWzpMyEwBv2hxLOVE8f9CUpXYoW6z7U
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNtcHl3bGVvd3hudnVjeW12d2d2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1Mzg0OTAyNSwiZXhwIjoyMDY5NDI1MDI1fQ.Wqr-HNkeWSIYt6Okc38FCgq8lppsf2c2EPvr5S5e1qc
GOOGLE_API_KEY=AIzaSyA_kWzpMyEwBv2hxLOVE8f9CUpXYoW6z7U
DATABASE_1_URL=postgresql+psycopg2://postgres.cmpywleowxnvucymvwgv:Superman%40_%2511223344@aws-0-us-west-1.pooler.supabase.com:5432/postgres?sslmode=require
DATABASE_2_URL=postgresql+psycopg2://postgres.cadkbesvlgkpwyjccobk:Superman%40_%2511223344@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
SUPABASE_URL=https://cmpywleowxnvucymvwgv.supabase.co
SUPABASE_JWT_SECRET =OSeH4HEt6kUNQ8iSUOk1JScLY9zN/VGJln92bLGu12K2ELtsoCUY3xEU9zmnyIDFcmMdffLy+5BsFeJImQolMQ==
```

---

## Calendar Integration

### Google Calendar Setup
1. **OAuth2 Flow**: Users authorize via `/authorize` endpoint
2. **Credential Storage**: OAuth tokens stored in database
3. **Event Management**: Automatic event creation for bookings
4. **Time Zone Handling**: Configurable timezone support

### Working Hours Configuration
```python
WORKING_HOURS = {
    "start": 8,  # 8 AM
    "end": 21    # 9 PM
}
SLOT_DURATION = 30  # minutes
```

### Calendar Features
- **Automatic Event Creation**: When bookings are made
- **Availability Checking**: Real-time slot availability
- **Multi-calendar Support**: Each realtor has their own calendar
- **Email Notifications**: Automatic attendee notifications

---

## RAG (Retrieval-Augmented Generation) System

### Architecture
```
Document Upload → Chunking → Embedding → Vector Storage → Query → Retrieval → Response Generation
```

### Components

#### 1. Document Processing
- **Text Splitting**: Character-based chunking with overlap
- **Embedding Generation**: Using HuggingFace models
- **Vector Storage**: pgvector for efficient similarity search

#### 2. Query Processing
- **Query Embedding**: Convert user questions to vectors
- **Similarity Search**: Find most relevant document chunks
- **Response Generation**: Combine retrieved content with AI responses

#### 3. Models Used
- **Embedding Model**: `BAAI/bge-large-en-v1.5` (768 dimensions)
- **LLM Model**: `models/gemini-2.0-flash`
- **Chunk Size**: 800 characters with 50 character overlap

### Usage Example
```python
# Initialize RAG engine
rag = RAGEngine()

# Query for relevant rules
response = rag.query("What is the pet policy?", source_id=1, k=3)

# Search for apartments
apartments = rag.search_apartments("2 bedroom apartment under $2000", k=5)
```

---

## File Management

### Supabase Integration
- **Bucket Name**: `realtor-files`
- **File Types**: Documents, images, property listings
- **Access Control**: Per-realtor file isolation

### File Upload Process
1. **Frontend Upload**: React form with file selection
2. **Backend Processing**: FastAPI multipart form handling
3. **Storage**: Supabase bucket upload
4. **Database Record**: Source table entry with file metadata
5. **RAG Processing**: Document chunking and embedding

### Supported File Types
- **Documents**: PDF, DOC, DOCX, TXT
- **Data Files**: JSON, CSV (for property listings)
- **Images**: JPG, PNG (for property photos)

---

## Configuration

### Environment Variables (`config.py`)

#### Database Configuration
```python
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
DATABASE_URL = os.getenv("DATABASE_1_URL")
```

#### API Configuration
```python
VAPI_API_KEY = os.getenv("VAPI_API_KEY")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID")
TWILIO_PHONE_NUMBER = "whatsapp:+14155238886"
```

#### Application Settings
```python
DEFAULT_TIMEZONE = "Asia/Karachi"
WORKING_HOURS = {"start": 8, "end": 21}
SLOT_DURATION = 30
DAILY_LIMIT = 50
```

#### AI Model Configuration
```python
EMBEDDING_MODEL_NAME = "BAAI/bge-large-en-v1.5"
LLM_MODEL_NAME = "models/gemini-2.0-flash"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 50
```

---

## Deployment

### Prerequisites
1. **PostgreSQL Database**: With pgvector extension
2. **Supabase Account**: For file storage and authentication
3. **Google Cloud Project**: For Calendar API
4. **Twilio Account**: For WhatsApp integration
5. **Python 3.8+**: For backend dependencies

### Installation Steps

#### 1. Clone Repository
```bash
git clone <repository-url>
cd "Final beta"
```

#### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 3. Environment Setup
```bash
# Create .env file with required variables
cp .env.example .env
# Edit .env with your configuration
```

#### 4. Database Setup
```bash
# Run database migrations
python -c "from db import create_tables; create_tables()"
```

#### 5. Start Application
```bash
uvicorn vapi.app:app --host 0.0.0.0 --port 8080
```

### Production Deployment
- **Platform**: Render 
- **Database**: Managed PostgreSQL with pgvector on Supabase
- **File Storage**: Supabase production bucket
- **SSL**: HTTPS configuration required
- **Environment Variables**: All secrets properly configured

---
## Realtor Onboarding:

* Steps to onboard the  realtor:
- Ask him to fill up the Signup Form (Name, Email, Password, Rules/Policies Files, Data.json file)
- After this ask him to confirm the email.
- After that ask him to give permission by visiting the /authorize end point suuch as : https://leasing-copilot-mvp.onrender.com/authorize?realtor_id=5 
- After that he will be able to view his listed apartments and bookings.

---
## Usage Examples

### 1. Creating a New Realtor
```javascript
// Frontend React form submission
const formData = new FormData();
formData.append("name", "John Doe");
formData.append("email", "john@example.com");
formData.append("contact", "+1234567890");
formData.append("files", file1);
formData.append("files", file2);

const response = await fetch("/CreateRealtor", {
    method: "POST",
    body: formData
});
```

### 2. Making a Booking
```python
# Backend booking creation
booking_data = {
    "address": "123 Main St",
    "date": "2024-01-15",
    "time": "14:30",
    "customer_email": "customer@example.com"
}

# Create calendar event
calendar = GoogleCalendar(realtor_id=1)
calendar.create_event(
    start_time_str="2024-01-15 14:30",
    summary="Apartment Visit",
    email="customer@example.com"
)
```

### 3. RAG Query
```python
# Query for relevant information
rag = RAGEngine()
response = rag.query(
    question="What are the parking rules?",
    source_id=1,
    k=3
)
```

### 4. WhatsApp Integration
```python
# Twilio webhook response
@app.post("/webhook")
async def webhook(request: Request):
    form_data = await request.form()
    user_message = form_data.get("Body", "")
    
    # Process with RAG
    response = rag.query(user_message, source_id=1)
    
    # Return TwiML response
    twiml = MessagingResponse()
    twiml.message(response)
    return Response(content=str(twiml), media_type="application/xml")
```

---

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors
**Symptoms**: Connection timeout or authentication failures
**Solutions**:
- Check `DATABASE_URL` environment variable
- Verify PostgreSQL server is running
- Ensure pgvector extension is installed

#### 2. Google Calendar Authentication Issues
**Symptoms**: "User not authenticated" errors
**Solutions**:
- Verify OAuth2 credentials in database
- Check `CREDENTIALS_FILE` path
- Ensure Google Calendar API is enabled
- Also if user is authenticated in google cloud console.

#### 3. RAG System Not Working
**Symptoms**: No relevant responses or embedding errors
**Solutions**:
- Check if documents are properly chunked and embedded
- Verify embedding model is accessible
- Check vector database connectivity

#### 4. File Upload Failures
**Symptoms**: Supabase upload errors
**Solutions**:
- Verify Supabase credentials
- Check bucket permissions
- Ensure file size limits are not exceeded

#### 5. WhatsApp Integration Issues
**Symptoms**: Messages not received or sent
**Solutions**:
- Verify Twilio credentials
- Check webhook URL configuration
- Ensure proper TwiML response format



### Health Check Endpoint
```python
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}
```

---

## API Response Codes

### Success Codes
- `200`: OK - Request successful
- `201`: Created - Resource created successfully

### Error Codes
- `400`: Bad Request - Invalid input data
- `401`: Unauthorized - Authentication required
- `404`: Not Found - Resource not found
- `500`: Internal Server Error - Server error

### Example Error Response
```json
{
    "detail": "User not authenticated. Please visit /authorize?realtor_id=1"
}
```

---

## Performance Considerations

### Database Optimization
- **Indexing**: Proper indexes on frequently queried columns
- **Connection Pooling**: Configured in SQLAlchemy engine
- **Vector Search**: pgvector for efficient similarity search

### Caching Strategy
- **Session Management**: Database session reuse
- **Embedding Cache**: Reuse computed embeddings
- **Response Cache**: Cache common RAG responses


---

## Security Best Practices

### Data Protection
- **Encryption**: All sensitive data encrypted at rest
- **Access Control**: Role-based access control
- **Audit Logging**: Track all data access and modifications

### API Security
- **Rate Limiting**: Prevent abuse with message limits
- **Input Validation**: All inputs validated and sanitized
- **CORS Configuration**: Restrict cross-origin requests (set front end URl in orgin only)

### Authentication
- **JWT Tokens**: Secure token-based authentication
- **Token Expiration**: Automatic token refresh
- **Multi-factor**: Support for additional authentication methods

---

## Support and Maintenance

---

## Conclusion

The Lease Bot system provides a comprehensive solution for real estate leasing automation, combining AI-powered customer support, calendar management, and property listing management. The modular architecture ensures scalability and maintainability, while the integration with external services provides a complete ecosystem for real estate professionals.

For technical support or questions, please refer to the troubleshooting section or contact the development team.

---

**Document Version**: 1.0  
**Last Updated**: 13 August, 2025  
**Maintained By**: Ahmad Fraz

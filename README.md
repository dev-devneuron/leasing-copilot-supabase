## Setup

1. Clone the repository:
git clone https://github.com/dev-devneuron/leasing-copilot-supabase.git
cd leasing-copilot-supabase

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate   # Mac/Linux
venv\Scripts\activate      # Windows


2. Install Poetry (if not installed):
   pip install poetry

3. Install dependencies:
   make init

## .env file
contact for the .env file to make everything run 

#optional are for testing purpose only
Create a .env file in both backend and frontend with the following keys 
(update values as required):

Backend (leasing-copilot-supabase/.env)
--------------------------------------
VAPI_API_KEY=
VAPI_ASSISTANT_ID=
TWILIO_AUTH_TOKEN=
TWILIO_ACCOUNT_SID=
GEMINI_API_KEY=
SUPABASE_SERVICE_KEY=
GOOGLE_API_KEY=
DATABASE_1_URL=
DATABASE_2_URL=
SUPABASE_URL=
SUPABASE_JWT_SECRET =
SUPABASE_SERVICE_ROLE_KEY=
TWILIO_ACCOUNT_SID2 = #optional
TWILIO_AUTH_TOKEN2 =  #optional
VAPI_API_KEY2 =       #optional
VAPI_ASSISTANT_ID2 =  #optional


## Optional
If you want to manually install the dependencies:
# Install dependencies
pip install -r requirements.txt



------------------------------------------------------------
 Frontend Setup (React + Vite)
------------------------------------------------------------
cd RealtorApp

# Install dependencies
npm install

# Start dev server
npm run dev



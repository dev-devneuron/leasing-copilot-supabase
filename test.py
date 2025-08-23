from supabase import create_client
import os
from dotenv import load_dotenv
load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

def test_upload():
    with open("test.png", "rb") as f:
        res = supabase.storage.from_("realtor-files").upload("test.png", f)
    print(res)

test_upload()
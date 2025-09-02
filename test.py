# from fastapi import Depends, HTTPException, Security,FastAPI
# from sqlmodel import Session, select
# import httpx
# import os
# from db import *
# from auth_module import get_current_realtor_id
# from sqlmodel import Session, select


# VAPI_API_KEY = "541ffaff-3f6d-4365-9320-0bb171f12bd7"
# VAPI_BASE_URL = "https://api.vapi.ai"
# headers = {"Authorization": f"Bearer {VAPI_API_KEY}"}

# app=FastAPI()



# @app.get("/recordings")
# def get_recordings(
#      #realtor_id: int = Depends(get_current_realtor_id)
#      ):
#     realtor_id=71
#     recordings = []

#     # Step 1: Look up the realtor in DB to get their Twilio number
#     with Session(engine) as session:
#         realtor = session.exec(
#             select(Realtor).where(Realtor.id == realtor_id)
#         ).first()

#         if not realtor:
#             raise HTTPException(status_code=404, detail="Realtor not found")

#         if not realtor.twilio_contact:
#             raise HTTPException(
#                 status_code=400,
#                 detail="Realtor does not have a Twilio contact configured"
#             )

#         twilio_number = realtor.twilio_contact
#         print("from supabse got twilio contact:",twilio_number)

#     # Step 2: Fetch all calls from VAPI
#     resp = requests.get(f"{VAPI_BASE_URL}/call", headers=headers)
#     calls = resp.json()

#     for call in calls:
#         # Step 3: Get the phoneNumberId from the call
#         phone_number_id = call.get("phoneNumberId")
#         print("phone from vapi call id",phone_number_id)
#         if not phone_number_id:
#             continue

#         # Step 4: Look up the number against the phoneNumberId
#         pn_resp = requests.get(
#             f"{VAPI_BASE_URL}/phone-number/{phone_number_id}", headers=headers
#         )
#         if pn_resp.status_code != 200:
#             continue

#         bot_number = pn_resp.json().get("number")
#         print("bot number from vapi",bot_number)

#         # Step 5: Match with realtor’s Twilio contact
#         if bot_number != twilio_number:
#             continue

#         # Step 7: Extract recordings if available
#         recording_url = call.get("artifact", {}).get("recordingUrl")
        
#         if recording_url:
#                 recordings.append(
#                     {
#                         "url": recording_url
#                     }
#                 )

#     return {"recordings": recordings}

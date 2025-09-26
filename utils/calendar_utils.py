from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from datetime import datetime, timedelta
import os
from google.oauth2.credentials import Credentials
import pickle
from pytz import timezone, utc
from config import DEFAULT_TIMEZONE, WORKING_HOURS, SLOT_DURATION
import abc
from DB.db import *


class BaseCalendar(abc.ABC):
    @abc.abstractmethod
    def create_event(self, start_time_str, summary, email):
        pass

    @abc.abstractmethod
    def is_time_available(self, start_time_str):
        pass

    @abc.abstractmethod
    def get_free_slots(self, date_str, tz_str=None):
        pass


class GoogleCalendar(BaseCalendar):
    def __init__(self, realtor_id: int):
        self.realtor_id = realtor_id

    def get_calendar_service(self):
        with Session(engine) as session:
            statement = select(Realtor).where(Realtor.id == self.realtor_id)
            result = session.exec(statement).first()

            if not result or not result.credentials:
                raise Exception(
                    f"User {self.realtor_id} not authenticated. Please visit /authorize?realtor_id={self.realtor_id}"
                )

            creds = Credentials.from_authorized_user_info(
                json.loads(result.credentials)
            )

            if creds.expired and creds.refresh_token:
                creds.refresh(Request())

                # Optional: Save updated credentials back
                result.credentials = creds.to_json()
                session.add(result)
                session.commit()

            return build("calendar", "v3", credentials=creds)

    def create_event(
        self, start_time_str, summary, email, description="Apartment Visit Booking"
    ):
        service = self.get_calendar_service()
        tz = timezone(DEFAULT_TIMEZONE)
        if isinstance(start_time_str, datetime):
            start_time = start_time_str
        else:
            try:
                start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
            except ValueError:
                try:
                    start_time = datetime.strptime(start_time_str, "%Y-%m-%d %I:%M %p")
                except ValueError:
                    raise ValueError(
                        "Invalid date format. Use 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD HH:MM AM/PM'"
                    )

        start_time = tz.localize(start_time)
        end_time = start_time + timedelta(minutes=30)

        event = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": DEFAULT_TIMEZONE,
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": DEFAULT_TIMEZONE,
            },
            "attendees": [{"email": email}],
        }

        event = (
            service.events()
            .insert(calendarId="primary", body=event, sendUpdates="all")
            .execute()
        )
        print("Event URL:", event.get("htmlLink"))
        return event

    def is_time_available(self, start_time_str):
        service = self.get_calendar_service()
        tz = timezone(DEFAULT_TIMEZONE)

        if isinstance(start_time_str, datetime):
            start_time = start_time_str
        else:
            try:
                start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
            except ValueError:
                try:
                    start_time = datetime.strptime(start_time_str, "%Y-%m-%d %I:%M %p")
                except ValueError:
                    raise ValueError(
                        "Invalid date format. Use 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD HH:MM AM/PM'"
                    )

        start_time = tz.localize(start_time)
        start_utc = start_time.astimezone(utc)
        end_utc = (start_time + timedelta(minutes=30)).astimezone(utc)

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_utc.isoformat(),
                timeMax=end_utc.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])
        return len(events) == 0

    def get_free_slots(self, date_str, tz_str=None):
        if tz_str is None:
            tz_str = DEFAULT_TIMEZONE

        try:
            # Get calendar service with error handling
            service = self.get_calendar_service()
            if not service:
                raise Exception("Failed to initialize calendar service")
        except Exception as e:
            print(f"Error getting calendar service: {e}")
            return []

        try:
            tz = timezone(tz_str)
            date = datetime.strptime(date_str, "%Y-%m-%d")

            start = tz.localize(date.replace(hour=WORKING_HOURS["start"], minute=0))
            end = tz.localize(date.replace(hour=WORKING_HOURS["end"], minute=0))

            body = {
                "timeMin": start.isoformat(),
                "timeMax": end.isoformat(),
                "timeZone": tz_str,
                "items": [{"id": "primary"}],
            }

            # Execute freebusy query with error handling
            try:
                events = service.freebusy().query(body=body).execute()
                if not events or "calendars" not in events:
                    print("No calendar data received from Google Calendar API")
                    return []
                
                busy_times = events["calendars"]["primary"].get("busy", [])
            except Exception as e:
                print(f"Error querying calendar freebusy: {e}")
                return []

            slots = []
            current = start
            while current < end:
                next_slot = current + timedelta(minutes=SLOT_DURATION)
                
                # Check for overlaps with error handling
                try:
                    overlap = any(
                        datetime.fromisoformat(b["start"]).astimezone(tz) < next_slot
                        and datetime.fromisoformat(b["end"]).astimezone(tz) > current
                        for b in busy_times
                    )
                except (ValueError, KeyError) as e:
                    print(f"Error parsing busy time data: {e}")
                    # If we can't parse the busy times, assume no overlap
                    overlap = False
                
                if not overlap:
                    slots.append(current.strftime("%I:%M %p"))
                current = next_slot

            return slots

        except ValueError as e:
            print(f"Invalid date format: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error in get_free_slots: {e}")
            return []

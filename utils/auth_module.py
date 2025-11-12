"""
Authentication Module

This module provides authentication and authorization utilities for FastAPI endpoints.
Handles JWT token validation and user identification for Property Managers and Realtors.
"""

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from DB.db import engine, Realtor, PropertyManager, get_user_data_by_auth_id
from sqlmodel import Session, select
from config import SUPABASE_JWT_SECRET

# HTTP Bearer token security scheme
security = HTTPBearer()

def get_current_realtor_id(
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Legacy function for backward compatibility - returns realtor ID only."""
    token = credentials.credentials
    try:
        # Decode without audience verification to prevent mismatch errors
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False}
        )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token: missing user ID"
            )

        # Look up the realtor in the DB
        with Session(engine) as session:
            realtor = session.exec(
                select(Realtor).where(Realtor.auth_user_id == user_id)
            ).first()

            if not realtor:
                raise HTTPException(
                    status_code=404,
                    detail="Realtor not found"
                )
            return realtor.realtor_id

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token expired"
        )
    except jwt.InvalidTokenError as e:
        # Give more debugging info in logs, but not in the API response
        print(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )


def get_current_user_data(
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """New function that returns user data for both Property Managers and Realtors."""
    token = credentials.credentials
    try:
        # Decode without audience verification to prevent mismatch errors
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False}
        )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token: missing user ID"
            )

        # Get user data (works for both Property Managers and Realtors)
        user_data = get_user_data_by_auth_id(user_id)
        return user_data

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token expired"
        )
    except jwt.InvalidTokenError as e:
        # Give more debugging info in logs, but not in the API response
        print(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )

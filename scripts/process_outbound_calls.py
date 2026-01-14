#!/usr/bin/env python3
"""
Scheduled Job: Process Outbound Call Queue

This script processes eligible contacts for outbound calling.
It should be run periodically (e.g., every hour) via cron or scheduler.

Usage:
    python scripts/process_outbound_calls.py [--batch-size N]

Example cron entry (runs every hour at minute 0):
    0 * * * * cd /path/to/leasap-backend && python scripts/process_outbound_calls.py
"""

import sys
import os
import argparse
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from DB.outbound_calling import process_outbound_call_queue
from DB.db import Session, engine
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(
        description="Process outbound call queue for eligible contacts"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Maximum number of calls to trigger in this batch (default: 10)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check eligibility but don't actually trigger calls"
    )
    
    args = parser.parse_args()
    
    print(f"🚀 Starting outbound call queue processing at {datetime.utcnow().isoformat()}")
    print(f"   Batch size: {args.batch_size}")
    print(f"   Dry run: {args.dry_run}")
    
    if not engine:
        print("❌ Database connection not available")
        sys.exit(1)
    
    try:
        with Session(engine) as session:
            if args.dry_run:
                # Just check eligibility, don't trigger calls
                from DB.outbound_calling import identify_follow_up_candidates, check_eligibility
                
                candidates = identify_follow_up_candidates(session, limit=args.batch_size * 2)
                
                eligible_count = 0
                ineligible_count = 0
                
                for candidate in candidates[:args.batch_size]:
                    contact = candidate["contact"]
                    eligibility = check_eligibility(contact, session)
                    
                    if eligibility["eligible"]:
                        eligible_count += 1
                        print(f"   ✅ Eligible: {contact.phone_number} - {contact.name or 'Unknown'}")
                    else:
                        ineligible_count += 1
                        print(f"   ❌ Not eligible: {contact.phone_number} - {eligibility['reason']}")
                
                print(f"\n📊 Dry run results:")
                print(f"   Total candidates checked: {len(candidates)}")
                print(f"   Eligible: {eligible_count}")
                print(f"   Not eligible: {ineligible_count}")
            else:
                # Process queue and trigger calls
                result = process_outbound_call_queue(session, batch_size=args.batch_size)
                
                print(f"\n📊 Processing results:")
                print(f"   Processed: {result['processed']}")
                print(f"   Called: {result['called']}")
                print(f"   Skipped: {result['skipped']}")
                print(f"   Errors: {result['errors']}")
                
                if result['errors'] > 0:
                    print(f"\n⚠️  Errors encountered:")
                    for r in result['results']:
                        if r.get('status') == 'error':
                            print(f"   - {r.get('phone_number')}: {r.get('error')}")
        
        print(f"✅ Queue processing completed at {datetime.utcnow().isoformat()}")
        
    except Exception as e:
        print(f"❌ Error processing queue: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
Quick test script for the listing parser.
Run this to test if the parser is working correctly.

Usage:
    python test_data/test_parser.py
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from DB.listing_parser import parse_listing_file

def test_file(file_path: str, description: str):
    """Test parsing a single file."""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"File: {file_path}")
    print(f"{'='*60}")
    
    try:
        # Read file
        with open(file_path, 'rb') as f:
            content = f.read()
        
        filename = os.path.basename(file_path)
        
        # Parse file
        print(f"\n📄 Parsing {filename}...")
        listings = parse_listing_file(content, filename, use_ai=True)
        
        # Display results
        print(f"\n✅ Successfully parsed {len(listings)} listing(s)\n")
        
        for i, listing in enumerate(listings, 1):
            print(f"  Listing {i}:")
            print(f"    Address: {listing.get('address', 'N/A')}")
            print(f"    Price: ${listing.get('price', 0):,.0f}")
            print(f"    Bedrooms: {listing.get('bedrooms', 'N/A')}")
            print(f"    Bathrooms: {listing.get('bathrooms', 'N/A')}")
            print(f"    Square Feet: {listing.get('square_feet', 'N/A')}")
            print(f"    Property Type: {listing.get('property_type', 'N/A')}")
            print(f"    Status: {listing.get('listing_status', 'N/A')}")
            if listing.get('features'):
                print(f"    Features: {', '.join(listing['features'])}")
            if listing.get('agent'):
                print(f"    Agent: {listing['agent']}")
            print()
        
        return True, len(listings)
        
    except Exception as e:
        print(f"\n❌ Error parsing {file_path}: {e}")
        import traceback
        traceback.print_exc()
        return False, 0

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("LISTING PARSER TEST SUITE")
    print("="*60)
    
    # Get test data directory
    test_dir = Path(__file__).parent
    test_files = [
        ("listings_test.json", "Standard JSON format"),
        ("listings_test.csv", "Standard CSV format"),
        ("listings_test_variations.csv", "CSV with alternative column names"),
        ("listings_test.txt", "Structured text format"),
        ("listings_test_malformed.json", "JSON with non-standard fields"),
        ("listings_test_unstructured.txt", "Unstructured natural language"),
    ]
    
    results = []
    total_listings = 0
    
    for filename, description in test_files:
        file_path = test_dir / filename
        if file_path.exists():
            success, count = test_file(str(file_path), description)
            results.append((filename, success, count))
            if success:
                total_listings += count
        else:
            print(f"\n⚠️  File not found: {file_path}")
            results.append((filename, False, 0))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"\nTotal files tested: {len(test_files)}")
    print(f"Successful: {sum(1 for _, success, _ in results if success)}")
    print(f"Failed: {sum(1 for _, success, _ in results if not success)}")
    print(f"Total listings parsed: {total_listings}")
    print("\nDetailed Results:")
    for filename, success, count in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} - {filename} ({count} listings)")
    
    print("\n" + "="*60)
    if all(success for _, success, _ in results):
        print("🎉 ALL TESTS PASSED!")
    else:
        print("⚠️  SOME TESTS FAILED - Check errors above")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()


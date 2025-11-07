"""
AI-Powered Listing Data Parser

This module provides robust parsing capabilities for property/apartment listing data
in various formats (JSON, CSV, TXT) with intelligent normalization and error handling.
Uses Google Gemini AI to handle malformed or inconsistent data formats.
"""

import json
import csv
import io
import re
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, date
import google.generativeai as genai
import os
from dotenv import load_dotenv
from config import LLM_MODEL_NAME

load_dotenv()

# Configure Gemini AI
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


class ListingParser:
    """
    AI-powered parser for property listing data that handles various formats
    and normalizes data to match the expected schema.
    """
    
    # Expected schema fields
    REQUIRED_FIELDS = ["address", "price"]
    OPTIONAL_FIELDS = [
        "listing_id", "bedrooms", "bathrooms", "square_feet", "lot_size_sqft",
        "year_built", "property_type", "listing_status", "days_on_market",
        "agent", "features", "listing_date", "description", "image_url"
    ]
    
    def __init__(self, use_ai: bool = True):
        """
        Initialize the parser.
        
        Args:
            use_ai: Whether to use AI for parsing malformed data (default: True)
        """
        self.use_ai = use_ai and GEMINI_API_KEY is not None
        self.model = None
        if self.use_ai:
            try:
                self.model = genai.GenerativeModel(LLM_MODEL_NAME)
            except Exception as e:
                print(f"Warning: Could not initialize AI model: {e}")
                self.use_ai = False
    
    def parse_file(self, file_content: bytes, filename: str) -> List[Dict[str, Any]]:
        """
        Parse a file and return normalized listing data.
        
        Args:
            file_content: Raw file content as bytes
            filename: Name of the file (used to determine format)
            
        Returns:
            List of normalized listing dictionaries
        """
        file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
        
        try:
            if file_ext == 'json':
                return self._parse_json(file_content)
            elif file_ext == 'csv':
                return self._parse_csv(file_content)
            elif file_ext in ['txt', 'text']:
                return self._parse_text(file_content)
            else:
                # Try to auto-detect format
                return self._auto_detect_and_parse(file_content, filename)
        except Exception as e:
            print(f"Error parsing file {filename}: {e}")
            # Fallback to AI parsing if available
            if self.use_ai:
                return self._ai_parse_raw_content(file_content, filename)
            raise ValueError(f"Failed to parse file {filename}: {str(e)}")
    
    def _parse_json(self, content: bytes) -> List[Dict[str, Any]]:
        """Parse JSON content."""
        try:
            decoded = content.decode('utf-8')
            # Try to handle BOM and other encoding issues
            if decoded.startswith('\ufeff'):
                decoded = decoded[1:]
            
            data = json.loads(decoded)
            
            # Handle different JSON structures
            if isinstance(data, dict):
                # Single listing object
                return [self._normalize_listing(data)]
            elif isinstance(data, list):
                # Array of listings
                return [self._normalize_listing(item) for item in data]
            else:
                raise ValueError("Invalid JSON structure")
                
        except json.JSONDecodeError as e:
            # Try to fix common JSON issues
            decoded = content.decode('utf-8')
            fixed = self._fix_json(decoded)
            if fixed:
                return self._parse_json(fixed.encode('utf-8'))
            raise ValueError(f"Invalid JSON format: {str(e)}")
    
    def _parse_csv(self, content: bytes) -> List[Dict[str, Any]]:
        """Parse CSV content with flexible column mapping."""
        try:
            decoded = content.decode('utf-8')
            # Handle BOM
            if decoded.startswith('\ufeff'):
                decoded = decoded[1:]
            
            # Try different delimiters
            for delimiter in [',', ';', '\t', '|']:
                try:
                    reader = csv.DictReader(io.StringIO(decoded), delimiter=delimiter)
                    rows = list(reader)
                    if rows:
                        return [self._normalize_listing(row) for row in rows]
                except:
                    continue
            
            raise ValueError("Could not parse CSV with any delimiter")
            
        except Exception as e:
            raise ValueError(f"CSV parsing error: {str(e)}")
    
    def _parse_text(self, content: bytes) -> List[Dict[str, Any]]:
        """Parse plain text content using AI."""
        decoded = content.decode('utf-8')
        
        if self.use_ai:
            return self._ai_parse_text(decoded)
        else:
            # Fallback: try to extract structured data using regex
            return self._regex_parse_text(decoded)
    
    def _auto_detect_and_parse(self, content: bytes, filename: str) -> List[Dict[str, Any]]:
        """Auto-detect file format and parse."""
        decoded = content.decode('utf-8', errors='ignore')
        
        # Try JSON first
        try:
            return self._parse_json(content)
        except:
            pass
        
        # Try CSV
        try:
            return self._parse_csv(content)
        except:
            pass
        
        # Fallback to text parsing
        return self._parse_text(content)
    
    def _normalize_listing(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a raw listing dictionary to match the expected schema.
        Handles various field name variations and data types.
        """
        normalized = {}
        
        # Field mapping: handle various column name variations
        field_mapping = {
            # Address variations
            'address': ['address', 'addr', 'location', 'street', 'street_address', 'property_address'],
            'price': ['price', 'cost', 'rent', 'rental_price', 'monthly_rent', 'list_price', 'sale_price'],
            'bedrooms': ['bedrooms', 'beds', 'bed', 'bedroom_count', 'num_bedrooms'],
            'bathrooms': ['bathrooms', 'baths', 'bath', 'bathroom_count', 'num_bathrooms'],
            'square_feet': ['square_feet', 'sqft', 'sq_ft', 'square_footage', 'area', 'size'],
            'lot_size_sqft': ['lot_size_sqft', 'lot_size', 'lot_sqft', 'lot_square_feet'],
            'year_built': ['year_built', 'built_year', 'year', 'construction_year'],
            'property_type': ['property_type', 'type', 'property_category', 'category'],
            'listing_status': ['listing_status', 'status', 'availability', 'available'],
            'days_on_market': ['days_on_market', 'dom', 'days_listed'],
            'listing_id': ['listing_id', 'id', 'mls_id', 'mls_number', 'property_id'],
            'listing_date': ['listing_date', 'date', 'list_date', 'created_date'],
            'description': ['description', 'desc', 'details', 'property_description'],
            'image_url': ['image_url', 'image', 'photo', 'photo_url', 'picture_url'],
        }
        
        # Normalize keys (case-insensitive)
        raw_lower = {k.lower().strip(): v for k, v in raw_data.items() if v is not None and v != ''}
        
        # Map fields
        for target_field, variations in field_mapping.items():
            for var in variations:
                if var.lower() in raw_lower:
                    value = raw_lower[var.lower()]
                    normalized[target_field] = self._normalize_value(target_field, value)
                    break
        
        # Handle nested structures (e.g., agent info)
        normalized = self._extract_nested_data(raw_data, normalized)
        
        # Handle features (can be string, array, or comma-separated)
        if 'features' not in normalized:
            normalized['features'] = self._extract_features(raw_data)
        
        # Handle agent information
        if 'agent' not in normalized:
            normalized['agent'] = self._extract_agent(raw_data)
        
        # Ensure required fields
        if 'address' not in normalized or not normalized['address']:
            # Try to construct from components
            normalized['address'] = self._construct_address(raw_data)
        
        if 'price' not in normalized or normalized['price'] is None:
            normalized['price'] = 0
        
        # Set defaults for optional fields
        normalized.setdefault('property_type', 'Apartment')
        normalized.setdefault('listing_status', 'Available')
        normalized.setdefault('features', [])
        normalized.setdefault('bedrooms', 0)
        normalized.setdefault('bathrooms', 0)
        
        # Clean and validate
        normalized = self._clean_listing(normalized)
        
        return normalized
    
    def _normalize_value(self, field: str, value: Any) -> Any:
        """Normalize a field value to the correct type."""
        if value is None or value == '':
            return None
        
        # Price normalization
        if field == 'price':
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                # Remove currency symbols and commas
                cleaned = re.sub(r'[^\d.]', '', str(value))
                try:
                    return float(cleaned)
                except:
                    return 0
            return 0
        
        # Numeric fields
        numeric_fields = ['bedrooms', 'bathrooms', 'square_feet', 'lot_size_sqft', 
                         'year_built', 'days_on_market']
        if field in numeric_fields:
            if isinstance(value, (int, float)):
                return float(value) if field in ['bathrooms'] else int(value)
            if isinstance(value, str):
                # Extract numbers from string
                numbers = re.findall(r'\d+\.?\d*', str(value))
                if numbers:
                    val = float(numbers[0])
                    return val if field == 'bathrooms' else int(val)
            return None
        
        # Date fields
        if field == 'listing_date':
            return self._parse_date(value)
        
        # String fields - strip whitespace
        if isinstance(value, str):
            return value.strip()
        
        return value
    
    def _parse_date(self, value: Any) -> Optional[str]:
        """Parse various date formats to ISO format (YYYY-MM-DD)."""
        if not value:
            return None
        
        if isinstance(value, (date, datetime)):
            return value.strftime('%Y-%m-%d')
        
        if isinstance(value, str):
            # Try common date formats
            formats = [
                '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d',
                '%m-%d-%Y', '%d-%m-%Y', '%B %d, %Y', '%b %d, %Y'
            ]
            for fmt in formats:
                try:
                    dt = datetime.strptime(value.strip(), fmt)
                    return dt.strftime('%Y-%m-%d')
                except:
                    continue
        
        return None
    
    def _extract_features(self, raw_data: Dict[str, Any]) -> List[str]:
        """Extract features from various formats."""
        features = []
        
        # Check common feature field names
        feature_fields = ['features', 'amenities', 'amenity', 'facilities', 'facility']
        for field in feature_fields:
            if field in raw_data:
                value = raw_data[field]
                if isinstance(value, list):
                    features.extend([str(f).strip() for f in value if f])
                elif isinstance(value, str):
                    # Split by comma, semicolon, or newline
                    split_features = re.split(r'[,;\n]', value)
                    features.extend([f.strip() for f in split_features if f.strip()])
                break
        
        return [f for f in features if f]
    
    def _extract_agent(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Extract agent information from various formats."""
        agent = {}
        
        # Check for nested agent object
        if 'agent' in raw_data and isinstance(raw_data['agent'], dict):
            agent_data = raw_data['agent']
            agent['name'] = agent_data.get('name') or agent_data.get('agent_name')
            agent['phone'] = agent_data.get('phone') or agent_data.get('contact') or agent_data.get('phone_number')
            agent['email'] = agent_data.get('email') or agent_data.get('email_address')
        else:
            # Check for flat agent fields
            agent_fields = {
                'name': ['agent_name', 'agent', 'contact_name', 'realtor_name'],
                'phone': ['agent_phone', 'agent_contact', 'phone', 'contact', 'phone_number'],
                'email': ['agent_email', 'email', 'email_address']
            }
            
            for key, variations in agent_fields.items():
                for var in variations:
                    if var in raw_data and raw_data[var]:
                        agent[key] = str(raw_data[var]).strip()
                        break
        
        # Return None if no agent data found
        if not any(agent.values()):
            return None
        
        return agent if agent else None
    
    def _extract_nested_data(self, raw_data: Dict[str, Any], normalized: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from nested structures."""
        # Handle nested metadata
        if 'metadata' in raw_data and isinstance(raw_data['metadata'], dict):
            nested = self._normalize_listing(raw_data['metadata'])
            normalized.update({k: v for k, v in nested.items() if k not in normalized or not normalized[k]})
        
        return normalized
    
    def _construct_address(self, raw_data: Dict[str, Any]) -> str:
        """Try to construct address from components."""
        components = []
        
        address_fields = ['street', 'street_address', 'address_line1', 'address_line_1']
        city_fields = ['city']
        state_fields = ['state', 'state_code']
        zip_fields = ['zip', 'zipcode', 'zip_code', 'postal_code']
        
        for field_list, component_name in [
            (address_fields, 'street'),
            (city_fields, 'city'),
            (state_fields, 'state'),
            (zip_fields, 'zip')
        ]:
            for field in field_list:
                if field in raw_data and raw_data[field]:
                    components.append(str(raw_data[field]).strip())
                    break
        
        if components:
            return ', '.join(components)
        
        return "Address not provided"
    
    def _clean_listing(self, listing: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and validate listing data."""
        # Remove None values from optional fields (but keep required ones)
        cleaned = {k: v for k, v in listing.items() if v is not None or k in self.REQUIRED_FIELDS}
        
        # Ensure price is positive
        if 'price' in cleaned and (not isinstance(cleaned['price'], (int, float)) or cleaned['price'] < 0):
            cleaned['price'] = 0
        
        # Ensure bedrooms and bathrooms are non-negative
        for field in ['bedrooms', 'bathrooms']:
            if field in cleaned and (not isinstance(cleaned[field], (int, float)) or cleaned[field] < 0):
                cleaned[field] = 0
        
        # Ensure features is a list
        if 'features' in cleaned and not isinstance(cleaned['features'], list):
            cleaned['features'] = []
        
        # Validate listing_status
        valid_statuses = ['Available', 'For Sale', 'For Rent', 'Sold', 'Rented']
        if 'listing_status' in cleaned and cleaned['listing_status'] not in valid_statuses:
            cleaned['listing_status'] = 'Available'
        
        return cleaned
    
    def _fix_json(self, json_str: str) -> Optional[str]:
        """Try to fix common JSON issues."""
        # Remove trailing commas
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        # Fix single quotes to double quotes (simple cases)
        json_str = re.sub(r"'([^']*)':", r'"\1":', json_str)
        return json_str
    
    def _regex_parse_text(self, text: str) -> List[Dict[str, Any]]:
        """Fallback text parsing using regex patterns."""
        listings = []
        
        # Try to find property listings in text
        # This is a simple fallback - AI parsing is preferred
        lines = text.split('\n')
        current_listing = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_listing:
                    listings.append(self._normalize_listing(current_listing))
                    current_listing = {}
                continue
            
            # Try to extract key-value pairs
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                current_listing[key] = value
        
        if current_listing:
            listings.append(self._normalize_listing(current_listing))
        
        return listings if listings else [self._normalize_listing({'address': 'Unknown', 'price': 0})]
    
    def _ai_parse_text(self, text: str) -> List[Dict[str, Any]]:
        """Use AI to parse unstructured text into listing data."""
        if not self.use_ai:
            return self._regex_parse_text(text)
        
        prompt = f"""You are a real estate data parser. Extract property listing information from the following text and return it as a JSON array of objects.

Each listing object should have these fields:
- address (required): Full property address
- price (required): Numeric price value
- bedrooms: Number of bedrooms (numeric)
- bathrooms: Number of bathrooms (numeric, can be decimal like 2.5)
- square_feet: Square footage (numeric)
- lot_size_sqft: Lot size in square feet (numeric)
- year_built: Year built (numeric)
- property_type: Type of property (e.g., "Apartment", "House", "Condo")
- listing_status: Status (e.g., "Available", "For Sale", "For Rent", "Sold", "Rented")
- days_on_market: Days on market (numeric)
- listing_id: Listing/MLS ID (string)
- listing_date: Date in YYYY-MM-DD format
- description: Property description (string)
- image_url: Image URL (string)
- features: Array of feature strings (e.g., ["Pool", "Gym", "Parking"])
- agent: Object with name, phone, email fields (or null)

Text to parse:
{text}

Return ONLY valid JSON array, no other text. If multiple properties are described, create multiple objects in the array. If no clear property data is found, return an empty array [].
"""
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Extract JSON from response (handle markdown code blocks)
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()
            
            data = json.loads(response_text)
            if isinstance(data, list):
                return [self._normalize_listing(item) for item in data]
            elif isinstance(data, dict):
                return [self._normalize_listing(data)]
            else:
                return []
        except Exception as e:
            print(f"AI parsing error: {e}")
            return self._regex_parse_text(text)
    
    def _ai_parse_raw_content(self, content: bytes, filename: str) -> List[Dict[str, Any]]:
        """Use AI to parse raw file content when standard parsing fails."""
        if not self.use_ai:
            raise ValueError(f"Could not parse file {filename} and AI is not available")
        
        try:
            decoded = content.decode('utf-8', errors='ignore')
            return self._ai_parse_text(decoded)
        except Exception as e:
            raise ValueError(f"AI parsing failed for {filename}: {str(e)}")


# Global parser instance
_default_parser = None

def get_parser(use_ai: bool = True) -> ListingParser:
    """Get or create the default parser instance."""
    global _default_parser
    if _default_parser is None:
        _default_parser = ListingParser(use_ai=use_ai)
    return _default_parser


def parse_listing_file(file_content: bytes, filename: str, use_ai: bool = True) -> List[Dict[str, Any]]:
    """
    Convenience function to parse a listing file.
    
    Args:
        file_content: Raw file content as bytes
        filename: Name of the file
        use_ai: Whether to use AI for parsing (default: True)
        
    Returns:
        List of normalized listing dictionaries
    """
    parser = get_parser(use_ai=use_ai)
    return parser.parse_file(file_content, filename)


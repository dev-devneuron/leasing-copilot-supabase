# Frontend Contact Form Integration Guide

## 📋 Overview

This guide explains how to integrate the contact form on your frontend with the backend API.

---

## 🔗 API Endpoint

**URL:** `POST /contact`

**Base URL:** Your backend URL (e.g., `https://your-backend-url.com` or `http://localhost:8000`)

**Full URL:** `https://your-backend-url.com/contact`

---

## 📤 Request Format

### Headers
```
Content-Type: application/json
```

### Request Body (JSON)
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "message": "I'm interested in learning more about your services.",
  "phone": "+1234567890",        // Optional
  "subject": "General Inquiry"   // Optional
}
```

### Required Fields
- `name` (string): Name of the person submitting the form
- `email` (string): Valid email address
- `message` (string): The message content

### Optional Fields
- `phone` (string): Phone number
- `subject` (string): Subject line

---

## ✅ Success Response

**Status Code:** `200 OK`

**Response Body:**
```json
{
  "message": "Thank you for contacting us! We've received your message and will get back to you soon.",
  "contact_id": 123,
  "submitted_at": "2024-01-15T10:30:00.000Z"
}
```

---

## ❌ Error Responses

### 400 Bad Request
Missing required fields or invalid data:
```json
{
  "detail": "Field 'name' is required"
}
```

### 500 Internal Server Error
Server error:
```json
{
  "detail": "Error submitting contact form: [error message]"
}
```

---

## 💻 Frontend Implementation Examples

### React/Next.js Example

```typescript
// ContactForm.tsx
import { useState } from 'react';

interface ContactFormData {
  name: string;
  email: string;
  message: string;
  phone?: string;
  subject?: string;
}

export default function ContactForm() {
  const [formData, setFormData] = useState<ContactFormData>({
    name: '',
    email: '',
    message: '',
    phone: '',
    subject: '',
  });
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      const response = await fetch('https://your-backend-url.com/contact', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: formData.name,
          email: formData.email,
          message: formData.message,
          phone: formData.phone || undefined,
          subject: formData.subject || undefined,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to submit form');
      }

      const data = await response.json();
      setSuccess(true);
      console.log('Form submitted successfully:', data);
      
      // Reset form
      setFormData({
        name: '',
        email: '',
        message: '',
        phone: '',
        subject: '',
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="contact-form">
      {success && (
        <div className="success-message">
          Thank you for contacting us! We'll get back to you soon.
        </div>
      )}
      
      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      <div>
        <label htmlFor="name">Name *</label>
        <input
          type="text"
          id="name"
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          required
        />
      </div>

      <div>
        <label htmlFor="email">Email *</label>
        <input
          type="email"
          id="email"
          value={formData.email}
          onChange={(e) => setFormData({ ...formData, email: e.target.value })}
          required
        />
      </div>

      <div>
        <label htmlFor="phone">Phone (Optional)</label>
        <input
          type="tel"
          id="phone"
          value={formData.phone}
          onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
        />
      </div>

      <div>
        <label htmlFor="subject">Subject (Optional)</label>
        <input
          type="text"
          id="subject"
          value={formData.subject}
          onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
        />
      </div>

      <div>
        <label htmlFor="message">Message *</label>
        <textarea
          id="message"
          value={formData.message}
          onChange={(e) => setFormData({ ...formData, message: e.target.value })}
          required
          rows={5}
        />
      </div>

      <button type="submit" disabled={loading}>
        {loading ? 'Submitting...' : 'Send Message'}
      </button>
    </form>
  );
}
```

### Vanilla JavaScript Example

```javascript
// contact-form.js
async function submitContactForm(formData) {
  try {
    const response = await fetch('https://your-backend-url.com/contact', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name: formData.name,
        email: formData.email,
        message: formData.message,
        phone: formData.phone || undefined,
        subject: formData.subject || undefined,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to submit form');
    }

    const data = await response.json();
    console.log('Form submitted successfully:', data);
    return data;
  } catch (error) {
    console.error('Error submitting form:', error);
    throw error;
  }
}

// HTML form handler
document.getElementById('contact-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  
  const formData = {
    name: document.getElementById('name').value,
    email: document.getElementById('email').value,
    message: document.getElementById('message').value,
    phone: document.getElementById('phone').value,
    subject: document.getElementById('subject').value,
  };

  try {
    const result = await submitContactForm(formData);
    alert('Thank you for contacting us! We\'ll get back to you soon.');
    e.target.reset();
  } catch (error) {
    alert('Error: ' + error.message);
  }
});
```

---

## 🔒 CORS Configuration

The backend is configured to accept requests from:
- `https://leaseap.com`
- `https://www.leasap.com`
- `http://localhost:3000` (development)
- `http://localhost:5173` (development)

If your frontend domain is different, contact the backend team to add it to the CORS whitelist.

---

## 📝 Form Validation

### Client-Side Validation (Recommended)

Before submitting, validate:
- **Name:** Required, at least 2 characters
- **Email:** Required, valid email format
- **Message:** Required, at least 10 characters
- **Phone:** Optional, if provided should be valid format
- **Subject:** Optional

### Example Validation

```javascript
function validateForm(formData) {
  const errors = [];

  if (!formData.name || formData.name.trim().length < 2) {
    errors.push('Name must be at least 2 characters');
  }

  if (!formData.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
    errors.push('Please enter a valid email address');
  }

  if (!formData.message || formData.message.trim().length < 10) {
    errors.push('Message must be at least 10 characters');
  }

  return errors;
}
```

---

## 🎨 UI/UX Recommendations

1. **Loading State:** Show a loading spinner or disable the submit button while the request is in progress
2. **Success Message:** Display a clear success message after submission
3. **Error Handling:** Show user-friendly error messages
4. **Form Reset:** Clear the form after successful submission
5. **Required Fields:** Mark required fields with an asterisk (*)
6. **Email Validation:** Use HTML5 email input type for better mobile keyboard support

---

## 🧪 Testing

### Test with cURL

```bash
curl -X POST https://your-backend-url.com/contact \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "message": "This is a test message",
    "phone": "+1234567890",
    "subject": "Test Subject"
  }'
```

### Test with Postman

1. Method: `POST`
2. URL: `https://your-backend-url.com/contact`
3. Headers: `Content-Type: application/json`
4. Body (raw JSON):
```json
{
  "name": "Test User",
  "email": "test@example.com",
  "message": "This is a test message"
}
```

---

## 📧 Email Notifications

When a contact form is submitted:
1. Data is saved to the database
2. A database trigger automatically sends an email notification to `founders@leasap.com`
3. The email includes all form details (name, email, phone, subject, message)

**Note:** Email notifications are handled automatically by the backend. No additional frontend code is needed.

---

## 🆘 Troubleshooting

### CORS Error
- **Problem:** Browser blocks the request due to CORS
- **Solution:** Ensure your frontend domain is in the backend's CORS whitelist

### 400 Bad Request
- **Problem:** Missing required fields or invalid data
- **Solution:** Check that `name`, `email`, and `message` are included and valid

### 500 Internal Server Error
- **Problem:** Server-side error
- **Solution:** Check backend logs, ensure database is accessible

### Network Error
- **Problem:** Cannot connect to backend
- **Solution:** Verify the backend URL is correct and the server is running

---

## 📞 Support

If you encounter any issues:
1. Check the browser console for error messages
2. Verify the API endpoint URL is correct
3. Test with cURL or Postman to isolate frontend vs backend issues
4. Contact the backend team with error details

---

**Ready to integrate!** Use the examples above as a starting point for your frontend implementation.

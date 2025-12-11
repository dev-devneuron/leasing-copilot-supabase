/**
 * Booking Management Component Example
 * 
 * This component demonstrates how to:
 * 1. Display bookings with original customer-sent time (no timezone conversion)
 * 2. Show timezone confirmation message to users
 * 3. Display call recordings and transcripts
 * 4. Update and delete bookings
 */

import React, { useState, useEffect } from 'react';

interface Booking {
  bookingId: number;
  propertyId: number;
  propertyAddress?: string;
  visitor: {
    name: string;
    phone: string;
    email?: string;
  };
  startAt: string; // ISO format (UTC for internal use)
  endAt: string; // ISO format (UTC for internal use)
  customerSentStartAt?: string; // Original time as customer sent it
  customerSentEndAt?: string; // Original time as customer sent it
  timezone: string;
  status: 'pending' | 'approved' | 'denied' | 'cancelled' | 'rescheduled';
  notes?: string;
  callRecord?: {
    vapiCallId: string;
    callTranscript?: string;
    callRecordingUrl?: string;
  };
  createdAt: string;
  updatedAt: string;
}

interface BookingCardProps {
  booking: Booking;
  onUpdate: (bookingId: number, updates: Partial<Booking>) => Promise<void>;
  onDelete: (bookingId: number) => Promise<void>;
}

const BookingCard: React.FC<BookingCardProps> = ({ booking, onUpdate, onDelete }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [isPlayingRecording, setIsPlayingRecording] = useState(false);
  const [showTranscript, setShowTranscript] = useState(false);
  const [formData, setFormData] = useState({
    visitorName: booking.visitor.name,
    visitorPhone: booking.visitor.phone,
    visitorEmail: booking.visitor.email || '',
    notes: booking.notes || '',
    startAt: booking.customerSentStartAt || booking.startAt,
    endAt: booking.customerSentEndAt || booking.endAt,
    timezone: booking.timezone,
  });

  const handleUpdate = async () => {
    try {
      await onUpdate(booking.bookingId, {
        visitor: {
          name: formData.visitorName,
          phone: formData.visitorPhone,
          email: formData.visitorEmail,
        },
        notes: formData.notes,
        customerSentStartAt: formData.startAt,
        customerSentEndAt: formData.endAt,
        timezone: formData.timezone,
      });
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to update booking:', error);
      alert('Failed to update booking. Please try again.');
    }
  };

  const handleDelete = async () => {
    if (window.confirm('Are you sure you want to delete this booking? This action cannot be undone.')) {
      try {
        await onDelete(booking.bookingId);
      } catch (error) {
        console.error('Failed to delete booking:', error);
        alert('Failed to delete booking. Please try again.');
      }
    }
  };

  // Format the original customer-sent time for display
  const formatCustomerTime = (timeString?: string) => {
    if (!timeString) return 'Not specified';
    // Display exactly as customer sent it
    return timeString;
  };

  return (
    <div className="booking-card" style={{
      border: '1px solid #ddd',
      borderRadius: '8px',
      padding: '16px',
      marginBottom: '16px',
      backgroundColor: '#fff',
    }}>
      <div className="booking-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
        <div>
          <h3 style={{ margin: '0 0 8px 0' }}>{booking.visitor.name}</h3>
          <p style={{ margin: '4px 0', color: '#666' }}>
            📞 {booking.visitor.phone}
            {booking.visitor.email && ` • ✉️ ${booking.visitor.email}`}
          </p>
          <p style={{ margin: '4px 0', color: '#666' }}>
            🏠 {booking.propertyAddress || `Property ID: ${booking.propertyId}`}
          </p>
        </div>
        <div>
          <span style={{
            padding: '4px 12px',
            borderRadius: '12px',
            fontSize: '12px',
            fontWeight: 'bold',
            backgroundColor: booking.status === 'approved' ? '#d4edda' : 
                           booking.status === 'pending' ? '#fff3cd' : 
                           booking.status === 'cancelled' ? '#f8d7da' : '#e2e3e5',
            color: booking.status === 'approved' ? '#155724' : 
                   booking.status === 'pending' ? '#856404' : 
                   booking.status === 'cancelled' ? '#721c24' : '#383d41',
          }}>
            {booking.status.toUpperCase()}
          </span>
        </div>
      </div>

      <div className="booking-time" style={{ marginTop: '16px', padding: '12px', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
        <div style={{ marginBottom: '8px' }}>
          <strong>⏰ Time (as customer mentioned):</strong>
          <div style={{ marginTop: '4px', padding: '8px', backgroundColor: '#fff', borderRadius: '4px' }}>
            <div>
              <strong>Start:</strong> {formatCustomerTime(booking.customerSentStartAt)}
            </div>
            <div style={{ marginTop: '4px' }}>
              <strong>End:</strong> {formatCustomerTime(booking.customerSentEndAt)}
            </div>
          </div>
        </div>
        
        {/* Timezone Confirmation Notice */}
        <div style={{
          marginTop: '12px',
          padding: '12px',
          backgroundColor: '#fff3cd',
          border: '1px solid #ffc107',
          borderRadius: '4px',
          fontSize: '14px',
        }}>
          <strong>⚠️ Timezone Confirmation Needed:</strong>
          <p style={{ margin: '8px 0 0 0' }}>
            The customer mentioned this time: <strong>{formatCustomerTime(booking.customerSentStartAt)}</strong>
            <br />
            Please confirm with the customer that this time is correct for their timezone ({booking.timezone}).
          </p>
        </div>
      </div>

      {/* Call Recording and Transcript Section */}
      {booking.callRecord && (
        <div className="call-record" style={{ marginTop: '16px', padding: '12px', backgroundColor: '#e7f3ff', borderRadius: '4px' }}>
          <h4 style={{ margin: '0 0 12px 0' }}>📞 Call Record</h4>
          
          {booking.callRecord.callRecordingUrl && (
            <div style={{ marginBottom: '12px' }}>
              <audio 
                controls 
                src={booking.callRecord.callRecordingUrl}
                style={{ width: '100%' }}
                onPlay={() => setIsPlayingRecording(true)}
                onPause={() => setIsPlayingRecording(false)}
                onEnded={() => setIsPlayingRecording(false)}
              >
                Your browser does not support the audio element.
              </audio>
            </div>
          )}
          
          {booking.callRecord.callTranscript && (
            <div>
              <button
                onClick={() => setShowTranscript(!showTranscript)}
                style={{
                  padding: '8px 16px',
                  backgroundColor: '#007bff',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  marginBottom: '8px',
                }}
              >
                {showTranscript ? 'Hide' : 'Show'} Transcript
              </button>
              
              {showTranscript && (
                <div style={{
                  marginTop: '8px',
                  padding: '12px',
                  backgroundColor: '#fff',
                  borderRadius: '4px',
                  maxHeight: '300px',
                  overflowY: 'auto',
                  fontSize: '14px',
                  lineHeight: '1.6',
                  whiteSpace: 'pre-wrap',
                }}>
                  {booking.callRecord.callTranscript}
                </div>
              )}
            </div>
          )}
          
          {booking.callRecord.vapiCallId && (
            <p style={{ margin: '8px 0 0 0', fontSize: '12px', color: '#666' }}>
              Call ID: {booking.callRecord.vapiCallId}
            </p>
          )}
        </div>
      )}

      {booking.notes && (
        <div style={{ marginTop: '12px', padding: '8px', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
          <strong>Notes:</strong> {booking.notes}
        </div>
      )}

      <div className="booking-actions" style={{ marginTop: '16px', display: 'flex', gap: '8px' }}>
        {!isEditing ? (
          <>
            <button
              onClick={() => setIsEditing(true)}
              style={{
                padding: '8px 16px',
                backgroundColor: '#007bff',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              ✏️ Edit
            </button>
            <button
              onClick={handleDelete}
              style={{
                padding: '8px 16px',
                backgroundColor: '#dc3545',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              🗑️ Delete
            </button>
          </>
        ) : (
          <>
            <button
              onClick={handleUpdate}
              style={{
                padding: '8px 16px',
                backgroundColor: '#28a745',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              ✅ Save
            </button>
            <button
              onClick={() => {
                setIsEditing(false);
                setFormData({
                  visitorName: booking.visitor.name,
                  visitorPhone: booking.visitor.phone,
                  visitorEmail: booking.visitor.email || '',
                  notes: booking.notes || '',
                  startAt: booking.customerSentStartAt || booking.startAt,
                  endAt: booking.customerSentEndAt || booking.endAt,
                  timezone: booking.timezone,
                });
              }}
              style={{
                padding: '8px 16px',
                backgroundColor: '#6c757d',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              ❌ Cancel
            </button>
          </>
        )}
      </div>

      {isEditing && (
        <div className="edit-form" style={{ marginTop: '16px', padding: '16px', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', marginBottom: '4px', fontWeight: 'bold' }}>Visitor Name:</label>
            <input
              type="text"
              value={formData.visitorName}
              onChange={(e) => setFormData({ ...formData, visitorName: e.target.value })}
              style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ddd' }}
            />
          </div>
          
          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', marginBottom: '4px', fontWeight: 'bold' }}>Visitor Phone:</label>
            <input
              type="text"
              value={formData.visitorPhone}
              onChange={(e) => setFormData({ ...formData, visitorPhone: e.target.value })}
              style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ddd' }}
            />
          </div>
          
          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', marginBottom: '4px', fontWeight: 'bold' }}>Visitor Email:</label>
            <input
              type="email"
              value={formData.visitorEmail}
              onChange={(e) => setFormData({ ...formData, visitorEmail: e.target.value })}
              style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ddd' }}
            />
          </div>
          
          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', marginBottom: '4px', fontWeight: 'bold' }}>Start Time (as customer sent):</label>
            <input
              type="text"
              value={formData.startAt}
              onChange={(e) => setFormData({ ...formData, startAt: e.target.value })}
              placeholder="e.g., 2025-12-01T16:00:00"
              style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ddd' }}
            />
          </div>
          
          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', marginBottom: '4px', fontWeight: 'bold' }}>End Time (as customer sent):</label>
            <input
              type="text"
              value={formData.endAt}
              onChange={(e) => setFormData({ ...formData, endAt: e.target.value })}
              placeholder="e.g., 2025-12-01T17:00:00"
              style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ddd' }}
            />
          </div>
          
          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', marginBottom: '4px', fontWeight: 'bold' }}>Timezone:</label>
            <input
              type="text"
              value={formData.timezone}
              onChange={(e) => setFormData({ ...formData, timezone: e.target.value })}
              placeholder="e.g., America/New_York"
              style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ddd' }}
            />
          </div>
          
          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', marginBottom: '4px', fontWeight: 'bold' }}>Notes:</label>
            <textarea
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              rows={3}
              style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ddd' }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

// Main Booking Management Component
const BookingManagement: React.FC = () => {
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';
  const token = localStorage.getItem('auth_token'); // Adjust based on your auth implementation

  useEffect(() => {
    fetchBookings();
  }, []);

  const fetchBookings = async () => {
    try {
      setLoading(true);
      // Adjust user_id based on your auth system
      const userId = localStorage.getItem('user_id');
      const response = await fetch(`${API_BASE_URL}/api/users/${userId}/bookings`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch bookings');
      }

      const data = await response.json();
      setBookings(data.bookings || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (bookingId: number, updates: Partial<Booking>) => {
    const response = await fetch(`${API_BASE_URL}/api/bookings/${bookingId}`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        visitor_name: updates.visitor?.name,
        visitor_phone: updates.visitor?.phone,
        visitor_email: updates.visitor?.email,
        start_at: updates.customerSentStartAt,
        end_at: updates.customerSentEndAt,
        timezone: updates.timezone,
        notes: updates.notes,
      }),
    });

    if (!response.ok) {
      throw new Error('Failed to update booking');
    }

    // Refresh bookings
    await fetchBookings();
  };

  const handleDelete = async (bookingId: number) => {
    const response = await fetch(`${API_BASE_URL}/api/bookings/${bookingId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error('Failed to delete booking');
    }

    // Refresh bookings
    await fetchBookings();
  };

  if (loading) {
    return <div>Loading bookings...</div>;
  }

  if (error) {
    return <div style={{ color: 'red' }}>Error: {error}</div>;
  }

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '24px' }}>Bookings Management</h1>
      
      {bookings.length === 0 ? (
        <p>No bookings found.</p>
      ) : (
        <div>
          {bookings.map((booking) => (
            <BookingCard
              key={booking.bookingId}
              booking={booking}
              onUpdate={handleUpdate}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default BookingManagement;


-- Check if WhatsApp messages are being saved
SELECT 
    chat_id,
    cust_id,
    date,
    count as message_count
FROM chatsession
ORDER BY date DESC
LIMIT 10;



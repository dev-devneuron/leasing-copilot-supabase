// Supabase Edge Function: Send Contact Form Email
// This function is triggered by a database trigger when a new contact form submission is created

// Setup type definitions for built-in Supabase Runtime APIs
import "jsr:@supabase/functions-js/edge-runtime.d.ts";

import nodemailer from "npm:nodemailer@6.9.7";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

Deno.serve(async (req: Request) => {
  // Handle CORS preflight requests
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    // Log raw request details for debugging
    console.log("=== Contact Form Email Request ===");
    console.log("Method:", req.method);
    console.log("URL:", req.url);
    console.log("Headers:", JSON.stringify(Object.fromEntries(req.headers.entries())));
    
    // Get raw body text first for debugging
    const rawBody = await req.text();
    console.log("Raw body:", rawBody);
    console.log("Raw body type:", typeof rawBody);
    console.log("Raw body length:", rawBody.length);
    
    // Parse the request payload
    let payload;
    try {
      // Try parsing the raw body as JSON
      payload = JSON.parse(rawBody);
      console.log("Parsed payload:", JSON.stringify(payload));
      console.log("Payload type:", typeof payload);
    } catch (e) {
      console.error("Failed to parse JSON:", e);
      console.error("Error details:", e.message);
      console.error("Raw body that failed:", rawBody);
      return new Response(
        JSON.stringify({
          error: "Invalid JSON payload",
          details: e.message || "Request body must be valid JSON",
          rawBody: rawBody.substring(0, 200), // First 200 chars for debugging
        }),
        {
          status: 400,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    console.log("Received payload:", JSON.stringify(payload));

    // Extract contact form data
    const {
      contact_id,
      name,
      email,
      phone,
      subject,
      message,
      submitted_at,
    } = payload;

    // Validate required fields
    if (!name || !email || !message) {
      return new Response(
        JSON.stringify({ error: "Missing required fields: name, email, message" }),
        {
          status: 400,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    // Get SMTP configuration from environment variables
    const smtpUser = Deno.env.get("SMTP_USER");
    const smtpPass = Deno.env.get("SMTP_PASS");
    const recipientEmail = Deno.env.get("RECIPIENT_EMAIL") || smtpUser;
    const smtpHost = Deno.env.get("SMTP_HOST") || "smtp.zoho.com";
    const smtpPort = parseInt(Deno.env.get("SMTP_PORT") || "587");
    const smtpSecure = Deno.env.get("SMTP_SECURE") === "true";

    if (!smtpUser || !smtpPass) {
      console.error("SMTP credentials not configured");
      return new Response(
        JSON.stringify({ error: "Email service not configured" }),
        {
          status: 500,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    // Create email transporter - supports Zoho Mail, Gmail, Outlook, and custom SMTP
    const transporter = nodemailer.createTransport({
      host: smtpHost,
      port: smtpPort,
      secure: smtpSecure, // true for 465, false for other ports (587)
      auth: {
        user: smtpUser,
        pass: smtpPass,
      },
      // Zoho Mail requires TLS
      tls: {
        ciphers: "SSLv3",
      },
    });

    // Build email content
    const emailSubject = subject || `New Contact Form Submission - ${name}`;
    const emailText = `
New Contact Form Submission

Contact ID: ${contact_id || "N/A"}

Contact Information:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Name: ${name}
Email: ${email}
${phone ? `Phone: ${phone}` : ""}

${subject ? `Subject: ${subject}` : ""}

Message:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
${message}

Submitted: ${submitted_at || new Date().toISOString()}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This is an automated notification from your Leasap contact form.
    `.trim();

    const emailHtml = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
    .header { background: #4F46E5; color: white; padding: 20px; border-radius: 8px 8px 0 0; }
    .content { background: #f9fafb; padding: 20px; border: 1px solid #e5e7eb; }
    .section { margin: 20px 0; }
    .label { font-weight: bold; color: #4F46E5; }
    .divider { border-top: 2px solid #e5e7eb; margin: 20px 0; }
    .message-box { background: white; padding: 15px; border-left: 4px solid #4F46E5; margin: 15px 0; }
    .footer { text-align: center; color: #6b7280; font-size: 12px; margin-top: 20px; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>📧 New Contact Form Submission</h1>
      <p>Contact ID: #${contact_id || "N/A"}</p>
    </div>
    <div class="content">
      <div class="section">
        <h2>Contact Information</h2>
        <p><span class="label">Name:</span> ${name}</p>
        <p><span class="label">Email:</span> <a href="mailto:${email}">${email}</a></p>
        ${phone ? `<p><span class="label">Phone:</span> <a href="tel:${phone}">${phone}</a></p>` : ""}
      </div>
      
      ${subject ? `
      <div class="divider"></div>
      <div class="section">
        <h2>Subject</h2>
        <p>${subject}</p>
      </div>
      ` : ""}
      
      <div class="divider"></div>
      <div class="section">
        <h2>Message</h2>
        <div class="message-box">
          <p>${message.replace(/\n/g, "<br>")}</p>
        </div>
      </div>
      
      <div class="divider"></div>
      <p><span class="label">Submitted:</span> ${submitted_at || new Date().toISOString()}</p>
    </div>
    <div class="footer">
      <p>This is an automated notification from your Leasap contact form.</p>
    </div>
  </div>
</body>
</html>
    `.trim();

    // Send email
    const mailOptions = {
      from: `Leasap Contact Form <${smtpUser}>`,
      to: recipientEmail,
      replyTo: email, // Allow replying directly to the contact
      subject: emailSubject,
      text: emailText,
      html: emailHtml,
    };

    const info = await transporter.sendMail(mailOptions);

    console.log("Email sent successfully:", info.messageId);

    return new Response(
      JSON.stringify({
        success: true,
        message: "Email sent successfully",
        messageId: info.messageId,
      }),
      {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  } catch (error) {
    console.error("Error sending email:", error);
    return new Response(
      JSON.stringify({
        error: "Failed to send email",
        details: error.message,
      }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
});

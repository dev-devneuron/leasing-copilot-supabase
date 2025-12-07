// Supabase Edge Function: Send Demo Request Email
// This function is triggered by a database trigger when a new demo request is created

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
    // Parse the request payload
    let payload;
    try {
      payload = await req.json();
    } catch (e) {
      console.error("Failed to parse JSON:", e);
      return new Response(
        JSON.stringify({ 
          error: "Invalid JSON payload",
          details: "Request body must be valid JSON"
        }),
        {
          status: 400,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    // Log received payload for debugging
    console.log("Received payload:", JSON.stringify(payload));

    // Extract demo request data
    const {
      demo_request_id,
      name,
      email,
      phone,
      company_name,
      preferred_date,
      preferred_time,
      timezone,
      notes,
      status,
      requested_at,
    } = payload;

    // Validate required fields
    if (!name || !email || !phone) {
      console.error("Missing required fields. Received:", {
        name: !!name,
        email: !!email,
        phone: !!phone,
        payloadKeys: Object.keys(payload || {})
      });
      return new Response(
        JSON.stringify({ 
          error: "Missing required fields: name, email, phone",
          received: {
            hasName: !!name,
            hasEmail: !!email,
            hasPhone: !!phone,
            payloadKeys: Object.keys(payload || {})
          }
        }),
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

    // Format preferred date/time
    let dateTimeInfo = "Not specified";
    if (preferred_date || preferred_time) {
      const parts: string[] = [];
      if (preferred_date) parts.push(`Date: ${preferred_date}`);
      if (preferred_time) parts.push(`Time: ${preferred_time}`);
      if (timezone) parts.push(`Timezone: ${timezone}`);
      dateTimeInfo = parts.join("\n");
    }

    // Build email content
    const emailSubject = `New Demo Request #${demo_request_id || "N/A"} - ${name}`;
    const emailText = `
New Demo Request Received

Request ID: ${demo_request_id || "N/A"}
Status: ${status || "pending"}

Contact Information:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Name: ${name}
Email: ${email}
Phone: ${phone}
${company_name ? `Company: ${company_name}` : ""}

Demo Preferences:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
${dateTimeInfo}

${notes ? `Additional Notes:\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n${notes}\n` : ""}

Submitted: ${requested_at || new Date().toISOString()}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This is an automated notification from your Leasap demo booking system.
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
    .footer { text-align: center; color: #6b7280; font-size: 12px; margin-top: 20px; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🎯 New Demo Request</h1>
      <p>Request ID: #${demo_request_id || "N/A"}</p>
    </div>
    <div class="content">
      <div class="section">
        <h2>Contact Information</h2>
        <p><span class="label">Name:</span> ${name}</p>
        <p><span class="label">Email:</span> <a href="mailto:${email}">${email}</a></p>
        <p><span class="label">Phone:</span> <a href="tel:${phone}">${phone}</a></p>
        ${company_name ? `<p><span class="label">Company:</span> ${company_name}</p>` : ""}
      </div>
      
      <div class="divider"></div>
      
      <div class="section">
        <h2>Demo Preferences</h2>
        ${preferred_date || preferred_time ? `
          <p><span class="label">Preferred Date:</span> ${preferred_date || "Not specified"}</p>
          <p><span class="label">Preferred Time:</span> ${preferred_time || "Not specified"}</p>
          ${timezone ? `<p><span class="label">Timezone:</span> ${timezone}</p>` : ""}
        ` : "<p>No preferred date/time specified</p>"}
      </div>
      
      ${notes ? `
      <div class="divider"></div>
      <div class="section">
        <h2>Additional Notes</h2>
        <p>${notes.replace(/\n/g, "<br>")}</p>
      </div>
      ` : ""}
      
      <div class="divider"></div>
      <p><span class="label">Status:</span> ${status || "pending"}</p>
      <p><span class="label">Submitted:</span> ${requested_at || new Date().toISOString()}</p>
    </div>
    <div class="footer">
      <p>This is an automated notification from your Leasap demo booking system.</p>
    </div>
  </div>
</body>
</html>
    `.trim();

    // Send email
    const mailOptions = {
      from: `Leasap Demo System <${smtpUser}>`,
      to: recipientEmail,
      replyTo: email, // Allow replying directly to the requester
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

# Test script for maintenance request endpoint
# This simulates what VAPI would send

$body = @{
    message = @{
        toolCalls = @(
            @{
                id = "test-123"
                type = "function"
                function = @{
                    name = "submitMaintenanceRequest"
                    arguments = @{
                        issue_description = "Test maintenance issue - kitchen sink leaking"
                        location = "kitchen"
                        category = "plumbing"
                        priority = "high"
                        tenant_name = "Test Tenant"
                        tenant_email = "test@example.com"
                        tenant_phone = "+14125551234"
                    }
                }
            }
        )
    }
} | ConvertTo-Json -Depth 10

Write-Host "Testing POST /submit_maintenance_request/" -ForegroundColor Cyan
Write-Host "Request Body:" -ForegroundColor Yellow
Write-Host $body
Write-Host ""

try {
    $response = Invoke-RestMethod `
        -Uri "https://leasing-copilot-mvp.onrender.com/submit_maintenance_request/" `
        -Method POST `
        -Body $body `
        -ContentType "application/json" `
        -ErrorAction Stop
    
    Write-Host "✅ Success!" -ForegroundColor Green
    Write-Host ($response | ConvertTo-Json -Depth 10)
} catch {
    Write-Host "❌ Error:" -ForegroundColor Red
    Write-Host $_.Exception.Message
    
    if ($_.ErrorDetails) {
        Write-Host "Error Details:" -ForegroundColor Yellow
        Write-Host $_.ErrorDetails.Message
    }
    
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response Body:" -ForegroundColor Yellow
        Write-Host $responseBody
    }
}


# Fires a fake Windows toast notification from "Mum" for the ScreenGuard demo.
# Run with Windows PowerShell 5.1 (WinRT types are not available in PowerShell 7):
#   powershell.exe -ExecutionPolicy Bypass -File demo\notify.ps1
# Optional: pass a delay in seconds so you can switch windows first:
#   powershell.exe -ExecutionPolicy Bypass -File demo\notify.ps1 5

param([int]$DelaySeconds = 0)

if ($DelaySeconds -gt 0) { Start-Sleep -Seconds $DelaySeconds }

[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

$xml = @"
<toast>
  <visual>
    <binding template="ToastGeneric">
      <text>Mum</text>
      <text>Your new card came: 4111 1111 1111 1111 exp 09/29. Ring me on 07700 900123 x</text>
    </binding>
  </visual>
</toast>
"@

$doc = New-Object Windows.Data.Xml.Dom.XmlDocument
$doc.LoadXml($xml)
$toast = [Windows.UI.Notifications.ToastNotification]::new($doc)

# Uses PowerShell's own app ID so no app registration is needed.
$appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)

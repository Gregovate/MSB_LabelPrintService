Option Explicit

Const TEMPLATE_PATH = "C:\MSB_LabelService\templates\QR_display_labels_2_line.lbx"
Const PRINTER_NAME  = "Brother PT-P950NW"

Dim g_called
g_called = False

Sub Log(msg)
    WScript.Echo Now & " | " & msg
End Sub

Function Printed(status, value)
    g_called = True
    Log "CALLBACK FIRED"
    Log "status = " & status
    Log "value  = " & value

    On Error Resume Next
    Log "doc.ErrorCode         = " & doc.ErrorCode
    Log "doc.Printer.ErrorCode = " & doc.Printer.ErrorCode
    Log "doc.Printer.ErrorString = " & doc.Printer.ErrorString
    On Error GoTo 0
End Function

Dim doc
Set doc = CreateObject("bpac.Document")

Log "Opening template: " & TEMPLATE_PATH
If Not doc.Open(TEMPLATE_PATH) Then
    Log "ERROR: Could not open template"
    WScript.Quit 1
End If

Log "Setting printer: " & PRINTER_NAME
If Not doc.SetPrinter(PRINTER_NAME, True) Then
    Log "ERROR: Could not set printer"
    doc.Close
    WScript.Quit 2
End If

On Error Resume Next

Log "Template media: " & doc.GetMediaName
Log "Printer media : " & doc.Printer.GetMediaName
Log "Printer ErrorCode before print: " & doc.Printer.ErrorCode
Log "Printer ErrorString before print: " & doc.Printer.ErrorString

Err.Clear
doc.SetPrintedCallback GetRef("Printed")
If Err.Number <> 0 Then
    Log "ERROR: SetPrintedCallback failed: " & Err.Description & " (" & Err.Number & ")"
    doc.Close
    WScript.Quit 3
End If

Log "Starting print..."
doc.StartPrint "", 0

Log "Sending one label..."
Dim result
result = doc.PrintOut(1, 0)
Log "PrintOut result: " & result

Log "Ending print..."
Dim endResult
endResult = doc.EndPrint
Log "EndPrint result: " & endResult

Log "Waiting 30 seconds for callback..."
Dim i
For i = 1 To 30
    If g_called Then Exit For
    WScript.Sleep 1000
Next

If Not g_called Then
    Log "NO CALLBACK RECEIVED within timeout"
    On Error Resume Next
    Log "doc.ErrorCode         = " & doc.ErrorCode
    Log "doc.Printer.ErrorCode = " & doc.Printer.ErrorCode
    Log "doc.Printer.ErrorString = " & doc.Printer.ErrorString
    On Error GoTo 0
End If

Log "Closing template..."
doc.Close

Log "Done."
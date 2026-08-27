# MSB Label Print Service — Operator Guide

**Author:** Greg Liebig / Engineering Innovations, LLC  
**Date:** 2026-03-22  
**System Version:** Label Service v3.x  

This guide explains how to operate and monitor the **Label Print Service**
running on the dedicated print server.

This is **NOT** a guide for printing labels in Directus.

For printing physical lable instructions, see:

👉 [Container & Display Label Printing SOP](https://github.com/Gregovate/MSB-Production-Database-Project/blob/main/Docs/02_Production_Database/02_Operational_SOPs/C_Container_and_Display_Label_Printing.md)

---

## 📌 Purpose of This Guide

This document is used to:

- Start the label print service if it is not running  
- Verify the service is operating correctly  
- Prevent duplicate print batches  
- Recover the system if labels are not printing  

---

## 👤 Who Should Use This Guide

This guide is intended for:

- Managers  
- Volunteers assisting with troubleshooting  
- Anyone responsible for the print server  

---

## ⚠️ Important

Most users **do not need this guide** during normal operation.

Only use this if:

- Labels are not printing  
- The system appears unresponsive  
- You are asked to check the print server  

---

## ⚠️ IMPORTANT SAFETY NOTES

### Tape Must Be Installed

The system cannot reliably detect an empty tape cartridge.

Before printing:

✔ Verify tape cartridge is installed  
✔ Verify tape width matches template (1.4")  
✔ Verify printer is powered on and online  

---

## ▶ Starting the Label Print Service (Print Server)

>The label printing system runs on a **dedicated print server machine**.
>Labels will NOT print unless this service is running.

---

### 🖥 Where This Runs

The service runs on the **Label Print Server** (separate machine).

This allows labels to be queued to print from any authenticated device at any time.

---

## ⚠ CRITICAL RULE — READ THIS FIRST

🚫 **DO NOT click "Print" multiple times in Directus**

If nothing prints immediately:

👉 **STOP and check the service first**

The system runs on a polling cycle and may take a few seconds to respond.

Repeated clicks will create **duplicate batches** and waste label tape.

---

## ▶ When You Should Start the Service

Only start the service if:

✔ Labels are not printing  
✔ The Blue service window is NOT open or in the task bar.

If the service is already running → DO NOT restart it

---

## ▶ Start Procedure

1. Go to the **Label Print Server**
2. Log in if needed
3. On the desktop, double-click:

👉 **Start Label Service** icon

---

### 🟦 Expected Result (IMPORTANT)

A window will open with:

✔ Blue background  
✔ Yellow text  
✔ Command-style appearance  

This is the **Label Print Service window**

---

### ✔ Service Ready State

Within a few seconds, you should see:

>Startup health check PASSED.

>Service READY — polling every 15 seconds.

If you see this, the system is ready.

---

## ⛔ IMPORTANT — Do NOT Close This Window

⚠ This window must remain open at all times

🚫 **DO NOT click the X (this will STOP the service)**  
✔ Use the **_ (minimize)** button instead  

If this window is closed:

❌ Label printing will STOP  
❌ The system will NOT recover automatically  

---

## 🌐 Required Browser Tabs

Open Google Chrome and make sure these are available:

- https://my.sheboyganlights.org  
- https://db.sheboyganlights.org  

---

## ✅ How to Confirm the System Is Working

Before reprinting anything, check:

✔ The blue/yellow service window is open  
✔ No error messages are shown  
✔ The system shows polling messages  

---

## ⚠ If Labels Did NOT Print

Follow this EXACT order:

1. **Wait 10–15 seconds**
   - The system may still be processing

2. **Check the service window**
   - Not open → Start it
   - Shows errors → STOP and report

3. **ONLY AFTER VERIFYING ABOVE**
   - Retry the print ONCE

🚫 Do NOT repeatedly click print

---

## ⏹ Stopping the Label Print Service (Only If Directed)

1. Click the blue service window  
2. Press:

>Ctrl + C

---

## 🚨 If There Is a Problem

If the service is running and printing still fails:

👉 Contact Greg

Do NOT continue retrying


- Initial operator guide for Label Service v3.x
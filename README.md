# EVS E-Waste Analyser — Full Project

## Architecture

```
[GitHub Pages]          [Flask Server]         [Docker n8n]
 upload/index.html  →   POST /upload       →   Webhook node
  (secure upload)        validates image        AI Agent (Grok)
                         forwards to n8n        Build HTML report
                         saves report ←─────────POST /save-report
                        /metal-prices ←─────────market data node
```

---
Download & setup:
-Docker Desktop 
-Inside Docker desktop setup n8n
-Set up ngrok for the internal pipeline

Local setup:
For Report files: D:\EVS\EVs\Reports
For Image files: D:\EVS\EVs\Images
  Remember:
    All the image what need to be sorted and need information need to be in the D:\EVS\EVs\Images folder.
All these files need to be in: D:\EVS\files (1)
<img width="358" height="607" alt="image" src="https://github.com/user-attachments/assets/0fa13ba8-4ffd-458f-a174-067e53302882" />

The GitHub index.html page needs to be deployed. 
Change the ngrok URL.
  Remember: Don't forget to add /upload at the end of the URL.
  Pause needs to be a minimum of 2s.

Run accordingly:
 1.bat
 2.bat
after getting all the iamge file on the D:\EVS\EVs\Reports folder.
  Run accordingly:
  3.bat and press enter to close.
  4.bat and press enter
  5.bat and enter
  6.bat
It'll show a dashboard.html file. From there file can be accessed on the page.
  The dashboard.html is saved in the D:\EVS\EVs\Reports folder. 


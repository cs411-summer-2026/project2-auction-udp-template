@echo off
title BidWave Auction System Launcher
echo ========================================
echo    BidWave Auction System Launcher
echo ========================================
echo.
echo Starting components...

:: Start SMTP Server (hidden window)
start "SMTP Server" /min cmd /k "python -m aiosmtpd -n -l localhost:8025"

:: Wait 2 seconds
timeout /t 2 /nobreak > nul

:: Start GUI Server
start "Auction Server" cmd /k "python auction_server.py"

:: Wait 1 second
timeout /t 1 /nobreak > nul

:: Start GUI Client 1
start "Client 1 - Bidder" cmd /k "python auction_client.py"

:: Start GUI Client 2
start "Client 2 - Bidder" cmd /k "python auction_client.py"

echo.
echo All components launched!
echo.
echo Instructions:
echo   1. In each client window, enter a bidder name (e.g., Alice, Bob)
echo   2. In the Server window, click "Start Server"
echo   3. Watch the auction in real-time!
echo   4. Type bid amounts in client windows and press Enter
echo.
echo Close all windows when done.
echo.
pause
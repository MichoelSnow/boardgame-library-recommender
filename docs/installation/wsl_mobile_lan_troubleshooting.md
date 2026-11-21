# WSL Mobile/LAN Development Troubleshooting

This is an investigation record for serving the development frontend and API
from WSL to devices on the local network. It is not a replacement for the
normal local or offline kiosk setup guides.

Investigation date: 2026-11-19

## Environment observed

- WSL version: `3.0.5.0`
- WSL kernel: `6.18.58.1-1`
- Windows version: `10.0.26200.9974`
- WSL has no user `.wslconfig` file, so it is using the default NAT networking
  mode.
- WSL `eth0`: `172.25.133.192/20`
- Windows WSL virtual adapter: `172.25.128.1/20`
- Windows Wi-Fi address: `192.168.0.58/24`
- Wi-Fi network observed: `Praise Science 2`

The `172.25.*` addresses are internal WSL/NAT addresses. Devices on the LAN
should use the Windows Wi-Fi address, currently `192.168.0.58`.

## Confirmed network findings

The frontend was listening correctly inside WSL:

```text
0.0.0.0:3000
```

Initially Windows exposed the WSL frontend only through loopback:

```text
127.0.0.1:3000 LISTEN
```

The existing Windows port-proxy table already contained the backend and an
unrelated service:

```text
0.0.0.0  8081  -> 172.25.133.192 8081
0.0.0.0  8000  -> 172.25.133.192 8000
```

There was no frontend entry. Adding this entry made the frontend reachable
through the Windows LAN address:

```powershell
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=3000 connectaddress=172.25.133.192 connectport=3000
```

Afterward, both Windows checks succeeded:

```powershell
Test-NetConnection 192.168.0.58 -Port 3000
Test-NetConnection 192.168.0.58 -Port 8000
```

The frontend returned `200 OK` and the backend returned `200 OK` when accessed
from Windows through `192.168.0.58`.

Important: the port-proxy target contains the current WSL IP. If WSL receives a
different IP after a restart, inspect the new address and update the proxy
entries.

## CORS verification

The exact frontend origin was tested against the backend:

```powershell
curl.exe -i -X OPTIONS http://192.168.0.58:8000/api/theme -H "Origin: http://192.168.0.58:3000" -H "Access-Control-Request-Method: GET" -H "Access-Control-Request-Headers: authorization,content-type"
```

The response was `HTTP/1.1 200 OK` and included:

```text
access-control-allow-origin: http://192.168.0.58:3000
access-control-allow-credentials: true
```

Therefore, LAN CORS was working after the backend was started with the LAN
frontend origin allowed.

## Frontend configuration requirement

Starting the frontend with only `HOST=0.0.0.0 npm start` left the development
fallback API URL as `http://localhost:8000/api`. On another laptop,
`localhost` refers to that laptop, not the WSL/Windows host. This caused the
guest kiosk status and login requests to fail with network errors.

For a temporary mobile/LAN development session, start the frontend with the
Windows LAN address in both API-related URLs:

```bash
HOST=0.0.0.0 REACT_APP_API_BASE_URL=http://192.168.0.58:8000/api REACT_APP_IMAGE_LOCAL_BASE_URL=http://192.168.0.58:8000/images npm start
```

Start the backend with the matching frontend origin:

```bash
CORS_ALLOWED_ORIGINS="http://192.168.0.58:3000,http://localhost:3000,http://127.0.0.1:3000" poetry run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

The frontend environment values are read when the development server starts;
restart the frontend after changing them.

## Useful diagnosis commands

From WSL:

```bash
ip -4 -o addr show
ss -ltnp | grep ':3000'
```

From PowerShell:

```powershell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' } | Format-Table InterfaceAlias,IPAddress,PrefixLength
Get-NetTCPConnection -LocalPort 3000 -State Listen
netsh interface portproxy show all
Test-NetConnection 192.168.0.58 -Port 3000
Test-NetConnection 192.168.0.58 -Port 8000
```

The backend can be checked without a browser:

```powershell
curl.exe -i http://192.168.0.58:8000/api/theme
```

## Remaining unresolved issue

After port forwarding, correct frontend API configuration, successful Windows
TCP checks, successful backend requests, and successful CORS preflight, another
laptop on the LAN could load the site and log in successfully.

The phone still could not reach either:

```text
http://192.168.0.58:3000
http://192.168.0.58:8000/api/theme
```

The phone reported a browser network error (`ERR_TOO_MANY_RETRIES`). Because
the laptop works and even the direct backend URL fails on the phone, the
remaining problem is phone/network-path specific rather than an application,
WSL, port-proxy, or CORS failure demonstrated by this investigation.

The following have not yet been established for the phone:

- its Wi-Fi IPv4 address and subnet;
- whether it is on the same non-guest SSID and subnet as `192.168.0.58`;
- whether cellular data, a VPN, private relay, or private DNS is changing its
  route;
- whether the access point applies client isolation to the phone.

The next useful check is to compare the phone's Wi-Fi IPv4 address with
`192.168.0.58/24`. If the phone is on `192.168.0.*` but still cannot reach the
backend while another laptop can, inspect router client-isolation/guest-device
settings and phone VPN/cellular routing.

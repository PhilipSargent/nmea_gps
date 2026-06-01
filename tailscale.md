# Consolidated Network Troubleshooting Logs & Marine NMEA System Profile

This document aggregates the complete technical history, system adjustments, network diagnostics, and environmental workarounds performed across multiple 
troubleshooting phases. It tracks the migration from remote SMB file sharing issues (Greece to Home NAS) to local boat network configuration (Mango OpenWrt 
Router to NMEA GPS over UDP).

---

## Part 1: Remote Windows SMB File Share Diagnostics (Tailscale Tunnel)

### 1.1 Symptoms & Error Profiles
When attempting to mount a home network share over a Tailscale VPN tunnel while connected to a restrictive public hotel network in Greece, the client 
terminal (`SnowGrey`) exhibited alternating network and authentication failures:

* **System Error 1244:** "The operation being requested was not performed because the user has not been authenticated."
* **System Error 59:** "An unexpected network error occurred."

### 1.2 Underlying Network Root Causes
1. **MTU Mismatch (Error 59):** The parent network interface (Hotel Wi-Fi) wrapped in the Tailscale VPN layer forced standard packet structures to fragment. 
Large SMB packets exceeding the adjusted Maximum Transmission Unit (MTU) size were dropped by regional transit routers.
2. **Security Policy Drops (Error 1244):** Windows 11 natively restricts unauthenticated/plain NTLM handshakes when encountering public network 
classifications to defend against credential hijacking.
3. **Subnet & Gateway Misidentification:** The target IP address `100.122.10.50` belonged to the home gateway OpenWrt router rather than the target storage 
file server itself.

### 1.3 Remediation Actions & Command Scripts

#### Step 1: Interface MTU Standardization
To resolve the physical packet fragmentation dropping the SMB connection (Error 59), the virtual Tailscale interface was throttled down to handle 
encapsulation headers cleanly:
```powershell
# Run from Administrator PowerShell
netsh interface ipv4 set subinterface "Tailscale" mtu=1280 store=active

Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\LanmanWorkstation\Parameters" -Name "AllowInsecureGuestAuth" -Value 1 -Type DWord
Part 2: Local Marine Network & UDP Data Stream Diagnosis (Mango Router)
2.1 Environmental Topology
Transitioning to an on-board vessel network, the infrastructure is completely 
localized and isolated from stable internet backbones:

Gateway / Access Point: GL.iNet Mango (GL-MT300N-V2) micro travel router running 
OpenWrt.

Internal Router Hostname: Guava

Gateway Local IP Address: 192.168.8.1

Telemetry Data Source: Mobile phone executing an unbuffered "NMEA over Network" GPS 
streaming engine.

Assigned Local IP Address: 192.168.8.146

Configured Destination Port: 30304

Target Protocol Layer: UDP Broadcast / Unicast

2.2 Deep Packet Inspection & The Physical Layer Failure
Symptom 1: Empty Kernel Connection Logs
When tracing whether the incoming NMEA telemetry packets were hitting the router, 
standard socket tools failed. Directly inspecting the Linux kernel's live state engine
 confirmed a major data gap:

Bash
root@Guava:~# grep "30304" /proc/net/nf_conntrack
Critical Insight: Because UDP is entirely stateless and connectionless, nf_conntrack 
does not expect an established multi-way handshake. However, it will display active 
inbound counters whenever a device streams data to a local interface port. A 
completely blank return meant packets were being entirely eliminated at the physical 
or data-link boundaries before ascending to the network layer stack.

Symptom 2: Severe Wireless Degradation
To assess link stability inside the vessel hull, a continuous ICMP loop back-to-back 
was initiated against the phone client:

Bash
root@Guava:~# ping 192.168.8.146
--- 192.168.8.146 ping statistics ---
41 packets transmitted, 4 packets received, 90% packet loss
round-trip min/avg/max = 89.920/623.683/2229.095 ms
Root Cause Evaluation: 90% packet loss paired with latency lag exceeding 2.2 seconds. 
Marine environments feature dense, complex boundaries (fiberglass composites, metallic
 battery arrays, aluminum bulkheads, and water tanks) that act as radio-frequency 
mirrors, inducing destructive multipath interference. Because UDP is a fire-and-forget
 protocol lacking acknowledgement mechanisms, the NMEA sentences simply evaporated 
over the air.

Part 3: Embedded OpenWrt System Quirks & Environment Handling
3.1 MediaTek Driver Nuances (Missing LuCI Submenus)
When investigating Layer-2 AP/Client Isolation to rule out client communication 
blocking, the traditional reference OpenWrt "Advanced Settings" paged tabs were 
completely missing.

Insight: The GL.iNet Mango hardware variant leverages target-specific MediaTek (ra0) 
wireless driver stacks. These drivers merge advanced configuration matrices—including 
channel allocation, isolation rules, and sideband widths—directly into the main 
General Setup viewport.

Resolution Method: To isolate and protect the weak 2.4GHz signal profile from high 
marine multipath interference, the channel width must be restricted from its default 
wide 40 MHz structure down to a concentrated 20 MHz layout, shifting the channel 
assignment lock to lower-noise channels (1 or 6).

3.2 Dropbear SSH Limitations (sftp-server Failures)
When attempting to sidestep high Git synchronization timeout metrics by executing a 
local secure folder deployment from the computer (SnowGrey), the file bridge collapsed
 instantly:

Plaintext
ash: /usr/libexec/sftp-server: not found
scp: Connection closed
Insight: Modern versions of OpenSSH (on Linux/Mac laptops) default to an SFTP engine 
backend wrapper rather than legacy RCP protocols when evaluating the scp command. The 
Mango router's native embedded SSH server (Dropbear) lacks an SFTP engine extension by
 default.

Offline Fix: Force your computer's terminal client to use the original, legacy 
pipeline explicitly by passing the -O switch:

Bash
scp -O -r ./nmea_gps root@192.168.8.1:~/nmea_gps
Online Fix: Permanently overlay an SFTP binary system handler into the Dropbear 
environment via the router's internal package manager:

Bash
opkg update && opkg install openssh-sftp-server
3.3 Architecture Compilations (Exec format error)
Evaluating localized environments directly inside synchronization targets resulted in 
architecture execution faults:

Plaintext
error: Failed to query Python interpreter
Caused by: Exec format error (os error 8)
Insight: Virtual directory patterns (.venv) capture, index, and cache binary objects 
bound explicitly to the compiling machine's processor. Attempting to run tools built 
on an Intel/AMD x86_64 or ARM64 workstation (SnowGrey) directly inside configurations 
mirroring a MIPS-based router (Guava) triggers execution architecture violations. 
Python implementations on OpenWrt nodes must exclude local .venv paths, relying 
strictly on sending raw .py scripts and utilizing native opkg runtime structures.

Part 4: Context Template for New LLM Threads
When initializing a new session to continue work on the boat's software stack, copy 
and paste this block into the prompt window:

CONTEXT: I am working on a marine/boat network using a GL.iNet Mango router running 
OpenWrt (hostname: Guava, IP: 192.168.8.1). I am attempting to stream real-time NMEA 
GPS sentences from an external mobile device (IP: 192.168.8.146) over UDP port 30304 
directly to the router. 

Diagnostic baselines established so far:
1. BusyBox netcat lacks standard server flags.
2. Kernel /proc/net/nf_conntrack shows zero entries for port 30304.
3. ICMP pinging the data source reveals extreme network degradation (90% packet loss, 
>2000ms latency spikes) due to structural hull interference and 40MHz channel 
congestion on the 2.4GHz band.
4. Laptop configuration uses native legacy scp restrictions (-O required due to 
missing openssh-sftp-server on Dropbear).

Please help me build on top of this network profile to implement [INSERT NEW GOAL 
HERE].

Once you save that on your laptop, you can easily copy **Part 4** right out of it 
whenever you open a fresh chat room!
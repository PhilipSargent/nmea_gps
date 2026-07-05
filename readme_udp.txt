Lots of trouble with poor Wi-Fi between phones and QK and the router guava.     
Reduced channel width to 20MBps improved. As did moving to Ch1 or 6 instead of 11.

Confusing: nc (netcat) (esp. on laptop WSL) drops nmea sentences after the first, but my nc.py does not and is better
for diagnosing problems.     

papaya has almost no software installed other than extroot.
Installed ncat (not netcat) 1/6/2026   using opkg.       

OK, using papaya I have it all working reliably. Ch11 and n only, no n/g, and the correct Wi-Fi name and password
(both guava and papaya now Ellin:54ellin54 )    
HOWEVER (3rd June) guava won't connect to PhilipPixel9 to get internet with N only !
So had to revert to g/n and 20/40 channel width.
BUT it is more important to actually record the data than to rsync it, so now (2026-06-03)
keeping on 11N only and 20Mbps. 
I will sync to djangotest manually via laptop - though it does connect intermittently, which is all we need.                        

Have to do this when I swap between guava & papaya:
ssh-keygen -f '/home/philip/.ssh/known_hosts' -R '192.168.8.1'                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                
Lots of trouble with poor WiFi between phones and QK and the router guava.     
Reduced channel width to 20MBps improved. As did moving to Ch1 or 6 instead of 11.

Confusing: nc (netcat) (esp. on laptop WSL) drops nmea sentences after the first, but my nc.py does not and is better
for diagnosing problems.     

papaya has almost no software installed other than extroot.
Installed ncat (not netcat) 1/6/2026   using opkg.       

OK, using papaya I have it all working reliably. Ch11 and n only, no n/g, and the correct wifi name and password
(both guava and papaya now Ellin:54ellin54 )                              

Have to do this when I swap between guava & papaya:
ssh-keygen -f '/home/philip/.ssh/known_hosts' -R '192.168.8.1'                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                
# UDFTP
Yet another reinvention of the wheel... reliable file transfer through UDP

## Why bother?

TCP is solid and reliable, sure — but at what cost??  
It sends ACKs for almost everything, slows down like crazy when packets drop, and gets super whiny on bad connections (high latency, packet loss, international routes... you name it (\*\*coughs** hostel wifi networks \*\*coughs** )).

UDP? Lightning fast, zero drama, no ACK nonsense.  
But yeah... it can just silently drop packets and pretend nothing happened. Not great if you actually want the whole file.

Here's the solution that gets the best of both worlds : 
- Blast the file super fast over UDP  
- Figure out what's missing  
- Fix the holes with TCP (because TCP is boring but trustworthy)  

## How to run this thing

1. Throw the `server.py` on a VPS with decent upload speed.  
2. Download whatever file you want to transfer onto the VPS .  
3. Turn up the heat on the server:
   ```bash
   python3 server.py
   ```
4. On your computer, run the client:
   ```bash
   python3 client.py
   ```

It should just work™ — UDP sends most of it quickly, TCP quietly cleans up the mess.

## Important stuff (aka don't blame me later)

- **Ports**: Open **5201/UDP** (data) and **5202/TCP** (repair) on your VPS firewall/security group.  
  Quick test:
  ```bash
  # On VPS
  nc -l 5202

  # From your machine
  nc -zv YOUR_VPS_IP 5202
  nc -zv YOUR_VPS_IP 5201
  ```

- **If almost nothing arrives over UDP** (like only 1–10 chunks out of thousands):  
  → Lower the speed in `server.py` — change `bPS = 40` to `bPS = 5` or `10`.  
  High loss turns the TCP repair into "just normal TCP with extra steps". Not fun.

- **File integrity**: No checksums yet. Super rare bit flips might sneak through.  
- **Security**: None. Zero. Zilch. Don't send nudes or bank details over this.

## Current status / known laziness

- No live retransmits — everything gets fixed at the end  
- Super basic rate limiting (just sleeps between packets)  
- No resume, no progress bar, no fancy stuff  
- If your connection is really trash → TCP repair might still take forever

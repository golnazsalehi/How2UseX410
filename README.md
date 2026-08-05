# How2UseX410

Notes for setting up and using the **USRP X410** from the host laptop.

Follow the steps in order — each one assumes the previous one succeeded.

---

## Step 1 — Connect the host and give it an IP

1. Connect the **QSFP-to-USB converter** between the X410's QSFP port and the laptop.
2. Power on the X410 and wait for it to finish booting.
3. From the repo folder, assign the host-side IP:

```bash
./set_ip.sh ens1f0 192.168.10.1
```

`set_ip.sh` takes two arguments:

| Argument | Meaning | Default |
| --- | --- | --- |
| 1 | Network interface name | `enp34s0` |
| 2 | Host IP address to assign | `192.168.10.1` |

The script asks for `sudo`, so it will prompt for the laptop password. It:

- flushes any existing IPs on the interface,
- assigns `192.168.10.1/24`,
- brings the interface up,
- sets the MTU to 9000 (jumbo frames — required for high-rate streaming),
- raises the socket buffer limits (`net.core.wmem_max` / `rmem_max`) to 25 MB.

If the script has never been run on this machine, make it executable first:

```bash
chmod +x set_ip.sh
```

### Finding the interface name

`ens1f0` is the name on this laptop. On a different machine, list the interfaces
and pick the one belonging to the converter:

```bash
ip -br link show
```

### Checking it worked

```bash
ip addr show ens1f0
```

You should see `inet 192.168.10.1/24`, state `UP`, and `mtu 9000`.

The X410 side of that link conventionally answers on `192.168.10.2`:

```bash
ping -c 3 192.168.10.2
```

---

## Next steps

- [ ] Confirm UHD sees the device (`uhd_find_devices`)
- [ ] Load / verify the FPGA image
- [ ] First streaming test

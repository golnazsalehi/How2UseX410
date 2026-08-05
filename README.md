# How2UseX410

Notes for setting up and using the **USRP X410** from the host laptop, in a
receive-only configuration (4 RX channels).

Follow the steps in order — each one assumes the previous one succeeded.

| File | What it is |
| --- | --- |
| `set_ip.sh` | Configures the host network interface that talks to the X410 |
| `x410_4rx.grc` | GNU Radio Companion flowgraph: 4-channel receive |
| `x410_4rx.py` | Python generated from that flowgraph (run directly) |

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

## Step 2 — Confirm UHD sees the radio

Before opening GNU Radio, check that UHD can reach the device over the link you
just configured:

```bash
uhd_find_devices --args addr=192.168.10.2
```

For a full listing of daughterboards, antennas, gain ranges, and sample rates:

```bash
uhd_usrp_probe --args addr=192.168.10.2
```

If `uhd_find_devices` finds nothing, the problem is Step 1 (wrong interface, no
IP, or the X410 still booting) — not GNU Radio.

---

## Step 3 — Receive on all 4 ports with GNU Radio

The X410 carries two daughterboards, each with two RF channels, so the front
panel gives four receive ports:

| GNU Radio channel | Subdev | Front-panel port |
| --- | --- | --- |
| 0 | `A:0` | RF0 |
| 1 | `A:1` | RF1 |
| 2 | `B:0` | RF2 |
| 3 | `B:1` | RF3 |

Connect an antenna (or cable) to each **TX/RX** port you intend to use.

### Running it

Either run the generated Python directly:

```bash
python3 x410_4rx.py
```

or open the flowgraph in GNU Radio Companion to edit it first:

```bash
gnuradio-companion x410_4rx.grc
```

A Qt window opens with four independent displays — one per channel — each
showing time, frequency, waterfall, and constellation. Channel 0's plot is
labelled with the absolute RF frequency; the other three show baseband.

### How the flowgraph is set up

Everything is done by a **single UHD: USRP Source** block. This is the important
part: you do *not* instantiate four sources. One source, four channels.

The settings that make it a 4-channel receiver:

| Field | Value | Why |
| --- | --- | --- |
| Device Address | `addr=192.168.10.2` | The X410 on the link from Step 1 |
| Num Channels | `4` | Gives the block four output ports |
| Sub Device Spec (Mb0) | `A:0 A:1 B:0 B:1` | Maps those four ports to the four RF front ends |
| Sync | `sync` (Unknown PPS) | Aligns the timebase across daughterboards |
| Start Time | `1` | Timed start, so all four channels begin on the same sample |

`Sync` and `Start Time` together are what make the four streams sample-aligned.
Without them the channels start at arbitrary offsets, which quietly ruins any
phase or delay measurement across ports.

Per-channel RF settings all reference the same variables, so changing one
variable retunes all four channels at once:

| Variable | Value in this example | Meaning |
| --- | --- | --- |
| `center_freq` | `4.0e9` | 4 GHz center on every channel |
| `samp_rate_rx` | `15.36e6` | 15.36 MS/s per channel |
| `rx_gain` | `10` | 10 dB RX gain on every channel |
| `num_samples` | `int(samp_rate_rx)*5` | 5 seconds of samples per channel |

Antenna is `TX/RX` on all four channels. `uhd_usrp_probe` lists the other
antenna names your daughterboard accepts if you need a different port.

The stream args field carries `peak=0.003906` (≈ 1/256), a scaling hint used
during conversion to `fc32`. It came with this example — leave it alone unless
you know you want different scaling.

**Sample rate choice.** 15.36 MS/s is the master clock rate divided by a clean
integer (245.76 MHz / 16). Pick rates that divide the master clock rate evenly;
otherwise UHD rounds to the nearest achievable rate and warns, and you end up
recording at a rate slightly different from the one you wrote down.

`samp_rate` (32000) and `samp_rate_tx`/`tx_gain` are leftovers from the template
and are not used anywhere in the receive path.

### Recording to disk

The flowgraph contains **Head → File Sink** chains for all four channels, but
they are **disabled**, which is why `x410_4rx.py` only shows the GUI plots. As
shipped, this flowgraph displays and records nothing.

To capture data:

1. Open `x410_4rx.grc` in GNU Radio Companion.
2. Select the four `Head` blocks and the four `File Sink` blocks and enable them
   (select the block, press `E`).
3. Regenerate / run (`F5`, then `F6`).

The `Head` blocks stop each stream after `num_samples`, so the capture is
exactly 5 seconds long and then ends on its own.

Channel-to-file mapping:

| Channel | Output file |
| --- | --- |
| 0 | `/mnt/ramdisk/uhd_ofdm_rx1.dat` |
| 1 | `/mnt/ramdisk/uhd_ofdm_rx2.dat` |
| 2 | `/mnt/ramdisk/uhd_ofdm_rx3.dat` |
| 3 | `/mnt/ramdisk/uhd_ofdm_rx4.dat` |

Note the off-by-one: channel `N` writes `rx(N+1).dat`.

**`/mnt/ramdisk` must exist before you run**, or the flowgraph errors out
immediately. It is a RAM-backed filesystem, used because a spinning disk or a
slow SSD cannot keep up and you get overflows (`O` characters in the console).

```bash
sudo mkdir -p /mnt/ramdisk
sudo mount -t tmpfs -o size=8G tmpfs /mnt/ramdisk
```

Size it generously. At 15.36 MS/s, `fc32` is 8 bytes per sample, so a 5-second
capture is **614 MB per channel, ~2.5 GB for all four**. RAM disks vanish on
reboot — copy captures to permanent storage before shutting down.

### Data format

File sinks write raw interleaved 32-bit floats (I, Q, I, Q, …) with no header —
i.e. `complex64`.

```python
import numpy as np
x = np.fromfile('/mnt/ramdisk/uhd_ofdm_rx1.dat', dtype=np.complex64)
```

```matlab
f = fopen('/mnt/ramdisk/uhd_ofdm_rx1.dat', 'rb');
raw = fread(f, Inf, 'float32');
fclose(f);
x = raw(1:2:end) + 1j*raw(2:2:end);
```

### Throughput sanity check

Four channels at 15.36 MS/s is about **2 Gbps on the wire** (UHD's default
over-the-wire format is `sc16`, 4 bytes per sample) — comfortable for the link,
but only with the MTU 9000 and socket buffer settings that `set_ip.sh` applies.
If you see `O` (overflow) printed in the terminal, the host is not keeping up:
lower the sample rate, close the GUI sinks, or check that Step 1 actually ran.

---

## Next steps

- [ ] Two-radio / external-clock synchronization
- [ ] Post-processing scripts for the captured `.dat` files

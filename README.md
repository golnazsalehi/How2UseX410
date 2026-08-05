# How2UseX410

Notes for setting up and using the **USRP X410** from the host laptop, in a
receive-only configuration (4 RX channels), plus the **PlutoSDR+** used as the
transmit side.

Steps 1–3 cover the X410 and run in order — each assumes the previous one
succeeded. The Pluto+ section is independent of them.

| File | What it is |
| --- | --- |
| `set_ip.sh` | Configures the host network interface that talks to the X410 |
| `x410_4rx.grc` | GNU Radio Companion flowgraph: 4-channel receive |
| `x410_4rx.py` | Python generated from that flowgraph (run directly) |
| `pluto+_Tx.py` | PlutoSDR+ transmitter: continuous tone on both TX channels |

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

### What the blocks do

A GNU Radio flowgraph is a set of **blocks** joined by arrows. Samples flow
along the arrows, left to right, continuously while the flowgraph runs. A block
with no input is a **source** (it produces samples); a block with no output is a
**sink** (it consumes them). Everything in between transforms or passes them
along.

This flowgraph uses four block types:

**UHD: USRP Source** — the source. It talks to the radio over the network link
from Step 1 and pushes the received samples into the flowgraph. All the RF
settings (frequency, gain, sample rate, antenna) live here, because this is the
only block that knows about hardware. With `Num Channels = 4` it has four
output ports, one per RF port, each carrying its own independent stream.

**QT GUI Sink** — a display. It takes a stream of samples and draws it in a Qt
window: time domain, frequency spectrum, waterfall, and constellation, all in
one widget. It is *only* for looking at the signal — samples that go into it are
plotted and thrown away. Nothing is saved. There are four of them here, one per
channel, which is why you get four sets of plots.

**Head** — a passthrough with a counter. It copies the first `num_items`
samples straight through, then stops producing anything. It changes nothing
about the data; its job is to *end* the capture. When every Head in the
flowgraph has hit its limit, the flowgraph shuts down on its own. Without a
Head, a recording runs until you press Ctrl-C and the output file grows until
the disk fills.

**File Sink** — writes whatever reaches it straight to a file on disk, raw, with
no header and no metadata. What it writes is exactly the sample format of the
stream (here `complex64`), which is why you have to know the format yourself
when reading the file back.

**How they connect.** A single output port can feed several blocks at once —
GNU Radio duplicates the stream. Each channel here fans out two ways:

```
                        ┌─► QT GUI Sink          (watch it live)
USRP Source ch N ───────┤
                        └─► Head ─► File Sink    (record N samples to disk)
```

So the plots and the recording see the identical samples; watching costs you
nothing in the recorded data.

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

## PlutoSDR+ — the transmit side

The **Pluto+** is a clone of the ADALM-PLUTO with two TX and two RX SMA
connectors and an RJ45 port. `pluto+_Tx.py` uses it as a signal generator:
a continuous tone out of both transmitters, to feed the X410's receivers.

It runs stock PlutoSDR firmware, so it identifies itself as an ordinary
ADALM-PLUTO. Don't use the model string to tell them apart — check
`hw_model_variant` instead (see "Confirming it is 2T2R" below).

### Installing the host software

The Pluto is driven through **libiio** (the C library that talks to the
hardware) and **pyadi-iio** (`import adi`, the Python layer on top of it).

#### Linux / Ubuntu

```bash
sudo apt install libiio-utils libiio-dev python3-libiio
pip3 install pyadi-iio
```

#### macOS

There is no Homebrew formula for libiio, so it has to be built from source.
Build dependencies first:

```bash
brew install cmake pkg-config libusb
```

Then build libiio. Use the tag that matches the `pylibiio` version pip will
install (v0.25 below), or the Python bindings and the library disagree:

```bash
git clone --depth 1 --branch v0.25 https://github.com/analogdevicesinc/libiio.git
cd libiio && mkdir build && cd build
cmake .. \
  -DCMAKE_INSTALL_PREFIX=/usr/local \
  -DOSX_FRAMEWORK=OFF \
  -DWITH_TESTS=ON -DWITH_DOC=OFF \
  -DWITH_USB_BACKEND=ON -DWITH_NETWORK_BACKEND=ON \
  -DWITH_SERIAL_BACKEND=OFF -DENABLE_PACKAGING=OFF
make -j$(sysctl -n hw.ncpu)
make install
```

`OSX_FRAMEWORK=OFF` matters: the default builds a `.framework` bundle, and the
Python bindings look for a plain `libiio.dylib`. No `sudo` is needed if
Homebrew already owns `/usr/local`.

The installed command-line tools have a broken rpath and won't find the library
they just linked against. Patch them once:

```bash
for b in /usr/local/bin/iio_*; do install_name_tool -add_rpath /usr/local/lib "$b"; done
```

Finally the Python side, in its own virtualenv:

```bash
python3 -m venv ~/.venvs/pluto
~/.venvs/pluto/bin/pip install numpy pyadi-iio
```

### Confirming it is connected

```bash
iio_info -S
```

Expected — the trailing `[usb:20.1.5]` is the URI the script needs:

```
Available contexts:
	0: 0456:b673 (Analog Devices Inc. PlutoSDR (ADALM-PLUTO)), serial=1040...23 [usb:20.1.5]
```

Nothing listed means the board is not enumerating: check the USB cable, or on
Ethernet check that the host can reach the Pluto's IP.

### Confirming it is 2T2R

A stock ADALM-PLUTO has one TX; the Pluto+ has two. The device itself will tell
you which you have:

```bash
iio_attr -u usb:20.1.5 -C hw_model_variant
```

`1` means the AD9363 is unlocked to AD9361 2T2R and TX2 exists. `0` means a
single-channel radio, and the two-channel script below cannot work on it.

Pass the URI explicitly. Without `-u`, these tools default to the *local*
backend, which does not exist on macOS — you get
`Unable to create Local IIO context : Function not implemented (78)`, which
looks like a device failure but is only a missing argument.

To see the channels directly, `iio_info -u usb:20.1.5` should list four TX scan
channels (`voltage0`–`voltage3`, i.e. two I/Q pairs) under
`cf-ad9361-dds-core-lpc`.

### Running the transmitter

```bash
~/.venvs/pluto/bin/python pluto+_Tx.py
```

It prints its configuration, starts transmitting, and keeps going until you
press **Ctrl-C**, which destroys the TX buffer and stops the carrier:

```
Connecting to    : usb:20.1.5
TX LO          : 2482.000 MHz  (shared by TX1 and TX2)
Sample rate    : 1.000 Msps
Buffer         : 16384 samples (16.384 ms), bin spacing 61.04 Hz
Tone type      : complex exponential
  TX1: attenuation -10 dB
        offset +100,000 Hz -> +99,975.59 Hz  (RF 2482.099976 MHz)
  TX2: attenuation -10 dB
        offset +100,000 Hz -> +99,975.59 Hz  (RF 2482.099976 MHz)

Transmitting on TX1 and TX2. Ctrl-C to stop.
```

### What `pluto+_Tx.py` does

Every knob is a variable at the top of the file:

| Variable | Default | Meaning |
| --- | --- | --- |
| `pluto_uri` | `""` | `""` auto-detects over USB. Set `"ip:172.19.222.191"` for Ethernet. |
| `center_freq` | `2482e6` | TX LO. **Shared by both channels** — see below. |
| `sample_rate` | `1e6` | 1 Msps. Also sets the tone's usable range, ±500 kHz. |
| `buffer_size` | `2**14` | Length of the repeating buffer; sets frequency resolution. |
| `real_tone` | `False` | `False` = complex exponential, one line at LO+offset. `True` = real cosine, lines at LO±offset. |
| `tone_offsets_ch0/1` | `[100_000]` | Baseband offsets per channel. Identical lists = same sine out of both. Add entries for multi-tone. |
| `tx_gain_ch0/1` | `-10` | **Attenuation** in dB, not gain. |

**One radio object, two channels.** `adi.ad9361` is the 2×2 class;
`adi.Pluto` is single-channel and cannot reach TX2. Enabling both is
`tx_enabled_channels = [0, 1]`, and the transmit call takes a *list* — one
array per channel, both the same length:

```python
sdr.tx([signal_ch0, signal_ch1])
```

**Both channels share one LO.** The AD9361 has a single TX synthesizer, so
TX1 and TX2 are always at the same center frequency. `center_freq` moves both
together and there is no per-channel equivalent. To separate the two outputs in
frequency, give them different baseband offsets — e.g. `[100_000]` and
`[250_000]` puts them 150 kHz apart around the same carrier.

**The buffer is cyclic.** `tx_cyclic_buffer = True` means `sdr.tx()` is called
**once** and the hardware repeats that buffer forever, giving gap-free CW. (The
alternative, re-sending in a Python loop, leaves a gap between every burst.)

**Tones are snapped to the buffer's FFT bins.** This is the non-obvious part. A
cyclic buffer must hold a whole number of cycles, or every wrap is a phase
discontinuity that smears the tone across the spectrum:

| | peak-to-leakage ratio |
| --- | --- |
| snapped to a bin (integer cycles) | 5.8 × 10⁸ |
| raw 100 kHz (1638.4 cycles) | 1.5 |

The cost is that you get the *nearest* achievable frequency — 99,975.59 Hz
instead of 100,000 Hz, with 16384 samples at 1 Msps. The script prints the
actual value. For exact round numbers, pick a buffer size that divides evenly:
`buffer_size = 10_000` makes 100 kHz exactly 1000 cycles.

**Amplitude.** Waveforms are normalized to their peak and scaled by
`2**14 * 0.9`, the range pyadi-iio expects before packing into the int16 TX
buffer. The normalize step is what keeps multi-tone sums from clipping.

### Verifying the tone without a spectrum analyzer

The AD9361 can loop its transmitter back into its receiver digitally, which
proves the waveform reaches the DAC path:

```python
sdr.loopback = 1        # 1 = digital TX->RX, 0 = off
```

Transmit different offsets per channel, receive, and FFT. Measured on this
setup, with TX1 at 100 kHz and TX2 at 250 kHz:

| | expected | measured | error |
| --- | --- | --- | --- |
| TX1 → RX1 | +99,975.59 Hz | +99,975.6 Hz | 0.0 Hz |
| TX2 → RX2 | +250,000.00 Hz | +250,000.0 Hz | 0.0 Hz |

Set `sdr.loopback = 0` afterwards. Note the limit: this exercises the digital
path, **not** the RF output at the SMA connectors. For that you need a cable
into an RX port or a spectrum analyzer.

### Gotchas

- **TX "gain" is attenuation.** `tx_hardwaregain_chanN` runs from `0` (full
  power) down to `-89.75`. Setting it to 0 is the loudest the radio goes, not
  the quietest.
- **Don't put a tone at 0 Hz offset.** LO leakage sits exactly at the carrier
  and will swamp it. Offset by a few tens of kHz at least.
- **The two outputs are frequency-coherent but not phase-calibrated.** They
  share an LO and sample clock so they won't drift apart, but the fixed phase
  and amplitude mismatch between the analog paths is not zero and can change
  across retunes. Measure it with a cabled loopback before relying on it.
- **`|offset| < sample_rate/2`.** The script raises `ValueError` rather than
  aliasing silently.
- **2482 MHz is in the 2.4 GHz ISM band**, so ambient WiFi and Bluetooth land
  in the same recordings.

---

## Next steps

- [ ] Two-radio / external-clock synchronization
- [ ] Post-processing scripts for the captured `.dat` files

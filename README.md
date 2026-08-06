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

Two radios sit on the transmit side of this setup, and `pluto+_Tx.py` drives
either one:

| | Serial | Silicon | TX | LO range | Firmware |
| --- | --- | --- | --- | --- | --- |
| **Pluto+** | `1040004a9e95...49ff3` | Rev.C AD9363A | 2 | 325 MHz – 3.8 GHz | vendor Pluto+ build, v0.33 |
| **stock Pluto** | `1044730a1997...7b229e` | Rev.B AD9364 | 1 | 46.875 MHz – 6 GHz | **SparSDR**, v0.33 |

The **Pluto+** is a clone of the ADALM-PLUTO with two TX and two RX SMA
connectors and an RJ45 port. Both boards identify themselves over USB as an
ordinary "PlutoSDR (ADALM-PLUTO)", so see
[Telling a Pluto+ from a stock Pluto](#telling-a-pluto-from-a-stock-pluto)
before assuming which is which.

The stock Pluto runs **SparSDR** firmware — a custom FPGA bitstream, not a
stock ADI image. Its transmit path is intact and this script drives it
normally, but **do not reflash that board**: an ADI `.frm` will wipe SparSDR
and you cannot get it back from one.

### The script

`pluto+_Tx.py` is a continuous-tone generator. It builds one period of a tone
in numpy, hands it to the radio as a **cyclic buffer**, and the hardware
repeats that buffer forever — gap-free CW with no per-sample work from the
host.

**What it sends, with the defaults in the file:**

| | |
| --- | --- |
| TX LO | 2.450 GHz |
| Baseband tone | +1 MHz, complex exponential (single sideband) |
| **Emitted carrier** | **2.451000000 GHz exactly** |
| Sample rate | 5 Msps |
| Buffer | 10 000 samples (2.000 ms), 500 Hz bins |
| Attenuation | −10 dB |
| Active port | TX1 only — TX2 is disabled *and* muted to −89.75 dB |

The tone lands on an exact round number because 5 Msps / 10 000 samples gives
500 Hz bins, and 1 MHz is 2000 whole cycles of that buffer. See
[Tones are snapped to the buffer's FFT bins](#what-pluto_txpy-does) for why that
matters.

On a spectrum analyzer you will see **three** lines, not one: the tone at
2.451 GHz, LO feedthrough at 2.450 GHz (−30 to −40 dBc), and the I/Q image at
2.449 GHz (−35 to −45 dBc). That is normal and is why the tone is offset from
the LO in the first place.

**The carrier is bound to the process lifetime.** `tx_destroy_buffer()` runs in
the `finally` block, so the tone stops on Ctrl-C, on closing the terminal, on
unplugging USB, and on the laptop going to sleep. The buffer lives on the host
side of the link — no host, no carrier. For a standalone transmitter that
survives losing the host you need the AD9361's internal DDS instead, which is a
different mechanism entirely.

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

Expected, with both boards attached — note the **serial**, which is what the
script selects on. The trailing `[usb:…]` URI is informational and will change
between runs:

```
Available contexts:
	0: 0456:b673 (Analog Devices Inc. PlutoSDR (ADALM-PLUTO)), serial=1044730a1997...7b229e [usb:20.11.5]
	1: 0456:b673 (Analog Devices Inc. PlutoSDR (ADALM-PLUTO)), serial=1040004a9e95...49ff3 [usb:20.2.5]
```

Nothing listed means the board is not enumerating: check the USB cable, or on
Ethernet check that the host can reach the Pluto's IP.

Pass the URI explicitly to these tools. Without `-u`, they default to the
*local* backend, which does not exist on macOS — you get
`Unable to create Local IIO context : Function not implemented (78)`, which
looks like a device failure but is only a missing argument.

### Telling a Pluto+ from a stock Pluto

**Count the TX channels.** Do not trust `hw_model_variant` or the model string:
on the two boards in this lab, *both* report `hw_model_variant = 1`, and both
identify as "PlutoSDR (ADALM-PLUTO)" over USB, yet only one has two
transmitters.

This lists every attached radio with its transmitter count and serial:

```bash
~/.venvs/pluto/bin/python -c "
import iio
for u, d in sorted(iio.scan_contexts().items()):
    c = iio.Context(u); dds = c.find_device('cf-ad9361-dds-core-lpc')
    n = len([x for x in dds.channels if x.output and x.scan_element]) // 2
    print(f'{u}  {n} TX  {c.attrs[\"hw_model\"]}  serial={c.attrs[\"hw_serial\"]}')
"
```

Output with both boards attached:

```
usb:20.11.5  1 TX  Analog Devices PlutoSDR Rev.B (Z7010-AD9364)  serial=1044730a1997...7b229e
usb:20.2.5   2 TX  Analog Devices PlutoSDR Rev.C (Z7010-AD9363A) serial=1040004a9e95...49ff3
```

`pluto+_Tx.py --list` prints the same thing with the alias appended, and is the
easier way to get it.

Measured here:

| Serial | Model | TX/RX | Which |
| --- | --- | --- | --- |
| `1040004a9e95...49ff3` | Rev.C Z7010-AD9363A | 2 TX / 2 RX | **Pluto+** |
| `1044730a1997...7b229e` | Rev.B Z7010-AD9364 | 1 TX / 1 RX | stock Pluto |

The giveaway in the model string is the transceiver part, not the revision:
the **AD9364 is 1T1R silicon** and can never do two channels, while the
AD9363A can be unlocked to AD9361 2T2R.

### Select by serial, never by URI

USB URIs are assigned by enumeration order and **move on their own**. The
Pluto+ went from `usb:20.1.5` to `usb:20.2.5` the moment the stock Pluto was
attached, and the stock Pluto was later observed moving from `usb:20.7.5` to
`usb:20.11.5` with nothing unplugged at all. A script that grabs "the first
context" will transmit from the wrong radio, or fail with a channel error.

`pluto+_Tx.py` therefore selects by serial, and accepts two short aliases so
you never have to paste one:

| Alias | Board |
| --- | --- |
| `pluto+` | the Pluto+, 2 TX |
| `pluto` | the stock Pluto, 1 TX |

If no serial is given and more than one radio is present, the script raises
rather than guessing.

### How to connect the radios

1. **USB.** Each board takes its own USB cable to the laptop. A Pluto requests
   a full **500 mA**, so give each one a direct port where you can. Both boards
   behind one bus-powered hub is the common cause of a board that powers up but
   never enumerates. Use a *powered* hub if you are short of ports.
2. **Cables matter.** Charge-only micro-USB cables look identical to data
   cables and are the single most common Pluto failure. If a board does not
   appear in `--list`, swap the cable before anything else.
3. **The Pluto+ has two micro-USB ports** — one power-only, one data. A data
   cable in the power port gives you LEDs and silence.
4. **Terminate every TX port you enable.** Put a 50 Ω load, an attenuator, or
   an antenna on TX1 of each board before transmitting. Never transmit into an
   open SMA.
5. **Feeding the X410**, run coax from each Pluto's TX1 into an X410 RF port
   through an attenuator. Both boards land near 2.451 GHz and will interfere
   with each other over the air, so cable them in rather than radiating.

Confirm both are visible before you start:

```bash
cd ~/Desktop/How2UseX410 && ~/.venvs/pluto/bin/python pluto+_Tx.py --list
```

```
usb:20.11.5      1 TX  serial=1044730a1997000220002200b12f7b229e  pluto
usb:20.2.5       2 TX  serial=1040004a9e95000ceaff17006e36049ff3  pluto+
```

### Running the transmitters

One command per board. **Each blocks until Ctrl-C, so they need separate
terminal windows** — pasting both into one terminal means the second never
starts until you kill the first, and killing the first stops its carrier. You
would never have both transmitting.

**Terminal 1 — the stock Pluto** (1 TX, SparSDR board):

```bash
cd ~/Desktop/How2UseX410 && ~/.venvs/pluto/bin/python pluto+_Tx.py -s pluto --tx 1
```

**Terminal 2 — the Pluto+** (2 TX, uses TX1 only and mutes TX2):

```bash
cd ~/Desktop/How2UseX410 && ~/.venvs/pluto/bin/python pluto+_Tx.py -s pluto+ --tx 1
```

Each prints its configuration and then transmits until **Ctrl-C**, which
destroys the TX buffer and stops the carrier:

```
Connecting to    : usb:20.2.5
Radio          : 2 TX  -> ad9361
TX LO          : 2450.000 MHz
Sample rate    : 5.000 Msps
Buffer         : 10000 samples (2.000 ms), bin spacing 500.00 Hz
Tone type      : complex exponential
  TX1: attenuation -10 dB
        offset +1,000,000 Hz -> +1,000,000.00 Hz  (RF 2451.000000 MHz)
  TX2: muted (-89.75 dB), channel disabled

Transmitting on TX1 only. Ctrl-C to stop.
```

Asking for `--tx 2` on the stock Pluto raises a clear error rather than a
confusing channel fault — the AD9364 is 1T1R silicon and has no TX2.

For a long unattended run, stop the laptop sleeping — sleep kills the carrier:

```bash
caffeinate -i ~/.venvs/pluto/bin/python pluto+_Tx.py -s pluto+ --tx 1
```

If the second process throws `PermissionError: Unable to claim interface`, that
is a stale USB handle rather than a hardware fault. Retry.

### Command-line flags

Everything in the Parameters block at the top of the file is a default; flags
override it, so one file drives both radios without editing.

| Flag | Meaning |
| --- | --- |
| `-l`, `--list` | List attached radios with TX count, serial and alias, then exit |
| `-s`, `--serial` | Serial, or the alias `pluto+` / `pluto` |
| `-u`, `--uri` | Explicit URI, e.g. `ip:192.168.2.1`. Overrides `--serial` |
| `--tx {1,2}` | Which TX connector transmits |
| `-f`, `--freq` | TX LO in Hz, e.g. `2.45e9` |
| `-t`, `--tone` | Baseband offset in Hz, e.g. `1e6` |
| `-r`, `--rate` | Sample rate in Sps |
| `-b`, `--buffer` | Cyclic buffer length in samples |
| `-g`, `--gain` | TX attenuation in dB (`0` = loudest, `-89.75` = quietest) |
| `--real` | Real cosine: lines at LO ± offset instead of one at LO + offset |

Running with no flags is the same as `-s pluto+ --tx 1` at the file's defaults.

### What `pluto+_Tx.py` does

Every knob is a variable at the top of the file, and each has a matching flag:

| Variable | Default | Meaning |
| --- | --- | --- |
| `pluto_serial` | Pluto+ serial | Which radio to use. Survives replugging; URIs do not. |
| `pluto_uri` | `""` | Override. Non-empty wins over `pluto_serial` — e.g. `"ip:172.19.222.191"` for Ethernet. |
| `tx_channel` | `1` | Which TX connector transmits. The other chain is disabled *and* muted. |
| `center_freq` | `2450e6` | TX LO. **Shared by both channels** — see below. |
| `sample_rate` | `5e6` | 5 Msps. Also sets the tone's usable range, ±2.5 MHz. |
| `buffer_size` | `10_000` | Length of the repeating buffer; sets frequency resolution. |
| `real_tone` | `False` | `False` = complex exponential, one line at LO+offset. `True` = real cosine, lines at LO±offset. |
| `tone_offsets_ch0/1` | `[1_000_000]` | Baseband offsets per channel. Add entries for multi-tone. |
| `tx_gain_ch0/1` | `-10` | **Attenuation** in dB, not gain. |
| `MUTE_DB` | `-89.75` | Most attenuation the AD9361 accepts; used to silence the idle chain. |

**The radio class is chosen by measured channel count.** `adi.ad9361` is the
2×2 class; `adi.Pluto` is single-channel and lacks `tx_hardwaregain_chan1`.
The script counts I/Q scan-element pairs on the DDS device and picks:

```python
sdr = adi.ad9361(uri) if n_tx >= 2 else adi.Pluto(uri)
```

This is why the same file works on both boards. It does **not** use the model
string or `hw_model_variant`, neither of which distinguishes them.

**One channel at a time.** `tx_enabled_channels = [chan]` enables just the
selected chain, and the transmit call takes a single array, not a list:

```python
sdr.tx(signal)
```

Disabling a channel stops its datapath but leaves the analog chain powered, so
the idle chain is *also* pinned to `MUTE_DB`. Both steps are needed to keep TX2
from leaking a copy of the carrier.

**Both channels share one LO.** The AD9361 has a single TX synthesizer, so
TX1 and TX2 are always at the same center frequency. `center_freq` moves both
together and there is no per-channel equivalent. To separate two outputs in
frequency, give them different baseband offsets.

**The buffer is cyclic.** `tx_cyclic_buffer = True` means `sdr.tx()` is called
**once** and the hardware repeats that buffer forever, giving gap-free CW. (The
alternative, re-sending in a Python loop, leaves a gap between every burst.)

**Tones are snapped to the buffer's FFT bins.** This is the non-obvious part. A
cyclic buffer must hold a whole number of cycles, or every wrap is a phase
discontinuity that smears the tone across the spectrum:

| | peak-to-leakage ratio |
| --- | --- |
| snapped to a bin (integer cycles) | 5.8 × 10⁸ |
| not snapped (fractional cycles) | 1.5 |

The cost is that you get the *nearest* achievable frequency, and the script
prints the actual value. Choose `sample_rate` and `buffer_size` together so the
tone divides evenly:

| Rate | Buffer | Bin | 1 MHz tone |
| --- | --- | --- | --- |
| 5 Msps | 10 000 | 500 Hz | 2000 cycles — **exact** |
| 5 Msps | `2**14` | 305.18 Hz | snaps to 1,000,061 Hz |
| 1 Msps | `2**14` | 61.04 Hz | rejected: offset ≥ rate/2 |

The `|offset| < sample_rate/2` check raises `ValueError` rather than aliasing
silently, which is why a 1 MHz tone needs at least 2 Msps.

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
- **The two outputs of one board are frequency-coherent but not
  phase-calibrated.** TX1 and TX2 share an LO and sample clock so they won't
  drift apart, but the fixed phase and amplitude mismatch between the analog
  paths is not zero and can change across retunes. Measure it with a cabled
  loopback before relying on it.
- **The two *boards* are not on the same frequency.** They have independent
  crystals, and the Pluto+'s `xo_correction` is still the uncalibrated default
  `40000000` while the stock Pluto is measured at `39999770` (5.75 ppm low). A
  stock Pluto XO is ±25 ppm, which at 2.45 GHz is up to **±61 kHz**. Expect the
  two carriers tens of kHz apart, drifting as the boards warm up. Calibrate
  `xo_correction` in `config.txt` if you need them co-frequency.
- **`|offset| < sample_rate/2`.** The script raises `ValueError` rather than
  aliasing silently.
- **The carrier dies with the process.** Ctrl-C, closing the terminal,
  unplugging USB, or the laptop sleeping all stop it. Use `caffeinate -i` for
  long runs.
- **2.45 GHz is in the 2.4 GHz ISM band**, so ambient WiFi and Bluetooth land
  in the same recordings — and a CW carrier there will disrupt nearby WiFi and
  BLE. Keep it cabled and attenuated unless you are in a chamber.
- **Do not reflash the stock Pluto.** It carries SparSDR; an ADI `.frm` will
  destroy that bitstream.

---

## Next steps

- [ ] Two-radio / external-clock synchronization
- [ ] Post-processing scripts for the captured `.dat` files

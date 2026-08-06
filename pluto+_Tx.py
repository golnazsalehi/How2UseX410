import argparse
import numpy as np
import adi
import iio
import time

# ===========================
# Parameters
# ===========================
# Which radio to use. Pick by SERIAL, not by URI: USB URIs like "usb:20.1.5"
# are assigned by enumeration order and shift as soon as you replug a cable or
# attach a second board. Serials never move.
#   1040004a9e95000ceaff17006e36049ff3  Pluto+       Rev.C AD9363A   2 TX / 2 RX
#   1044730a1997000220002200b12f7b229e  stock Pluto  Rev.B AD9364    1 TX / 1 RX
# Run `iio_info -S` to list what is attached.
pluto_serial = "1040004a9e95000ceaff17006e36049ff3"   ## the Pluto+ (2 TX)

# pluto_uri = "ip:172.19.222.191"   ## Ethernet connection (sysnet internal)
pluto_uri = ""                      ## non-empty overrides pluto_serial

# Which TX connector transmits: 1 or 2. Only this chain is enabled; the other
# is left out of tx_enabled_channels AND pinned to full attenuation, so it
# cannot leak a copy of the carrier. The stock Pluto only has TX1.
tx_channel = 1
center_freq = 2450_000_000      # 2.45 GHz -- TX LO. SHARED by both channels:
                                # the AD9361 has one TX LO, so TX1 and TX2 are
                                # always at the same center frequency.
sample_rate = 5_000_000         # 5 Msps -- must exceed 2*|offset|, so a 1 MHz
                                # tone needs at least 2 Msps. 5 leaves margin.
buffer_size = 10_000            # one period of the cyclic buffer. Chosen with
                                # the sample rate so the tone lands exactly on a
                                # bin: 5 Msps / 10000 = 500 Hz bins, and 1 MHz is
                                # 2000 whole cycles. (2**14 would give 305.18 Hz
                                # bins, and 1 MHz would snap to 1,000,061 Hz.)
real_tone = False               # False: complex exponential -> one line at LO+offset
                                # True:  real cosine        -> lines at LO±offset

# Baseband tone offsets in Hz, per channel, relative to the LO.
# One entry = single tone; add more for multi-tone on that channel.
# Identical lists = the same sine out of both connectors.
# Must satisfy |offset| < sample_rate/2. Avoid 0 Hz: LO leakage sits there.
tone_offsets_ch0 = [1_000_000]
tone_offsets_ch1 = [1_000_000]

# TX "gain" is ATTENUATION in dB: 0 = full power, -89.75 = minimum.
# Less negative = louder.
tx_gain_ch0 = -10
tx_gain_ch1 = -10

MUTE_DB = -89.75                # the most attenuation the AD9361 accepts

# ===========================
# Command line overrides
# ===========================
# Everything above is a default. Flags let you drive both radios from one file
# without editing it -- run two processes, one per board.
#
#   python3 pluto+_Tx.py --list
#   python3 pluto+_Tx.py -s pluto+ --tx 1
#   python3 pluto+_Tx.py -s pluto  --tx 1 -t 2e6

KNOWN = {
    "pluto+": "1040004a9e95000ceaff17006e36049ff3",   # Rev.C AD9363A, 2 TX
    "pluto":  "1044730a1997000220002200b12f7b229e",   # Rev.B AD9364,  1 TX
}


def tx_count(uri):
    """How many transmitters this board actually has.

    Counts I/Q scan-element pairs on the DDS device. This is the only
    trustworthy discriminator: both boards in this lab report
    hw_model_variant = 1 and both identify as "PlutoSDR (ADALM-PLUTO)".
    """
    ctx = iio.Context(uri)
    dds = ctx.find_device("cf-ad9361-dds-core-lpc")
    return len([c for c in dds.channels if c.output and c.scan_element]) // 2


_p = argparse.ArgumentParser(description="PlutoSDR continuous-tone transmitter")
_p.add_argument("-s", "--serial", help="serial, or the alias 'pluto+' / 'pluto'")
_p.add_argument("-u", "--uri", help="explicit URI, e.g. ip:192.168.2.1 (overrides --serial)")
_p.add_argument("--tx", type=int, choices=(1, 2), help="which TX connector")
_p.add_argument("-f", "--freq", type=float, help="TX LO in Hz, e.g. 2.45e9")
_p.add_argument("-t", "--tone", type=float, help="baseband offset in Hz, e.g. 1e6")
_p.add_argument("-r", "--rate", type=float, help="sample rate in Sps")
_p.add_argument("-b", "--buffer", type=int, help="cyclic buffer length in samples")
_p.add_argument("-g", "--gain", type=float, help="TX attenuation in dB (0 = loudest)")
_p.add_argument("--real", action="store_true", help="real cosine: lines at LO±offset")
_p.add_argument("-l", "--list", action="store_true", help="list attached radios and exit")
_a = _p.parse_args()

if _a.list:
    found = sorted(iio.scan_contexts().items())
    if not found:
        raise SystemExit("No PlutoSDR attached.")
    for _u, _d in found:
        _serial = iio.Context(_u).attrs["hw_serial"]
        _alias = next((k for k, v in KNOWN.items() if v == _serial), "")
        print(f"{_u:16} {tx_count(_u)} TX  serial={_serial}  {_alias}")
    raise SystemExit(0)

if _a.serial:
    pluto_serial = KNOWN.get(_a.serial.lower(), _a.serial)
if _a.uri:
    pluto_uri = _a.uri
if _a.tx:
    tx_channel = _a.tx
if _a.freq:
    center_freq = int(_a.freq)
if _a.rate:
    sample_rate = int(_a.rate)
if _a.buffer:
    buffer_size = _a.buffer
if _a.tone is not None:
    tone_offsets_ch0 = tone_offsets_ch1 = [int(_a.tone)]
if _a.gain is not None:
    tx_gain_ch0 = tx_gain_ch1 = _a.gain
if _a.real:
    real_tone = True

# ===========================
# Generate the tone(s)
# ===========================
# A cyclic buffer repeats forever in hardware, so the waveform must contain a
# whole number of cycles -- otherwise every wrap is a phase jump, which smears
# the tone across the spectrum. Snapping each tone to the nearest FFT bin of the
# buffer guarantees that.
bin_spacing = sample_rate / buffer_size


def build_tone(offsets):
    n = np.arange(buffer_size)
    waveform = np.zeros(buffer_size, dtype=np.complex128)
    actual = []

    for offset in offsets:
        if abs(offset) >= sample_rate / 2:
            raise ValueError(
                f"Tone offset {offset} Hz is outside ±{sample_rate/2:.0f} Hz "
                f"(half the sample rate)."
            )

        k = int(round(offset / bin_spacing))       # nearest whole number of cycles
        actual.append(k * bin_spacing)

        if real_tone:
            waveform += np.cos(2 * np.pi * k * n / buffer_size)
        else:
            waveform += np.exp(2j * np.pi * k * n / buffer_size)

    # Normalize to the peak, then scale to the range pyadi-iio expects for the
    # int16 TX buffer. Matters for multi-tone, where the peaks add up.
    waveform /= np.max(np.abs(waveform))
    return (waveform * (2**14 * 0.9)).astype(np.complex64), actual


signal_ch0, actual_ch0 = build_tone(tone_offsets_ch0)
signal_ch1, actual_ch1 = build_tone(tone_offsets_ch1)

# ===========================
# PlutoSDR Configuration (Pluto+, 2 TX)
# ===========================
def resolve_uri():
    if pluto_uri:
        return pluto_uri

    contexts = iio.scan_contexts()
    if not contexts:
        raise RuntimeError(
            "No PlutoSDR found. Plug it in, or set pluto_uri explicitly."
        )

    listing = "\n".join(f"    {u}  {d}" for u, d in sorted(contexts.items()))

    if pluto_serial:
        matches = [u for u, d in contexts.items() if pluto_serial in d]
        if not matches:
            raise RuntimeError(
                f"No PlutoSDR with serial {pluto_serial}. Attached:\n{listing}"
            )
        return matches[0]

    # No serial given: only safe when there is exactly one radio. Refuse to
    # guess rather than transmit from the wrong board.
    if len(contexts) > 1:
        raise RuntimeError(
            f"{len(contexts)} PlutoSDRs attached -- set pluto_serial to choose "
            f"one:\n{listing}"
        )
    return next(iter(contexts))


uri = resolve_uri()
print(f"Connecting to    : {uri}")

n_tx = tx_count(uri)
if tx_channel not in (1, 2):
    raise ValueError(f"tx_channel must be 1 or 2, got {tx_channel}")
if tx_channel > n_tx:
    raise RuntimeError(
        f"tx_channel = {tx_channel} but this radio has {n_tx} transmitter(s). "
        f"The AD9364 in the stock Pluto is 1T1R silicon -- there is no TX2."
    )

# adi.ad9361 is the 2x2 class; adi.Pluto is single-channel and lacks
# tx_hardwaregain_chan1. Pick by measured channel count, not by model string.
sdr = adi.ad9361(uri) if n_tx >= 2 else adi.Pluto(uri)

chan = tx_channel - 1
signal = signal_ch0 if chan == 0 else signal_ch1
offsets = tone_offsets_ch0 if chan == 0 else tone_offsets_ch1
actual = actual_ch0 if chan == 0 else actual_ch1
gain = tx_gain_ch0 if chan == 0 else tx_gain_ch1

sdr.tx_enabled_channels = [chan]        # only this chain streams
sdr.sample_rate = sample_rate
sdr.tx_rf_bandwidth = sample_rate
sdr.tx_lo = center_freq
if n_tx >= 2:
    # Disabling a channel stops its datapath but leaves the analog chain
    # powered; max attenuation is what actually keeps TX2 quiet.
    sdr.tx_hardwaregain_chan0 = gain if chan == 0 else MUTE_DB
    sdr.tx_hardwaregain_chan1 = gain if chan == 1 else MUTE_DB
else:
    sdr.tx_hardwaregain_chan0 = gain
sdr.tx_cyclic_buffer = True   # Hardware repeats the buffer -> gap-free CW

# ===========================
# Transmit
# ===========================
print(f"Radio          : {n_tx} TX  -> {type(sdr).__name__}")
print(f"TX LO          : {center_freq/1e6:.3f} MHz")
print(f"Sample rate    : {sample_rate/1e6:.3f} Msps")
print(f"Buffer         : {buffer_size} samples ({buffer_size/sample_rate*1e3:.3f} ms), "
      f"bin spacing {bin_spacing:.2f} Hz")
print(f"Tone type      : {'real cosine' if real_tone else 'complex exponential'}")
print(f"  TX{tx_channel}: attenuation {gain} dB")
for req, act in zip(offsets, actual):
    print(f"        offset {req:+,.0f} Hz -> {act:+,.2f} Hz  "
          f"(RF {(center_freq + act)/1e6:.6f} MHz)")
if n_tx >= 2:
    print(f"  TX{2 if tx_channel == 1 else 1}: muted ({MUTE_DB} dB), channel disabled")

# One enabled channel -> one array (not a list).
# With a cyclic buffer this is called ONCE -- the hardware loops it from then on.
sdr.tx(signal)
print(f"\nTransmitting on TX{tx_channel} only. Ctrl-C to stop.")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    sdr.tx_destroy_buffer()
    print("Stopped.")

import numpy as np
import adi
import iio
import time

# ===========================
# Parameters
# ===========================
# pluto_uri = "ip:172.19.222.191"   ## Ethernet connection (sysnet internal)
pluto_uri = ""                      ## "" = auto-detect over USB
center_freq = 2482_000_000      # 2.482 GHz -- TX LO. SHARED by both channels:
                                # the AD9361 has one TX LO, so TX1 and TX2 are
                                # always at the same center frequency.
sample_rate = 1_000_000         # 1 Msps
buffer_size = 2**14             # 16384 samples -- one period of the cyclic buffer
real_tone = False               # False: complex exponential -> one line at LO+offset
                                # True:  real cosine        -> lines at LO±offset

# Baseband tone offsets in Hz, per channel, relative to the LO.
# One entry = single tone; add more for multi-tone on that channel.
# Identical lists = the same sine out of both connectors.
# Must satisfy |offset| < sample_rate/2. Avoid 0 Hz: LO leakage sits there.
tone_offsets_ch0 = [100_000]
tone_offsets_ch1 = [100_000]

# TX "gain" is ATTENUATION in dB: 0 = full power, -89.75 = minimum.
# Less negative = louder.
tx_gain_ch0 = -10
tx_gain_ch1 = -10

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
    return sorted(contexts)[0]


# adi.ad9361 is the 2x2 class. adi.Pluto is single-channel and cannot drive TX2.
uri = resolve_uri()
print(f"Connecting to    : {uri}")
sdr = adi.ad9361(uri)
sdr.tx_enabled_channels = [0, 1]
sdr.sample_rate = sample_rate
sdr.tx_rf_bandwidth = sample_rate
sdr.tx_lo = center_freq
sdr.tx_hardwaregain_chan0 = tx_gain_ch0
sdr.tx_hardwaregain_chan1 = tx_gain_ch1
sdr.tx_cyclic_buffer = True   # Hardware repeats the buffer -> gap-free CW

# ===========================
# Transmit
# ===========================
print(f"TX LO          : {center_freq/1e6:.3f} MHz  (shared by TX1 and TX2)")
print(f"Sample rate    : {sample_rate/1e6:.3f} Msps")
print(f"Buffer         : {buffer_size} samples ({buffer_size/sample_rate*1e3:.3f} ms), "
      f"bin spacing {bin_spacing:.2f} Hz")
print(f"Tone type      : {'real cosine' if real_tone else 'complex exponential'}")

for ch, (requested, actual, gain) in enumerate(
    [(tone_offsets_ch0, actual_ch0, tx_gain_ch0),
     (tone_offsets_ch1, actual_ch1, tx_gain_ch1)]
):
    print(f"  TX{ch+1}: attenuation {gain} dB")
    for req, act in zip(requested, actual):
        print(f"        offset {req:+,.0f} Hz -> {act:+,.2f} Hz  "
              f"(RF {(center_freq + act)/1e6:.6f} MHz)")

# One array per enabled channel, both the same length.
# With a cyclic buffer this is called ONCE -- the hardware loops it from then on.
sdr.tx([signal_ch0, signal_ch1])
print("\nTransmitting on TX1 and TX2. Ctrl-C to stop.")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    sdr.tx_destroy_buffer()
    print("Stopped.")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Not titled yet
# Author: wcsng-101
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt
from gnuradio import qtgui
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import uhd
import time
import sip
import threading



class x410_4rx(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "Not titled yet", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Not titled yet")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except BaseException as exc:
            print(f"Qt GUI: Could not set Icon: {str(exc)}", file=sys.stderr)
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "x410_4rx")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.samp_rate_rx = samp_rate_rx = 15.36e6
        self.tx_gain = tx_gain = 10
        self.samp_rate_tx = samp_rate_tx = samp_rate_rx
        self.samp_rate = samp_rate = 32000
        self.rx_gain = rx_gain = 10
        self.num_samples = num_samples = int(samp_rate_rx)*5
        self.center_freq = center_freq = 4.0e9

        ##################################################
        # Blocks
        ##################################################

        self.uhd_usrp_source_0_0_0 = uhd.usrp_source(
            ",".join(("addr=192.168.10.2", '')),
            uhd.stream_args(
                cpu_format="fc32",
                args='peak=0.003906',
                channels=list(range(0,4)),
            ),
        )
        self.uhd_usrp_source_0_0_0.set_subdev_spec('A:0 A:1 B:0 B:1', 0)
        self.uhd_usrp_source_0_0_0.set_samp_rate(samp_rate_rx)
        self.uhd_usrp_source_0_0_0.set_time_unknown_pps(uhd.time_spec(0))

        self.uhd_usrp_source_0_0_0.set_center_freq(center_freq, 0)
        self.uhd_usrp_source_0_0_0.set_antenna('TX/RX', 0)
        self.uhd_usrp_source_0_0_0.set_gain(rx_gain, 0)

        self.uhd_usrp_source_0_0_0.set_center_freq(center_freq, 1)
        self.uhd_usrp_source_0_0_0.set_antenna('TX/RX', 1)
        self.uhd_usrp_source_0_0_0.set_gain(rx_gain, 1)

        self.uhd_usrp_source_0_0_0.set_center_freq(center_freq, 2)
        self.uhd_usrp_source_0_0_0.set_antenna('TX/RX', 2)
        self.uhd_usrp_source_0_0_0.set_gain(rx_gain, 2)

        self.uhd_usrp_source_0_0_0.set_center_freq(center_freq, 3)
        self.uhd_usrp_source_0_0_0.set_antenna('TX/RX', 3)
        self.uhd_usrp_source_0_0_0.set_gain(rx_gain, 3)

        self.uhd_usrp_source_0_0_0.set_start_time(uhd.time_spec(1))
        self.qtgui_sink_x_0_0_0_0_0_0 = qtgui.sink_c(
            1024, #fftsize
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            samp_rate_rx, #bw
            "", #name
            True, #plotfreq
            True, #plotwaterfall
            True, #plottime
            True, #plotconst
            None # parent
        )
        self.qtgui_sink_x_0_0_0_0_0_0.set_update_time(1.0/10)
        self._qtgui_sink_x_0_0_0_0_0_0_win = sip.wrapinstance(self.qtgui_sink_x_0_0_0_0_0_0.qwidget(), Qt.QWidget)

        self.qtgui_sink_x_0_0_0_0_0_0.enable_rf_freq(False)

        self.top_layout.addWidget(self._qtgui_sink_x_0_0_0_0_0_0_win)
        self.qtgui_sink_x_0_0_0_0_0 = qtgui.sink_c(
            1024, #fftsize
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            samp_rate_rx, #bw
            "", #name
            True, #plotfreq
            True, #plotwaterfall
            True, #plottime
            True, #plotconst
            None # parent
        )
        self.qtgui_sink_x_0_0_0_0_0.set_update_time(1.0/10)
        self._qtgui_sink_x_0_0_0_0_0_win = sip.wrapinstance(self.qtgui_sink_x_0_0_0_0_0.qwidget(), Qt.QWidget)

        self.qtgui_sink_x_0_0_0_0_0.enable_rf_freq(False)

        self.top_layout.addWidget(self._qtgui_sink_x_0_0_0_0_0_win)
        self.qtgui_sink_x_0_0_0_0 = qtgui.sink_c(
            1024, #fftsize
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            samp_rate_rx, #bw
            "", #name
            True, #plotfreq
            True, #plotwaterfall
            True, #plottime
            True, #plotconst
            None # parent
        )
        self.qtgui_sink_x_0_0_0_0.set_update_time(1.0/10)
        self._qtgui_sink_x_0_0_0_0_win = sip.wrapinstance(self.qtgui_sink_x_0_0_0_0.qwidget(), Qt.QWidget)

        self.qtgui_sink_x_0_0_0_0.enable_rf_freq(False)

        self.top_layout.addWidget(self._qtgui_sink_x_0_0_0_0_win)
        self.qtgui_sink_x_0_0_0 = qtgui.sink_c(
            1024, #fftsize
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            samp_rate_rx, #bw
            "", #name
            True, #plotfreq
            True, #plotwaterfall
            True, #plottime
            True, #plotconst
            None # parent
        )
        self.qtgui_sink_x_0_0_0.set_update_time(1.0/10)
        self._qtgui_sink_x_0_0_0_win = sip.wrapinstance(self.qtgui_sink_x_0_0_0.qwidget(), Qt.QWidget)

        self.qtgui_sink_x_0_0_0.enable_rf_freq(True)

        self.top_layout.addWidget(self._qtgui_sink_x_0_0_0_win)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.uhd_usrp_source_0_0_0, 0), (self.qtgui_sink_x_0_0_0, 0))
        self.connect((self.uhd_usrp_source_0_0_0, 1), (self.qtgui_sink_x_0_0_0_0, 0))
        self.connect((self.uhd_usrp_source_0_0_0, 2), (self.qtgui_sink_x_0_0_0_0_0, 0))
        self.connect((self.uhd_usrp_source_0_0_0, 3), (self.qtgui_sink_x_0_0_0_0_0_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "x410_4rx")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_samp_rate_rx(self):
        return self.samp_rate_rx

    def set_samp_rate_rx(self, samp_rate_rx):
        self.samp_rate_rx = samp_rate_rx
        self.set_num_samples(int(self.samp_rate_rx)*5)
        self.set_samp_rate_tx(self.samp_rate_rx)
        self.qtgui_sink_x_0_0_0.set_frequency_range(0, self.samp_rate_rx)
        self.qtgui_sink_x_0_0_0_0.set_frequency_range(0, self.samp_rate_rx)
        self.qtgui_sink_x_0_0_0_0_0.set_frequency_range(0, self.samp_rate_rx)
        self.qtgui_sink_x_0_0_0_0_0_0.set_frequency_range(0, self.samp_rate_rx)
        self.uhd_usrp_source_0_0_0.set_samp_rate(self.samp_rate_rx)

    def get_tx_gain(self):
        return self.tx_gain

    def set_tx_gain(self, tx_gain):
        self.tx_gain = tx_gain

    def get_samp_rate_tx(self):
        return self.samp_rate_tx

    def set_samp_rate_tx(self, samp_rate_tx):
        self.samp_rate_tx = samp_rate_tx

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate

    def get_rx_gain(self):
        return self.rx_gain

    def set_rx_gain(self, rx_gain):
        self.rx_gain = rx_gain
        self.uhd_usrp_source_0_0_0.set_gain(self.rx_gain, 0)
        self.uhd_usrp_source_0_0_0.set_gain(self.rx_gain, 1)
        self.uhd_usrp_source_0_0_0.set_gain(self.rx_gain, 2)
        self.uhd_usrp_source_0_0_0.set_gain(self.rx_gain, 3)

    def get_num_samples(self):
        return self.num_samples

    def set_num_samples(self, num_samples):
        self.num_samples = num_samples

    def get_center_freq(self):
        return self.center_freq

    def set_center_freq(self, center_freq):
        self.center_freq = center_freq
        self.uhd_usrp_source_0_0_0.set_center_freq(self.center_freq, 0)
        self.uhd_usrp_source_0_0_0.set_center_freq(self.center_freq, 1)
        self.uhd_usrp_source_0_0_0.set_center_freq(self.center_freq, 2)
        self.uhd_usrp_source_0_0_0.set_center_freq(self.center_freq, 3)




def main(top_block_cls=x410_4rx, options=None):

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()
    tb.flowgraph_started.set()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()

#! /usr/bin/python
# -*- coding: utf-8 -*-
#
#  Copyright 2015 Matthieu Baerts & Quentin De Coninck
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#  To install on this machine: matplotlib, numpy

from __future__ import print_function

##################################################
##                   IMPORTS                    ##
##################################################

import argparse
import common as co
from math import ceil
import matplotlib
# Do not use any X11 backend
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mptcp
import numpy as np
import os
import os.path
import pickle
import sys
import tcp
import time

parser = argparse.ArgumentParser(
    description="Summarize stat files generated by analyze")
parser.add_argument("-s",
                    "--stat", help="directory where the stat files of smartphone are stored", default=co.DEF_STAT_DIR+'_'+co.DEF_IFACE)
parser.add_argument("-m",
                    "--stat-mporg", help="directory where the stat files of smartphone are stored", default=co.DEF_STAT_DIR+'_'+co.DEF_IFACE)
parser.add_argument('-S',
                    "--sums", help="directory where the summary graphs will be stored", default=co.DEF_SUMS_DIR+'_'+co.DEF_IFACE)

args = parser.parse_args()

mp_dir_exp = os.path.abspath(os.path.expanduser(args.stat_mporg))
stat_dir_exp = os.path.abspath(os.path.expanduser(args.stat))
sums_dir_exp = os.path.abspath(os.path.expanduser(args.sums))

co.check_directory_exists(sums_dir_exp)

def fetch_data(dir_exp):
    co.check_directory_exists(dir_exp)
    dico = {}
    for dirpath, dirnames, filenames in os.walk(dir_exp):
        for fname in filenames:
            try:
                stat_file = open(os.path.join(dirpath, fname), 'r')
                dico[fname] = pickle.load(stat_file)
                stat_file.close()
            except IOError as e:
                print(str(e) + ': skip stat file ' + fname, file=sys.stderr)

    return dico

NOSTR = "server"
SMART = "smartphone"
dataset = {}
dataset[NOSTR] = fetch_data(mp_dir_exp)
dataset[SMART] = fetch_data(stat_dir_exp)

def ensures_smartphone_to_proxy():
    for fname in dataset[SMART].keys():
        for conn_id in dataset[SMART][fname].keys():
            if isinstance(dataset[SMART][fname][conn_id], mptcp.MPTCPConnection):
                inside = True
                for flow_id, flow in dataset[SMART][fname][conn_id].flows.iteritems():
                    if not flow.attr[co.DADDR].startswith('172.17.') and not flow.attr[co.DADDR] == co.IP_PROXY:
                        dataset[SMART][fname].pop(conn_id, None)
                        inside = False
                        break
                if inside:
                    for direction in co.DIRECTIONS:
                        # This is a fix for wrapping seq num
                        if dataset[SMART][fname][conn_id].attr[direction][co.BYTES_MPTCPTRACE] < -1:
                            dataset[SMART][fname][conn_id].attr[direction][co.BYTES_MPTCPTRACE] = 2**32 + dataset[SMART][fname][conn_id].attr[direction][co.BYTES_MPTCPTRACE]

ensures_smartphone_to_proxy()


def correct_mptcptrace_bytes():
    for fname in dataset[NOSTR].keys():
        for conn_id in dataset[NOSTR][fname].keys():
            if isinstance(dataset[NOSTR][fname][conn_id], mptcp.MPTCPConnection):
                for direction in co.DIRECTIONS:
                    # This is a fix for wrapping seq num
                    if dataset[NOSTR][fname][conn_id].attr[direction][co.BYTES_MPTCPTRACE] < -1:
                        dataset[NOSTR][fname][conn_id].attr[direction][co.BYTES_MPTCPTRACE] = 2**32 + dataset[NOSTR][fname][conn_id].attr[direction][co.BYTES_MPTCPTRACE]

correct_mptcptrace_bytes()


def bursts_mptcp(log_file=sys.stdout):
    bursts_sec = {co.S2D: {'all': {NOSTR: [], SMART: []}}, co.D2S: {'all': {NOSTR: [], SMART: []}}}
    color = ['red', 'blue']
    graph_fname_sec = "merge_bursts_sec"
    base_graph_path_sec = os.path.join(sums_dir_exp, graph_fname_sec)
    for ds, data in dataset.iteritems():
        count_total = {co.S2D: 0, co.D2S: 0}
        count_more_100 = {co.S2D: 0, co.D2S: 0}
        count_more_200 = {co.S2D: 0, co.D2S: 0}
        count_less_10 = {co.S2D: 0, co.D2S: 0}
        for fname, conns in data.iteritems():
            for conn_id, conn in conns.iteritems():
                # We never know, still check
                if isinstance(conn, mptcp.MPTCPConnection):
                    if conn.attr[co.DURATION] > 0.0 and len(conn.flows) >= 2:
                        duration = conn.attr[co.DURATION]
                        if duration == 0.0:
                            continue
                        for direction in co.DIRECTIONS:
                            if conn.attr[direction].get(co.BYTES_MPTCPTRACE, 0) < 1000000:
                                continue
                            if conn.attr[direction][co.BYTES_MPTCPTRACE] > 1 and co.BURSTS in conn.attr[direction] and len(conn.attr[direction][co.BURSTS]) > 0:
                                count_total[direction] += 1
                                bursts_sec[direction]['all'][ds].append((len(conn.attr[direction][co.BURSTS]) - 1.0) / duration)
                                if (len(conn.attr[direction][co.BURSTS]) - 1.0) / duration >= 100:
                                    count_more_100[direction] += 1
                                    if (len(conn.attr[direction][co.BURSTS]) - 1.0) / duration >= 200:
                                        count_more_200[direction] += 1
                                if (len(conn.attr[direction][co.BURSTS]) - 1.0) / duration <= 10:
                                    count_less_10[direction] += 1
        print(ds)
        print(">100", count_more_100[co.D2S])
        print(">200", count_more_200[co.D2S])
        print("<10", count_less_10[co.D2S])
        print("Total", count_total[co.D2S])

    co.plot_cdfs_with_direction(bursts_sec, color, '# switches / second', base_graph_path_sec, natural=True, label_order=[NOSTR, SMART])
    co.plot_cdfs_with_direction(bursts_sec, color, '# switches / second', base_graph_path_sec + "_cut", xlim=200, natural=True, label_order=[NOSTR, SMART])
    co.plot_cdfs_with_direction(bursts_sec, color, '# switches / second', base_graph_path_sec + "_ccdf", natural=True, xlog=True, ylog=True, ccdf=True, label_order=[NOSTR, SMART])


def plot_rtt_d2s(log_file=sys.stdout):
    rtt_diff = {NOSTR: [], SMART: []}
    rtt_maxmin = {NOSTR: [], SMART: []}
    graph_fname_rtt = "merge_rtt_d2s"
    base_graph_path_rtt = os.path.join(sums_dir_exp, graph_fname_rtt)
    for ds, data in dataset.iteritems():
        count_conn = 0
        count_max_10 = 0
        count_min_100 = 0
        count_min_1000 = 0
        max_value = 0
        for fname, conns in data.iteritems():
            for conn_id, conn in conns.iteritems():
                # We never know, still check
                if isinstance(conn, mptcp.MPTCPConnection):
                    count_flow = 0
                    max_flow = 0.0
                    min_flow = float('inf')
                    for flow_id, flow in conn.flows.iteritems():
                        if flow.attr[co.D2S].get(co.BYTES, 0) < 100000:
                            continue
                        data = flow.attr[co.D2S]
                        if co.RTT_MIN in data and co.RTT_AVG in data:

                            count_flow += 1
                            max_flow = max(max_flow, data[co.RTT_AVG])
                            min_flow = min(min_flow, data[co.RTT_AVG])

                            if data[co.RTT_MIN] < 1.0:
                                print("LOW RTT", fname, conn_id, flow_id, data[co.RTT_MIN], data[co.RTT_AVG], data[co.RTT_MAX], flow.attr[co.D2S].get(co.RTT_3WHS, 0), flow.attr[co.D2S].get(co.BYTES, 0), flow.attr[co.D2S].get(co.RTT_SAMPLES, 0), flow.attr[co.DADDR], file=log_file)

                    if count_flow >= 2:
                        count_conn += 1
                        rtt_diff[ds].append(max_flow - min_flow)
                        if max_flow - min_flow <= 10.0:
                            count_max_10 += 1
                        if max_flow - min_flow >= 100.0:
                            count_min_100 += 1
                            if max_flow - min_flow >= 1000.0:
                                count_min_1000 += 1
                        max_value = max(max_value, max_flow - min_flow)
                        if min_flow > 0.0:
                            rtt_maxmin[ds].append([min_flow, max_flow])

        print(ds)
        print("TOTAL", count_conn, "<=10ms", count_max_10, ">=100ms", count_min_100, ">=1000ms", count_min_1000, "Max", max_value)


    co.plot_cdfs_natural({'all': rtt_diff}, ['red', 'blue'], "Difference of avg RTT between worst and best subflow (ms)", base_graph_path_rtt, label_order=[NOSTR, SMART], xlog=True, xlim=10000)
    co.scatter_plot({'all': rtt_maxmin}, "Min avg RTT subflow (ms)", "Max avg RTT subflow (ms)", {NOSTR: "blue", SMART: "red"}, sums_dir_exp, "merge_scatter_rtt_d2s_log", label_order=[NOSTR, SMART])
    co.scatter_plot({'all': rtt_maxmin}, "Min avg RTT subflow (ms)", "Max avg RTT subflow (ms)", {NOSTR: "blue", SMART: "red"}, sums_dir_exp, "merge_scatter_rtt_d2s", label_order=[NOSTR, SMART], log_scale_x=False, log_scale_y=False, plot_identity=True)

#bursts_mptcp()
plot_rtt_d2s()

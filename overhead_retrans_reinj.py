#! /usr/bin/python
# -*- coding: utf-8 -*-
#
#  Copyright 2015 Quentin De Coninck
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

import argparse
import common as co
import common_graph as cog
import matplotlib
# Do not use any X11 backend
matplotlib.use('Agg')
matplotlib.rcParams['pdf.fonttype'] = 42
matplotlib.rcParams['ps.fonttype'] = 42
import matplotlib.pyplot as plt
import mptcp
import numpy as np
import os
import tcp

##################################################
##                  ARGUMENTS                   ##
##################################################

parser = argparse.ArgumentParser(
    description="Summarize stat files generated by analyze")
parser.add_argument("-s",
                    "--stat", help="directory where the stat files are stored", default=co.DEF_STAT_DIR + '_' + co.DEF_IFACE)
parser.add_argument('-S',
                    "--sums", help="directory where the summary graphs will be stored", default=co.DEF_SUMS_DIR + '_' + co.DEF_IFACE)
parser.add_argument("-d",
                    "--dirs", help="list of directories to aggregate", nargs="+")

args = parser.parse_args()
stat_dir_exp = os.path.abspath(os.path.expanduser(args.stat))
sums_dir_exp = os.path.abspath(os.path.expanduser(args.sums))
co.check_directory_exists(sums_dir_exp)

##################################################
##                 GET THE DATA                 ##
##################################################

connections = cog.fetch_valid_data(stat_dir_exp, args)
multiflow_connections, singleflow_connections = cog.get_multiflow_connections(connections)

##################################################
##               PLOTTING RESULTS               ##
##################################################


def plot(connections, multiflow_connections, sums_dir_exp):
    RETRANS = 'Retransmission'
    REINJ = 'Reinjection'

    results = {co.C2S: {REINJ: [], RETRANS: []}, co.S2C: {REINJ: [], RETRANS: []}}
    graph_fname = "overhead_retrans_reinj_multiflow.pdf"
    graph_full_path = os.path.join(sums_dir_exp, graph_fname)
    log_filename = "overhead_logging"
    log_file = open(log_filename, 'w')

    total_unique = {co.S2D: 0, co.D2S: 0}
    total_retrans = {co.S2D: 0, co.D2S: 0}
    total_reinj = {co.S2D: 0, co.D2S: 0}
    total_reinj_mptcp = {co.S2D: 0, co.D2S: 0}
    for fname, data in multiflow_connections.iteritems():
        for conn_id, conn in data.iteritems():
            retrans_bytes = {co.C2S: 0, co.S2C: 0}
            reinj_bytes = {co.C2S: 0, co.S2C: 0}
            total_bytes = {co.C2S: 0, co.S2C: 0}
            total_data_bytes = {co.C2S: 0, co.S2C: 0}
            reinj_data_bytes = {co.C2S: 0, co.S2C: 0}

            # Restrict to connections using at least 2 SFs
            ok = False

            nb_flows = 0
            for flow_id, flow in conn.flows.iteritems():
                if flow.attr[co.C2S].get(co.BYTES, 0) > 0 or flow.attr[co.S2C].get(co.BYTES, 0) > 0:
                    nb_flows += 1

            if nb_flows >= 2:
                ok = True

            if not ok:
                continue

            for direction in co.DIRECTIONS:
                total_unique[direction] += conn.attr[direction].get(co.BYTES_MPTCPTRACE, 0)

                for flow_id, flow in conn.flows.iteritems():
                    if direction not in flow.attr:
                        continue
                    if co.BYTES in flow.attr[direction]:
                        # total_bytes[direction] += flow.attr[direction][co.BYTES_FRAMES_TOTAL]
                        total_bytes[direction] = total_bytes[direction] + flow.attr[direction][co.BYTES]
                        # retrans_bytes[direction] += flow.attr[direction].get(co.BYTES_FRAMES_RETRANS, 0)
                        retrans_bytes[direction] = retrans_bytes[direction] + flow.attr[direction].get(co.BYTES_RETRANS, 0)
                        # reinj_bytes[direction] += flow.attr[direction].get(co.REINJ_ORIG_BYTES, 0) + (flow.attr[direction].get(co.REINJ_ORIG_PACKS, 0) * co.FRAME_MPTCP_OVERHEAD)
                        reinj_bytes[direction] = reinj_bytes[direction] + flow.attr[direction].get(co.REINJ_ORIG_BYTES, 0)
                        total_data_bytes[direction] = total_data_bytes[direction] + flow.attr[direction].get(co.BYTES, 0)
                        reinj_data_bytes[direction] = reinj_data_bytes[direction] + flow.attr[direction].get(co.REINJ_ORIG_BYTES, 0)

                total_retrans[direction] += retrans_bytes[direction]
                total_reinj[direction] += reinj_bytes[direction]
                total_reinj_mptcp[direction] += conn.attr[direction].get(co.REINJ_BYTES, 0)

            for direction in co.DIRECTIONS:
                if total_bytes[direction] > 0:
                    results[direction][RETRANS].append((retrans_bytes[direction] + 0.0) / total_data_bytes[direction])
                    results[direction][REINJ].append((reinj_data_bytes[direction] + 0.0) / total_data_bytes[direction])
                    if (retrans_bytes[direction] + 0.0) / total_data_bytes[direction] >= 1.0:
                        print("RETRANS", direction, (retrans_bytes[direction] + 0.0) / total_data_bytes[direction], total_bytes[direction], file=log_file)
                    if (reinj_bytes[direction] + 0.0) / total_data_bytes[direction] >= 1.0:
                        print("REINJ", direction, (reinj_bytes[direction] + 0.0) / total_data_bytes[direction], total_bytes[direction], file=log_file)


    ls = {RETRANS: '--', REINJ: '-'}
    log_file.close()
    color = {RETRANS: 'blue', REINJ: 'red'}
    for direction in co.DIRECTIONS:
        plt.figure()
        plt.clf()
        fig, ax = plt.subplots()
        min_y = 1.0

        for dataset in [RETRANS, REINJ]:
            sample = np.array(sorted(results[direction][dataset]))
            sorted_array = np.sort(sample)
            yvals = np.arange(len(sorted_array)) / float(len(sorted_array))
            if len(sorted_array) > 0:
                # Add a last point
                sorted_array = np.append(sorted_array, sorted_array[-1])
                yvals = np.append(yvals, 1.0)
                index = 0
                for x_value in sorted_array:
                    if x_value > 0.0:
                        break
                    else:
                        index += 1
                min_y = min(min_y, yvals[index])
                print("YMIN", dataset, yvals[index])
                print("1%", dataset, (len([x for x in sorted_array if x <= 0.01]) + 0.0) / len(sorted_array))
                print("10%", dataset, (len([x for x in sorted_array if x <= 0.1]) + 0.0) / len(sorted_array))
                # Log plot

                ax.plot(sorted_array, yvals, color=color[dataset], linewidth=2, linestyle=ls[dataset], label=dataset)

        ax.set_xscale('log')
        ax.legend(loc='lower right')

        plt.xlabel('Fraction of unique bytes', fontsize=24, labelpad=-1)
        plt.ylabel("CDF", fontsize=24)
        plt.ylim(ymin=min_y - 0.01)
        print("YMIN:", min_y)
        # Show most interesting part
        plt.xlim(xmin=0.00001, xmax=30.)
        plt.savefig(os.path.splitext(graph_full_path)[0] + '_' + direction + '.pdf')
        plt.close('all')

        print("TOTAL UNIQUE", total_unique)
        print("TOTAL RETRANS", total_retrans)
        print("TOTAL REINJ", total_reinj)
        print("TOTAL REINJ MPTCP", total_reinj_mptcp)

plot(connections, multiflow_connections, sums_dir_exp)

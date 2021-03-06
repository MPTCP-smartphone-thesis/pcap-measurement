#! /usr/bin/python
# -*- coding: utf-8 -*-
#
#  Copyright 2014-2015 Matthieu Baerts & Quentin De Coninck
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

import argparse
import matplotlib
# Do not use any X11 backend
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os
import pcapy
import statsmodels.api as sm

parser = argparse.ArgumentParser(
    description="Summarize stat files generated by analyze")
parser.add_argument("pcap", help="path to the pcap to compute CDF")

args = parser.parse_args()

reader = pcapy.open_offline(args.pcap)
sizes = []

while True:
    try:
        (header, payload) = reader.next()
        sizes.append(header.getlen())
    except pcapy.PcapError:
        break

plt.figure()
plt.clf()
fig, ax = plt.subplots()

graph_fname = os.getcwd() + "/cdf_size_packets_" + os.path.basename(os.path.splitext(args.pcap)[0]) + ".pdf"

try:
    sample = np.array(sorted(sizes))

    ecdf = sm.distributions.ECDF(sample)

    x = np.linspace(min(sample), max(sample))
    y = ecdf(x)
    ax.step(x, y, color='b')
except ZeroDivisionError as e:
    print(str(e))

# Shrink current axis's height by 10% on the top
box = ax.get_position()
ax.set_position([box.x0, box.y0,
                 box.width, box.height * 0.9])

# Put a legend above current axis
# ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.05), fancybox=True, shadow=True, ncol=len(aggl_res[cond]))

plt.xlabel('Size of packets in bytes', fontsize=18)
plt.savefig(graph_fname)
plt.close('all')

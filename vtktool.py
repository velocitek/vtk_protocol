import argparse
import csv
from datetime import datetime, timezone
import numpy as np
import os
import struct
import sys
import transformations
import vtk_pb2


def main():
    parser = argparse.ArgumentParser(
        description='Tool to convert vtk file to csv.')
    parser.add_argument('input', help='Input file in .vtk format.')
    parser.add_argument('output', nargs='?',
                        help='Output file in .csv format.')
    parser.add_argument('--debug', default=False,
                        action='store_true', help='Show decoded data')
    parser.add_argument('--debug-size', default=False, action='store_true',
                        help='Calculate size per message when reading or writing data.')

    args = parser.parse_args()

    points = []

    if args.input.lower().endswith('.vtk'):
        with open(args.input, 'rb') as f:
            points = vtk_records_to_points(read_vtk(f))
            if args.debug_size and len(points) > 0:
                fsize = os.stat(args.input).st_size
                print("Read {} messages from {} bytes. Avg {:.1f} bytes/msg.".format(
                      len(points), fsize, fsize/len(points)))

    else:
        print("No intelligible input provided")
        sys.exit(-1)

    if args.debug:
        print(points)

    if args.output:
        if args.output.lower().endswith('.csv'):
            with open(args.output, 'w') as csvfile:
                write_csv(csvfile, points)


def read_vtk(input):
    """Take an open input file (rb) and returns the content as an array of VTKMessage."""

    records = []
    bytes_read = 0
    while True:
        len_data = input.read(2)
        if not len_data:
            break
        length = struct.unpack('<H', len_data)[0]
        data = input.read(length)
        if not data:
            print("Error - Not enough data :/")
            break

        r = vtk_pb2.Record.FromString(data)
        records.append(r)

    return records


def vtk_records_to_points(records):
    """ Takes an array of VTK Records and returns an array of Points"""

    points = []
    for r in records:
        if r.HasField('trackpoint'):
            tp = r.trackpoint
            p = {}
            p['time'] = datetime.fromtimestamp(
                tp.seconds + tp.centiseconds / 1e2, tz=timezone.utc)
            p['latitude'] = tp.latitudeE7 / 1e7
            p['longitude'] = tp.longitudeE7 / 1e7
            p['sog'] = tp.sog_knotsE1 / 1e1
            p['cog'] = tp.cog
            p['q1'] = tp.q1E3 / 1e3
            p['q2'] = tp.q2E3 / 1e3
            p['q3'] = tp.q3E3 / 1e3
            p['q4'] = tp.q4E3 / 1e3
            quaternion = [p['q1'], p['q2'], p['q3'], p['q4']]
            angles = transformations.euler_from_quaternion(quaternion)
            p['mag_heading'] = -np.degrees(angles[2]) % 360

            # Heel to starboard is positive.
            p['heel'] = np.degrees(angles[0])

            # Bow up is positive.
            p['pitch'] = -np.degrees(angles[1])

            points.append(p)
        else:
            print("Not a position report record: {}".format(r))

    return points


def write_csv(csvfile, points):
    fieldnames = ['time', 'latitude', 'longitude', 'sog', 'cog',
                  'q1', 'q2', 'q3', 'q4', 'mag_heading', 'heel', 'pitch']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    for p in points:
        writer.writerow(p)


if __name__ == '__main__':
    main()

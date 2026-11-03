import struct
import unittest

import numpy as np

from scout_lio_support.cloud_conversion import (
    Field, InvalidCloud, OUTPUT_DTYPE, convert_cloud,
)


FIELDS = [Field("x", 0, 7), Field("y", 4, 7), Field("z", 8, 7),
          Field("intensity", 12, 7), Field("ring", 16, 4), Field("timestamp", 24, 8)]
STAMP = 1730000000.0


def make_cloud(points, *, endian="<", width=None, padding=0):
    width = len(points) if width is None else width
    height = len(points) // width
    rows = []
    for row in range(height):
        rows.append(b"".join(struct.pack(endian + "ffffH6xd", *point)
                            for point in points[row * width:(row + 1) * width])
                    + b"\xff" * padding)
    return dict(data=b"".join(rows), fields=FIELDS, width=width, height=height,
                point_step=32, row_step=width * 32 + padding,
                is_bigendian=endian == ">", stamp_seconds=STAMP)


class CloudConversionTests(unittest.TestCase):
    def test_epoch_precision_real_rings_and_nonmonotonic_time(self):
        source = [(1.0, 2.0, 3.0, 12.0, 31, STAMP + .09),
                  (4.0, 5.0, 6.0, 9.0, 0, STAMP + .001)]
        result = convert_cloud(**make_cloud(source))
        points = np.frombuffer(result.data, dtype=OUTPUT_DTYPE)
        self.assertEqual(result.count, 2)
        self.assertEqual(len(result.data), 48)
        self.assertEqual(points["ring"].tolist(), [31, 0])
        np.testing.assert_allclose(points["time"], [.09, .001], atol=3e-7)
        self.assertGreater(result.max_time, float(points["time"][-1]))
        self.assertEqual(struct.unpack_from("<H", result.data, 16)[0], 31)
        self.assertAlmostEqual(struct.unpack_from("<f", result.data, 20)[0], .09, places=6)

    def test_big_endian_organized_cloud_with_row_padding(self):
        source = [(float(i), 2.0, 3.0, 10.0, i, STAMP + .01 * i) for i in range(4)]
        result = convert_cloud(**make_cloud(source, endian=">", width=2, padding=11))
        points = np.frombuffer(result.data, dtype=OUTPUT_DTYPE)
        self.assertEqual(points["x"].tolist(), [0., 1., 2., 3.])
        self.assertEqual(points["ring"].tolist(), [0, 1, 2, 3])
        np.testing.assert_allclose(points["time"], [0., .01, .02, .03], atol=3e-7)

    def test_nan_and_out_of_range_rings_are_filtered(self):
        source = [(1., 2., 3., 5., 0, STAMP),
                  (float("nan"), 2., 3., 5., 1, STAMP),
                  (1., 2., 3., 5., 32, STAMP),
                  (1., 2., 3., 5., 2, float("nan"))]
        result = convert_cloud(**make_cloud(source))
        self.assertEqual((result.count, result.dropped), (1, 3))

    def test_mismatched_clock_rejects_cloud(self):
        for difference in (-1.0, 1.0, 1730000000.0):
            source = [(1., 2., 3., 5., 0, STAMP + difference)]
            with self.subTest(difference=difference), self.assertRaisesRegex(InvalidCloud, "time mismatch"):
                convert_cloud(**make_cloud(source))

    def test_small_negative_rounding_is_clamped(self):
        result = convert_cloud(**make_cloud([(1., 2., 3., 5., 0, STAMP - .0002)]))
        self.assertEqual(np.frombuffer(result.data, dtype=OUTPUT_DTYPE)["time"][0], 0.)

    def test_float32_epoch_timestamp_is_rejected(self):
        cloud = make_cloud([(1., 2., 3., 5., 0, STAMP)])
        cloud["fields"] = FIELDS[:-1] + [Field("timestamp", 24, 7)]
        with self.assertRaisesRegex(InvalidCloud, "FLOAT64"):
            convert_cloud(**cloud)

    def test_missing_ring_and_missing_time_rejected(self):
        for missing in ("ring", "timestamp"):
            cloud = make_cloud([(1., 2., 3., 5., 0, STAMP)])
            cloud["fields"] = [field for field in FIELDS if field.name != missing]
            with self.subTest(missing=missing), self.assertRaisesRegex(InvalidCloud, "missing measured"):
                convert_cloud(**cloud)

    def test_relative_float32_seconds(self):
        cloud = make_cloud([(1., 2., 3., 5., 7, STAMP)])
        cloud["fields"] = FIELDS[:-1] + [Field("time", 24, 7)]
        data = bytearray(cloud["data"])
        struct.pack_into("<f", data, 24, .065)
        cloud["data"] = data
        result = convert_cloud(**cloud, timestamp_field="time", timestamp_mode="relative")
        self.assertAlmostEqual(result.max_time, .065, places=6)

    def test_native_autoware_channel_relative_nanoseconds_layout(self):
        fields = [Field("x", 0, 7), Field("y", 4, 7), Field("z", 8, 7),
                  Field("intensity", 12, 2), Field("return_type", 13, 2),
                  Field("channel", 14, 4), Field("azimuth", 16, 7),
                  Field("elevation", 20, 7), Field("distance", 24, 7),
                  Field("time_stamp", 28, 6)]
        # Exact deployed driver layout: UINT8 intensity and UINT16 channel.
        points = [struct.pack("<fffBBHfffI", 1., 2., 3., 201, 1, 31, .4, .1, 5., 99999999),
                  struct.pack("<fffBBHfffI", 4., 5., 6., 17, 0, 0, .3, .2, 6., 1234567)]
        cloud = dict(data=b"".join(points), fields=fields, width=2, height=1,
                     point_step=32, row_step=64, is_bigendian=False,
                     stamp_seconds=STAMP)
        result = convert_cloud(**cloud, ring_field="channel", timestamp_field="time_stamp",
                               timestamp_mode="relative_ns")
        converted = np.frombuffer(result.data, dtype=OUTPUT_DTYPE)
        self.assertEqual(converted["ring"].tolist(), [31, 0])
        self.assertEqual(converted["intensity"].tolist(), [201., 17.])
        np.testing.assert_allclose(converted["time"], [.099999999, .001234567], atol=4e-9)
        np.testing.assert_allclose(converted["x"], [1., 4.])
        self.assertAlmostEqual(result.max_time, .099999999, places=9)
        # Misconfigured units must fail rather than reinterpret UINT32 as seconds.
        with self.assertRaisesRegex(InvalidCloud, "second timestamps"):
            convert_cloud(**cloud, ring_field="channel", timestamp_field="time_stamp",
                          timestamp_mode="relative")

    def test_relative_ns_rejects_float_or_signed_timestamps(self):
        for datatype in (5, 7, 8):
            cloud = make_cloud([(1., 2., 3., 5., 0, STAMP)])
            cloud["fields"] = FIELDS[:-1] + [Field("timestamp", 24, datatype)]
            with self.subTest(datatype=datatype), self.assertRaisesRegex(InvalidCloud, "UINT32"):
                convert_cloud(**cloud, timestamp_mode="relative_ns")

    def test_bad_buffer_layout_rejected(self):
        cloud = make_cloud([(1., 2., 3., 5., 0, STAMP)])
        cloud["data"] = cloud["data"][:-1]
        with self.assertRaisesRegex(InvalidCloud, "shorter"):
            convert_cloud(**cloud)
        cloud = make_cloud([(1., 2., 3., 5., 0, STAMP)])
        cloud["row_step"] = 16
        with self.assertRaisesRegex(InvalidCloud, "point_step/row_step"):
            convert_cloud(**cloud)


if __name__ == "__main__":
    unittest.main()

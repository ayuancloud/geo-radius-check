#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""geo_radius 单元测试：覆盖公式、边界（等于半径）、免开方等价性与精度对照。"""

import io
import json
import math
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import geo_radius as gr  # noqa: E402

CENTER_LNG = 114.123456
CENTER_LAT = 30.123456


class TestConstants(unittest.TestCase):
    def test_coefficients(self):
        self.assertAlmostEqual(gr.K_LNG_M_PER_DEG, 96486.25, places=6)
        self.assertAlmostEqual(gr.K_LAT_M_PER_DEG, 110852.42, places=6)

    def test_presets_thresholds(self):
        self.assertEqual(gr.RADIUS_PRESETS, (5.0, 10.0, 20.0))
        self.assertEqual([r * r for r in gr.RADIUS_PRESETS], [25.0, 100.0, 400.0])


class TestDistance(unittest.TestCase):
    def test_same_point_is_zero(self):
        self.assertEqual(gr.distance_m(CENTER_LNG, CENTER_LAT, CENTER_LNG, CENTER_LAT), 0.0)

    def test_pure_north_offset(self):
        """只有纬度差时，距离 = ΔB * 110852.42。"""
        lat = CENTER_LAT + 1e-5
        self.assertAlmostEqual(
            gr.distance_m(CENTER_LNG, lat, CENTER_LNG, CENTER_LAT),
            1e-5 * gr.K_LAT_M_PER_DEG,
            places=9,
        )

    def test_pure_east_offset(self):
        """只有经度差时，距离 = ΔL * 96486.25。"""
        lng = CENTER_LNG + 1e-5
        self.assertAlmostEqual(
            gr.distance_m(lng, CENTER_LAT, CENTER_LNG, CENTER_LAT),
            1e-5 * gr.K_LNG_M_PER_DEG,
            places=9,
        )

    def test_pythagorean_components(self):
        """dx = 3、dy = 4 时 d 必须等于 5。"""
        lng = CENTER_LNG + 3.0 / gr.K_LNG_M_PER_DEG
        lat = CENTER_LAT + 4.0 / gr.K_LAT_M_PER_DEG
        self.assertAlmostEqual(gr.distance_m(lng, lat, CENTER_LNG, CENTER_LAT), 5.0, places=9)

    def test_symmetry(self):
        a = gr.distance_m(114.1235, 30.1235, CENTER_LNG, CENTER_LAT)
        b = gr.distance_m(CENTER_LNG, CENTER_LAT, 114.1235, 30.1235)
        self.assertAlmostEqual(a, b, places=9)

    def test_sq_matches_sqrt(self):
        sq = gr.distance_sq_m2(114.1235, 30.1237, CENTER_LNG, CENTER_LAT)
        self.assertAlmostEqual(math.sqrt(sq), gr.distance_m(114.1235, 30.1237, CENTER_LNG, CENTER_LAT), places=12)

    def test_haversine_reference_close(self):
        """与 haversine 参考值对照：1 km 内相对误差应小于 1%。"""
        cases = [
            (114.123456, 30.124456),
            (114.124456, 30.123456),
            (114.124000, 30.124000),
            (114.122000, 30.122000),
        ]
        for lng, lat in cases:
            approx = gr.distance_m(lng, lat, CENTER_LNG, CENTER_LAT)
            ref = gr.haversine_distance_m(lng, lat, CENTER_LNG, CENTER_LAT)
            self.assertLess(abs(approx - ref) / ref, 0.01, f"{(lng, lat)} 误差过大")


class TestRadiusDecision(unittest.TestCase):
    def _point_at_distance(self, meters, direction="east"):
        if direction == "east":
            return CENTER_LNG + meters / gr.K_LNG_M_PER_DEG, CENTER_LAT
        return CENTER_LNG, CENTER_LAT + meters / gr.K_LAT_M_PER_DEG

    def test_center_is_always_within(self):
        for radius in gr.RADIUS_PRESETS:
            self.assertTrue(gr.is_within_radius(CENTER_LNG, CENTER_LAT, CENTER_LNG, CENTER_LAT, radius))

    def test_inside_and_outside(self):
        for radius in gr.RADIUS_PRESETS:
            for direction in ("east", "north"):
                inside = self._point_at_distance(radius * 0.99, direction)
                outside = self._point_at_distance(radius * 1.01, direction)
                self.assertTrue(gr.is_within_radius(*inside, CENTER_LNG, CENTER_LAT, radius))
                self.assertFalse(gr.is_within_radius(*outside, CENTER_LNG, CENTER_LAT, radius))

    def test_exactly_on_radius_is_within(self):
        """等于半径时视为在范围内。"""
        for radius in gr.RADIUS_PRESETS:
            point = self._point_at_distance(radius)
            self.assertAlmostEqual(gr.distance_m(*point, CENTER_LNG, CENTER_LAT), radius, places=6)
            # 坐标反算存在约 1 ulp 浮点误差，用极小相对容差保证“恰好等于半径”判定稳定
            self.assertTrue(gr.is_within_radius(*point, CENTER_LNG, CENTER_LAT, radius, 1e-9))

    def test_epsilon_does_not_leak_meaningful_slack(self):
        """容差只吸收浮点误差：明显超出半径的点仍判为范围外。"""
        for radius in gr.RADIUS_PRESETS:
            point = self._point_at_distance(radius * 1.0001)
            self.assertFalse(gr.is_within_radius(*point, CENTER_LNG, CENTER_LAT, radius, 1e-9))

    def test_default_is_strict_comparison(self):
        """默认 epsilon=0，即与 r² 严格比较。"""
        point = self._point_at_distance(6.0)
        sq = gr.distance_sq_m2(*point, CENTER_LNG, CENTER_LAT)
        self.assertEqual(gr.is_within_radius_sq(sq, 5.0), sq <= 25.0)
        self.assertFalse(gr.is_within_radius_sq(sq, 5.0))

    def test_exact_threshold_squares(self):
        """半径 5/10/20 分别与 25/100/400 比较。"""
        expected = {5.0: 25.0, 10.0: 100.0, 20.0: 400.0}
        for radius, threshold in expected.items():
            point = self._point_at_distance(radius)
            sq = gr.distance_sq_m2(*point, CENTER_LNG, CENTER_LAT)
            self.assertAlmostEqual(sq, threshold, places=6)
            self.assertTrue(gr.is_within_radius_sq(sq, radius, 1e-9))
            self.assertFalse(gr.is_within_radius_sq(sq + 1e-6, radius))

    def test_sq_path_equivalent_to_sqrt_path(self):
        """免开方判定与开方判定结果必须完全一致。"""
        samples = [
            (114.123456, 30.123456),
            (114.123470, 30.123456),
            (114.123456, 30.123480),
            (114.123490, 30.123490),
            (114.123600, 30.123600),
            (114.130000, 30.130000),
        ]
        for radius in gr.RADIUS_PRESETS:
            for lng, lat in samples:
                by_sq = gr.is_within_radius(lng, lat, CENTER_LNG, CENTER_LAT, radius)
                by_sqrt = gr.distance_m(lng, lat, CENTER_LNG, CENTER_LAT) <= radius
                self.assertEqual(by_sq, by_sqrt, f"{(lng, lat)} r={radius}")

    def test_preset_helpers(self):
        near = self._point_at_distance(4.0)
        mid = self._point_at_distance(8.0)
        far = self._point_at_distance(18.0)
        beyond = self._point_at_distance(25.0)

        self.assertTrue(gr.is_within_5m(*near, CENTER_LNG, CENTER_LAT))
        self.assertFalse(gr.is_within_5m(*mid, CENTER_LNG, CENTER_LAT))
        self.assertTrue(gr.is_within_10m(*mid, CENTER_LNG, CENTER_LAT))
        self.assertFalse(gr.is_within_10m(*far, CENTER_LNG, CENTER_LAT))
        self.assertTrue(gr.is_within_20m(*far, CENTER_LNG, CENTER_LAT))
        self.assertFalse(gr.is_within_20m(*beyond, CENTER_LNG, CENTER_LAT))

    def test_zero_radius(self):
        self.assertTrue(gr.is_within_radius(CENTER_LNG, CENTER_LAT, CENTER_LNG, CENTER_LAT, 0))
        self.assertFalse(gr.is_within_radius(114.123457, CENTER_LAT, CENTER_LNG, CENTER_LAT, 0))


class TestValidation(unittest.TestCase):
    def test_rejects_out_of_range(self):
        with self.assertRaises(ValueError):
            gr.distance_m(181.0, 30.0, CENTER_LNG, CENTER_LAT)
        with self.assertRaises(ValueError):
            gr.distance_m(114.0, 91.0, CENTER_LNG, CENTER_LAT)

    def test_rejects_non_numeric(self):
        with self.assertRaises(ValueError):
            gr.distance_m("114.123456°", 30.0, CENTER_LNG, CENTER_LAT)
        with self.assertRaises(ValueError):
            gr.distance_m(None, 30.0, CENTER_LNG, CENTER_LAT)
        with self.assertRaises(ValueError):
            gr.is_within_radius(114.0, 30.0, CENTER_LNG, CENTER_LAT, True)

    def test_rejects_negative_radius(self):
        with self.assertRaises(ValueError):
            gr.is_within_radius(114.0, 30.0, CENTER_LNG, CENTER_LAT, -1)

    def test_accepts_numeric_strings(self):
        self.assertAlmostEqual(
            gr.distance_m("114.123466", "30.123456", CENTER_LNG, CENTER_LAT),
            1e-5 * gr.K_LNG_M_PER_DEG,
            places=6,
        )


class TestCheckPointAndFilter(unittest.TestCase):
    def test_check_point_fields(self):
        result = gr.check_point(114.123470, 30.123456, CENTER_LNG, CENTER_LAT, 5.0)
        self.assertIsInstance(result, gr.RadiusCheckResult)
        self.assertAlmostEqual(result.dx_m, (114.123470 - CENTER_LNG) * gr.K_LNG_M_PER_DEG, places=9)
        self.assertAlmostEqual(result.dy_m, 0.0, places=12)
        self.assertAlmostEqual(result.distance_sq_m2, result.dx_m ** 2, places=9)
        self.assertAlmostEqual(result.threshold_sq_m2, 25.0, places=9)
        self.assertTrue(result.within)
        self.assertEqual(set(result.to_dict()), {
            "lng", "lat", "center_lng", "center_lat", "radius_m", "dx_m", "dy_m",
            "distance_sq_m2", "distance_m", "within", "threshold_sq_m2",
        })

    def test_filter_points_keeps_order_and_payload(self):
        points = [
            ("A", 114.123456, 30.123456),
            ("B", 114.123460, 30.123456),
            ("C", 114.130000, 30.130000),
            ("D", 114.123456, 30.123570),
        ]
        kept = gr.filter_points([(p[1], p[2]) for p in points], CENTER_LNG, CENTER_LAT, 5.0)
        self.assertEqual(len(kept), 2)
        self.assertEqual(kept[0][0], 114.123456)
        self.assertEqual(kept[1][0], 114.123460)

    def test_filter_points_rejects_short_tuple(self):
        with self.assertRaises(ValueError):
            gr.filter_points([(114.123456,)], CENTER_LNG, CENTER_LAT, 5.0)


class TestCli(unittest.TestCase):
    def _run(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = gr.main(argv)
        return code, buffer.getvalue()

    def test_single_point_inside(self):
        code, out = self._run([
            "--center-lng", str(CENTER_LNG), "--center-lat", str(CENTER_LAT),
            "--lng", "114.123458", "--lat", "30.123456", "--radius", "5",
        ])
        self.assertEqual(code, 0)
        self.assertIn("范围内", out)

    def test_single_point_outside(self):
        code, out = self._run([
            "--center-lng", str(CENTER_LNG), "--center-lat", str(CENTER_LAT),
            "--lng", "114.124000", "--lat", "30.123456", "--radius", "5",
        ])
        self.assertEqual(code, 1)
        self.assertIn("范围外", out)

    def test_single_point_json(self):
        code, out = self._run([
            "--center-lng", str(CENTER_LNG), "--center-lat", str(CENTER_LAT),
            "--lng", "114.123458", "--lat", "30.123456", "--radius", "10", "--json",
        ])
        payload = json.loads(out)
        self.assertEqual(code, 0)
        self.assertTrue(payload["within"])
        self.assertAlmostEqual(payload["radius_m"], 10.0)
        self.assertAlmostEqual(payload["threshold_sq_m2"], 100.0)

    def test_file_mode(self):
        content = "# 示例点位\n114.123456,30.123456,中心\n114.123470,30.123456,东14m\n114.130000,30.130000,远处\n\n"
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as handle:
            handle.write(content)
            path = handle.name
        try:
            code, out = self._run([
                "--center-lng", str(CENTER_LNG), "--center-lat", str(CENTER_LAT),
                "--file", path, "--radius", "10", "--json",
            ])
            payload = json.loads(out)
            self.assertEqual(code, 0)
            self.assertEqual(payload["total"], 3)
            self.assertEqual(payload["within"], 2)
            self.assertEqual([r["label"] for r in payload["results"]], ["中心", "东14m", "远处"])
        finally:
            os.unlink(path)

    def test_invalid_args_exit_code_2(self):
        code, _ = self._run([
            "--center-lng", "114.0", "--center-lat", "30.0",
            "--lng", "114.0", "--radius", "-5",
        ])
        self.assertEqual(code, 2)

    def test_missing_lat_exit_code_2(self):
        code, _ = self._run([
            "--center-lng", "114.0", "--center-lat", "30.0", "--lng", "114.0",
        ])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""精度对照：本算法（北纬 30° 修正系数）与 haversine 球面距离的比较。

用法::

    python3 examples/precision_report.py            # 默认中心点 30°N, 114°E
    python3 examples/precision_report.py 30.123456 114.123456

输出各距离、各方向上的绝对误差与相对误差，用于判断该近似是否满足业务精度。
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"))

import geo_radius as gr  # noqa: E402

DISTANCES_M = (5, 10, 20, 50, 100, 200, 500, 1000)
BEARINGS = ("东", "北", "东北")


def point_at(center_lng: float, center_lat: float, meters: float, bearing: str):
    """按指定方向生成与中心点相距 meters 的点（用本算法系数反算，便于对照）。"""
    if bearing == "东":
        return center_lng + meters / gr.K_LNG_M_PER_DEG, center_lat
    if bearing == "北":
        return center_lng, center_lat + meters / gr.K_LAT_M_PER_DEG
    offset = meters / math.sqrt(2.0)
    return (
        center_lng + offset / gr.K_LNG_M_PER_DEG,
        center_lat + offset / gr.K_LAT_M_PER_DEG,
    )


def main() -> int:
    center_lat = float(sys.argv[1]) if len(sys.argv) > 1 else 30.123456
    center_lng = float(sys.argv[2]) if len(sys.argv) > 2 else 114.123456
    print(f"中心点：B0 = {center_lat}°，L0 = {center_lng}°")
    print(f"系数：K_LNG = {gr.K_LNG_M_PER_DEG} m/°，K_LAT = {gr.K_LAT_M_PER_DEG} m/°\n")

    header = f"{'方向':<4} {'目标(m)':>8} {'本算法(m)':>12} {'haversine(m)':>13} {'绝对误差(m)':>12} {'相对误差':>10}"
    print(header)
    print("-" * len(header.encode("gbk", errors="ignore")))

    worst = 0.0
    for bearing in BEARINGS:
        for target in DISTANCES_M:
            lng, lat = point_at(center_lng, center_lat, target, bearing)
            approx = gr.distance_m(lng, lat, center_lng, center_lat)
            ref = gr.haversine_distance_m(lng, lat, center_lng, center_lat)
            abs_err = approx - ref
            rel_err = abs(abs_err) / ref if ref else 0.0
            worst = max(worst, rel_err)
            print(
                f"{bearing:<4} {target:>8.0f} {approx:>12.4f} {ref:>13.4f} "
                f"{abs_err:>12.4f} {rel_err * 100:>9.4f}%"
            )

    print(f"\n最大相对误差：{worst * 100:.4f}%")
    print("说明：误差随距离增大而增大；本近似适用于北纬 30° 附近的短距离判定。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

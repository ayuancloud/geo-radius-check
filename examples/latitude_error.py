#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""系数标定分析：两个系数分别等价于哪个纬度的每度弧长，以及误差随纬度的变化。

- 东西方向：每 1° 经度对应 ``111195.0802 * cos(B0)`` m（111195.0802 = π/180 * 6371008.8）。
- 南北方向：每 1° 纬度对应 WGS-84 子午线弧长级数
  ``M(B0) = 111132.92 - 559.82*cos(2B0) + 1.175*cos(4B0) - 0.0023*cos(6B0)`` m。

用法::

    python3 examples/latitude_error.py
"""

import math

R = 6371008.8
M_PER_DEG_EQUATOR = math.pi / 180.0 * R  # 赤道每度弧长

K_LNG_M_PER_DEG = 96486.25
K_LAT_M_PER_DEG = 110852.42

LATITUDES = (20, 25, 28, 29, 29.5, 30, 30.5, 31, 32, 35, 40, 45, 50)


def meridian_m_per_deg(lat_deg: float) -> float:
    """WGS-84 子午线每度弧长（m）。"""
    c2 = math.cos(2 * math.radians(lat_deg))
    c4 = math.cos(4 * math.radians(lat_deg))
    c6 = math.cos(6 * math.radians(lat_deg))
    return 111132.92 - 559.82 * c2 + 1.175 * c4 - 0.0023 * c6


def parallel_m_per_deg(lat_deg: float) -> float:
    """球面近似下每 1° 经度对应的东西方向弧长（m）。"""
    return M_PER_DEG_EQUATOR * math.cos(math.radians(lat_deg))


def main() -> int:
    print("=== 系数标定 ===")
    print(f"K_LAT = {K_LAT_M_PER_DEG} m/°  vs  M(30°N) = {meridian_m_per_deg(30):.4f} m/°"
          f"  → 差 {K_LAT_M_PER_DEG - meridian_m_per_deg(30):+.6f} m")
    equiv = math.degrees(math.acos(K_LNG_M_PER_DEG / M_PER_DEG_EQUATOR))
    print(f"K_LNG = {K_LNG_M_PER_DEG} m/°  等价于 cos(B0) = {K_LNG_M_PER_DEG / M_PER_DEG_EQUATOR:.6f}"
          f"  →  B0 ≈ {equiv:.3f}°N")
    print("结论：纬度系数即 30°N 处的子午线每度弧长；经度系数对应约 29.8°N 的纬线每度弧长。")

    print("\n=== 误差随纬度变化（正值表示本算法把距离算大了）===")
    print(f"{'纬度':>6} {'东西向相对误差':>16} {'南北向相对误差':>16}")
    for lat in LATITUDES:
        e_lng = K_LNG_M_PER_DEG / parallel_m_per_deg(lat) - 1.0
        e_lat = K_LAT_M_PER_DEG / meridian_m_per_deg(lat) - 1.0
        print(f"{lat:>6.1f} {e_lng * 100:>15.4f}% {e_lat * 100:>15.4f}%")

    print("\n=== 换算成实际距离误差（以半径 20 m 判定为例）===")
    print(f"{'纬度':>6} {'东西向 20m 误差':>18} {'南北向 20m 误差':>18}")
    for lat in (25, 29, 30, 31, 35, 40):
        e_lng = (K_LNG_M_PER_DEG / parallel_m_per_deg(lat) - 1.0) * 20
        e_lat = (K_LAT_M_PER_DEG / meridian_m_per_deg(lat) - 1.0) * 20
        print(f"{lat:>6.1f} {e_lng:>15.3f} m {e_lat:>15.3f} m")

    print("\n提示：若业务点不在北纬 30° 附近，请把系数换成目标纬度 B0 的每度弧长：")
    print("  K_LNG = 111195.0802 * cos(B0)，K_LAT = 111132.92 - 559.82*cos(2B0) + 1.175*cos(4B0) - 0.0023*cos(6B0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

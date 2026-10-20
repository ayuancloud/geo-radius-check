#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""geo_radius —— 北纬 30° 附近短距离经纬度半径判定（可免开方）。

算法（北纬 30° 附近修正系数）::

    d ≈ sqrt( [(L - L0) * 96486.25]^2 + [(B - B0) * 110852.42]^2 )

    (L - L0) * 96486.25  : 东西方向（经度方向）距离，单位 m
    (B - B0) * 110852.42 : 南北方向（纬度方向）距离，单位 m

判定是否在半径 r 内（等于半径时视为范围内）::

    [(L - L0) * 96486.25]^2 + [(B - B0) * 110852.42]^2 <= r^2

半径 5 / 10 / 20 m 时，与 25 / 100 / 400 直接比较即可，无需开平方。

坐标一律使用十进制度数（例如 ``114.123456``），不要填“度、分、秒”。

命令行用法::

    # 单点判定：在 5 m 内返回码 0，否则返回码 1
    python3 geo_radius.py --center-lng 114.123456 --center-lat 30.123456 \
                          --lng 114.123460 --lat 30.123458 --radius 5

    # 批量判定（CSV/空白分隔，每行 "lng,lat[,label]"，# 为注释）
    python3 geo_radius.py --center-lng 114.123456 --center-lat 30.123456 \
                          --file points.csv --radius 10 --json

注意：这是北纬 30° 附近的短距离近似，公式精度不代表原始定位坐标的精度。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

__all__ = [
    "K_LNG_M_PER_DEG",
    "K_LAT_M_PER_DEG",
    "RADIUS_PRESETS",
    "RadiusCheckResult",
    "distance_sq_m2",
    "distance_m",
    "is_within_radius",
    "is_within_radius_sq",
    "check_point",
    "filter_points",
    "haversine_distance_m",
]

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

#: 北纬 30° 附近，每 1° 经度对应的东西方向距离（m）
K_LNG_M_PER_DEG: float = 96486.25

#: 北纬 30° 附近，每 1° 纬度对应的南北方向距离（m）
K_LAT_M_PER_DEG: float = 110852.42

#: 常用半径预设（m）——对应阈值平方 25 / 100 / 400
RADIUS_PRESETS: Tuple[float, ...] = (5.0, 10.0, 20.0)

#: 地球平均半径（m），仅用于 haversine 参考对比，不参与本算法
EARTH_RADIUS_M: float = 6371008.8


# ---------------------------------------------------------------------------
# 校验
# ---------------------------------------------------------------------------


def _as_float(value: object, name: str) -> float:
    """把入参转成 float，失败时抛出可读的 ValueError。"""
    if isinstance(value, bool):
        raise ValueError(f"{name} 必须是数字（十进制度数），收到布尔值 {value!r}")
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError(
            f"{name} 必须是数字（十进制度数，例如 114.123456），收到 {value!r}"
        ) from None


def _check_lng(lng: object) -> float:
    value = _as_float(lng, "经度 L")
    if not math.isfinite(value):
        raise ValueError(f"经度 L 必须是有限数值，收到 {lng!r}")
    if not -180.0 <= value <= 180.0:
        raise ValueError(f"经度 L 超出 [-180, 180]，收到 {value}")
    return value


def _check_lat(lat: object) -> float:
    value = _as_float(lat, "纬度 B")
    if not math.isfinite(value):
        raise ValueError(f"纬度 B 必须是有限数值，收到 {lat!r}")
    if not -90.0 <= value <= 90.0:
        raise ValueError(f"纬度 B 超出 [-90, 90]，收到 {value}")
    return value


def _check_radius(radius_m: object) -> float:
    value = _as_float(radius_m, "半径 r")
    if not math.isfinite(value):
        raise ValueError(f"半径 r 必须是有限数值，收到 {radius_m!r}")
    if value < 0:
        raise ValueError(f"半径 r 不能为负数，收到 {value}")
    return value


def _check_epsilon(epsilon: object) -> float:
    value = _as_float(epsilon, "容差 epsilon")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"容差 epsilon 必须是非负有限数值，收到 {epsilon!r}")
    return value


# ---------------------------------------------------------------------------
# ① 计算两点距离
# ---------------------------------------------------------------------------


def _offsets_m(
    lng: object,
    lat: object,
    center_lng: object,
    center_lat: object,
) -> Tuple[float, float]:
    """返回 (东西方向位移 dx, 南北方向位移 dy)，单位 m。"""
    lng_f, lat_f = _check_lng(lng), _check_lat(lat)
    lng0_f, lat0_f = _check_lng(center_lng), _check_lat(center_lat)
    dx = (lng_f - lng0_f) * K_LNG_M_PER_DEG
    dy = (lat_f - lat0_f) * K_LAT_M_PER_DEG
    return dx, dy


def distance_sq_m2(
    lng: object,
    lat: object,
    center_lng: object,
    center_lat: object,
) -> float:
    """距离的平方（m²），无需开方。

    ``dx² + dy²``，其中 ``dx = (L - L0) * 96486.25``、``dy = (B - B0) * 110852.42``。
    """
    dx, dy = _offsets_m(lng, lat, center_lng, center_lat)
    return dx * dx + dy * dy


def distance_m(
    lng: object,
    lat: object,
    center_lng: object,
    center_lat: object,
) -> float:
    """两点之间的近似水平距离 d，单位 m。"""
    return math.sqrt(distance_sq_m2(lng, lat, center_lng, center_lat))


# ---------------------------------------------------------------------------
# ② / ③ 半径判定（免开方）
# ---------------------------------------------------------------------------


def is_within_radius_sq(
    distance_sq: object,
    radius_m: object,
    epsilon: float = 0.0,
) -> bool:
    """直接用平方值判定：``distance_sq <= r²`` 即在范围内。

    ``epsilon`` 为可选相对容差（默认 0，即严格比较）；判定条件变为
    ``distance_sq <= r² * (1 + epsilon)``，用于吸收坐标浮点往返产生的
    约 1 ulp 误差，使“恰好等于半径”的点稳定落在范围内。
    """
    r = _check_radius(radius_m)
    sq = _as_float(distance_sq, "距离平方 d²")
    if sq < 0:
        raise ValueError(f"距离平方 d² 不能为负数，收到 {sq}")
    return sq <= r * r * (1.0 + _check_epsilon(epsilon))


def is_within_radius(
    lng: object,
    lat: object,
    center_lng: object,
    center_lat: object,
    radius_m: object = 5.0,
    epsilon: float = 0.0,
) -> bool:
    """判断待测点是否在中心点半径 ``radius_m`` 内（等于半径视为范围内）。

    实现走免开方路径：``dx² + dy² <= r²``；``epsilon`` 为可选相对容差（默认 0）。
    """
    r = _check_radius(radius_m)
    sq = distance_sq_m2(lng, lat, center_lng, center_lat)
    return sq <= r * r * (1.0 + _check_epsilon(epsilon))


def is_within_5m(lng: object, lat: object, center_lng: object, center_lat: object) -> bool:
    """中心点半径 5 m 以内（阈值平方 25）。"""
    return is_within_radius(lng, lat, center_lng, center_lat, 5.0)


def is_within_10m(lng: object, lat: object, center_lng: object, center_lat: object) -> bool:
    """中心点半径 10 m 以内（阈值平方 100）。"""
    return is_within_radius(lng, lat, center_lng, center_lat, 10.0)


def is_within_20m(lng: object, lat: object, center_lng: object, center_lat: object) -> bool:
    """中心点半径 20 m 以内（阈值平方 400）。"""
    return is_within_radius(lng, lat, center_lng, center_lat, 20.0)


# ---------------------------------------------------------------------------
# 结构化结果 / 批量
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RadiusCheckResult:
    """一次半径判定的完整结果。"""

    lng: float
    lat: float
    center_lng: float
    center_lat: float
    radius_m: float
    dx_m: float
    dy_m: float
    distance_sq_m2: float
    distance_m: float
    within: bool
    threshold_sq_m2: float

    def to_dict(self) -> dict:
        """转成可直接 json.dumps 的 dict。"""
        return {
            "lng": self.lng,
            "lat": self.lat,
            "center_lng": self.center_lng,
            "center_lat": self.center_lat,
            "radius_m": self.radius_m,
            "dx_m": self.dx_m,
            "dy_m": self.dy_m,
            "distance_sq_m2": self.distance_sq_m2,
            "distance_m": self.distance_m,
            "within": self.within,
            "threshold_sq_m2": self.threshold_sq_m2,
        }


def check_point(
    lng: object,
    lat: object,
    center_lng: object,
    center_lat: object,
    radius_m: object = 5.0,
) -> RadiusCheckResult:
    """判定并返回详细结果（距离、分量位移、阈值平方等）。"""
    dx, dy = _offsets_m(lng, lat, center_lng, center_lat)
    r = _check_radius(radius_m)
    sq = dx * dx + dy * dy
    return RadiusCheckResult(
        lng=_check_lng(lng),
        lat=_check_lat(lat),
        center_lng=_check_lng(center_lng),
        center_lat=_check_lat(center_lat),
        radius_m=r,
        dx_m=dx,
        dy_m=dy,
        distance_sq_m2=sq,
        distance_m=math.sqrt(sq),
        within=sq <= r * r,
        threshold_sq_m2=r * r,
    )


def filter_points(
    points: Iterable[Sequence[object]],
    center_lng: object,
    center_lat: object,
    radius_m: object = 5.0,
) -> List[Sequence[object]]:
    """从 ``[(lng, lat), ...]`` 中筛出落在半径内的点，保持原顺序。"""
    r = _check_radius(radius_m)
    lng0, lat0 = _check_lng(center_lng), _check_lat(center_lat)
    r_sq = r * r
    kept: List[Sequence[object]] = []
    for index, point in enumerate(points):
        if len(point) < 2:
            raise ValueError(f"第 {index} 个点至少需要 (lng, lat) 两个分量，收到 {point!r}")
        dx = (_check_lng(point[0]) - lng0) * K_LNG_M_PER_DEG
        dy = (_check_lat(point[1]) - lat0) * K_LAT_M_PER_DEG
        if dx * dx + dy * dy <= r_sq:
            kept.append(point)
    return kept


# ---------------------------------------------------------------------------
# 参考实现（仅用于对照，不参与判定）
# ---------------------------------------------------------------------------


def haversine_distance_m(
    lng: object,
    lat: object,
    center_lng: object,
    center_lat: object,
) -> float:
    """Haversine 球面距离（m），作为精度对照的参考实现。"""
    lng_f, lat_f = _check_lng(lng), _check_lat(lat)
    lng0_f, lat0_f = _check_lng(center_lng), _check_lat(center_lat)
    phi1, phi2 = math.radians(lat0_f), math.radians(lat_f)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lng_f - lng0_f)
    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


# ---------------------------------------------------------------------------
# 命令行
# ---------------------------------------------------------------------------


def _iter_file_points(path: str, delimiter: str):
    """逐行读取 ``lng,lat[,label]``；忽略空行与 # 注释行。"""
    with open(path, "r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(delimiter) if p.strip() != ""]
            if len(parts) < 2:
                raise ValueError(f"{path} 第 {line_no} 行无法解析为 lng{delimiter}lat：{line!r}")
            label = delimiter.join(parts[2:]) if len(parts) > 2 else ""
            yield line_no, parts[0], parts[1], label


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="geo_radius.py",
        description=(
            "北纬 30° 附近短距离经纬度半径判定（免开方）。"
            "坐标使用十进制度数，例如 114.123456。"
        ),
        epilog=(
            "退出码：0 = 在半径内（单点模式）或全部执行成功（批量模式）；"
            "1 = 不在半径内；2 = 参数或数据错误。"
        ),
    )
    parser.add_argument("--center-lng", required=True, help="中心点经度 L0（十进制度数）")
    parser.add_argument("--center-lat", required=True, help="中心点纬度 B0（十进制度数）")
    parser.add_argument("--radius", type=float, default=5.0, help="目标半径 r，单位 m（默认 5）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")

    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--lng", help="待判断点经度 L（单点模式）")
    target.add_argument("--file", help="批量模式：每行 lng,lat[,label] 的文件路径")

    parser.add_argument("--lat", help="待判断点纬度 B（单点模式，需与 --lng 同时给出）")
    parser.add_argument("--delimiter", default=",", help="批量模式的分隔符（默认逗号）")
    parser.add_argument(
        "--pretty", action="store_true", help="JSON 输出时缩进美化"
    )
    return parser


def _dump(payload: dict, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        center_lng = _check_lng(args.center_lng)
        center_lat = _check_lat(args.center_lat)
        radius = _check_radius(args.radius)
    except ValueError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    # 单点模式
    if args.lng is not None:
        if args.lat is None:
            print("错误：单点模式需要同时提供 --lng 与 --lat", file=sys.stderr)
            return 2
        try:
            result = check_point(args.lng, args.lat, center_lng, center_lat, radius)
        except ValueError as exc:
            print(f"错误：{exc}", file=sys.stderr)
            return 2

        if args.json:
            _dump(result.to_dict(), args.pretty)
        else:
            verdict = "范围内" if result.within else "范围外"
            print(f"d = {result.distance_m:.6f} m    r = {radius:g} m    → {verdict}")
            print(
                f"d² = {result.distance_sq_m2:.6f} m²    阈值 r² = {result.threshold_sq_m2:g} m²"
            )
            print(f"dx = {result.dx_m:.6f} m    dy = {result.dy_m:.6f} m")
        return 0 if result.within else 1

    # 批量模式
    assert args.file is not None
    rows: List[dict] = []
    within_count = 0
    try:
        for line_no, lng_raw, lat_raw, label in _iter_file_points(args.file, args.delimiter):
            result = check_point(lng_raw, lat_raw, center_lng, center_lat, radius)
            within_count += 1 if result.within else 0
            row = result.to_dict()
            row["line"] = line_no
            if label:
                row["label"] = label
            rows.append(row)
    except (OSError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    if args.json:
        _dump(
            {
                "center_lng": center_lng,
                "center_lat": center_lat,
                "radius_m": radius,
                "total": len(rows),
                "within": within_count,
                "results": rows,
            },
            args.pretty,
        )
    else:
        print(f"中心点 ({center_lng}, {center_lat})  半径 {radius:g} m")
        print(f"{'行':>5}  {'经度':>14}  {'纬度':>13}  {'距离(m)':>12}  判定  标签")
        for row in rows:
            verdict = "范围内" if row["within"] else "范围外"
            print(
                f"{row['line']:>5}  {row['lng']:>14.6f}  {row['lat']:>13.6f}  "
                f"{row['distance_m']:>12.3f}  {verdict}  {row.get('label', '')}"
            )
        print(f"合计 {len(rows)} 点，其中 {within_count} 点在半径内")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

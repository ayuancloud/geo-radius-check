import test from 'node:test';
import assert from 'node:assert/strict';

import {
  K_LNG_M_PER_DEG,
  K_LAT_M_PER_DEG,
  RADIUS_PRESETS,
  distanceM,
  distanceSqM2,
  isWithinRadius,
  isWithinRadiusSq,
  isWithin5m,
  isWithin10m,
  isWithin20m,
  checkPoint,
  filterPoints,
  haversineDistanceM,
} from '../geoRadius.js';

const CENTER_LNG = 114.123456;
const CENTER_LAT = 30.123456;

const pointAt = (meters, direction = 'east') =>
  direction === 'east'
    ? [CENTER_LNG + meters / K_LNG_M_PER_DEG, CENTER_LAT]
    : [CENTER_LNG, CENTER_LAT + meters / K_LAT_M_PER_DEG];

const closeTo = (actual, expected, tolerance, message) =>
  assert.ok(
    Math.abs(actual - expected) <= tolerance,
    `${message ?? ''} 期望 ${expected}，实际 ${actual}`,
  );

test('常量与预设阈值', () => {
  assert.equal(K_LNG_M_PER_DEG, 96486.25);
  assert.equal(K_LAT_M_PER_DEG, 110852.42);
  assert.deepEqual([...RADIUS_PRESETS], [5, 10, 20]);
  assert.deepEqual(RADIUS_PRESETS.map((r) => r * r), [25, 100, 400]);
});

test('同点距离为 0', () => {
  assert.equal(distanceM(CENTER_LNG, CENTER_LAT, CENTER_LNG, CENTER_LAT), 0);
});

test('单向位移等于系数乘差值', () => {
  closeTo(distanceM(CENTER_LNG, CENTER_LAT + 1e-5, CENTER_LNG, CENTER_LAT), 1e-5 * K_LAT_M_PER_DEG, 1e-9, '北向');
  closeTo(distanceM(CENTER_LNG + 1e-5, CENTER_LAT, CENTER_LNG, CENTER_LAT), 1e-5 * K_LNG_M_PER_DEG, 1e-9, '东向');
});

test('勾股关系 dx=3, dy=4 => d=5', () => {
  const [lng, lat] = [CENTER_LNG + 3 / K_LNG_M_PER_DEG, CENTER_LAT + 4 / K_LAT_M_PER_DEG];
  closeTo(distanceM(lng, lat, CENTER_LNG, CENTER_LAT), 5, 1e-9, '3-4-5');
  closeTo(distanceSqM2(lng, lat, CENTER_LNG, CENTER_LAT), 25, 1e-9, 'd²');
});

test('等于半径时视为范围内', () => {
  for (const radius of RADIUS_PRESETS) {
    for (const direction of ['east', 'north']) {
      const [lng, lat] = pointAt(radius, direction);
      closeTo(distanceM(lng, lat, CENTER_LNG, CENTER_LAT), radius, 1e-9, `r=${radius}`);
      assert.equal(isWithinRadius(lng, lat, CENTER_LNG, CENTER_LAT, radius, 1e-9), true, `${radius}m ${direction}`);
    }
  }
});

test('半径内外判定', () => {
  for (const radius of RADIUS_PRESETS) {
    const [inLng, inLat] = pointAt(radius * 0.99);
    const [outLng, outLat] = pointAt(radius * 1.01);
    assert.equal(isWithinRadius(inLng, inLat, CENTER_LNG, CENTER_LAT, radius), true);
    assert.equal(isWithinRadius(outLng, outLat, CENTER_LNG, CENTER_LAT, radius), false);
  }
});

test('5/10/20 m 对应 25/100/400', () => {
  const expected = { 5: 25, 10: 100, 20: 400 };
  for (const [radius, threshold] of Object.entries(expected)) {
    const [lng, lat] = pointAt(Number(radius));
    closeTo(distanceSqM2(lng, lat, CENTER_LNG, CENTER_LAT), threshold, 1e-6, `r=${radius}`);
    assert.equal(isWithinRadiusSq(threshold, Number(radius), 1e-9), true);
    assert.equal(isWithinRadiusSq(threshold + 1e-6, Number(radius)), false);
  }
});

test('免开方与开方判定结果一致', () => {
  const samples = [
    [114.123456, 30.123456],
    [114.12347, 30.123456],
    [114.123456, 30.12348],
    [114.12349, 30.12349],
    [114.1236, 30.1236],
    [114.13, 30.13],
  ];
  for (const radius of RADIUS_PRESETS) {
    for (const [lng, lat] of samples) {
      assert.equal(
        isWithinRadius(lng, lat, CENTER_LNG, CENTER_LAT, radius),
        distanceM(lng, lat, CENTER_LNG, CENTER_LAT) <= radius,
      );
    }
  }
});

test('预设半径便捷函数', () => {
  assert.equal(isWithin5m(...pointAt(4), CENTER_LNG, CENTER_LAT), true);
  assert.equal(isWithin5m(...pointAt(8), CENTER_LNG, CENTER_LAT), false);
  assert.equal(isWithin10m(...pointAt(8), CENTER_LNG, CENTER_LAT), true);
  assert.equal(isWithin10m(...pointAt(18), CENTER_LNG, CENTER_LAT), false);
  assert.equal(isWithin20m(...pointAt(18), CENTER_LNG, CENTER_LAT), true);
  assert.equal(isWithin20m(...pointAt(25), CENTER_LNG, CENTER_LAT), false);
});

test('checkPoint 返回完整字段', () => {
  const result = checkPoint(114.12347, 30.123456, CENTER_LNG, CENTER_LAT, 5);
  closeTo(result.dxM, (114.12347 - CENTER_LNG) * K_LNG_M_PER_DEG, 1e-9, 'dx');
  assert.equal(result.dyM, 0);
  closeTo(result.distanceSqM2, result.dxM ** 2, 1e-9, 'd²');
  assert.equal(result.within, true);
  assert.equal(result.thresholdSqM2, 25);
  assert.deepEqual(Object.keys(result).sort(), [
    'centerLat',
    'centerLng',
    'distanceM',
    'distanceSqM2',
    'dxM',
    'dyM',
    'lat',
    'lng',
    'radiusM',
    'thresholdSqM2',
    'within',
  ]);
});

test('filterPoints 保序并保留原对象', () => {
  const points = [
    { id: 'A', lng: 114.123456, lat: 30.123456 },
    { id: 'B', lng: 114.12346, lat: 30.123456 },
    { id: 'C', lng: 114.13, lat: 30.13 },
    { id: 'D', lng: 114.123456, lat: 30.12357 },
  ];
  const kept = filterPoints(points, CENTER_LNG, CENTER_LAT, 5);
  assert.deepEqual(kept.map((p) => p.id), ['A', 'B']);
  assert.equal(kept[0], points[0]);
});

test('参数校验', () => {
  assert.throws(() => distanceM(181, 30, CENTER_LNG, CENTER_LAT), RangeError);
  assert.throws(() => distanceM(114, 91, CENTER_LNG, CENTER_LAT), RangeError);
  assert.throws(() => distanceM('114.123456°', 30, CENTER_LNG, CENTER_LAT), TypeError);
  assert.throws(() => distanceM(null, 30, CENTER_LNG, CENTER_LAT), TypeError);
  assert.throws(() => isWithinRadius(114, 30, CENTER_LNG, CENTER_LAT, -1), RangeError);
  assert.throws(() => isWithinRadiusSq(-1, 5), RangeError);
  assert.throws(() => filterPoints([{ lng: 114 }], CENTER_LNG, CENTER_LAT, 5), TypeError);
});

test('接受数字字符串', () => {
  closeTo(distanceM('114.123466', '30.123456', CENTER_LNG, CENTER_LAT), 1e-5 * K_LNG_M_PER_DEG, 1e-6, '字符串入参');
});

test('与 haversine 参考值误差 < 1%（1 km 内）', () => {
  const cases = [
    [114.123456, 30.124456],
    [114.124456, 30.123456],
    [114.124, 30.124],
    [114.122, 30.122],
  ];
  for (const [lng, lat] of cases) {
    const approx = distanceM(lng, lat, CENTER_LNG, CENTER_LAT);
    const ref = haversineDistanceM(lng, lat, CENTER_LNG, CENTER_LAT);
    assert.ok(Math.abs(approx - ref) / ref < 0.01, `${lng},${lat} 误差过大：${approx} vs ${ref}`);
  }
});

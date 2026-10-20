/**
 * geoRadius —— 北纬 30° 附近短距离经纬度半径判定（可免开方）。
 *
 * 距离公式：
 *   d ≈ sqrt( [(L - L0) * 96486.25]^2 + [(B - B0) * 110852.42]^2 )
 *
 * 半径判定（等于半径视为范围内，走免开方路径）：
 *   [(L - L0) * 96486.25]^2 + [(B - B0) * 110852.42]^2 <= r^2
 *
 * 半径 5 / 10 / 20 m 时，与 25 / 100 / 400 直接比较即可。
 * 坐标一律使用十进制度数（例如 114.123456），不要填“度、分、秒”。
 *
 * 注意：这是北纬 30° 附近的短距离近似，公式精度不代表原始定位坐标的精度。
 *
 * @module geoRadius
 */

/** 北纬 30° 附近，每 1° 经度对应的东西方向距离（m）。 */
export const K_LNG_M_PER_DEG = 96486.25;

/** 北纬 30° 附近，每 1° 纬度对应的南北方向距离（m）。 */
export const K_LAT_M_PER_DEG = 110852.42;

/** 常用半径预设（m）——对应阈值平方 25 / 100 / 400。 */
export const RADIUS_PRESETS = Object.freeze([5, 10, 20]);

/** 地球平均半径（m），仅用于 haversine 参考对比。 */
export const EARTH_RADIUS_M = 6371008.8;

function toNumber(value, name) {
  if (typeof value === 'boolean' || value === null || value === undefined || value === '') {
    throw new TypeError(`${name} 必须是数字（十进制度数，例如 114.123456），收到 ${String(value)}`);
  }
  const num = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(num)) {
    throw new TypeError(`${name} 必须是有限数值，收到 ${String(value)}`);
  }
  return num;
}

function checkLng(lng) {
  const value = toNumber(lng, '经度 L');
  if (value < -180 || value > 180) {
    throw new RangeError(`经度 L 超出 [-180, 180]，收到 ${value}`);
  }
  return value;
}

function checkLat(lat) {
  const value = toNumber(lat, '纬度 B');
  if (value < -90 || value > 90) {
    throw new RangeError(`纬度 B 超出 [-90, 90]，收到 ${value}`);
  }
  return value;
}

function checkRadius(radiusM) {
  const value = toNumber(radiusM, '半径 r');
  if (value < 0) {
    throw new RangeError(`半径 r 不能为负数，收到 ${value}`);
  }
  return value;
}

function checkEpsilon(epsilon) {
  const value = toNumber(epsilon, '容差 epsilon');
  if (value < 0) {
    throw new RangeError(`容差 epsilon 必须是非负数值，收到 ${value}`);
  }
  return value;
}

/** 返回 [东西方向位移 dx, 南北方向位移 dy]，单位 m。 */
function offsetsM(lng, lat, centerLng, centerLat) {
  const dx = (checkLng(lng) - checkLng(centerLng)) * K_LNG_M_PER_DEG;
  const dy = (checkLat(lat) - checkLat(centerLat)) * K_LAT_M_PER_DEG;
  return [dx, dy];
}

/** 距离的平方（m²），无需开方。 */
export function distanceSqM2(lng, lat, centerLng, centerLat) {
  const [dx, dy] = offsetsM(lng, lat, centerLng, centerLat);
  return dx * dx + dy * dy;
}

/** 两点之间的近似水平距离 d，单位 m。 */
export function distanceM(lng, lat, centerLng, centerLat) {
  return Math.sqrt(distanceSqM2(lng, lat, centerLng, centerLat));
}

/** 直接用平方值判定：distanceSq <= r² 即在范围内。 */
export function isWithinRadiusSq(distanceSq, radiusM, epsilon = 0) {
  const r = checkRadius(radiusM);
  const sq = toNumber(distanceSq, '距离平方 d²');
  if (sq < 0) {
    throw new RangeError(`距离平方 d² 不能为负数，收到 ${sq}`);
  }
  return sq <= r * r * (1 + checkEpsilon(epsilon));
}

/**
 * 判断待测点是否在中心点半径 radiusM 内（等于半径视为范围内）。
 * epsilon 为可选相对容差（默认 0，严格比较），用于吸收坐标浮点往返误差。
 */
export function isWithinRadius(lng, lat, centerLng, centerLat, radiusM = 5, epsilon = 0) {
  const r = checkRadius(radiusM);
  return distanceSqM2(lng, lat, centerLng, centerLat) <= r * r * (1 + checkEpsilon(epsilon));
}

/** 中心点半径 5 m 以内（阈值平方 25）。 */
export function isWithin5m(lng, lat, centerLng, centerLat) {
  return isWithinRadius(lng, lat, centerLng, centerLat, 5);
}

/** 中心点半径 10 m 以内（阈值平方 100）。 */
export function isWithin10m(lng, lat, centerLng, centerLat) {
  return isWithinRadius(lng, lat, centerLng, centerLat, 10);
}

/** 中心点半径 20 m 以内（阈值平方 400）。 */
export function isWithin20m(lng, lat, centerLng, centerLat) {
  return isWithinRadius(lng, lat, centerLng, centerLat, 20);
}

/** 判定并返回详细结果。 */
export function checkPoint(lng, lat, centerLng, centerLat, radiusM = 5) {
  const r = checkRadius(radiusM);
  const [dx, dy] = offsetsM(lng, lat, centerLng, centerLat);
  const sq = dx * dx + dy * dy;
  return {
    lng: checkLng(lng),
    lat: checkLat(lat),
    centerLng: checkLng(centerLng),
    centerLat: checkLat(centerLat),
    radiusM: r,
    dxM: dx,
    dyM: dy,
    distanceSqM2: sq,
    distanceM: Math.sqrt(sq),
    within: sq <= r * r,
    thresholdSqM2: r * r,
  };
}

/**
 * 从 [{ lng, lat, ...extra }, ...] 中筛出落在半径内的点，保持原顺序。
 * 返回新数组，元素为原对象引用。
 */
export function filterPoints(points, centerLng, centerLat, radiusM = 5) {
  const r = checkRadius(radiusM);
  const lng0 = checkLng(centerLng);
  const lat0 = checkLat(centerLat);
  const rSq = r * r;
  const kept = [];
  let index = 0;
  for (const point of points) {
    if (!point || typeof point !== 'object') {
      throw new TypeError(`第 ${index} 个点必须是 { lng, lat } 对象，收到 ${String(point)}`);
    }
    const dx = (checkLng(point.lng) - lng0) * K_LNG_M_PER_DEG;
    const dy = (checkLat(point.lat) - lat0) * K_LAT_M_PER_DEG;
    if (dx * dx + dy * dy <= rSq) {
      kept.push(point);
    }
    index += 1;
  }
  return kept;
}

/** Haversine 球面距离（m），仅用于精度对照。 */
export function haversineDistanceM(lng, lat, centerLng, centerLat) {
  const phi1 = (checkLat(centerLat) * Math.PI) / 180;
  const phi2 = (checkLat(lat) * Math.PI) / 180;
  const dPhi = phi2 - phi1;
  const dLambda = ((checkLng(lng) - checkLng(centerLng)) * Math.PI) / 180;
  const a =
    Math.sin(dPhi / 2) ** 2 + Math.cos(phi1) * Math.cos(phi2) * Math.sin(dLambda / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(a)));
}

export default {
  K_LNG_M_PER_DEG,
  K_LAT_M_PER_DEG,
  RADIUS_PRESETS,
  distanceSqM2,
  distanceM,
  isWithinRadius,
  isWithinRadiusSq,
  isWithin5m,
  isWithin10m,
  isWithin20m,
  checkPoint,
  filterPoints,
  haversineDistanceM,
};

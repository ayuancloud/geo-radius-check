# geo-radius-check

按**北纬 30° 附近**的修正系数，用经纬度快速计算两点距离，并判断目标点是否落在中心点的 **5 m / 10 m / 20 m** 半径内。纯数学、零依赖、可免开方判定，适合高频调用（围栏判定、点位校验、签到范围判断等）。

- 公式来源：北纬 30° 附近的短距离平面近似（把经纬度差按每度弧长换算成米，再算欧氏距离）。
- 语言：Python 3.8+ 与 JavaScript（ESM，Node 18+ / 浏览器）各一份等价实现，接口一一对应。
- 判定阈值：半径 5 / 10 / 20 m 对应 **25 / 100 / 400**，无需开平方。

---

## 一、算法

**中心点**：经度 `L0`、纬度 `B0`；**待判断点**：经度 `L`、纬度 `B`。
经纬度均使用**十进制度数**，例如 `114.123456`，不要直接填“度、分、秒”。

### ① 计算两点距离

```
d ≈ sqrt( [ (L - L0) × 96486.25 ]² + [ (B - B0) × 110852.42 ]² )
```

| 项 | 含义 | 单位 |
|---|---|---|
| `(L - L0) × 96486.25` | 东西方向（经度方向）距离 | m |
| `(B - B0) × 110852.42` | 南北方向（纬度方向）距离 | m |
| `d` | 两点之间的近似水平距离 | m |

### ② 判断是否在目标半径内

| 目标范围 | 判断条件 |
|---|---|
| 中心点半径 5 m 以内 | `d ≤ 5` |
| 中心点半径 10 m 以内 | `d ≤ 10` |
| 中心点半径 20 m 以内 | `d ≤ 20` |

等于半径时，视为在范围内。

### ③ 不开平方也可以直接判断

设目标半径为 `r`，只要满足

```
[ (L - L0) × 96486.25 ]² + [ (B - B0) × 110852.42 ]² ≤ r²
```

就判定为范围内。因此半径 5、10、20 m 分别与 **25、100、400** 比较即可。

> 注意：这是北纬 30° 附近的短距离近似，公式精度不代表原始定位坐标的精度。

---

## 二、目录结构

```
geo-radius-check/
├── python/
│   ├── geo_radius.py            # 核心实现 + 命令行（无第三方依赖）
│   └── tests/test_geo_radius.py # unittest 用例（31 项）
├── javascript/
│   ├── geoRadius.js             # ESM 实现（浏览器/Node 通用）
│   ├── package.json
│   └── test/geoRadius.test.js   # node:test 用例（14 项）
├── examples/
│   ├── points.csv               # 批量判定示例数据（lng,lat[,label]）
│   ├── precision_report.py      # 与 haversine 球面距离的精度对照
│   └── latitude_error.py        # 系数标定与误差随纬度变化分析
└── LICENSE
```

---

## 三、快速开始

### 1. Python 作为库

```python
import sys
sys.path.insert(0, "python")

import geo_radius as gr

L0, B0 = 114.123456, 30.123456     # 中心点
L,  B  = 114.123560, 30.123456     # 待判断点

gr.distance_m(L, B, L0, B0)                    # 10.034569...  (m)
gr.distance_sq_m2(L, B, L0, B0)                # 100.692595...  (m²)

gr.is_within_radius(L, B, L0, B0, 10)          # False（10.03 m > 10 m）
gr.is_within_5m(L, B, L0, B0)                  # False
gr.is_within_10m(L, B, L0, B0)                 # False
gr.is_within_20m(L, B, L0, B0)                 # True

r = gr.check_point(L, B, L0, B0, 10)           # 结构化结果
r.distance_m, r.distance_sq_m2, r.threshold_sq_m2, r.within
r.to_dict()                                    # 可直接 json.dumps

gr.filter_points([(114.123456, 30.123456),     # 批量筛出范围内的点
                  (114.130000, 30.130000)],
                 L0, B0, 20)
```

### 2. Python 命令行

```bash
# 单点判定：在半径内退出码 0，否则 1，参数/数据错误 2
python3 python/geo_radius.py --center-lng 114.123456 --center-lat 30.123456 \
                             --lng 114.123560 --lat 30.123456 --radius 10
# d = 10.034570 m    r = 10 m    → 范围外
# d² = 100.692595 m²    阈值 r² = 100 m²
# dx = 10.034570 m    dy = 0.000000 m

# 批量判定（每行 lng,lat[,label]，# 为注释；支持 --json / --pretty / --delimiter）
python3 python/geo_radius.py --center-lng 114.123456 --center-lat 30.123456 \
                             --file examples/points.csv --radius 10
# 中心点 (114.123456, 30.123456)  半径 10 m
#     行              经度             纬度         距离(m)  判定  标签
#     3      114.123456      30.123456         0.000  范围内  中心点 d=0.00m
#     4      114.123460      30.123456         0.386  范围内  东 0.39m
#     5      114.123500      30.123456         4.245  范围内  东 4.25m
#     6      114.123560      30.123456        10.035  范围外  东 10.03m
#     ...
# 合计 8 点，其中 3 点在半径内
```

### 3. JavaScript

```js
import { distanceM, isWithinRadius, isWithin10m, checkPoint, filterPoints } from './javascript/geoRadius.js';

const L0 = 114.123456, B0 = 30.123456;
const L = 114.123560, B = 30.123456;

distanceM(L, B, L0, B0);              // 10.034569...
isWithinRadius(L, B, L0, B0, 10);     // false
isWithin10m(L, B, L0, B0);            // false
checkPoint(L, B, L0, B0, 10).within;  // false

filterPoints([{ lng: L0, lat: B0 }, { lng: 114.13, lat: 30.13 }], L0, B0, 20);
// [{ lng: 114.123456, lat: 30.123456 }]

// 免开方：先算平方再和 r² 比较
import { distanceSqM2 } from './javascript/geoRadius.js';
distanceSqM2(L, B, L0, B0) <= 10 * 10; // false
```

浏览器中直接引入即可（ESM，无构建步骤）：

```html
<script type="module">
  import { isWithinRadius } from './geoRadius.js';
  console.log(isWithinRadius(114.12346, 30.123456, 114.123456, 30.123456, 5));
</script>
```

---

## 四、API 对照

| 功能 | Python | JavaScript |
|---|---|---|
| 距离（m） | `distance_m(lng, lat, center_lng, center_lat)` | `distanceM(lng, lat, centerLng, centerLat)` |
| 距离平方（m²，免开方） | `distance_sq_m2(...)` | `distanceSqM2(...)` |
| 半径判定 | `is_within_radius(..., radius_m=5, epsilon=0)` | `isWithinRadius(..., radiusM=5, epsilon=0)` |
| 用平方值判定 | `is_within_radius_sq(distance_sq, radius_m, epsilon=0)` | `isWithinRadiusSq(distanceSq, radiusM, epsilon=0)` |
| 5 / 10 / 20 m 便捷函数 | `is_within_5m` / `is_within_10m` / `is_within_20m` | `isWithin5m` / `isWithin10m` / `isWithin20m` |
| 详细结果 | `check_point(...)` → `RadiusCheckResult` | `checkPoint(...)` → 普通对象 |
| 批量筛选 | `filter_points(points, ...)` | `filterPoints(points, ...)` |
| 参考实现 | `haversine_distance_m(...)` | `haversineDistanceM(...)` |
| 常量 | `K_LNG_M_PER_DEG`、`K_LAT_M_PER_DEG`、`RADIUS_PRESETS` | `K_LNG_M_PER_DEG`、`K_LAT_M_PER_DEG`、`RADIUS_PRESETS` |

约定与行为：

- 坐标必须是十进制度数；字符串形式的数字（如 `"114.123456"`）会被接受，带单位符号的（如 `"114.123456°"`）会报错。
- 经度超出 `[-180, 180]`、纬度超出 `[-90, 90]`、半径为负，都会抛出错误（Python `ValueError`，JS `RangeError`/`TypeError`）。
- 判定默认是**严格比较**（`epsilon = 0`），与 `≤ r²` 完全一致。
- `epsilon` 为可选**相对容差**：判定条件变为 `d² ≤ r² × (1 + epsilon)`。它用于吸收“坐标反算 → 浮点往返”带来的约 1 ulp 误差，让数学上恰好落在边界上的点稳定判为范围内。实测在 `114°E` 这种较大经度上，`5/96486.25` 的往返误差会让 `d²` 偏大约 `1e-10` 量级，此时取 `epsilon = 1e-9` 即可，不要用它来放宽业务容差。

---

## 五、精度说明

### 1. 两个系数的含义

- **`110852.42`（南北方向）**：正好是 WGS-84 椭球在北纬 30° 处**子午线每度弧长**（级数值 110852.4248 m，差 0.0048 m）。
- **`96486.25`（东西方向）**：等价于北纬约 **29.8°** 处的纬线每度弧长（`96486.25 / 111195.0802 = 0.867720 = cos 29.805°`）。

也就是说，这套系数是“把 30°N 附近 1° 经纬度折算成米”的固定比例，属于**等距圆柱式平面近似**。

### 2. 与 haversine 球面距离的对照

`python3 examples/precision_report.py`（中心点 30.123456°N, 114.123456°E）实测：

| 方向 | 5 m | 10 m | 100 m | 1000 m | 相对误差（恒定） |
|---|---|---|---|---|---|
| 东 | 0.016 m | 0.032 m | 0.320 m | 3.197 m | +0.32% |
| 北 | 0.016 m | 0.031 m | 0.309 m | 3.091 m | −0.31% |
| 东北 | 0.0002 m | 0.0005 m | 0.005 m | 0.064 m | +0.005% |

结论：**相对误差是常数级（约 0.3% 以内），绝对误差随距离线性增长**。判定 5 / 10 / 20 m 半径时，公式带来的距离偏差只有毫米到厘米量级，远小于手机定位本身（民用 GPS 通常 5–10 m 甚至更大）的误差。

### 3. 换成其他纬度会怎样

`python3 examples/latitude_error.py` 实测（正值 = 本算法把距离算大了）：

| 纬度 B0 | 东西向相对误差 | 南北向相对误差 | 20 m 判定时的东西向偏差 |
|---|---|---|---|
| 20° | −7.66% | +0.13% | −1.53 m |
| 25° | −4.26% | +0.07% | −0.85 m |
| 28° | −1.72% | +0.03% | −0.34 m |
| 29° | −0.79% | +0.02% | −0.16 m |
| 30° | +0.20% | −0.00% | +0.04 m |
| 31° | +1.23% | −0.02% | +0.25 m |
| 35° | +5.93% | −0.08% | +1.19 m |
| 40° | +13.27% | −0.16% | +2.66 m |

**适用范围**：北纬 30° 附近（大致 28°–32°）时误差很小；纬度偏离越大，东西方向误差增长越快（因为 `cos B0` 变化剧烈）。若业务点不在 30°N 附近，请把系数换成目标纬度 `B0` 的每度弧长：

```
K_LNG = 111195.0802 × cos(B0)
K_LAT = 111132.92 − 559.82·cos(2B0) + 1.175·cos(4B0) − 0.0023·cos(6B0)   # WGS-84 子午线弧长级数
```

### 4. 使用注意

- **公式精度 ≠ 坐标精度**。这套近似只负责“把经纬度差换算成米”，如果两端坐标来自不同坐标系，误差会远大于公式误差：在中国大陆，WGS-84（GPS 原始）与 GCJ-02（多数在线地图）之间的偏移可达数十至数百米；GCJ-02 与 BD-09 之间还有额外偏移。做围栏判定前务必先统一坐标系。
- 该公式只考虑水平距离，不考虑高程差、地形起伏。
- 判定是“点 vs 点”的几何关系，不考虑定位圆概率误差（CEP）。若业务需要抗抖动，建议先把 `r` 按定位精度做补偿，而不是修改公式。
- 跨 180° 经线、极区、长距离（数十公里以上）场景不适用，请改用 haversine 或 Vincenty / 大地测量库。

---

## 六、运行测试

```bash
# Python（31 项，覆盖公式、边界、免开方等价性、参数校验、CLI）
python3 python/tests/test_geo_radius.py

# JavaScript（14 项，node:test，Node 18+）
cd javascript && npm test        # 等价于 node --test test/
```

测试覆盖的关键性质：同点距离为 0；单向位移等于系数乘差值；`dx=3, dy=4 → d=5`；**恰好等于半径时判为范围内**；`5/10/20 → 25/100/400`；免开方判定与开方判定结果完全一致；与 haversine 参考值的相对误差 < 1%；非法输入（越界、非数字、负半径、带单位符号）正确报错。

---

## 七、常见问题

**为什么要用免开方判定？**
判定只需要比较 `d²` 与 `r²`，省掉一次 `sqrt`。在百万级点位批量筛选时可以省下可观开销；同时避免开方带来的额外浮点舍入。

**为什么半径 5/10/20 对应 25/100/400？**
因为比较的是距离的平方：`5² = 25`、`10² = 100`、`20² = 400`。

**为什么必须用十进制度数？**
公式中的系数单位是“米/度”。如果传入度分秒（例如 `30°07'24.4"`）而不换算，结果会整体错位。

**要不要加容差？**
数学上边界点应判为范围内，但“按米反算回经纬度”再算回来会引入约 1 ulp 浮点误差，使 `d²` 比 `r²` 大出 `1e-10` 量级。若业务中存在“正好等于半径”的点，建议传 `epsilon = 1e-9`。

---

## 八、许可

MIT，见 [LICENSE](LICENSE)。

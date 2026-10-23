---
name: amazon-us-to-mx-listing
description: 亚马逊跨站复制 Listing（US→MX，墨西哥站）。当老板要"把 US 产品复制到 MX / 墨西哥站上传 / US 转 MX / 传这几个 ASIN 到墨西哥"时使用。支持张奥迪、刘冬冬两店（--store 切换）。自动取产品类型、按 MX 公式换算价格（(US 价+5.99)×18−MX$99.99）、Generic 品牌 + GTIN 豁免 + COLOR 变体上传，内置 MX 与 CA/AU 的全部字段差异铁律，开完回验。
---

# 亚马逊跨站复制 Listing（US → MX）

把 US 站 ASIN 自动复制到 MX 站（墨西哥站）上架。**MX 的字段结构与 CA/AU 都不同**，本 skill 的所有坑已固化进脚本默认值，直接跑即可，不要手改公式和字段。

## 触发条件

老板说「复制 listing 到 MX」「US 转 MX」「传这几个 ASIN 到墨西哥站」「把今天新上架传到 MX」等。

## 一键用法

```bash
cd .workbuddy/skills/amazon-us-to-mx-listing/scripts

python run_mx.py B0XXX,B0YYY,B0ZZZ          # 默认张奥迪，给定 US 站 ASIN（逗号分隔）
python run_mx.py --today                    # 自动抓 US 站当天(UTC)新上架
python run_mx.py --today --dry-run          # 只构建+校验，不提交（推荐第一次先用这个）
python run_mx.py --store liudongdong --today    # 指定店铺
```

单组调试：
```bash
python build_mx.py --store liudongdong --parent <US父SKU> --child <US子SKU> [--dry-run|--run]
```

## 多店支持

`--store` 可选 `zhangaodi`（默认）/ `liudongdong`，配置集中在 `scripts/stores.py`。

| 项 | 张奥迪 zhangaodi | 刘冬冬 liudongdong |
|---|---|---|
| 凭证文件 | `sp-api-workbuddy奥迪.txt` | `sp-api-workbuddy刘冬冬.txt` |
| seller | `A1ON6BNVRPOF3T` | `A37KA1V9F4DYXQ` |
| US 品牌 | `EAOEIHD` | **`Generic`** |
| SKU 命名 | 无站点后缀 → **追加 `-mx`** | `-US`/`-us` **替换**为 `-MX`/`-mx` |

⚠️ MX 走 **NA 端点 + 凭证文件第 1 个 refresh_token**（第 0 个是 AU 站）。
⚠️ 两店凭证文件里 seller_id 行**都是空的**，seller_id 必须手抄。

## 完整流程

1. 反查 SKU + PT（`searchListingsItems` 翻页）
2. 父子分组（**listing attributes 的 `parentage_level` + `child_parent_sku_relationship.parent_sku` 权威判断**，不用 catalog relationships）
3. 按 PT 拉 MX schema（自动缓存 `scripts/_mx_schema_<PT>.json`），按 required 做必填校验
4. 构建 MX patch（`build_mx.build`，铁律全固化）
5. 上传（先父后子）
6. 回验（等 90s，逐 SKU 查 ASIN / 状态 / 错误码）

## 铁律（照抄，不要改）

### 一、身份与端点
- seller：张奥迪 `A1ON6BNVRPOF3T` / 刘冬冬 `A37KA1V9F4DYXQ`（MX 与 US 同 seller）。
- MX marketplace = `A1AM78C64UM0Y8`，端点 **NA**（`sellingpartnerapi-na.amazon.com`）。
- token：凭证文件**第 0 个 = AU，第 1 个 = NA(US/CA/MX)**，MX 用第 1 个。

### 二、价格（老板 2026-10-17 定版）
- `target = US 售价 + 5.99`
- **`MX 报价 = round_to_99(target × 18 − MX$99.99)`**（"→.99" = `int(x+0.5) - 0.01`）
- `list_price = 报价 × 1.7`
- 币种 **MXN**
- 实测：US $13.99 → target 19.98 → **MX$259.99 / 划线 MX$441.98**

> ⚠️ 乘数 **18** 是 2026-10-17 老板定版，旧的 **19.5 已作废**（19.5 会算成 MX$289.99，差 30 比索）。
> 恒量在 `build_mx.MX_RATE`，改价只改这一处。

### 三、字段结构（MX 同 AU、不同 CA —— 这条最容易错）
1. **`list_price` 用 `value_with_tax`**（CA 用 `value`）→ 用错报 **99022**。
2. **`purchasable_offer` 无 required、不带 `quantity`**（带了报 90000900 被忽略）。
3. **`merchant_shipping_group` 一律去掉**，让 Amazon 自动分配（US 模板 UUID 不通用，报 90244）。
4. MX schema **无** `manufacturer_contact_information`（AU 也没有，CA 有）。
5. `item_length_width_height.unit` 枚举**仅** `centimeters`。
6. 父体不带 `purchasable_offer` / `list_price` / `fulfillment_availability`（否则 90244 / 99022）。

### 四、品牌与语言
- 品牌 **`Generic`**（⚠️ **不是 `Genérico`** —— 现网实测 zhangaodi MX 全是 Generic）
- `language_tag` = **`es_MX`**
- **标题沿用英语**：现网 MX listing 就是英语标题（如 "Christmas Diamond Art Wreath Kit..."），US 标题**可直接复用，无需翻译**

### 五、条件必填（schema.required 查不到，漏填报 90220）
已固化在 `build_mx.PT_EXTRA_RAW`：

| PT | 必填字段 |
|---|---|
| `FOOD_SLICER` | `number_of_items` / `care_instructions` / `item_length_width_height`（尺寸取 item_name 的「14 x 7 cm」） |
| `PET_APPAREL` / `PET_TOY` / `DESK_PAD` / `ANIMAL_SHELTER` / `PET_BED_MAT` | `warranty_description` = "No warranty"（`PET_TOY` 2026-10-22 补） |
| `BASKETBALL_HOOP` | `warranty_description` = "No warranty" / `import_designation` = "Importado"（尺寸由下方自动换算） |
| `BACKPACK` | `number_of_compartments` = 1（2026-10-22 补；US 侧无此属性） |
| `LINT_REMOVER` | `contains_battery_or_cell` = "cell" / `battery_installation_device_type` = "not_installed" / `has_multiple_battery_powered_components` = false（2026-10-22 补） |
| 通用兜底 | `generic_keyword` 若在 props 里而 US 无值 → 自动取 `item_type_keyword`（连字符转空格，截 50 字），已固化在 `build_mx.build` |

**尺寸字段不同名（2026-10-20 起自动处理）**：MX 只认 `item_depth_width_height`（单位**仅** centimeters），US 是 `item_length_width_height`（多为 inches）。`build_mx._mx_dims()` 自动做 depth←length / width←width / height←height + 英寸→厘米换算，**不要手填**。

**新 PT 报 90220 时**：把缺的字段补进 `PT_EXTRA_RAW`（照 CA 的 `batch_ca.py` 抄，按 MX schema 的 `properties` 白名单过滤）。

### 六、browse node
- `recommended_browse_nodes` **按 PT 动态判断是否必填**（`FOOD_SLICER` 的 MX required 就不含它）。
- 若某 PT 需要，节点是**站点专属的**，必须用 MX 的值，不能套 CA/AU。
- 取法：MX 前台竞品详情页 → Best Sellers Rank 类目链接 `/gp/bestsellers/<dept>/<node>`；或复制站内同 PT 已有 listing 的值。

### 七、通用规则
- `variation_theme` **强制 `COLOR`**（子体名填在 `color.value`）。
  ⚠️ **US 侧主题常是 `ITEM_PACKAGE_QUANTITY`，照抄会导致 MX 子体挂不上父体（报 8801）** ——
  MX 子体的 `item_package_quantity` 多半相同，Amazon 认为「同变体值已被占用」。已在 `build_mx` 里强制改 COLOR。
- **独立 listing（US 侧无 `parentage_level`）绝不能发 `parentage_level`/`child_parent_sku_relationship`**，
  否则 `parent_sku` 为空 → 报 **90253**。`build_mx.build(..., standalone=True)` 已处理。
- **PT 不能信 `summaries.productType`**：部分 listing 返回占位值 `PRODUCT`，提交报 **4000004**。
  真实 PT 取 `items[].productTypes`（`run_mx._real_pt` / `_retry_sku.real_pt` 已处理）。
- 库存 500、处理 2 天、`fulfillment_channel_code` = `DEFAULT`
- `country_of_origin` = `CN`
- `supplier_declared_has_product_identifier_exemption` = `true`（GTIN 豁免）
- 不填 `externally_assigned_product_identifier` / `merchant_suggested_asin`
- `unit_count.type.value` 统一转小写
- 标题去品牌前缀（`stores.BRAND_PREFIXES`）
- 图片跨站直接复用 US CDN URL
- `model_name` / `model_number` 只在 MX schema 认识时才填

## 脚本

| 文件 | 作用 |
|---|---|
| `scripts/stores.py` | 店铺配置（凭证 / seller / token 下标 / 品牌 / SKU 后缀） |
| `scripts/auth.py` | NA 端点 LWA 认证（`set_store()` 切店） |
| `scripts/build_mx.py` | 构建 patch（全部铁律 + PT_EXTRA + schema 驱动裁剪） |
| `scripts/run_mx.py` | 一键入口（反查→分组→上传→回验） |
| `scripts/_retry_group.py` | 修完 `build_mx` 后**只重传某一组**（`--store X --parent <US父SKU> [--with-parent]`），不必重跑全店 |
| `scripts/_retry_sku.py` | **按 US SKU 列表重传（秒级，不翻全店）**，自动判父/子/独立 + 真实 PT，`--force-pt` 可强制 PT。**修完 build_mx 优先用它** |
| `scripts/_verify_mx.py` | 按 SKU 列表回验 ASIN / status / ERROR+WARNING 码 |
| `scripts/_swap_main_img.py` | 主图被判含文字（18027/18320）时，把 US 备选图顶到主图位重传（`--idx 1/2/3`） |

## 常见错误码速查

| 错误码 | 含义 | 处理 |
|---|---|---|
| 99022 | `list_price` 少了 `value_with_tax` | MX 同 AU 必须用 `value_with_tax`，不是 `value` |
| 90000900 | 字段不适用被忽略 | 去掉 `purchasable_offer.quantity`；按 schema 白名单裁字段 |
| 90244 | 模板不适用 / 枚举不合法 | 去掉 `merchant_shipping_group`；**`unit_count.type.value` 枚举不合法也报 90244**（MX 多为 `["unidad"]`，US 的 `Count` 要映射成 `unidad`，映射不上就整条 `unit_count` 不传——已固化在 `build_mx.UNIT_COUNT_MAP`）。⚠️ 无 `enum` 的 PT 也必须映射（2026-10-20 修：以前只在有 enum 时才映射，导致 `Count` 原样发出被拒）。清空 `unit_count` 不行，会转报 90220 必填 |
| 90220 | 条件必填缺失 | 查 `PT_EXTRA_RAW`，补对应 PT 的字段 |
| 8560 / 13013 | 该 PT 的可售 SKU 需真实 UPC | GTIN 豁免对它不生效（已知：`ADVENT_CALENDAR`、`COSMETIC_NAIL_SET`、`DECORATIVE_SIGNAGE`、`BODY_POSITIONER`、`APPENDAGE_WARMER`、`ANIMAL_SHELTER`、`LAUNDRY_HAMPER`、`PILLOW`，2026-10-22 新增 `APPAREL`、`PET_TOY`、`GARLAND`、`PET_APPAREL`、`FUNNEL`、`SLEEPING_BAG`、`SHELF`、`BACKPACK`）→ 后台申请豁免或提供 UPC。父体照样能出 ASIN，只有子体卡住。**注意：子体即使带 13013，ASIN 也可能已分配且状态 DISCOVERABLE，但 offer 挂不上（不可买）**。✅ 反例：`BASKETBALL_HOOP` 2026-10-20 实测 5/5 子体全出 ASIN 且 BUYABLE，**不在**黑名单内（此前记错，实际中招的是同批 `LAUNDRY_HAMPER`；`LAUNDRY_HAMPER` 2026-10-22 实测又能出 ASIN，说明是按属性而非 PT 判定，仍按「需 UPC」处理） |
| 18320 | 主图缺失或不合规（ERROR，但 listing 仍可能 BUYABLE） | 先确认 `main_product_image_locator.media_location` 已写入（多为 CDN 透传成功、Amazon 侧判定图片不合格，如非纯白底/带文字水印）→ 换 US 备选图（`other_product_image_locator_1`）重传，或换素材 |
| 18448 | **WARNING**：缺关键属性（非阻塞，listing 可 BUYABLE） | 只影响搜索/筛选曝光。实测涉及 `PET_TOY`（`pet_toy_type` / `breed_recommendation` / `recommended_uses_for_product`）、`BASKETBALL_HOOP`（`indoor_outdoor_usage`）。要补就在 `PT_EXTRA_RAW` 对应 PT 加这些字段；不补也能卖，不必当失败处理 |
| 100521 | Amazon 合规审核中（非报错） | 等 48h 自动放行，无需重传 |
| 100720 | language_tag 错 | 改 `es_MX` |
| 4000004 | **PT 用了占位值 `PRODUCT`**，Amazon 不支持创建 | `summaries.productType` 不可信，改取 `productTypes`（`_real_pt`）|
| 90253 | 独立 listing 误声明了子体关系（`child_parent_sku_relationship` 无 `parent_sku`）| 独立品走 `standalone=True`，不发 parentage/relationship |
| 8801 | 子体挂不上父体：变体值重复 | 多半是 `variation_theme` 用了 `ITEM_PACKAGE_QUANTITY`。强制 COLOR 后重传父体+子体 |
| 18027 | **ERROR**：主图被判定含文字/logo/水印（比 18320 更严，会拒收）| 用 `_swap_main_img.py --idx 1` 把 US 备选图顶到主图位重传；仍不合格就换素材 |
| 18367 | WARNING：Amazon 自动纠正了 PT（如 `LINT_REMOVER` → `SMALL_HOME_APPLIANCES`）| 非阻塞。**父体要跟着改成同一 PT 重传**，否则变体族对不齐 |
| 8541 | ERROR：标题命中已有 ASIN，但属性对不上 → 既不匹配也不新建 | 需决策：跟卖该 ASIN（offer-only）或改标题/属性做差异 |
| 100730 | ERROR：目录里已有完全相同 listing 正在处理 | 多为同批重复提交；等处理完（隔天）重传即可 |

## 已知限制
- ASIN 由 Amazon 异步分配，**提交当天可能查不到，隔天（约 20h）才出**；判断成功看 `issues` 为空。
- Amazon 可能自动纠正 PT（`18367` warning，如 `AUTO_ACCESSORY` → `STAPLER`），纠正后会转 100521 人工审核（≤48h）。
- 父体不需要价格与库存，回验时父体无价属正常。
- 大店全量翻页（1000+ ASIN）易 read timeout，`auth.request` 已内置 3 次重试。
- 目前只覆盖张奥迪/刘冬冬两店（US→MX 同店）。

## 首次上线验证（2026-10-17）
- `5X-Q1H6-6BP1-mx`（父）+ `4Y-09EZ-02EM-mx`（子，Manual Fat Trimmer）
- 双 ACCEPTED、issues = 0；US $13.99 → MX$259.99 / 划线 MX$441.98
- 隔天回验：子体 ASIN `B0HNCY79TT`，状态 **BUYABLE + DISCOVERABLE**（真可售）

# US→MX 每日复制（18:00 automation）执行记录

## 2026-10-21（21:00）
- 两店**均 0 个 US 新上架**，无上传动作。zhangaodi 近 2/3 天窗口 21 条全为 10-20 那批；liudongdong 近 14 天 13 条，最近一批停在 10-17。两店 listing 全量读取正常（1000 / 569），排除凭证与翻页问题。
- 昨日 21 个 MX SKU 回查：**3 项遗留自行解决** — 74-2RD3-3196 父出 ASIN B0HNPMXYNK；DD-2B7L-M2R1 的 100521 放行转 BUYABLE；QF-L4DT-HY2Y 的 18320 主图错误自动消失。现 8 可售 + 6 父体 = 14 已上线。
- 仍卡 7 个子体 13013+8560（PILLOW 1 / ANIMAL_SHELTER 6），等老板申请类目 UPC 豁免或给真实 UPC。US 侧这些 SKU 是 BUYABLE 的（EAOEIHD 有豁免），但 MX 走 Generic 拿不到。
- 新增发现：WARNING **18448**（缺关键属性，非阻塞但影响搜索曝光）— PET_TOY 缺 pet_toy_type/breed_recommendation/recommended_uses_for_product；BASKETBALL_HOOP 缺 indoor_outdoor_usage。已写入 SKILL.md 速查表，未改代码（要补就在 PT_EXTRA_RAW 加默认值）。
- 报告：`reports/MX-2026-10-21.md`。

## 2026-10-20（21:00 复跑，最终口径）
- zhangaodi：US 当天 21 ASIN → 6 组（PILLOW 1 子 / TOYS_AND_GAMES 1 子 / ANIMAL_SHELTER 3 子 / BASKETBALL_HOOP 5 子 / DRINKING_CUP 2 子 / ANIMAL_SHELTER 3 子）；liudongdong 0（已交叉验证）。
- 21 个全部提交成功；7 个完全可售；5 父体出 ASIN；74-2RD3-3196 父体 ASIN 待出；DD-2B7L-M2R1 100521 审核中。
- 卡点：7 子体 13013+8560（PILLOW 为本轮新增中招 PT，ANIMAL_SHELTER 6 个）→ 需 UPC/类目豁免，等老板。
- 新问题：QF-L4DT-HY2Y-mx 报 18320 主图不合规（图 URL 与 US 同源），需换纯白底主图。
- 修复：`_check_mx_status.py` 的 issues 恒空 bug（tuple 当 dict）；`SKILL.md` 8560 名单加 PILLOW、移除 BASKETBALL_HOOP（今日 5/5 BUYABLE）、新增 18320 行。
- 结论：`unit_count` 无条件映射修复已确证有效——15:50 被 90244 挡住的 5 个 BASKETBALL_HOOP 子体本轮全部 BUYABLE。

## 2026-10-20（15:50 早批，已被 21:00 复跑覆盖）
- zhangaodi：US 当天 11 ASIN → 3 组（DRINKING_CUP / ANIMAL_SHELTER / BASKETBALL_HOOP）；liudongdong 0 个。
- 命中新 PT `BASKETBALL_HOOP` 的 90220（缺 item_depth_width_height / warranty_description / import_designation）→ 已补进 PT_EXTRA_RAW，并新增通用尺寸换算（US 英寸 length_width_height → MX 厘米 depth_width_height）。
- 又发现 unit_count 映射漏洞（无 enum 时未映射 Count→unidad）→ 已改为无条件映射。
- 新增 `_retry_group.py`（单组重传，免全店重扫）。
- 最终：6 个 listing 完全可售；1 子体未创建（13013/8560）；5 个子体 ASIN 已出但 offer 挂不上（13013+90244，需真实 UPC）。
- 结论：`LAUNDRY_HAMPER` 的 unit_count "medida" 白名单无法从 schema 获得，unidad/Unidad/清空均失败 → 归入需 UPC 类问题，等老板申请类目豁免。

## 2026-10-18
- 两店当天（UTC）均 0 个 US 新上架，无上传动作。
- 已交叉验证 0 为真实值（非漏抓）：zhangaodi 近 3 天 52 条、liudongdong 近 3 天 8 条，createdDate DESC 首位均恰为 10-17 那批，索引正常。
- 遗留回查：liudongdong 昨日 8/8 全部出 ASIN 且 DISCOVERABLE（4 个 BUYABLE），100521 审核已放行；zhangaodi 昨日 7 个子体仍因 8560/13013（需真实 UPC）未创建，待老板处理。

## 2026-10-17
- zhangaodi：US 当天新上架 9 ASIN → 2 组（BODY_POSITIONER 3 子 / APPENDAGE_WARMER 4 子）。
  - 首次全部被 90244（unit_count 枚举 Count 不在 MX 白名单）拒 → 修 `build_mx.UNIT_COUNT_MAP`（Count→unidad）后重传 ACCEPTED。
  - 结果：2 个父体出 ASIN（DISCOVERABLE）；7 个子体全部 8560/13013（需真实 UPC）。
- liudongdong：US 当天新上架 8 ASIN → 4 组（HOLE_PUNCH×2 / AUTO_ACCESSORY / JUICER），全部 ACCEPTED。
  - 首次运行 `search_us_listings` read timeout 失败 → auth.request 加 3 次重试后成功。
  - 结果：1 子体出 ASIN；AUTO_ACCESSORY 组 100521 审核中（Amazon 自动改 PT→STAPLER）；其余等隔天出 ASIN。
- 结论沉淀：8560/13013 已知名单新增 BODY_POSITIONER、APPENDAGE_WARMER；100521 属审核非报错；unit_count 枚举映射已固化。

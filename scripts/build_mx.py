# -*- coding: utf-8 -*-
"""US → MX 复制 Listing 的 patch 构建器。

MX 实测口径（2026-10-17）：
  - 品牌 `Generic`（**不是 Genérico**，以现网实测为准）；`language_tag=es_MX`；
    标题**沿用英语**（现网 MX listing 即英语标题，无需翻译）
  - 价格：target = US 价 + 5.99；MX 报价 = target × 18 − MX$99.99 → .99；划线价 = 报价 × 1.7
    ⚠️ 乘数 18 为老板 2026-10-17 定版（原 19.5 作废）
  - 字段结构**同 AU、不同于 CA**：`list_price` 用 `value_with_tax`；`purchasable_offer` 无 required
  - MX schema 无 `manufacturer_contact_information`；`item_length_width_height.unit` 仅 `centimeters`
  - SKU 后缀见 stores.to_mx_sku
"""
import argparse
import gzip
import json
import os
import sys
import time
import urllib.parse
import urllib.request

import auth
import stores

US_FREIGHT = 5.99
MX_FREIGHT = 99.99
MX_RATE = 18              # 老板 2026-10-17 定版：19.5 → 18
LIST_RATE = 1.7          # 划线价 = 报价 × 1.7
LANG = "es_MX"

# MX 的 unit_count.type.value 枚举极少（多为 unidad），US 的 Count/Piece 要映射过来
UNIT_COUNT_MAP = {
    "count": "unidad", "counts": "unidad", "piece": "unidad", "pieces": "unidad",
    "unit": "unidad", "units": "unidad", "pcs": "unidad", "unidad": "unidad",
}

# MX 的「规则型条件必填」字段表（schema.required 查不到，漏填报 90220）
PT_EXTRA_RAW = {
    # FOOD_SLICER 在 MX 条件必填（同 CA/AU）。尺寸取自 item_name「14 x 7 cm」。
    "FOOD_SLICER": {
        "number_of_items": [{"value": 1, "marketplace_id": auth.MX}],
        "item_length_width_height": [{
            "length": {"value": 14, "unit": "centimeters"},
            "width": {"value": 7, "unit": "centimeters"},
            "height": {"value": 2, "unit": "centimeters"},
            "marketplace_id": auth.MX,
        }],
        "care_instructions": [{
            "value": "Hand Wash Only", "language_tag": LANG,
            "marketplace_id": auth.MX}],
    },
    "PET_APPAREL": {
        "warranty_description": [{
            "value": "No warranty", "language_tag": LANG, "marketplace_id": auth.MX}],
    },
    "DESK_PAD": {
        "warranty_description": [{
            "value": "No warranty", "language_tag": LANG, "marketplace_id": auth.MX}],
    },
    "ANIMAL_SHELTER": {
        "warranty_description": [{
            "value": "No warranty", "language_tag": LANG, "marketplace_id": auth.MX}],
    },
    "PET_BED_MAT": {
        "warranty_description": [{
            "value": "No warranty", "language_tag": LANG, "marketplace_id": auth.MX}],
    },
    # PET_TOY 2026-10-22 实测 90220 需 warranty_description
    "PET_TOY": {
        "warranty_description": [{
            "value": "No warranty", "language_tag": LANG, "marketplace_id": auth.MX}],
    },
    # BASKETBALL_HOOP 在 MX 条件必填三项（2026-10-20 实测 90220）。
    # 尺寸 item_depth_width_height 由 _mx_dims() 从 US 的 item_length_width_height 换算，不写死在这里。
    "BASKETBALL_HOOP": {
        "warranty_description": [{
            "value": "No warranty", "language_tag": LANG, "marketplace_id": auth.MX}],
        "import_designation": [{
            "value": "Importado", "language_tag": LANG, "marketplace_id": auth.MX}],
    },
    # BACKPACK 2026-10-22 实测 90220 需 number_of_compartments（US 侧无此属性，默认 1）
    "BACKPACK": {
        "number_of_compartments": [{"value": 1, "marketplace_id": auth.MX}],
    },
    # LINT_REMOVER 在 MX 条件必填电池三件套（2026-10-22 实测 90220）。
    # MX 的 contains_battery_or_cell 枚举只有 battery/cell（没有"无电池"选项），
    # 该品 US 侧 batteries_included=true（模板默认值），故按 "cell" + not_installed 作答最低风险。
    "LINT_REMOVER": {
        "contains_battery_or_cell": [{"value": "cell", "marketplace_id": auth.MX}],
        "battery_installation_device_type": [{
            "value": "not_installed", "marketplace_id": auth.MX}],
        "has_multiple_battery_powered_components": [{
            "value": False, "marketplace_id": auth.MX}],
    },
}

# 尺寸单位换算（MX 的 item_depth_width_height 只认 centimeters）
_TO_CM = {"inches": 2.54, "inch": 2.54, "in": 2.54, "centimeters": 1.0, "cm": 1.0,
          "feet": 30.48, "ft": 30.48, "millimeters": 0.1, "mm": 0.1, "meters": 100.0, "m": 100.0}

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------- schema ----------
def load_mx_schema(pt):
    cache = os.path.join(_SCRIPT_DIR, f"_mx_schema_{pt}.json")
    if os.path.exists(cache):
        try:
            return json.load(open(cache, encoding="utf-8"))
        except Exception:
            pass
    st, r = auth.request("GET", f"/definitions/2020-09-01/productTypes/{pt}?"
                                + urllib.parse.urlencode({"marketplaceIds": auth.MX}))
    if st != 200:
        raise RuntimeError(f"MX schema HTTP {st}: {json.dumps(r, ensure_ascii=False)[:300]}")
    url = (r.get("schema") or {}).get("link", {}).get("resource")
    if not url:
        raise RuntimeError("MX schema 无 link")
    with urllib.request.urlopen(urllib.request.Request(url), context=auth._ctx, timeout=90) as resp:
        raw = resp.read()
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
    sch = json.loads(raw.decode())
    json.dump(sch, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
    return sch


# ---------- listing ----------
def get_us_listing(sku):
    qs = urllib.parse.urlencode({"marketplaceIds": auth.US, "includedData": "attributes,summaries"})
    try:
        st, r = auth.request("GET", f"/listings/2021-08-01/items/{auth.SELLER_ID}/{sku}?{qs}")
    except Exception as e:
        raise RuntimeError(f"GET US {sku} 网络异常：{e}")
    if st != 200:
        hint = "（--parent/--child 要传 US 站的 SKU，不是 ASIN）" if st == 404 else ""
        raise RuntimeError(f"GET US {sku} HTTP {st} {hint}: {json.dumps(r, ensure_ascii=False)[:300]}")
    return r.get("attributes") or {}, (r.get("summaries") or [{}])[0]


def put_listing(sku, patch):
    qs = urllib.parse.urlencode({"marketplaceIds": auth.MX})
    return auth.request("PUT", f"/listings/2021-08-01/items/{auth.SELLER_ID}/{sku}?{qs}", patch)


# ---------- 价格 ----------
def round_to_99(x):
    return round(int(x + 0.5) - 0.01 + 0.0, 2)


def calc_mx_price(us_price):
    """MX 报价 = (US 价 + 5.99) × 18 − 99.99，四舍五入到 .99；划线 = 报价 × 1.7。"""
    target = us_price + US_FREIGHT
    offer = round_to_99(target * MX_RATE - MX_FREIGHT)
    return target, offer, round(offer * LIST_RATE, 2)


# ---------- 构建 ----------
def retag(value):
    if isinstance(value, list):
        return [retag(v) for v in value]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k == "marketplace_id":
                out[k] = auth.MX
            elif k == "language_tag":
                out[k] = LANG
            else:
                out[k] = retag(v)
        return out
    return value


def _dim_cm(d):
    """单个维度 → 厘米（保留 1 位）。无法换算返回 None。"""
    if not isinstance(d, dict):
        return None
    v, u = d.get("value"), (d.get("unit") or "").strip().lower()
    if not isinstance(v, (int, float)):
        return None
    f = _TO_CM.get(u)
    return None if f is None else round(float(v) * f, 1)


def _mx_dims(attrs, props):
    """MX 用 item_depth_width_height（仅 centimeters），US 用 item_length_width_height。
    映射 depth←length / width←width / height←height，并做英寸→厘米换算。"""
    if "item_depth_width_height" not in props:
        return None
    src = (attrs.get("item_length_width_height") or [None])[0]
    if not isinstance(src, dict):
        return None
    dep, wid, hei = _dim_cm(src.get("length")), _dim_cm(src.get("width")), _dim_cm(src.get("height"))
    if None in (dep, wid, hei) or min(dep, wid, hei) <= 0:
        return None
    return [{
        "depth": {"value": dep, "unit": "centimeters"},
        "width": {"value": wid, "unit": "centimeters"},
        "height": {"value": hei, "unit": "centimeters"},
        "marketplace_id": auth.MX,
    }]


def build(attrs, us_price, sku_mx, is_parent, pt, props, required,
          parent_sku_mx=None, browse_node=None, standalone=False):
    a = {k: retag(v) for k, v in attrs.items() if k in props}
    dropped = sorted(set(attrs.keys()) - set(props))

    a["brand"] = [{"value": "Generic", "language_tag": LANG, "marketplace_id": auth.MX}]
    mfr = a.get("manufacturer")
    if not mfr or not any(x.get("value") for x in mfr if isinstance(x, dict)):
        a["manufacturer"] = [{"value": "Generic", "language_tag": LANG, "marketplace_id": auth.MX}]

    name = (attrs.get("item_name") or [{}])[0].get("value", "")
    a["item_name"] = [{"value": stores.strip_brand(name), "language_tag": LANG, "marketplace_id": auth.MX}]
    a["country_of_origin"] = [{"value": "CN", "marketplace_id": auth.MX}]
    a["supplier_declared_has_product_identifier_exemption"] = [{"value": True, "marketplace_id": auth.MX}]
    a["batteries_required"] = [{"value": False, "marketplace_id": auth.MX}]

    if "model_name" in props:
        a["model_name"] = [{"value": sku_mx, "marketplace_id": auth.MX}]
    else:
        a.pop("model_name", None)
    if "model_number" in props:
        a["model_number"] = [{"value": sku_mx, "marketplace_id": auth.MX}]
    else:
        a.pop("model_number", None)

    a.pop("externally_assigned_product_identifier", None)
    a.pop("merchant_suggested_asin", None)
    a.pop("merchant_shipping_group", None)      # 各站模板不通用，让 Amazon 自动分配

    # 枚举大小写 + 枚举白名单校验（US 的 Count 在 MX 只认 unidad，否则 90244）
    if "unit_count" in a:
        enum = ((((props.get("unit_count") or {}).get("items") or {}).get("properties") or {})
                .get("type") or {}).get("properties", {}).get("value", {}).get("enum")
        bad = False
        for uc in a["unit_count"] or []:
            t = uc.get("type")
            if isinstance(t, dict) and isinstance(t.get("value"), str):
                # 无 enum 的 PT 也照样要映射：MX 不认 US 的 "Count"（报 90244）
                v = UNIT_COUNT_MAP.get(t["value"].strip().lower())
                if v is None:
                    bad = True          # 映射不上就不传，unit_count 非必填
                    continue
                if enum and v not in enum:
                    bad = True
                    continue
                t["value"] = v
        if bad:
            a.pop("unit_count", None)

    # MX 尺寸字段与 US 不同名：item_length_width_height → item_depth_width_height
    if "item_depth_width_height" in props and "item_depth_width_height" not in a:
        dims = _mx_dims(attrs, props)
        if dims:
            a["item_depth_width_height"] = dims

    if is_parent:
        a.pop("color", None)
        a["parentage_level"] = [{"value": "parent", "marketplace_id": auth.MX}]
        a["child_parent_sku_relationship"] = [{"child_relationship_type": "variation",
                                              "marketplace_id": auth.MX}]
        # 父体不带价格/库存（否则 90244 / 99022）
        a.pop("purchasable_offer", None)
        a.pop("list_price", None)
        a.pop("fulfillment_availability", None)
    else:
        target, offer, listp = us_price
        a["purchasable_offer"] = [{
            "currency": "MXN", "audience": "ALL",
            "our_price": [{"schedule": [{"value_with_tax": offer}]}],
            "marketplace_id": auth.MX,
        }]
        a["list_price"] = [{"currency": "MXN", "value_with_tax": listp, "marketplace_id": auth.MX}]
        a["fulfillment_availability"] = [{
            "fulfillment_channel_code": "DEFAULT", "quantity": 500,
            "lead_time_to_ship_max_days": 2, "marketplace_id": auth.MX,
        }]
        a["parentage_level"] = [{"value": "child", "marketplace_id": auth.MX}]
        a["child_parent_sku_relationship"] = [{
            "child_relationship_type": "variation", "parent_sku": parent_sku_mx,
            "marketplace_id": auth.MX}]

    # 真独立 listing（US 侧无 parentage_level）：不能声明 child，parent_sku 为空会报 90253
    if standalone and not is_parent:
        a.pop("parentage_level", None)
        a.pop("child_parent_sku_relationship", None)

    # 变体主题铁律 = COLOR。US 侧常是 ITEM_PACKAGE_QUANTITY，而 MX 子体的
    # item_package_quantity 往往相同 → 绑定时报 8801「子体无法挂到父体」。
    if not standalone and "variation_theme" in props and "variation_theme" in a:
        nm = (((props["variation_theme"].get("items") or {}).get("properties") or {})
              .get("name") or {})
        enum = nm.get("enum") or []
        dep = (nm.get("$lifecycle") or {}).get("enumDeprecated") or []
        if (not enum or "COLOR" in enum) and "COLOR" not in dep:
            a["variation_theme"] = [{"name": "COLOR"}]

    # generic_keyword：MX 部分 PT 条件必填（90220），用 US item_type_keyword 兜底生成
    if "generic_keyword" in props and not a.get("generic_keyword"):
        kw = ((attrs.get("item_type_keyword") or [{}])[0].get("value") or "").replace("-", " ").strip()
        if not kw:
            kw = " ".join(name.split()[:5])
        if kw:
            a["generic_keyword"] = [{"value": kw[:50], "language_tag": LANG,
                                     "marketplace_id": auth.MX}]

    # 规则型条件必填（按 schema 白名单过滤）
    for k, v in PT_EXTRA_RAW.get(pt, {}).items():
        if k in props:
            a[k] = v

    if browse_node:
        a["recommended_browse_nodes"] = [{"value": str(browse_node), "marketplace_id": auth.MX}]

    missing = [k for k in required if k not in a]
    return a, dropped, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parent", required=True, help="US 站父 SKU（不是 ASIN）")
    ap.add_argument("--child", required=True, help="US 站子 SKU（不是 ASIN）")
    ap.add_argument("--store", default=stores.DEFAULT_STORE, choices=list(stores.STORES))
    ap.add_argument("--browse-node", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--run", action="store_true")
    args = ap.parse_args()

    auth.set_store(args.store)
    parent_mx = stores.to_mx_sku(args.parent, args.store)
    child_mx = stores.to_mx_sku(args.child, args.store)
    print(f"店铺={args.store} | US seller={auth.SELLER_ID}")
    print(f"SKU 映射：{args.parent} → {parent_mx} ；{args.child} → {child_mx}")

    pattrs, psum = get_us_listing(args.parent)
    pt = psum.get("productType")
    sch = load_mx_schema(pt)
    props = sch.get("properties") or {}
    req = sch.get("required") or []
    print(f"PT={pt} | MX required={req} | 属性 {len(props)}")

    pd, pdrop, pmiss = build(pattrs, None, parent_mx, True, pt, props, req, browse_node=args.browse_node)
    print(f"[父] {parent_mx} 剔除={pdrop} 缺必填={pmiss}")

    cattrs, csum = get_us_listing(args.child)
    us_price = cattrs["purchasable_offer"][0]["our_price"][0]["schedule"][0]["value_with_tax"]
    t, o, l = calc_mx_price(us_price)
    print(f"[子] {args.child} ASIN={csum.get('asin')} US${us_price} → target {t} × {MX_RATE} − {MX_FREIGHT} "
          f"→ MX${o} / 划线 MX${l}")
    cd, cdrop, cmiss = build(cattrs, (t, o, l), child_mx, False, pt, props, req, parent_mx, args.browse_node)
    print(f"[子] {child_mx} 剔除={cdrop} 缺必填={cmiss}")

    if pmiss or cmiss:
        print("⚠️ 必填缺失，不提交:", pmiss, cmiss)
        return

    json.dump({"parent": pd, "child": cd}, open("_mx_payload.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    if args.run:
        print("\n--- 提交 ---")
        st, r = put_listing(parent_mx, {"productType": pt, "requirements": "LISTING", "attributes": pd})
        print(f"[父] {parent_mx} → HTTP {st} {r.get('status') if isinstance(r, dict) else r}")
        time.sleep(2)
        st2, r2 = put_listing(child_mx, {"productType": pt, "requirements": "LISTING", "attributes": cd})
        print(f"[子] {child_mx} → HTTP {st2} {r2.get('status') if isinstance(r2, dict) else r2}")
        for tag, rr in (("父", r), ("子", r2)):
            if isinstance(rr, dict):
                for i in (rr.get("issues") or []):
                    print(f"   [{tag}][{i.get('severity')}] {i.get('code')} "
                          f"{i.get('attributeNames')} {(i.get('message') or '')[:140]}")
        json.dump({"parent": r, "child": r2}, open("_mx_put_result.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()

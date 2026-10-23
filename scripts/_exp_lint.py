# -*- coding: utf-8 -*-
"""实验：LINT_REMOVER 子体 90220 电池字段的解法探针。
在当前 patch 上做不同变体后 PUT，观察 issues 变化。
用法: python _exp_lint.py --store zhangaodi --sku WBXZ-261022-FUR-1PC
"""
import argparse
import json

import auth
import build_mx as bm
import stores


def run(tag, patch, sku_mx):
    st, r = bm.put_listing(sku_mx, {"productType": patch["pt"],
                                    "requirements": "LISTING",
                                    "attributes": patch["attrs"]})
    errs = [(i.get("code"), i.get("attributeNames")) for i in (r.get("issues") or [])
            if i.get("severity") == "ERROR"]
    print(f"[{tag}] HTTP {st} status={r.get('status')} errs={errs}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=stores.DEFAULT_STORE, choices=list(stores.STORES))
    ap.add_argument("--sku", required=True)
    a = ap.parse_args()
    auth.set_store(a.store)
    sku_mx = stores.to_mx_sku(a.sku, a.store)
    attrs, summ = bm.get_us_listing(a.sku)
    pt = summ.get("productType")
    sch = bm.load_mx_schema(pt)
    props, req = sch.get("properties") or {}, sch.get("required") or []
    us_price = attrs["purchasable_offer"][0]["our_price"][0]["schedule"][0]["value_with_tax"]
    t, o, l = bm.calc_mx_price(us_price)
    base, _, _ = bm.build(attrs, (t, o, l), sku_mx, False, pt, props, req, None)

    # A: 去掉 batteries_required，不填电池族
    A = dict(base); A.pop("batteries_required", None)
    A["generic_keyword"] = [{"value": "lint remover", "language_tag": "es_MX",
                             "marketplace_id": auth.MX}]
    run("A 去batteries_required+generic_keyword", {"pt": pt, "attrs": A}, sku_mx)

    # B: 保留 batteries_required=false，补齐三项电池字段
    B = dict(base)
    B["contains_battery_or_cell"] = [{"value": "cell", "marketplace_id": auth.MX}]
    B["battery_installation_device_type"] = [{"value": "not_installed", "marketplace_id": auth.MX}]
    B["has_multiple_battery_powered_components"] = [{"value": False, "marketplace_id": auth.MX}]
    B["generic_keyword"] = [{"value": "lint remover", "language_tag": "es_MX",
                             "marketplace_id": auth.MX}]
    run("B 补三项电池+generic_keyword", {"pt": pt, "attrs": B}, sku_mx)


if __name__ == "__main__":
    main()

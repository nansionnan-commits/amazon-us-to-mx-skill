# -*- coding: utf-8 -*-
"""诊断：对指定 US SKU（独立可售）重建 MX patch 并试提交，打印全部 issues。
用法: python _diag_invalid.py --store zhangaodi --sku WBXZ-261022-FCT [--no-put]
"""
import argparse
import json
import sys

import auth
import build_mx as bm
import stores


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=stores.DEFAULT_STORE, choices=list(stores.STORES))
    ap.add_argument("--sku", required=True, help="US 站 SKU")
    ap.add_argument("--no-put", action="store_true")
    a = ap.parse_args()

    auth.set_store(a.store)
    sku_mx = stores.to_mx_sku(a.sku, a.store)
    attrs, summ = bm.get_us_listing(a.sku)
    pt = summ.get("productType")
    sch = bm.load_mx_schema(pt)
    props, req = sch.get("properties") or {}, sch.get("required") or []
    print(f"store={a.store} PT={pt} SKU={a.sku} -> {sku_mx}")
    print(f"MX required={req}")
    print(f"US attrs keys = {sorted(attrs.keys())}")

    us_price = attrs["purchasable_offer"][0]["our_price"][0]["schedule"][0]["value_with_tax"]
    t, o, l = bm.calc_mx_price(us_price)
    print(f"US${us_price} -> target {t} -> MX${o} / 划线 MX${l}")

    pd, drop, miss = bm.build(attrs, (t, o, l), sku_mx, False, pt, props, req, None)
    print(f"剔除={drop}\n缺必填={miss}")
    print("payload keys =", sorted(pd.keys()))
    json.dump({"productType": pt, "requirements": "LISTING", "attributes": pd},
              open(f"_diag_{a.sku}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    if a.no_put:
        return
    st, r = bm.put_listing(sku_mx, {"productType": pt, "requirements": "LISTING", "attributes": pd})
    print(f"\nPUT -> HTTP {st} status={r.get('status') if isinstance(r, dict) else r}")
    for i in (r.get("issues") or []) if isinstance(r, dict) else []:
        print(f"  [{i.get('severity')}] {i.get('code')} attr={i.get('attributeNames')} :: "
              f"{(i.get('message') or '')[:220]}")


if __name__ == "__main__":
    main()

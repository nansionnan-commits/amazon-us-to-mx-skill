# -*- coding: utf-8 -*-
"""对某个 US 父 SKU 的整组变体重传 MX（失败后修 build_mx 再跑这个，不用重跑全店）。

用法：
  python _retry_group.py --store zhangaodi --parent 5G-NPP0-EOUV
  python _retry_group.py --store zhangaodi --parent 5G-NPP0-EOUV --with-parent
  python _retry_group.py --store zhangaodi --parent 5G-NPP0-EOUV --dry-run

子体 PUT 是 upsert：404（从未创建）与已 ACCEPTED 的再次提交都安全。
"""
import argparse
import time
import urllib.parse

import auth
import build_mx as bm
import stores


def find_children(parent_sku):
    """父 SKU → 父 ASIN → catalog relationships 取子 ASIN → 映射回子 SKU。"""
    qs = urllib.parse.urlencode({"marketplaceIds": auth.US, "includedData": "summaries"})
    st, r = auth.request("GET", f"/listings/2021-08-01/items/{auth.SELLER_ID}/{parent_sku}?{qs}")
    if st != 200:
        raise RuntimeError(f"GET 父 {parent_sku} HTTP {st}")
    par_asin = ((r.get("summaries") or [{}])[0]).get("asin")
    qs2 = urllib.parse.urlencode({"marketplaceIds": auth.US, "includedData": "relationships"})
    st2, r2 = auth.request("GET", f"/catalog/2022-04-01/items/{par_asin}?{qs2}")
    child_asins = []
    if st2 == 200:
        for mp in r2.get("relationships", []):
            for rel in mp.get("relationships", []):
                if rel.get("type") == "VARIATION":
                    child_asins += rel.get("childAsins") or []
    # ASIN → SKU
    out, token = [], None
    want = set(child_asins)
    while want:
        params = {"marketplaceIds": auth.US, "pageSize": 20, "includedData": "summaries"}
        if token:
            params["pageToken"] = token
        st3, r3 = auth.request("GET", f"/listings/2021-08-01/items/{auth.SELLER_ID}?"
                                     + urllib.parse.urlencode(params))
        if st3 != 200:
            break
        for it in r3.get("items", []):
            a = ((it.get("summaries") or [{}])[0]).get("asin")
            if a in want:
                out.append(it["sku"])
                want.discard(a)
        token = (r3.get("pagination") or {}).get("nextToken")
        if not token:
            break
    return par_asin, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True, choices=list(stores.STORES))
    ap.add_argument("--parent", required=True, help="US 站父 SKU")
    ap.add_argument("--with-parent", action="store_true", help="连父体一起重传")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    auth.set_store(args.store)
    parent_mx = stores.to_mx_sku(args.parent, args.store)
    pattrs, psum = bm.get_us_listing(args.parent)
    pt = psum.get("productType")
    sch = bm.load_mx_schema(pt)
    props, req = sch.get("properties") or {}, sch.get("required") or []
    print(f"店铺={args.store} PT={pt} 父 {args.parent} → {parent_mx}")

    if args.with_parent:
        pd, _, pmiss = bm.build(pattrs, None, parent_mx, True, pt, props, req)
        if not args.dry_run:
            st, r = bm.put_listing(parent_mx, {"productType": pt, "requirements": "LISTING",
                                               "attributes": pd})
            print(f"[父] PUT {parent_mx} → HTTP {st} {r.get('status') if isinstance(r, dict) else r}")
            time.sleep(2)
        else:
            print(f"[父] dry-run 缺必填={pmiss}")

    par_asin, children = find_children(args.parent)
    print(f"父 ASIN={par_asin} 子体 {len(children)} 个: {children}")

    for csku in children:
        csku_mx = stores.to_mx_sku(csku, args.store)
        cattrs, csum = bm.get_us_listing(csku)
        try:
            us_price = cattrs["purchasable_offer"][0]["our_price"][0]["schedule"][0]["value_with_tax"]
        except Exception as e:
            print(f"[子] {csku_mx} 读源价失败 {e}")
            continue
        t, o, l = bm.calc_mx_price(us_price)
        cd, cdrop, cmiss = bm.build(cattrs, (t, o, l), csku_mx, False, pt, props, req, parent_mx)
        print(f"[子] {csku_mx} US${us_price} → MX${o}/划线 MX${l} 缺必填={cmiss}")
        if cmiss:
            continue
        if args.dry_run:
            continue
        st, r = bm.put_listing(csku_mx, {"productType": pt, "requirements": "LISTING", "attributes": cd})
        print(f"  PUT → HTTP {st} {r.get('status') if isinstance(r, dict) else r}")
        for i in (r.get("issues") or []) if isinstance(r, dict) else []:
            if i.get("severity") == "ERROR":
                print(f"   ❌ {i.get('code')} {i.get('attributeNames')} {(i.get('message') or '')[:120]}")
        time.sleep(1.2)


if __name__ == "__main__":
    main()

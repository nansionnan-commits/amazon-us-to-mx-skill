# -*- coding: utf-8 -*-
"""逐 SKU 回验 MX 状态（ASIN / status / ERROR 码 + WARNING 码）。
用法: python _verify_mx.py --store zhangaodi SKU1,SKU2,...
"""
import argparse
import time
import urllib.parse

import auth
import stores


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=stores.DEFAULT_STORE, choices=list(stores.STORES))
    ap.add_argument("skus")
    a = ap.parse_args()
    auth.set_store(a.store)
    print(f"{'MX SKU':<30} {'ASIN':<13} {'STATUS':<26} ERR / WARN")
    for sku in [x.strip() for x in a.skus.split(",") if x.strip()]:
        qs = urllib.parse.urlencode({"marketplaceIds": auth.MX,
                                     "includedData": "summaries,issues",
                                     "issueLocale": "es_MX"})
        st, r = auth.request("GET", f"/listings/2021-08-01/items/{auth.SELLER_ID}/{sku}?{qs}")
        if st != 200 or not isinstance(r, dict):
            print(f"{sku:<30} {'-':<13} {'HTTP'+str(st):<26}")
            continue
        s = (r.get("summaries") or [{}])[0]
        errs = sorted({i.get("code") for i in (r.get("issues") or []) if i.get("severity") == "ERROR"})
        warns = sorted({i.get("code") for i in (r.get("issues") or []) if i.get("severity") == "WARNING"})
        status = ",".join(s.get("status") or []) or "-"
        print(f"{sku:<30} {str(s.get('asin') or '-'):<13} {status:<26} E={errs} W={warns}")
        time.sleep(0.4)


if __name__ == "__main__":
    main()

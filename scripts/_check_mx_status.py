# -*- coding: utf-8 -*-
"""回查昨日（及近期）已上传的 MX SKU 当前状态，用于遗留问题跟踪。
用法：python _check_mx_status.py <store> <US_SKU1,US_SKU2,...>
"""
import sys
import urllib.parse

import auth
import stores


def verify(sku):
    qs = urllib.parse.urlencode({"marketplaceIds": auth.MX, "includedData": "summaries,issues",
                                 "issueLocale": "es_MX"})
    try:
        st, r = auth.request("GET", f"/listings/2021-08-01/items/{auth.SELLER_ID}/{sku}?{qs}")
    except Exception as e:
        return None, f"EXC {e}", {}
    if st != 200:
        return None, f"HTTP {st}", {}
    summ = (r.get("summaries") or [{}])[0]
    codes = {}
    msgs = {}
    for i in (r.get("issues") or []):
        sev = i.get("severity")
        c = i.get("code")
        codes[f"{sev}:{c}"] = codes.get(f"{sev}:{c}", 0) + 1
        msgs.setdefault(f"{sev}:{c}", (i.get("message") or "")[:100])
    return summ.get("asin"), (summ.get("status"), summ.get("productType")), (codes, msgs)


def main():
    store = sys.argv[1]
    us_skus = [s for s in sys.argv[2].split(",") if s.strip()]
    auth.set_store(store)
    print(f"店={store} MX seller={auth.SELLER_ID}")
    for us in us_skus:
        mx = stores.to_mx_sku(us, store)
        asin, info, extra = verify(mx)
        stt, pt = (info if isinstance(info, tuple) else (info, ""))
        stt = ",".join(stt) if isinstance(stt, list) else str(stt)
        # extra = (codes, msgs)；此前误判 extra 为 dict，导致 issues 永远打印成 {}
        codes, msgs = extra if isinstance(extra, tuple) else ({}, {})
        print(f"{mx:<26} ASIN={str(asin):<12} PT={str(pt):<18} 状态={stt:<30} {codes}")
        for k, m in msgs.items():
            print(f"    {k}  {m}")


if __name__ == "__main__":
    main()

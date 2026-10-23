# -*- coding: utf-8 -*-
"""亚马逊跨站复制 Listing 一键入口（US → MX，同店）。

用法：
  python run_mx.py B0XXX,B0YYY,B0ZZZ        给定 US 站 ASIN（逗号分隔，可含父/子/独立）
  python run_mx.py --today                  自动抓 US 站当天(UTC)新上架
  python run_mx.py --today --dry-run        只构建+校验，不提交（推荐）
  python run_mx.py --store liudongdong --today   指定店铺（默认 zhangaodi）

流程：反查 SKU/PT → 父子分组（attributes 权威）→ 构建 MX patch → 上传(先父后子) → 回验
铁律见 SKILL.md；脚本默认值已按铁律设置，**不要**手改价格公式/字段结构。
"""
import json
import sys
import time
import urllib.parse
from datetime import datetime, timezone

import auth
import build_mx as bm
import stores


# ---------- 1. 反查 US 站 listing ----------
def _real_pt(item, summ):
    """summaries.productType 对部分 listing 返回占位值 PRODUCT（不可创建），
    真实 PT 要以 items[].productTypes 为准。"""
    for p in (item.get("productTypes") or []):
        if p.get("marketplaceId") == auth.US and p.get("productType"):
            return p["productType"]
    return summ.get("productType")


def search_us_listings():
    asin2sku, sku2pt = {}, {}
    token = None
    while True:
        params = {"marketplaceIds": auth.US, "pageSize": 20,
                  "includedData": "summaries,productTypes",
                  "sortBy": "createdDate", "sortOrder": "DESC"}
        if token:
            params["pageToken"] = token
        st, r = auth.request("GET", f"/listings/2021-08-01/items/{auth.SELLER_ID}?"
                                    + urllib.parse.urlencode(params))
        if st != 200:
            print(f"⚠️ US listing 翻页中断 HTTP {st}")
            break
        for it in r.get("items", []):
            summ = (it.get("summaries") or [{}])[0]
            sku, asin = it.get("sku"), summ.get("asin")
            if sku and asin:
                asin2sku[asin] = sku
                sku2pt[sku] = _real_pt(it, summ)
        token = (r.get("pagination") or {}).get("nextToken")
        if not token:
            break
    return asin2sku, sku2pt


# ---------- 2. 当天新上架 ----------
def fetch_today_asins():
    created_after = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
    asins, token = [], None
    while True:
        params = {"marketplaceIds": auth.US, "pageSize": 20, "includedData": "summaries",
                  "sortBy": "createdDate", "sortOrder": "DESC", "createdAfter": created_after}
        if token:
            params["pageToken"] = token
        st, r = auth.request("GET", f"/listings/2021-08-01/items/{auth.SELLER_ID}?"
                                    + urllib.parse.urlencode(params))
        if st != 200:
            break
        for it in r.get("items", []):
            summ = (it.get("summaries") or [{}])[0]
            if summ.get("asin"):
                asins.append(summ["asin"])
        token = (r.get("pagination") or {}).get("nextToken")
        if not token:
            break
    return asins


# ---------- 3. 父子关系（权威：listing attributes） ----------
def get_us_attrs(sku):
    qs = urllib.parse.urlencode({"marketplaceIds": auth.US, "includedData": "attributes"})
    st, r = auth.request("GET", f"/listings/2021-08-01/items/{auth.SELLER_ID}/{sku}?{qs}")
    return r.get("attributes") or {}


# ---------- 4. 分组 ----------
def fetch_child_skus(parent_asin, asin2sku):
    """兜底：用 catalog relationships 反查父下的子 SKU。
    仅在「输入只给了父 ASIN、没带子体」时使用；不用它判断父子关系（索引会滞后）。"""
    qs = urllib.parse.urlencode({"marketplaceIds": auth.US, "includedData": "relationships"})
    st, r = auth.request("GET", f"/catalog/2022-04-01/items/{parent_asin}?{qs}")
    if st != 200:
        return []
    out = []
    for mp in r.get("relationships", []):
        for rel in mp.get("relationships", []):
            if rel.get("type") == "VARIATION":
                for c in (rel.get("childAsins") or []):
                    if c in asin2sku:
                        out.append(asin2sku[c])
    return out


def resolve_groups(asins, asin2sku, sku2pt):
    """权威依据：listing attributes 的 parentage_level + child_parent_sku_relationship.parent_sku。
    不用 catalog relationships 判断父子（对当天新上架索引未完成，会把父/子误判为独立 listing）。"""
    child2parent, parents_today, standalone = {}, set(), []
    for a in asins:
        if a not in asin2sku:
            continue
        sku = asin2sku[a]
        attrs = get_us_attrs(sku)
        pl = (attrs.get("parentage_level") or [{}])
        pl = pl[0].get("value") if pl and isinstance(pl[0], dict) else None
        rel = attrs.get("child_parent_sku_relationship") or []
        psku = rel[0].get("parent_sku") if rel and isinstance(rel[0], dict) else None
        if pl == "child" and psku:
            child2parent[sku] = psku
        elif pl == "parent":
            parents_today.add(sku)
        else:
            standalone.append(sku)

    sku2asin = {v: k for k, v in asin2sku.items()}
    groups = []
    for psku in parents_today:
        children = [c for c, p in child2parent.items() if p == psku]
        if not children:
            par_asin = sku2asin.get(psku)
            if par_asin:
                children = fetch_child_skus(par_asin, asin2sku)
                if children:
                    print(f"  ℹ️ 父 {psku} 的子体由 relationships 兜底补齐 {len(children)} 个")
        groups.append({"parent_sku": psku, "pt": sku2pt.get(psku),
                       "children": children, "standalone": False})
    for c, p in child2parent.items():
        if p not in parents_today:
            print(f"  ⚠️ 子 {c} 的父 {p} 不在本次集合，按独立可售处理")
            groups.append({"parent_sku": c, "pt": sku2pt.get(c),
                           "children": [], "standalone": True})
    for sku in standalone:
        groups.append({"parent_sku": sku, "pt": sku2pt.get(sku),
                       "children": [], "standalone": True})
    return groups


# ---------- 5. 上传 ----------
def upload_group(g, store=stores.DEFAULT_STORE, dry_run=False):
    parent_sku = g["parent_sku"]
    pt = g["pt"]
    sch = bm.load_mx_schema(pt)
    props = sch.get("properties") or {}
    req = sch.get("required") or []

    parent_mx = stores.to_mx_sku(parent_sku, store)
    pattrs, _ = bm.get_us_listing(parent_sku)

    if g["standalone"]:
        us_par = ((pattrs.get("parentage_level") or [{}])[0].get("value") or "").lower()
        is_parent = (us_par == "parent")
    else:
        is_parent = True

    if is_parent and not g["standalone"]:
        pd, pdrop, pmiss = bm.build(pattrs, None, parent_mx, True, pt, props, req)
        print(f"[父] {parent_mx} 剔除={pdrop} 缺必填={pmiss}")
        pat = {"productType": pt, "requirements": "LISTING", "attributes": pd}
        if pmiss:
            print("  ⚠️ 父体必填缺失，跳过整组")
            return None
    elif is_parent and g["standalone"]:
        pd, pdrop, pmiss = bm.build(pattrs, None, parent_mx, True, pt, props, req)
        print(f"[独立·父] {parent_mx} 剔除={pdrop} 缺必填={pmiss}")
        pat = {"productType": pt, "requirements": "LISTING", "attributes": pd}
        if pmiss:
            return None
    else:
        try:
            us_price = pattrs["purchasable_offer"][0]["our_price"][0]["schedule"][0]["value_with_tax"]
        except Exception as e:
            print(f"[独立] {parent_mx} 读源价失败：{e}")
            return None
        t, o, l = bm.calc_mx_price(us_price)
        # 独立 listing：is_parent 为 False 且无父体，必须 standalone=True（否则误发 child 关系报 90253）
        pd, pdrop, pmiss = bm.build(pattrs, (t, o, l), parent_mx, False, pt, props, req, None,
                                    standalone=True)
        print(f"[独立·可售] {parent_mx} US${us_price} → MX${o}/划线 MX${l} 缺必填={pmiss}")
        pat = {"productType": pt, "requirements": "LISTING", "attributes": pd}
        if pmiss:
            print(f"  ⚠️ 独立品必填缺失，跳过：{pmiss}")
            return None
        if dry_run:
            return parent_mx
        st, r = bm.put_listing(parent_mx, pat)
        print(f"  PUT → HTTP {st} {r.get('status') if isinstance(r, dict) else r}")
        for i in (r.get("issues") or []) if isinstance(r, dict) else []:
            if i.get("severity") == "ERROR":
                print(f"   ❌ {i.get('code')} {i.get('attributeNames')} {(i.get('message') or '')[:160]}")
        return parent_mx

    # 子体
    cpatches = []
    for csku in g["children"]:
        csku_mx = stores.to_mx_sku(csku, store)
        try:
            cattrs, _ = bm.get_us_listing(csku)
            us_price = cattrs["purchasable_offer"][0]["our_price"][0]["schedule"][0]["value_with_tax"]
        except Exception as e:
            print(f"[子] {csku_mx} 读源失败：{e}")
            continue
        t, o, l = bm.calc_mx_price(us_price)
        cd, cdrop, cmiss = bm.build(cattrs, (t, o, l), csku_mx, False, pt, props, req, parent_mx)
        print(f"[子] {csku_mx} US${us_price} → MX${o}/划线 MX${l} 剔除={cdrop} 缺必填={cmiss}")
        if cmiss:
            print("  ⚠️ 子体必填缺失，跳过该子")
            continue
        cpatches.append((csku_mx, {"productType": pt, "requirements": "LISTING", "attributes": cd}))

    if dry_run:
        print("  （dry-run，未提交）")
        return parent_mx

    st, r = bm.put_listing(parent_mx, pat)
    print(f"[父] PUT → HTTP {st} {r.get('status') if isinstance(r, dict) else r}")
    time.sleep(2)
    for csku_mx, cpatch in cpatches:
        st2, r2 = bm.put_listing(csku_mx, cpatch)
        print(f"[子] PUT {csku_mx} → HTTP {st2} {r2.get('status') if isinstance(r2, dict) else r2}")
        for i in (r2.get("issues") or []) if isinstance(r2, dict) else []:
            if i.get("severity") == "ERROR":
                print(f"   ❌ {i.get('code')} {i.get('attributeNames')} {(i.get('message') or '')[:140]}")
        time.sleep(1.2)
    return parent_mx


# ---------- 6. 回验 ----------
def verify(sku):
    qs = urllib.parse.urlencode({"marketplaceIds": auth.MX, "includedData": "summaries,issues",
                                 "issueLocale": "es_MX"})
    try:
        st, r = auth.request("GET", f"/listings/2021-08-01/items/{auth.SELLER_ID}/{sku}?{qs}")
    except Exception:
        return None, "404", {}
    summ = (r.get("summaries") or [{}])[0]
    codes = {}
    for i in (r.get("issues") or []):
        if i.get("severity") == "ERROR":
            codes[i.get("code")] = codes.get(i.get("code"), 0) + 1
    return summ.get("asin"), summ.get("status"), codes


def main():
    dry = "--dry-run" in sys.argv
    argv = [a for a in sys.argv[1:] if a != "--dry-run"]
    store = stores.DEFAULT_STORE
    if "--store" in argv:
        i = argv.index("--store")
        if i + 1 >= len(argv):
            print("❌ --store 后面要跟店铺名")
            return
        store = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if store not in stores.STORES:
        print(f"❌ 未知店铺 {store}，可选：{list(stores.STORES)}")
        return
    auth.set_store(store)
    print(f"店铺 = {store}（US/MX seller {auth.SELLER_ID}）")

    if not argv:
        print(__doc__)
        return
    arg = argv[0]
    if arg == "--today":
        asins = fetch_today_asins()
        print(f"自动抓取 US 站当天新上架 {len(asins)} 个 ASIN")
    else:
        asins = [a.strip() for a in arg.split(",") if a.strip()]
        print(f"输入 {len(asins)} 个 ASIN: {asins}")

    asin2sku, sku2pt = search_us_listings()
    print(f"US 站全量 listing 已加载：{len(asin2sku)} 个 ASIN")

    groups = resolve_groups(asins, asin2sku, sku2pt)
    print(f"\n解析出 {len(groups)} 个组：")
    for g in groups:
        kind = "独立" if g["standalone"] else "变体"
        print(f"  [{kind}] {g['pt']}: 父 {g['parent_sku']} -> {len(g['children'])} 子 {g['children']}")

    print("\n开始上传..." if not dry else "\n开始 dry-run...")
    all_mx = []
    for g in groups:
        try:
            p = upload_group(g, store=store, dry_run=dry)
            if p:
                all_mx.append(p)
                all_mx += [stores.to_mx_sku(c, store) for c in g["children"]]
        except Exception as e:
            print(f"  ⚠️ 组 {g['parent_sku']} 异常: {e}")

    if dry:
        print("\ndry-run 完成，未提交。")
        return

    print("\n等待 90s 异步校验...")
    time.sleep(90)
    print("\n===== 回验 =====")
    print(f"{'SKU':<30} {'ASIN':<12} {'状态':<24} 错误码")
    for sku in all_mx:
        asin, status, codes = verify(sku)
        stt = ",".join(status) if isinstance(status, list) else str(status)
        print(f"{sku:<30} {str(asin):<12} {stt:<24} {codes}")


if __name__ == "__main__":
    main()

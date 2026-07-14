"""
Download + clean pipeline for AREA 303 ideas #01-#05 (Ollama-first modeling).

Reproduces the `*_clean.parquet` (+ .csv) files documented in
dataset/by_idea/idea_0X_*/USE_THESE.md, writing them into each idea folder so
the modeling scripts can load them locally.

Sources (from each dataset's _SOURCE.txt):
  vispam        HuggingFace/GitHub  (FREE, no auth)   -> ideas 01, 05
  asos          HuggingFace         (FREE, no auth)   -> idea 02
  fake_reviews  HuggingFace mirror  (FREE, no auth)   -> idea 05
  shopee        Kaggle  (needs kaggle.json)           -> idea 01
  sephora       Kaggle  (needs kaggle.json)           -> ideas 03, 05
  tiki          Kaggle  (needs kaggle.json)           -> ideas 02, 03
  rees46 churn  Kaggle  (needs kaggle.json)           -> idea 04
  utkarshx27    Kaggle  (needs kaggle.json)           -> idea 04

Usage:
    python code/download_clean_ideas.py                # all available sources
    python code/download_clean_ideas.py vispam asos    # only named sources

Kaggle sources are skipped with a clear message if ~/.kaggle/kaggle.json (or
KAGGLE_USERNAME/KAGGLE_KEY env vars) are not present. Drop credentials in and
re-run, or ask the data-processing teammate for the cleaned parquet files.
"""
from __future__ import annotations

import io
import os
import sys
import zipfile
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BY_IDEA = ROOT / "dataset" / "by_idea"
CACHE = ROOT / ".cache"
CACHE.mkdir(exist_ok=True)

IDEA_DIRS = {
    "01": BY_IDEA / "idea_01_review_sentiment",
    "02": BY_IDEA / "idea_02_dynamic_pricing",
    "03": BY_IDEA / "idea_03_personal_shopper",
    "04": BY_IDEA / "idea_04_customer_churn",
    "05": BY_IDEA / "idea_05_fake_review",
}

# category names in vispam that count as the AREA 303 focus (clothing + cosmetics + footwear)
IN_DOMAIN_CATEGORIES = {"Thời Trang", "Sắc Đẹp", "Giày Dép"}

SPAM_LABEL_NAMES = {0: "not_spam", 1: "spam"}


def _save(df: pd.DataFrame, name: str, idea_keys: list[str]) -> None:
    """Write <name>.parquet + .csv into each idea folder that uses it."""
    for k in idea_keys:
        out = IDEA_DIRS[k]
        out.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out / f"{name}.parquet", index=False)
        df.to_csv(out / f"{name}.csv", index=False, encoding="utf-8-sig")
        print(f"  -> wrote {out.relative_to(ROOT)}/{name}.parquet  ({df.shape[0]:,} rows x {df.shape[1]} cols)")


def _download(url: str, timeout: int = 180) -> bytes:
    print(f"  downloading {url}")
    return urllib.request.urlopen(url, timeout=timeout).read()


# ----------------------------------------------------------------------------
# FREE sources (no auth)
# ----------------------------------------------------------------------------
def clean_vispam() -> None:
    """UIT ViSpamReviews v2 -> vispam_clean.parquet (ideas 01 + 05)."""
    print("[vispam] Vietnamese spam/review dataset (v2)")
    url = "https://raw.githubusercontent.com/sonlam1102/vispamdetection/main/dataset/vispamdetectionv2.zip"
    z = zipfile.ZipFile(io.BytesIO(_download(url)))
    frames = []
    split_map = {"train.csv": "train", "dev.csv": "dev", "test.csv": "test"}
    for fname, split in split_map.items():
        with z.open(fname) as fh:
            part = pd.read_csv(fh)
        part["split"] = split
        frames.append(part)
    raw = pd.concat(frames, ignore_index=True)

    df = pd.DataFrame({
        "comment": raw["comment"].astype("string"),
        "rating": raw["rating"].astype("int64"),
        "category": raw["category"].astype("string"),
        "in_domain": raw["category"].isin(IN_DOMAIN_CATEGORIES),
        "label": raw["label"].astype("int64"),
        "spam_label_name": raw["label"].map(SPAM_LABEL_NAMES).astype("string"),
        "spam_label": raw["spam_label"].astype("int64"),
        "product_name": raw["product_name"].astype("string"),
        "description": raw["description"].astype("string"),
        "num_sold": pd.to_numeric(raw["num_sold"], errors="coerce").fillna(0).astype("int64"),
        "num_review": pd.to_numeric(raw["num_review"], errors="coerce").fillna(0).astype("int64"),
        "split": raw["split"].astype("string"),
    })
    _save(df, "vispam_clean", ["01", "05"])


def clean_makeup() -> None:
    """English cosmetics catalog (USD) -> makeup_catalog_clean.parquet (ideas 02, 03)."""
    print("[makeup] English cosmetics/makeup catalog (HuggingFace)")
    try:
        from datasets import load_dataset
        df = load_dataset("YUVALON/makeup-products-1000", split="train").to_pandas()
    except Exception as e:  # noqa: BLE001
        print(f"  SKIP makeup: {str(e)[:120]}")
        return
    out = pd.DataFrame({
        "id": df["product_id"].astype("string"),
        "name": df["product_name"].astype("string"),
        "category": df["category"].astype("string").str.replace("_", " "),
        "brand": df["brand"].astype("string"),
        "price": pd.to_numeric(df["price_usd"], errors="coerce"),
        "rating": pd.to_numeric(df.get("rating", 0), errors="coerce").fillna(0),
        "review_count": pd.to_numeric(df.get("num_reviews", 0), errors="coerce").fillna(0).astype("int64"),
        "description": df.get("description", pd.Series([""] * len(df))).astype("string"),
    })
    out = out.dropna(subset=["price"]).query("price > 0").reset_index(drop=True)
    _save(out, "makeup_catalog_clean", ["02", "03"])


def clean_asos() -> None:
    """ASOS clothing catalog (GBP) -> asos_catalog_clean.parquet (idea 02)."""
    print("[asos] ASOS e-commerce catalog (HuggingFace)")
    try:
        from datasets import load_dataset
        ds = load_dataset("TrainingDataPro/asos-e-commerce-dataset", split="train")
        df = ds.to_pandas()
    except Exception as e:  # noqa: BLE001
        print(f"  SKIP asos: {e}")
        return
    # keep documented columns where present
    keep = [c for c in ["url", "name", "size", "category", "price", "color", "sku", "description", "images"] if c in df.columns]
    df = df[keep].copy()
    if "price" in df.columns:
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
    _save(df, "asos_catalog_clean", ["02"])


def clean_fake_reviews() -> None:
    """English CG/OR fake-review dataset -> fake_reviews_clean.parquet (ideas 01 + 05).

    Source: theArijitDas/Fake-Reviews-Dataset (HF) — a cleaned version of the
    Salminen et al. Kaggle set. Per its card: label 0 = original/genuine,
    label 1 = computer-generated (fake). English platform primary corpus.
    """
    print("[fake_reviews] English computer-generated vs genuine reviews")
    try:
        from datasets import load_dataset
        df = load_dataset("theArijitDas/Fake-Reviews-Dataset", split="train").to_pandas()
        print(f"  loaded from HF: theArijitDas/Fake-Reviews-Dataset ({len(df)} rows)")
    except Exception as e:  # noqa: BLE001
        print(f"  SKIP fake_reviews: {str(e)[:120]}")
        return
    is_fake = pd.to_numeric(df["label"], errors="coerce").fillna(0).astype("int64")
    out = pd.DataFrame({
        "category": df["category"].astype("string"),
        "rating": pd.to_numeric(df["rating"], errors="coerce"),
        "label": is_fake.map({1: "CG", 0: "OR"}).astype("string"),
        "label_name": is_fake.map({1: "fake", 0: "genuine"}).astype("string"),
        "is_fake": is_fake,
        "text": df["text"].astype("string"),
    })
    out = out.dropna(subset=["text"])
    out = out[out["text"].str.strip().str.len() >= 3]
    _save(out, "fake_reviews_clean", ["01", "05"])


# ----------------------------------------------------------------------------
# Kaggle sources (need credentials)
# ----------------------------------------------------------------------------
def _have_kaggle() -> bool:
    if os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"):
        return True
    return (Path.home() / ".kaggle" / "kaggle.json").exists()


def _kaggle_download(dataset: str, dest: Path) -> Path | None:
    if not _have_kaggle():
        print(f"  SKIP {dataset}: no Kaggle credentials (~/.kaggle/kaggle.json). "
              "Add creds and re-run, or get the cleaned parquet from the data teammate.")
        return None
    dest.mkdir(parents=True, exist_ok=True)
    import kaggle  # noqa: PLC0415  (import here so free sources work without kaggle configured)
    kaggle.api.dataset_download_files(dataset, path=str(dest), unzip=True)
    return dest


def clean_shopee() -> None:
    """Shopee VN reviews -> shopee_clean.parquet (idea 01). Kaggle."""
    print("[shopee] Shopee VN product reviews (Kaggle)")
    d = _kaggle_download("dduongdev/shopee-vietnamese-product-reviews-sentiment", CACHE / "shopee")
    if not d:
        return
    csvs = list(d.glob("**/*.csv"))
    if not csvs:
        print("  SKIP shopee: no csv found after download")
        return
    raw = pd.read_csv(max(csvs, key=lambda p: p.stat().st_size))
    cols = {c.lower(): c for c in raw.columns}
    text_c = cols.get("text") or cols.get("comment") or cols.get("review")
    rate_c = cols.get("rating") or cols.get("rate") or cols.get("star")
    id_c = cols.get("id") or cols.get("product_id")
    df = pd.DataFrame({
        "id": raw[id_c].astype("string") if id_c else pd.Series(range(len(raw))).astype("string"),
        "text": raw[text_c].astype("string"),
        "rating": pd.to_numeric(raw[rate_c], errors="coerce").fillna(0).astype("int64"),
    })
    df["label"] = df["rating"].apply(lambda r: "positive" if r >= 4 else "negative").astype("string")
    _save(df, "shopee_clean", ["01"])


def clean_tiki() -> None:
    """Tiki.vn fashion catalog -> tiki_catalog_clean.parquet (ideas 02, 03). Kaggle."""
    print("[tiki] Tiki.vn fashion catalog (Kaggle)")
    d = _kaggle_download("michaelminhpham/vietnamese-tiki-e-commerce-dataset", CACHE / "tiki")
    if not d:
        return
    csvs = list(d.glob("**/*.csv"))
    if not csvs:
        print("  SKIP tiki: no csv found")
        return
    raw = pd.read_csv(max(csvs, key=lambda p: p.stat().st_size))
    print(f"  raw tiki columns: {list(raw.columns)[:25]}")
    raw.columns = [c.strip() for c in raw.columns]
    if "original_price" in raw and "price" in raw:
        raw["discount_pct"] = ((raw["original_price"] - raw["price"]) /
                               raw["original_price"].replace(0, pd.NA) * 100).fillna(0.0)
    _save(raw, "tiki_catalog_clean", ["02", "03"])


def clean_sephora() -> None:
    """Sephora cosmetics reviews -> sephora_reviews_clean.parquet (ideas 03, 05). Kaggle."""
    print("[sephora] Sephora cosmetics reviews (Kaggle)")
    d = _kaggle_download("nadyinky/sephora-products-and-skincare-reviews", CACHE / "sephora")
    if not d:
        return
    review_csvs = [p for p in d.glob("**/*.csv") if "review" in p.name.lower()]
    if not review_csvs:
        print("  SKIP sephora: no review csv found")
        return
    raw = pd.concat([pd.read_csv(p, low_memory=False) for p in review_csvs], ignore_index=True)
    if "rating" in raw:
        raw["sentiment"] = raw["rating"].apply(
            lambda r: "negative" if r <= 2 else ("neutral" if r == 3 else "positive"))
    _save(raw, "sephora_reviews_clean", ["03", "05"])


def clean_churn() -> None:
    """REES46 churn table -> rees46_churn_clean.parquet (idea 04). Kaggle."""
    print("[churn] REES46 e-commerce churn (Kaggle)")
    d = _kaggle_download("fridrichmrtn/e-commerce-churn-dataset-rees46", CACHE / "churn")
    if not d:
        return
    files = list(d.glob("**/*.parquet")) + list(d.glob("**/*.csv"))
    if not files:
        print("  SKIP churn: no data file found")
        return
    f = max(files, key=lambda p: p.stat().st_size)
    raw = pd.read_parquet(f) if f.suffix == ".parquet" else pd.read_csv(f)
    _save(raw, "rees46_churn_clean", ["04"])


def clean_churn_events() -> None:
    """REAL churn table derived from free REES46 event logs (HuggingFace).

    -> rees46_events_churn.parquet (idea 04). No Kaggle needed.

    Label = inactivity churn: a user with activity before the cutoff (max_ts - 30d)
    but NO event in the last-30-day holdout window is churned (1). Features are
    RFM-style signals computed from events before the cutoff.
    """
    print("[churn_events] deriving real churn labels from REES46 events (HF)")
    try:
        from huggingface_hub import hf_hub_download
        ev = hf_hub_download("nguyenmaiductrong/rees46-full-temporal",
                             "graph/train_events.parquet", repo_type="dataset")
    except Exception as e:  # noqa: BLE001
        print(f"  SKIP churn_events: {str(e)[:120]}")
        return
    df = pd.read_parquet(ev, columns=["user_idx", "behavior_id", "timestamp", "user_session"])
    DAY = 86400
    tmax = int(df["timestamp"].max())
    cutoff = tmax - 30 * DAY
    hist = df[df["timestamp"] <= cutoff]
    future_users = set(df.loc[df["timestamp"] > cutoff, "user_idx"].unique())

    g = hist.groupby("user_idx")
    last_ts = g["timestamp"].max()
    first_ts = g["timestamp"].min()
    purchases = hist.assign(p=(hist["behavior_id"] == 2)).groupby("user_idx")["p"].sum()
    carts = hist.assign(c=(hist["behavior_id"] == 1)).groupby("user_idx")["c"].sum()

    last30 = hist[hist["timestamp"] > cutoff - 30 * DAY]
    prev30 = hist[(hist["timestamp"] > cutoff - 60 * DAY) & (hist["timestamp"] <= cutoff - 30 * DAY)]
    sess_last = last30.groupby("user_idx")["user_session"].nunique()
    cnt_last = last30.groupby("user_idx").size()
    cnt_prev = prev30.groupby("user_idx").size()

    users = last_ts.index
    out = pd.DataFrame(index=users)
    out["recency_days"] = ((cutoff - last_ts) / DAY).round(0)
    out["frequency_orders"] = purchases.reindex(users).fillna(0).astype(int)
    out["monetary_avg"] = pd.NA  # no price in event log
    out["tenure_months"] = ((last_ts - first_ts) / (30 * DAY)).round(1)
    out["sessions_last_month"] = sess_last.reindex(users).fillna(0).astype(int)
    cr = carts.reindex(users).fillna(0)
    pu = purchases.reindex(users).fillna(0)
    out["cart_abandon_rate"] = ((cr - pu).clip(lower=0) / cr.replace(0, pd.NA)).fillna(0).round(3)
    cl, cp = cnt_last.reindex(users).fillna(0), cnt_prev.reindex(users).fillna(0)
    out["trend"] = "stable"
    out.loc[cl < cp * 0.7, "trend"] = "declining"
    out.loc[cl > cp * 1.3, "trend"] = "growing"
    out["label"] = (~out.index.to_series().isin(future_users)).astype(int)
    out["source"] = "rees46_events"
    out = out.reset_index(drop=True)

    print(f"  users: {len(out)} | churn rate: {out.label.mean():.3f}")
    _save(out, "rees46_events_churn", ["04"])


def clean_utkarshx27() -> None:
    """Fashion marketplace user profiles -> utkarshx27_users_clean.parquet (idea 04). Kaggle."""
    print("[utkarshx27] Fashion user data (Kaggle)")
    d = _kaggle_download("utkarshx27/fashion-ecommerce-user-data", CACHE / "utkarshx27")
    if not d:
        return
    csvs = list(d.glob("**/*.csv"))
    if not csvs:
        print("  SKIP utkarshx27: no csv found")
        return
    raw = pd.read_csv(max(csvs, key=lambda p: p.stat().st_size))
    _save(raw, "utkarshx27_users_clean", ["04"])


TASKS = {
    "vispam": clean_vispam,
    "asos": clean_asos,
    "makeup": clean_makeup,
    "fake_reviews": clean_fake_reviews,
    "shopee": clean_shopee,
    "tiki": clean_tiki,
    "sephora": clean_sephora,
    "churn": clean_churn,
    "churn_events": clean_churn_events,
    "utkarshx27": clean_utkarshx27,
}


def main(argv: list[str]) -> None:
    wanted = argv or list(TASKS)
    print(f"Kaggle credentials detected: {_have_kaggle()}")
    print(f"Running: {', '.join(wanted)}\n")
    for name in wanted:
        fn = TASKS.get(name)
        if not fn:
            print(f"! unknown source '{name}' (choices: {', '.join(TASKS)})")
            continue
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR in {name}: {e}")
        print()


if __name__ == "__main__":
    main(sys.argv[1:])

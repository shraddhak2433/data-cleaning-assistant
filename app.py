"""Data Cleaning Assistant: upload a CSV, see data quality issues, clean it, download the result.
Run: streamlit run app.py
"""
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Data Cleaning Assistant", layout="wide")
st.title("Data Cleaning Assistant")
st.write("Upload a CSV to check its quality, clean it and download the result.")


def quality_report(df):
    return pd.DataFrame({
        "dtype": df.dtypes.astype(str),
        "missing": df.isna().sum(),
        "missing %": (df.isna().mean() * 100).round(1),
        "unique": df.nunique(),
    })


def prepare(df):
    """Treat blank text as missing and convert number-like text columns to numbers."""
    df = df.copy()
    converted = []
    for c in df.select_dtypes("object"):
        df[c] = df[c].replace(r"^\s*$", pd.NA, regex=True)
        as_num = pd.to_numeric(df[c], errors="coerce")
        non_null = df[c].notna().sum()
        if non_null and as_num.notna().sum() >= 0.95 * non_null:
            df[c] = as_num
            converted.append(c)
    return df, converted


def find_outliers(df):
    out = {}
    for col in df.select_dtypes("number"):
        if df[col].nunique() <= 2:
            continue  # 0/1 columns have no real outliers
        q1, q3 = df[col].quantile([0.25, 0.75])
        iqr = q3 - q1
        mask = (df[col] < q1 - 1.5 * iqr) | (df[col] > q3 + 1.5 * iqr)
        if mask.sum():
            out[col] = int(mask.sum())
    return out


def clean(df, drop_dupes, num_fill, cat_fill, strip_text):
    df = df.copy()
    if strip_text:
        for c in df.select_dtypes("object"):
            df[c] = df[c].str.strip()
    if drop_dupes:
        df = df.drop_duplicates()
    for c in df.select_dtypes("number"):
        if num_fill != "Leave as is" and df[c].isna().any():
            df[c] = df[c].fillna(df[c].median() if num_fill == "Median" else df[c].mean())
    for c in df.select_dtypes("object"):
        if cat_fill != "Leave as is" and df[c].isna().any():
            df[c] = df[c].fillna(df[c].mode().iloc[0] if cat_fill == "Most common value" and not df[c].mode().empty else "Unknown")
    return df


file = st.file_uploader("Choose a CSV file", type="csv")
if file:
    raw, converted = prepare(pd.read_csv(file))
    if converted:
        st.info("Converted text columns to numbers: " + ", ".join(converted))
    c1, c2, c3 = st.columns(3)
    c1.metric("Rows", len(raw))
    c2.metric("Duplicate rows", int(raw.duplicated().sum()))
    c3.metric("Missing cells", int(raw.isna().sum().sum()))

    st.subheader("Quality report")
    st.dataframe(quality_report(raw))
    outliers = find_outliers(raw)
    if outliers:
        st.warning("Possible outliers (IQR rule): " + ", ".join(f"{k}: {v}" for k, v in outliers.items()))

    st.sidebar.header("Cleaning options")
    drop_dupes = st.sidebar.checkbox("Remove duplicate rows", True)
    strip_text = st.sidebar.checkbox("Trim spaces in text columns", True)
    num_fill = st.sidebar.selectbox("Missing numbers", ["Median", "Mean", "Leave as is"])
    cat_fill = st.sidebar.selectbox("Missing text", ["Most common value", "Unknown", "Leave as is"])

    cleaned = clean(raw, drop_dupes, num_fill, cat_fill, strip_text)
    st.subheader("Before and after")
    b, a = st.columns(2)
    b.write("Before"); b.metric("Rows", len(raw)); b.metric("Missing cells", int(raw.isna().sum().sum()))
    a.write("After"); a.metric("Rows", len(cleaned)); a.metric("Missing cells", int(cleaned.isna().sum().sum()))
    st.dataframe(cleaned.head(50))
    st.download_button("Download cleaned CSV", cleaned.to_csv(index=False).encode(), "cleaned.csv", "text/csv")

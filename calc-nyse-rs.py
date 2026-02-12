#!/usr/bin/env python

import FinanceDataReader as fdr
import yfinance as yf
import os
import os.path
import time
import numpy as np
import pandas as pd
import datetime as dt
import textwrap


LIST_FILENAME = "nyse-list.csv"
TARGET = 'NYSE'
DATA_DIR_ROOT = "DATA"

print("Fetching NYSE stock listings...")
nyse_list = fdr.StockListing(TARGET)
nyse_list.to_csv(LIST_FILENAME)

print(f"Total stocks: {nyse_list.shape[0]}")

now = dt.datetime.now()
date = now.strftime("%Y-%m-%d")

data_dir = os.path.join(DATA_DIR_ROOT, date)
os.makedirs(data_dir, exist_ok=True)

# Download historical data using yfinance
for i in nyse_list.itertuples():
    print(f"Processing ({i.Index}): {i.Symbol} / {i.Name}")
    filename = f"{i.Symbol}-{i.Name}.csv"
    # Clean filename (remove special characters)
    filename = filename.replace('/', '-').replace('\\', '-')
    file_path = os.path.join(data_dir, filename)

    if os.path.exists(file_path):
        print(f"  {file_path} already exists. Skipping download.")
    else:
        try:
            print(f"  Downloading {i.Symbol}...")
            ticker = yf.Ticker(i.Symbol)
            data = ticker.history(start="2022-01-01")

            if len(data) > 0:
                data.to_csv(file_path)
                print(f"  Downloaded {i.Symbol}. Waiting...")
                time.sleep(np.random.uniform(0.05, 0.15))
            else:
                print(f"  No data for {i.Symbol}")
        except Exception as e:
            print(f"  Error downloading {i.Symbol}: {e}")

print("All stocks downloaded.")

quater = 21 * 3
# 1 year = 252 = 21 * 3 * 4

rs_df = pd.DataFrame(columns=[
    'Symbol',
    'Name',
    'Score',
    'YesterdayScore',
    'Close1',
    'Close2',
    'MA50',
    'MA150',
    'MA200',
    'LastMonthMA200',
    'Min52W',
    'Max52W'
])


def c(symbol):
    link = f"https://finance.yahoo.com/quote/{symbol}"
    return f"[{symbol}]({link})"


def calc_score(data, day=-1):
    try:
        today = data.loc[data.index[day]]
        one_quarter_ago = data.loc[data.index[day - (quater)]]
        two_quarter_ago = data.loc[data.index[day - (quater * 2)]]
        three_quarter_ago = data.loc[data.index[day - (quater * 3)]]
        four_quarter_ago = data.loc[data.index[day - (quater * 4)]]

        score_1 = today.Close / one_quarter_ago.Close
        score_2 = one_quarter_ago.Close / two_quarter_ago.Close
        score_3 = two_quarter_ago.Close / three_quarter_ago.Close
        score_4 = three_quarter_ago.Close / four_quarter_ago.Close

        # https://www.williamoneil.com/proprietary-ratings-and-rankings/
        total_score = (score_1 * 2) + score_2 + score_3 + score_4
        return total_score

    except IndexError as e:
        print(f"  Insufficient date range: {e}")
        return -1


# Calculate RS scores
for i in nyse_list.itertuples():
    print(f"Calculating RS ({i.Index}): {i.Symbol} / {i.Name}")
    filename = f"{i.Symbol}-{i.Name}.csv"
    filename = filename.replace('/', '-').replace('\\', '-')
    file_path = os.path.join(data_dir, filename)

    if not os.path.exists(file_path):
        print(f"  File not found: {file_path}")
        continue

    data = pd.read_csv(file_path, index_col=0, parse_dates=True)
    today_score = calc_score(data)
    yesterday_score = calc_score(data, -2)

    if today_score != -1:
        today = data.loc[data.index[-1]]
        four_quarter_ago = data.loc[data.index[-1 - (quater * 4)]]

        data_260 = data.tail(260)
        data_260_close = data_260.Close
        max_52w = data_260_close.max()
        min_52w = data_260_close.min()
        data_220_close = data_260_close.tail(220)
        last_month_ma_200 = int(data_220_close.head(200).mean())
        data_200_close = data_220_close.tail(200)
        ma_200 = int(data_200_close.mean())
        data_150_close = data_200_close.tail(150)
        ma_150 = int(data_150_close.mean())
        data_50_close = data_150_close.tail(50)
        ma_50 = int(data_50_close.mean())

        rs_df = pd.concat([rs_df, pd.DataFrame([{
            'Symbol': i.Symbol,
            'Name': i.Name,
            'Score': today_score,
            'YesterdayScore': yesterday_score,
            'Close1': four_quarter_ago.Close,
            'Close2': today.Close,
            'MA50': ma_50,
            'MA150': ma_150,
            'MA200': ma_200,
            'LastMonthMA200': last_month_ma_200,
            'Min52W': min_52w,
            'Max52W': max_52w,
        }])], ignore_index=True)
    print(f"  today score: {today_score} / yesterday score: {yesterday_score}")

rs_df['Rank'] = rs_df['Score'].rank()
rs_df['RS'] = (rs_df['Rank'] * 98 / len(rs_df)).apply(np.int64) + 1

rs_df['YesterdayRank'] = rs_df['YesterdayScore'].rank()
rs_df['YesterdayRS'] = (rs_df['YesterdayRank'] * 98 /
                        len(rs_df)).apply(np.int64) + 1

na_index = rs_df['YesterdayRS'].isna()
rs_df['RankChange'] = rs_df['RS'] - rs_df['YesterdayRS']
rs_df.loc[na_index, 'RankChange'] = -1

sorted_df = rs_df.sort_values('Rank', ascending=False)

posts_dir = os.path.join("docs", "_posts")
os.makedirs(posts_dir, exist_ok=True)
result_file_path = os.path.join(posts_dir, f"{date}-nyse-rs.markdown")

with open(result_file_path, "w") as f:
    header_start = '''\
    ---
    layout: single
    '''
    f.write(textwrap.dedent(header_start))
    f.write(now.strftime('title: "NYSE Relative Strength %Y-%m-%d"\n'))
    f.write(now.strftime("date: %Y-%m-%d %H:%M:%S +0000\n"))
    header_end = '''\
    categories: rs
    ---
    '''
    f.write(textwrap.dedent(header_end))

    comment = '''\
    Calculated Relative Strength for all NYSE stocks.

    Based on [William O'Neil's Relative Strength Rating](https://www.williamoneil.com/proprietary-ratings-and-rankings/).

    ## NYSE Relative Strength Rankings

    |Symbol|Name|1 Year Ago|Close|RS|
    |------|---|----------|-----|--|
    '''
    f.write(textwrap.dedent(comment))

    for i in sorted_df.itertuples():
        if i.RankChange == 0:
            change = ""
        elif i.RankChange > 0:
            change = f"(+{int(i.RankChange)})"
        else:
            change = f"({int(i.RankChange)})"
        f.write(
            f"|{c(i.Symbol)}|{i.Name}|{i.Close1:.2f}|{i.Close2:.2f}|{i.RS} {change}|\n")


# Minervini Trend Template
result_file_path = os.path.join(
    posts_dir, f"{date}-nyse-trend-template.markdown")

minervini = sorted_df[sorted_df.RS >= 70]
minervini = minervini[minervini.Close2 > minervini.MA50]
minervini = minervini[minervini.Close2 > minervini.MA150]
minervini = minervini[minervini.Close2 > minervini.MA200]
minervini = minervini[minervini.MA50 > minervini.MA150]
minervini = minervini[minervini.MA150 > minervini.MA200]
minervini = minervini[minervini.MA200 > minervini.LastMonthMA200]
minervini = minervini[minervini.Close2 > minervini.Min52W * 1.3]
minervini = minervini[minervini.Close2 > minervini.Max52W * 0.75]

with open(result_file_path, "w") as f:
    header_start = '''\
    ---
    layout: single
    '''
    f.write(textwrap.dedent(header_start))
    f.write(now.strftime('title: "NYSE Minervini Trend Template %Y-%m-%d"\n'))
    f.write(now.strftime("date: %Y-%m-%d %H:%M:%S +0000\n"))
    header_end = '''\
    categories: minervini
    ---
    '''
    f.write(textwrap.dedent(header_end))

    comment = '''\
    Stocks that meet Mark Minervini's Trend Template criteria.

    Only showing stocks that pass all 8 criteria. Filtered stocks are not shown.

    ## Minervini Trend Template

    |Symbol|Name|Close|RS|52W High,Low|MA50,150,200|
    |------|---|-----|--|-----------|-----------|
    '''
    f.write(textwrap.dedent(comment))

    for i in minervini.itertuples():
        f.write(
            f"|{c(i.Symbol)}|{i.Name}|{i.Close2:.2f}|{i.RS}|{i.Max52W:.2f}, {i.Min52W:.2f}|{i.MA50}, {i.MA150}, {i.MA200}|\n")

    f.write("\n")
    footer = '''\
    ## Minervini Trend Template Criteria

    From "Trade Like a Stock Market Wizard: How to Achieve Super Performance in Stocks in Any Market"

     1. The current stock price is above both the 150-day (30-week) and the 200-day (40-week) moving average price lines.
     1. The 150-day moving average is above the 200-day moving average.
     1. The 200-day moving average line is trending up for at least 1 month (preferably 4–5 months minimum in most cases).
     1. The 50-day (10-week) moving average is above both the 150-day and 200-day moving averages.
     1. The current stock price is trading above the 50-day moving average.
     1. The current stock price is at least 30 percent above its 52-week low. (Many of the best selections will be 100 percent, 300 percent, or greater above their 52-week low before they emerge from a solid consolidation period and mount a large scale advance.)
     1. The current stock price is within at least 25 percent of its 52-week high (the closer to a new high the better).
     1. The relative strength ranking (as reported in Investor's Business Daily) is no less than 70, and preferably in the 80s or 90s, which will generally be the case with the better selections.
    '''
    f.write(textwrap.dedent(footer))

print(f"\n✓ NYSE RS calculation complete!")
print(f"  Generated: {posts_dir}/{date}-nyse-rs.markdown")
print(f"  Generated: {posts_dir}/{date}-nyse-trend-template.markdown")

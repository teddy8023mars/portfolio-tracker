# Portfolio Tracker

Daily portfolio report script with comprehensive profit/loss analysis including CPF opportunity costs.

## Features

- Real-time stock price tracking via Yahoo Finance
- Breakeven price calculation (target price to sell without loss)
- Trading suggestions based on current price vs target price
- Comprehensive P&L analysis including:
  - Paper profit/loss
  - Transaction fees (DBS Vickers)
  - CPF OA opportunity cost (3.5% p.a.)
  - Net profit/loss after all costs

## Portfolio

- DBS (D05.SI): 100 shares @ $54.59
- CapitaLand (C38U.SI): 1900 shares @ $2.45
- STI ETF (ES3.SI): 1238 shares @ $4.63

Buy date: 2025-10-28

## Usage

```bash
python3 daily_portfolio_report.py
```

## Requirements

- Python 3.11+
- yfinance
- tabulate

Install dependencies:
```bash
pip3 install yfinance tabulate
```

## CPF Parameters

- Account: OA Account
- Current balance: $20,000
- Investment amount: $15,935 (in $20k-$36k range)
- Applicable rate: 3.5% p.a. (2.5% base + 1% extra)

## Transaction Fees (DBS Vickers)

- Commission: 0.18% or minimum $27.25
- Clearing fee: 0.0325%
- Trading fee: 0.0075%
- Settlement fee: $0.35

## Trading Suggestion Rules

- ✅ Can sell: Current price ≥ Target price
- ⚠️ Near target: Distance to target < 0.5%
- ⏳ Hold: Current price < Target but > Cost
- 🔻 Consider stop loss: Loss > 5%

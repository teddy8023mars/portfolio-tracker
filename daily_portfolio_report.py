#!/usr/bin/env python3
"""
每日投资组合报告生成器
包含：实时价格、目标价格、交易建议、完整盈亏分析（含CPF机会成本）
"""

import yfinance as yf
from datetime import datetime, date
from tabulate import tabulate

# 投资组合配置
PORTFOLIO = [
    {
        "symbol": "D05.SI",
        "name": "DBS",
        "cost": 54.59,
        "shares": 100,
        "buy_date": "2025-10-28"
    },
    {
        "symbol": "C38U.SI",
        "name": "CapitaLand",
        "cost": 2.45,
        "shares": 1900,
        "buy_date": "2025-10-28"
    },
    {
        "symbol": "ES3.SI",
        "name": "STI ETF",
        "cost": 4.63,
        "shares": 1238,
        "buy_date": "2025-10-28"
    }
]

# CPF参数
CPF_OA_RATE = 0.035  # 3.5% p.a. (2.5%基础 + 1%额外，适用于$20k-$36k区间)
CPF_OA_BALANCE = 20000
INVESTMENT_AMOUNT = 15935

# 费用参数 (DBS Vickers)
COMMISSION_RATE = 0.0018  # 0.18%
MIN_COMMISSION = 27.25  # 最低佣金
CLEARING_FEE_RATE = 0.000325  # 0.0325%
TRADING_FEE_RATE = 0.000075  # 0.0075%
SETTLEMENT_FEE = 0.35  # 固定费用


def calculate_transaction_fee(amount):
    """计算交易费用（买入或卖出）"""
    commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
    clearing_fee = amount * CLEARING_FEE_RATE
    trading_fee = amount * TRADING_FEE_RATE
    settlement_fee = SETTLEMENT_FEE
    return commission + clearing_fee + trading_fee + settlement_fee


def calculate_holding_days(buy_date_str):
    """计算持有天数"""
    buy_date = datetime.strptime(buy_date_str, "%Y-%m-%d").date()
    today = date.today()
    return (today - buy_date).days


def calculate_cpf_opportunity_cost(investment_amount, days):
    """计算CPF机会成本"""
    return investment_amount * CPF_OA_RATE * (days / 365)


def get_stock_price(symbol):
    """获取股票当前价格和涨跌"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2d")
        
        if len(hist) >= 1:
            current_price = hist['Close'].iloc[-1]
            
            # 计算涨跌
            if len(hist) >= 2:
                prev_price = hist['Close'].iloc[-2]
                change = current_price - prev_price
                change_pct = (change / prev_price) * 100
            else:
                change = 0
                change_pct = 0
                
            return current_price, change, change_pct
        else:
            return None, None, None
    except Exception as e:
        print(f"获取 {symbol} 价格失败: {e}")
        return None, None, None


def calculate_breakeven_price(cost, shares):
    """计算不亏钱的目标价格（考虑买入和卖出费用）"""
    # 买入总成本
    buy_amount = cost * shares
    buy_fee = calculate_transaction_fee(buy_amount)
    total_buy_cost = buy_amount + buy_fee
    
    # 需要通过迭代找到卖出价格，使得卖出后收入 = 总买入成本
    # 简化计算：假设卖出价格为P，则卖出收入 = P * shares - sell_fee
    # sell_fee = calculate_transaction_fee(P * shares)
    # 我们需要: P * shares - sell_fee = total_buy_cost
    
    # 迭代求解
    target_price = cost
    for _ in range(10):  # 迭代10次应该足够收敛
        sell_amount = target_price * shares
        sell_fee = calculate_transaction_fee(sell_amount)
        net_proceeds = sell_amount - sell_fee
        
        if net_proceeds < total_buy_cost:
            target_price = target_price * (total_buy_cost / net_proceeds)
        else:
            break
    
    return target_price


def get_trading_suggestion(current_price, target_price, cost):
    """生成交易建议"""
    if current_price >= target_price:
        distance = ((current_price - target_price) / target_price) * 100
        return f"✅ 可卖出 (高于目标 {distance:.2f}%)"
    elif current_price >= target_price * 0.995:  # 距离目标<0.5%
        distance = ((target_price - current_price) / target_price) * 100
        return f"⚠️ 接近目标 (差 {distance:.2f}%)"
    elif current_price >= cost:
        return "⏳ 持有 (高于成本但未达目标)"
    else:
        loss_pct = ((current_price - cost) / cost) * 100
        if loss_pct <= -5:
            return f"🔻 考虑止损 (亏损 {abs(loss_pct):.2f}%)"
        else:
            return f"⏳ 持有 (亏损 {abs(loss_pct):.2f}%)"


def generate_report():
    """生成完整报告"""
    print("=" * 80)
    print(f"📊 每日投资组合报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()
    
    # 表格数据
    table_data = []
    total_investment = 0
    total_current_value = 0
    total_paper_profit = 0
    
    detailed_analysis = []
    
    for stock in PORTFOLIO:
        symbol = stock["symbol"]
        name = stock["name"]
        cost = stock["cost"]
        shares = stock["shares"]
        buy_date = stock["buy_date"]
        
        # 获取当前价格
        current_price, change, change_pct = get_stock_price(symbol)
        
        if current_price is None:
            print(f"⚠️ 无法获取 {name} ({symbol}) 的价格数据")
            continue
        
        # 计算目标价格
        target_price = calculate_breakeven_price(cost, shares)
        
        # 计算收益
        investment = cost * shares
        current_value = current_price * shares
        paper_profit = current_value - investment
        paper_profit_pct = (paper_profit / investment) * 100
        
        # 交易建议
        suggestion = get_trading_suggestion(current_price, target_price, cost)
        
        # 添加到表格
        table_data.append([
            name,
            f"${cost:.2f}",
            f"${current_price:.2f}",
            f"${target_price:.2f}",
            f"{change:+.2f} ({change_pct:+.2f}%)" if change is not None else "N/A",
            f"${paper_profit:,.2f}",
            f"{paper_profit_pct:+.2f}%",
            suggestion
        ])
        
        total_investment += investment
        total_current_value += current_value
        total_paper_profit += paper_profit
        
        # 详细盈亏分析
        holding_days = calculate_holding_days(buy_date)
        buy_fee = calculate_transaction_fee(investment)
        sell_amount = current_value
        sell_fee = calculate_transaction_fee(sell_amount)
        cpf_cost = calculate_cpf_opportunity_cost(investment, holding_days)
        
        net_profit = paper_profit - sell_fee - cpf_cost
        
        detailed_analysis.append({
            "name": name,
            "investment": investment,
            "buy_fee": buy_fee,
            "current_value": current_value,
            "paper_profit": paper_profit,
            "sell_fee": sell_fee,
            "holding_days": holding_days,
            "cpf_cost": cpf_cost,
            "net_profit": net_profit
        })
    
    # 打印表格
    headers = ["产品", "成本价", "当前价", "目标价", "今日涨跌", "账面收益", "收益率", "交易建议"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    print()
    
    # 打印总览
    total_paper_profit_pct = (total_paper_profit / total_investment) * 100
    print(f"💰 投资总额: ${total_investment:,.2f}")
    print(f"📈 当前市值: ${total_current_value:,.2f}")
    print(f"📊 账面收益: ${total_paper_profit:,.2f} ({total_paper_profit_pct:+.2f}%)")
    print()
    
    # 详细盈亏分析
    print("=" * 80)
    print("📋 详细盈亏分析（如果今天卖出）")
    print("=" * 80)
    print()
    
    for analysis in detailed_analysis:
        print(f"【{analysis['name']}】")
        print(f"  投资金额:        ${analysis['investment']:,.2f}")
        print(f"  买入费用:        ${analysis['buy_fee']:.2f}")
        print(f"  当前市值:        ${analysis['current_value']:,.2f}")
        print(f"  账面收益:        ${analysis['paper_profit']:,.2f}")
        print(f"  卖出费用:        ${analysis['sell_fee']:.2f}")
        print(f"  持有天数:        {analysis['holding_days']} 天")
        print(f"  CPF机会成本:     ${analysis['cpf_cost']:.2f} (3.5% p.a.)")
        print(f"  真实盈亏:        ${analysis['net_profit']:,.2f}")
        
        if analysis['net_profit'] >= 0:
            print(f"  ✅ 真实收益率:    {(analysis['net_profit'] / analysis['investment']) * 100:+.2f}%")
        else:
            print(f"  ❌ 真实亏损率:    {(analysis['net_profit'] / analysis['investment']) * 100:+.2f}%")
        print()
    
    # 总体真实盈亏
    total_sell_fee = sum(a['sell_fee'] for a in detailed_analysis)
    total_cpf_cost = sum(a['cpf_cost'] for a in detailed_analysis)
    total_net_profit = sum(a['net_profit'] for a in detailed_analysis)
    total_net_profit_pct = (total_net_profit / total_investment) * 100
    
    print("=" * 80)
    print("💡 总体真实盈亏")
    print("=" * 80)
    print(f"账面收益:        ${total_paper_profit:,.2f}")
    print(f"卖出费用:        -${total_sell_fee:.2f}")
    print(f"CPF机会成本:     -${total_cpf_cost:.2f}")
    print(f"真实盈亏:        ${total_net_profit:,.2f} ({total_net_profit_pct:+.2f}%)")
    print()
    
    print("=" * 80)
    print("📝 说明")
    print("=" * 80)
    print("• 目标价格: 卖出后不亏钱的最低价格（含所有费用）")
    print("• 真实盈亏: 账面收益 - 卖出费用 - CPF机会成本")
    print("• CPF机会成本: 使用CPF OA投资的机会成本 (3.5% p.a.)")
    print("• 交易费用: DBS Vickers佣金0.18%或最低$27.25 + 其他费用")
    print("=" * 80)


if __name__ == "__main__":
    try:
        generate_report()
    except Exception as e:
        print(f"❌ 报告生成失败: {e}")
        import traceback
        traceback.print_exc()

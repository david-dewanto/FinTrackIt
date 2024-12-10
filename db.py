import yfinance as yf
from datetime import datetime
from typing import Dict

api_keys = {
    "e54d4431-5dab-474e-b71a-0db1fcb9e659": "7oDYjo3d9r58EJKYi5x4E8"
}

users = {
    "7oDYjo3d9r58EJKYi5x4E8": {
        "name": "Bob"
    }
}

investment_data = {
    "7oDYjo3d9r58EJKYi5x4E8": [
        {
            "ticker":"BBCA",
            "purchase_date":"10/11/2024"
        },
        {
            "ticker":"TLKM",
            "purchase_date":"10/11/2024"
        }
    ]
}

def check_api_key(api_key: str):
    return api_key in api_keys

def get_user_from_api_key(api_key: str):
    return "OK"

def get_historical_prices(api_key: str) -> Dict[str, Dict[str, float]]:
    print("masuk 3")
    user_investments = investment_data[api_keys[api_key]]
    results = {}
    
    for investment in user_investments:
        ticker = investment['ticker']
        purchase_date = datetime.strptime(investment['purchase_date'], '%d/%m/%Y')
        
        try:
            stock = yf.Ticker(ticker + ".JK")  
            
            hist = stock.history(start=purchase_date)
            
            if not hist.empty:
                price_dict = {
                    date.strftime('%Y-%m-%d'): price 
                    for date, price in hist['Close'].items()
                }
                results[ticker] = price_dict
            else:
                results[ticker] = {}
                
        except Exception as e:
            results[ticker] = {'error': str(e)}
    
    return results
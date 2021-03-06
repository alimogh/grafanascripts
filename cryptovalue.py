#!/usr/bin/python3
import eventlet
requests = eventlet.import_patched('requests.__init__')
import json, datetime, time, traceback
from influxdb import InfluxDBClient
import config as cfg

client = InfluxDBClient(host='localhost', port=8086)
times = {}
global_data = {}

def get_info_dummy(id):
	return {'price': 0.0, 'market_cap': 0.0}

def get_info_cmc(id):
	response = requests.get("https://api.coinmarketcap.com/v1/ticker/" + id + "/?convert=" + cfg.fiat_currency, timeout=3)
	data = json.loads(response.text)[0]
	market_cap = data['market_cap_' + cfg.fiat_currency.lower()]
	return {'price': float(data['price_' + cfg.fiat_currency.lower()]), 'market_cap': float(market_cap if market_cap is not None else 0)}

def get_info_coinlib(id):
	response = requests.get("https://coinlib.io/api/v1/coin?key=" + cfg.coinlib_api_key + "&pref=" + cfg.fiat_currency + "&symbol=" + id, timeout=3)
	data = json.loads(response.text)
	if 'coinlib' not in global_data:
		global_data['coinlib'] = {}
	global_data['coinlib'][id] = data
	market_cap = data['market_cap']
	return {'price': float(data['price']), 'market_cap': float(market_cap if market_cap is not None else 0)}

def get_info_southxchange(id):
	response = requests.get("http://www.southxchange.com/api/prices", timeout=3)
	data = json.loads(response.text)
	for market in data:
		if market['Market'] == id + '/BTC':
			return {'price': float(market['Last']) * float(global_data['coinlib']['btc']['price']), 'market_cap': 0.0}
	return {'price': 0.0, 'market_cap': 0.0}

def get_info_tradeogre(id):
	response = requests.get("https://tradeogre.com/api/v1/ticker/BTC-" + id, timeout=3)
	data = json.loads(response.text)
	return {'price': float(data['price']) * float(global_data['coinlib']['btc']['price']), 'market_cap': 0.0}

def get_info_stocksexchange(id):
	for market in global_data['stocksexchange']:
		if market['market_name'] == id + '_BTC':
			return {'price': float(market['last']) * float(global_data['coinlib']['btc']['price']), 'market_cap': 0.0}
	return {'price': 0.0, 'market_cap': 0.0}

def get_info_crex24(id):
	response = requests.get("https://api.crex24.com/CryptoExchangeService/BotPublic/ReturnTicker?request=[NamePairs=BTC_" + id + "]", timeout=3)
	data = json.loads(response.text)['Tickers'][0]
	return {'price': float(data['Last']) * float(global_data['coinlib']['btc']['price']), 'market_cap': 0.0}

def get_info_kucoin(id):
	response = requests.get("https://api.kucoin.com/v1/open/tick?symbol=" + id + "-BTC", timeout=3)
	data = json.loads(response.text)['data']
	return {'price': float(data['lastDealPrice']) * float(global_data['coinlib']['btc']['price']), 'market_cap': 0.0}

def update_stocksexchange():
	try:
		if 'stocksexchange' in times and time.perf_counter() - times['stocksexchange'] < 120:
			return
		times['stocksexchange'] = time.perf_counter()
		response = None
		with eventlet.Timeout(10):
			response = requests.get("https://stocks.exchange/api2/ticker", timeout=3)
		global_data['stocksexchange'] = json.loads(response.text)
	except KeyboardInterrupt:
		raise
	except:
		print('Error updating stocksexchange')
		traceback.print_exc()

def update_value(name, price_id, info_function, interval):
	try:
		if name in times and time.perf_counter() - times[name] < interval:
			return
		times[name] = time.perf_counter()

		print('Querying', name, 'balance...')
		client.switch_database('cryptobalances')
		result = list(client.query('select * from ' + name + ' order by desc limit 1').get_points())
		balance = float(0)
		if len(result) > 0:
			balance = float(result[0]['balance'])
		client.switch_database('cryptovalues')

		print('Getting', name, 'price...')
		info = None
		with eventlet.Timeout(10):
			info = info_function(price_id)
		value = balance * info['price']

		print('Writing', name, 'to db')
		client.write_points([{'measurement': name, 'fields': {'price': info['price'], 'balance': balance, 'value': value, 'market_cap': info['market_cap']}}])
		print(name, info['price'], balance, value, info['market_cap'])
	except KeyboardInterrupt:
		raise
	except:
		print('Error updating', name)
		traceback.print_exc()

while True:
	update_stocksexchange()
	update_value('btc', 'btc', get_info_coinlib, 120)
	update_value('xmr', 'xmr', get_info_coinlib, 300)
	update_value('etn', 'etn', get_info_coinlib, 900)
	update_value('eth', 'eth', get_info_coinlib, 600)
	update_value('etc', 'etc', get_info_coinlib, 600)
	update_value('bch', 'bch', get_info_coinlib, 900)
	update_value('aeon', 'aeon', get_info_coinlib, 1200)
	update_value('zcl', 'zcl', get_info_coinlib, 1200)
	update_value('itns', 'intensecoin', get_info_cmc, 900)
	update_value('msr', 'msr', get_info_coinlib, 300)
	update_value('ltc', 'ltc', get_info_coinlib, 600)
	update_value('trtl', 'TRTL', get_info_tradeogre, 30)
	update_value('jnt', 'jnt', get_info_coinlib, 1800)
	update_value('krb', 'krb', get_info_coinlib, 1800)
	update_value('dero', 'DERO', get_info_stocksexchange, 60)
	update_value('bbs', 'BBS', get_info_crex24, 60)
	update_value('xao', 'XAO', get_info_tradeogre, 30)
	update_value('grft', 'GRFT', get_info_tradeogre, 30)
	update_value('btcp', 'btcp', get_info_cmc, 900)
	update_value('storm', 'storm', get_info_coinlib, 1800)
	update_value('utnp', 'utnp', get_info_coinlib, 1800)

	time.sleep(1)

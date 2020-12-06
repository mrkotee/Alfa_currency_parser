from sqlalchemy import driver, session
from alfa_parser import Currency_parser
from alc_base import Currency_types, Currency_rates, Buyed_Currency
from currency_bot import bot


driver = driver(PATH_TO_BASE)
Session = session(driver)
session = Session()


parser = Currency_parser()

currencies = parser.parse_currency()

messages = {}
for currency in currencies:
	session.add(Currency_rates(Currency_types.id,
		currency.to_buy,
		currency.to_cell) ## how to know type of currency??
	for user_id in users:
		user_buyed = cur_session.query(Buyed_Currency).filter(Buyed_Currency.user_id == user_id).filter(Buyed_Currency.currency_type == currency.type).all()
		for buyed in user_buyed:
			if buyed.waiting_for >= currency_rate:
				pass
				# add this to msg
		
	
	# bot.send_message(user_id, currency_text)
		
		
